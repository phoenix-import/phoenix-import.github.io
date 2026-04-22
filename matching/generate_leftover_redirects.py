#!/usr/bin/env python3
"""
generate_leftover_redirects.py

Parses an htaccess-style redirect file and resolves any intermediate
old phoeniximport.com URLs to final Shopify URLs using the existing
collection, product, pages, and utilize redirect lookup tables.

Usage:
  python3 generate_leftover_redirects.py [input_file]

  input_file  Path to the htaccess/CSV file (default: 'Leftover redirects.htaccess.csv')
              Output files are derived from the input filename.

Outputs (all new files, no existing files modified):
  <stem>_redirects.csv         — resolved Shopify-ready redirects
  <stem>_unresolved.csv        — entries whose destination couldn't be resolved
  <stem>_skipped_rewrites.csv  — RewriteRule regex entries (not importable to Shopify)
"""

import csv
import os
import re
import sys
from difflib import SequenceMatcher
from urllib.parse import unquote

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Input file: first CLI arg or default
_raw_input = sys.argv[1] if len(sys.argv) > 1 else "Leftover redirects.htaccess.csv"
INPUT_FILE = _raw_input if os.path.isabs(_raw_input) else os.path.join(SCRIPT_DIR, _raw_input)

# Derive output filenames from the input stem
_stem = re.sub(r"\.(?:csv|htaccess\.csv|htaccess)$", "", os.path.basename(INPUT_FILE), flags=re.IGNORECASE)
_stem = _stem.rstrip(".")  # clean up any trailing dot

LANGS = ["de", "en", "es", "fr", "it", "nl"]

LOOKUP_FILES = {
    "collection": "collection_redirects_{lang}.csv",
    "product":    "product_redirects_{lang}.csv",
    "pages":      "pages_redirects_{lang}.csv",
    "utilize":    "utilize_redirects_{lang}.csv",
}

_parsed_stem = re.sub(r"^LeftoverRedirects_", "LeftoverRedirectsParsed_", _stem)
OUTPUT_FILE     = os.path.join(SCRIPT_DIR, f"{_parsed_stem}.csv")
HTACCESS_FILE   = os.path.join(SCRIPT_DIR, f"{_parsed_stem}.htaccess")
UNRESOLVED_FILE = os.path.join(SCRIPT_DIR, f"{_stem}_unresolved.csv")
SKIPPED_FILE    = os.path.join(SCRIPT_DIR, f"{_stem}_skipped_rewrites.csv")

SHOPIFY_DOMAIN = "https://www.phoeniximport.com"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DOMAIN_PREFIXES = (
    "https://www.phoeniximport.com",
    "http://www.phoeniximport.com",
    "https://phoeniximport.com",
    "http://phoeniximport.com",
)


def strip_domain(url: str) -> str:
    """Strip phoeniximport.com domain from a URL; return relative path."""
    url = url.strip()
    for prefix in DOMAIN_PREFIXES:
        if url.lower().startswith(prefix.lower()):
            path = url[len(prefix):]
            return path if path else "/"
    return url  # already relative, or genuinely external


def lang_from_path(path: str) -> str | None:
    m = re.match(r"^/([a-zA-Z]{2})/", path)
    return m.group(1).lower() if m else None


def fuzzy_best_collection(slug: str, collection_handles: set[str], threshold: float) -> str | None:
    """Return the best-matching collection handle if similarity ≥ threshold, else None."""
    best_score, best_handle = 0.0, None
    for h in collection_handles:
        score = SequenceMatcher(None, slug, h).ratio()
        if score > best_score:
            best_score, best_handle = score, h
    return best_handle if best_score >= threshold else None


def clean_product_slug(slug: str) -> str:
    """Strip trailing size/dimension/colour suffixes so fuzzy match focuses on the product name."""
    # Remove trailing tokens that look like sizes (e.g. -l, -xl, -200-ml, -147x208-cm, -08-cm, -24-cm)
    slug = re.sub(r"(-(?:\d[\dx]*[a-z]*|[a-z]{1,2}))+$", "", slug)
    return slug


def keyword_best_collection(slug: str, collection_handles: set[str]) -> str | None:
    """
    Return a collection handle whose name starts with the same first word as slug,
    preferring the shortest (most specific) matching handle.
    Returns None if no match is found.
    """
    first_word = slug.split("-")[0]
    if not first_word:
        return None
    candidates = [h for h in collection_handles if h.startswith(first_word + "-") or h == first_word]
    if not candidates:
        return None
    # Prefer the shortest match (most specific / least generic)
    return min(candidates, key=len)


def is_shopify_path(path: str) -> bool:
    """True if path is already in a Shopify URL format."""
    if any(seg in path for seg in ("/collections/", "/products/", "/pages/", "/blogs/")):
        return True
    # Language-root URLs like /nl, /de, …
    if re.fullmatch(r"/?(?:[a-z]{2})?", path):
        return True
    return False


def is_old_phoenix_path(path: str) -> bool:
    """True if path is an old phoeniximport.com path that needs resolving."""
    return bool(re.search(r"/(?:nl|de|en|es|fr|it)/[1-4]/", path)
                or re.search(r"/(?:nl|de|en|es|fr|it)/webshop/", path))


# ---------------------------------------------------------------------------
# Lookup table loader
# ---------------------------------------------------------------------------

def load_lookup_tables() -> tuple[dict[str, str], set[str]]:
    """
    Load all existing redirect CSVs into:
      lookup         — old_path → shopify_relative_path
      collection_handles — set of known Shopify collection handle strings
    """
    lookup: dict[str, str] = {}
    collection_handles: set[str] = set()
    loaded = 0
    for kind, pattern in LOOKUP_FILES.items():
        for lang in LANGS:
            fname = os.path.join(SCRIPT_DIR, pattern.format(lang=lang))
            if not os.path.exists(fname):
                continue
            with open(fname, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)  # skip header
                for row in reader:
                    if len(row) < 2:
                        continue
                    src, dst = row[0].strip(), row[1].strip()
                    if src and dst:
                        if src not in lookup:
                            lookup[src] = dst
                            loaded += 1
                        # Also index a lowercase key so percent-encoded paths
                        # like /de/2/%C3%BCber-uns.aspx resolve when lowercased.
                        src_lower = src.lower()
                        if src_lower not in lookup:
                            lookup[src_lower] = dst
                        if dst.startswith("/collections/"):
                            collection_handles.add(dst[len("/collections/"):])
    print(f"  Loaded {loaded} mappings, {len(collection_handles)} collection handles")
    return lookup, collection_handles


# ---------------------------------------------------------------------------
# Destination resolver
# ---------------------------------------------------------------------------

def resolve_destination(
    raw_dest: str,
    lookup: dict[str, str],
    collection_handles: set[str],
) -> tuple[str, str]:
    """
    Resolve a raw destination URL/path to a final Shopify path.

    Returns (resolved_path, status) where status is one of:
      'ok'          — resolved to a Shopify URL
      'fallback'    — resolved via a best-effort fallback (parent category / slug)
      'unresolved'  — could not resolve
    """
    path = strip_domain(raw_dest).lower()  # normalise: all lookup keys are lowercase

    # Already a Shopify-format path
    if is_shopify_path(path):
        return path, "ok"

    # Destination is a root URL with language param (e.g. /?language=IT → /it)
    m_lang = re.match(r"^/\?language=([a-z]{2})$", path)
    if m_lang:
        return f"/{m_lang.group(1)}", "fallback"

    # Webshop product-list URLs → language homepage
    if "/webshop/" in path:
        lang = lang_from_path(path)
        return (f"/{lang}" if lang else "/"), "fallback"

    # Old /lang/1/ homepage variants
    if re.search(r"/[a-z]{2}/1/", path):
        if path in lookup:
            return lookup[path], "ok"
        lang = lang_from_path(path)
        return (f"/{lang}" if lang else "/"), "fallback"

    # Standard lookup (handles /lang/2/, /lang/3/, /lang/4/ paths)
    if path in lookup:
        resolved = strip_domain(lookup[path])
        return resolved, "ok"

    # Try URL-decoded variant
    decoded = unquote(path)
    if decoded != path and decoded in lookup:
        resolved = strip_domain(lookup[decoded])
        return resolved, "ok"

    # Lower-cased variant (the CSVs use lower-case paths)
    lower = path.lower()
    if lower in lookup:
        resolved = strip_domain(lookup[lower])
        return resolved, "ok"

    # --- Extra fallbacks for old /lang/3/ subcategory paths ---
    if re.search(r"/[a-z]{2}/3/", path):
        slug = re.sub(r"\.aspx$", "", path.split("/")[-1])

        # 1. Slug exactly matches a known Shopify collection handle
        if slug in collection_handles:
            return f"/collections/{slug}", "fallback"

        # 2. Parent category path: /lang/3/cat/subcat.aspx → /lang/3/cat.aspx
        parts = path.rstrip("/").split("/")  # ['', 'nl', '3', 'cat', 'subcat.aspx']
        if len(parts) >= 5:
            parent_path = "/" + "/".join(parts[1:4]) + ".aspx"  # /lang/3/cat.aspx
            if parent_path in lookup:
                return strip_domain(lookup[parent_path]), "fallback"
            # Parent slug might itself be a known collection handle
            parent_slug = parts[3]
            if parent_slug in collection_handles:
                return f"/collections/{parent_slug}", "fallback"

    # --- Fallback for unresolved /lang/2/ info pages → lang homepage ---
    if re.search(r"/[a-z]{2}/2/", path):
        lang = lang_from_path(path)
        return (f"/{lang}" if lang else "/"), "fallback"

    # --- Extra fallback for old /lang/4/SKU/ product paths ---
    # SKU may be numeric (12345) or alphanumeric (st09). If the exact slug
    # isn't found, try any product with the same SKU in the same language.
    m = re.match(r"^(/[a-z]{2})/4/([^/]+)/(.+?)\.aspx$", path)
    if m:
        lang_prefix, sku, prod_slug = m.group(1), m.group(2), m.group(3)
        sku_pattern = f"{lang_prefix}/4/{sku}/"
        for candidate_src, candidate_dst in lookup.items():
            if candidate_src.startswith(sku_pattern):
                return strip_domain(candidate_dst), "fallback"

        # Discontinued product — fuzzy match slug against collection handles,
        # then keyword (first-word) match, fall back to lang homepage if nothing sticks.
        clean = clean_product_slug(prod_slug)
        handle = fuzzy_best_collection(clean, collection_handles, threshold=0.60)
        lang = lang_prefix.lstrip("/")
        if handle:
            return f"/collections/{handle}", "fallback"
        handle = keyword_best_collection(clean, collection_handles)
        if handle:
            return f"/collections/{handle}", "fallback"
        return f"/{lang}", "fallback"

    # --- Fuzzy category match for unresolved /lang/3/ paths ---
    if re.search(r"/[a-z]{2}/3/", path):
        slug = re.sub(r"\.aspx$", "", path.split("/")[-1])
        handle = fuzzy_best_collection(slug, collection_handles, threshold=0.70)
        if handle:
            return f"/collections/{handle}", "fallback"
        # Fall back to lang homepage
        lang = lang_from_path(path)
        return (f"/{lang}" if lang else "/"), "fallback"

    return path, "unresolved"


# ---------------------------------------------------------------------------
# htaccess parser
# ---------------------------------------------------------------------------

def parse_htaccess(filepath: str):
    """
    Yield (source, raw_dest, line_type) tuples.
    line_type is 'redirect' or 'rewrite'.
    """
    with open(filepath, encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = raw_line.strip()

            if not line or line.startswith("#") or line.startswith("###"):
                continue

            # RewriteRule <pattern> <dest> [flags]
            m = re.match(r"^RewriteRule\s+(\S+)\s+(\S+)(?:\s+\[.*\])?$", line)
            if m:
                yield m.group(1), m.group(2), "rewrite"
                continue

            # Redirect 301 <source> <dest>  (space or tab separated)
            m = re.match(r"^Redirect\s+301\s+(\S+)\s+(\S+)$", line)
            if m:
                yield m.group(1), m.group(2), "redirect"
                continue


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Loading lookup tables…")
    lookup, collection_handles = load_lookup_tables()

    resolved_rows: list[tuple[str, str]] = []
    unresolved_rows: list[tuple[str, str, str]] = []
    rewrite_rows: list[tuple[str, str]] = []

    seen_sources: set[str] = set()

    print(f"Parsing {os.path.basename(INPUT_FILE)} …")
    entries = list(parse_htaccess(INPUT_FILE))
    redirects_found = sum(1 for _, _, t in entries if t == "redirect")
    rewrites_found  = sum(1 for _, _, t in entries if t == "rewrite")
    print(f"  {redirects_found} Redirect 301 entries, {rewrites_found} RewriteRule entries")

    for src, raw_dest, line_type in entries:

        # RewriteRules can't be imported to Shopify (regex-based) — collect separately
        if line_type == "rewrite":
            rewrite_rows.append((src, raw_dest))
            continue

        # Normalise source to a relative path
        src_path = strip_domain(src) if src.startswith("http") else src

        # Deduplicate by source path (keep first occurrence)
        if src_path in seen_sources:
            continue

        # Self-referential check (source and destination resolve to the same path).
        # Normalise percent-encoding case so %C3%BC and %c3%bc compare equal.
        dest_path_raw = strip_domain(raw_dest)
        def _norm_pct(p: str) -> str:
            return re.sub(r"%[0-9a-fA-F]{2}", lambda m: m.group().upper(), p)
        if _norm_pct(src_path) == _norm_pct(dest_path_raw):
            # The htaccess was just doing www/HTTPS normalisation — source == dest.
            # The source URL itself may still need a Shopify redirect, so try
            # resolving it directly through the lookup tables before giving up.
            resolved, status = resolve_destination(src_path, lookup, collection_handles)
            if status != "unresolved" and resolved != src_path:
                seen_sources.add(src_path)
                resolved_rows.append((src_path, resolved))
            else:
                unresolved_rows.append((src_path, raw_dest, "self-referential"))
                seen_sources.add(src_path)
            continue

        # If the source URL is already a key in the existing redirect tables,
        # it will be handled by those CSVs — no need to duplicate it here.
        if src_path in lookup:
            unresolved_rows.append((src_path, raw_dest, "source-already-in-existing-csv"))
            seen_sources.add(src_path)
            continue

        resolved, status = resolve_destination(raw_dest, lookup, collection_handles)

        # Guard against a redirect looping back to its own source
        if resolved == src_path:
            unresolved_rows.append((src_path, raw_dest, "resolves-to-self"))
            seen_sources.add(src_path)
            continue

        seen_sources.add(src_path)

        if status == "unresolved":
            unresolved_rows.append((src_path, raw_dest, "no-lookup-match"))
        else:
            resolved_rows.append((src_path, resolved))

    # -----------------------------------------------------------------------
    # Write outputs
    # -----------------------------------------------------------------------
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Redirect from", "Redirect to"])
        writer.writerows(resolved_rows)

    with open(UNRESOLVED_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Source", "Original destination", "Reason"])
        writer.writerows(unresolved_rows)

    with open(SKIPPED_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Pattern", "Destination"])
        writer.writerows(rewrite_rows)

    with open(HTACCESS_FILE, "w", encoding="utf-8") as f:
        for src, dst in resolved_rows:
            f.write(f"Redirect 301 {src} {SHOPIFY_DOMAIN}{dst}\n")

    print(f"\nDone!")
    print(f"  Resolved:              {len(resolved_rows):>4}  → {os.path.basename(OUTPUT_FILE)}")
    print(f"  Unresolved / skipped:  {len(unresolved_rows):>4}  → {os.path.basename(UNRESOLVED_FILE)}")
    print(f"  RewriteRules (regex):  {len(rewrite_rows):>4}  → {os.path.basename(SKIPPED_FILE)}")
    print(f"  htaccess output:       {len(resolved_rows):>4}  → {os.path.basename(HTACCESS_FILE)}")


if __name__ == "__main__":
    main()
