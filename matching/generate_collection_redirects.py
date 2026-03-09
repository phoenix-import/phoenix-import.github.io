#!/usr/bin/env python3
"""
generate_collection_redirects.py
---------------------------------
Produces redirect CSVs (one per language) mapping old phoeniximport.com
category/collection URLs (/3/) to new Shopify /collections/{handle} URLs.

Collection source (authoritative)
----------------------------------
  ../shopify-copy-parser-extended.html  –  COLLECTIONS constant, one list per
  language, ~252 active handles.  This list excludes deprecated collections
  (sale/clearance, discontinued brands, etc.) that are present in the xlsx
  export but were never created in Shopify.

Sitemap files (one per language, same folder as this script):
  Sitemap{LANG}.aspx

Matching strategy
-----------------
The last path segment of each old /3/ URL (the most specific slug) is matched
against the Shopify collection handles for that language.

1. Exact  –  slug == handle  (covers the majority)
2. Fuzzy  –  difflib.SequenceMatcher ratio ≥ 0.80 across the full handle list
             (no prefix pre-filter, so accent-dropping mismatches are caught:
              e.g. old "rucherwerk" vs Shopify "raucherwerk")

Unmatched slugs are written to unmatched_collections.csv for manual review.
Most genuinely unmatched slugs correspond to deprecated collections that have
no target in Shopify, so no redirect is needed.

Output files (same folder as this script):
  collection_redirects_{lang}.csv  —  old_url, new_url
  unmatched_collections.csv        —  lang, old_url, slug
"""

import csv
import difflib
import json
import re
from pathlib import Path

SCRIPT_DIR      = Path(__file__).parent
HTML_PATH       = SCRIPT_DIR.parent / "shopify-copy-parser-extended.html"
LANGUAGES       = ["de", "en", "es", "fr", "it", "nl"]
FUZZY_THRESHOLD = 0.80

CATEGORY_RE  = re.compile(r"https://[^/]+/([a-z]{2})/3/([^\"<\s]+)\.aspx")
URL_BLOCK_RE = re.compile(r"<url>(.*?)</url>", re.DOTALL)
HREF_RE      = re.compile(r'href="(https://[^"]+)"')
LOC_RE       = re.compile(r"<loc>(https://[^<]+)</loc>")
COLLECTIONS_RE = re.compile(r"const COLLECTIONS = (\{.*?\});", re.DOTALL)


# ---------------------------------------------------------------------------
# 1.  Load collection handles from the HTML parser (authoritative active list)
# ---------------------------------------------------------------------------

def load_collection_handles() -> dict[str, list[str]]:
    """
    Parses the COLLECTIONS constant from shopify-copy-parser-extended.html.
    Returns {lang_lower: [handle, ...]} with empty strings removed.
    """
    html = HTML_PATH.read_text(encoding="utf-8")
    m    = COLLECTIONS_RE.search(html)
    if not m:
        raise RuntimeError(f"Could not find COLLECTIONS constant in {HTML_PATH}")

    raw: dict[str, list[str]] = json.loads(m.group(1))

    lang_handles: dict[str, list[str]] = {}
    for lang in LANGUAGES:
        handles = [h for h in raw.get(lang.upper(), []) if h]
        lang_handles[lang] = handles
        print(f"  [{lang.upper()}] {len(handles):,} active collection handles loaded")

    return lang_handles


# ---------------------------------------------------------------------------
# 2.  Parse sitemaps for /3/ category URLs
# ---------------------------------------------------------------------------

def parse_all_category_urls() -> dict[str, str]:
    """
    Returns {"lang:last_slug": full_old_url} for every unique (lang, slug) pair
    found across all sitemap files.  All language variants are typically present
    in the first sitemap parsed (via hreflang alternates), but we scan all six
    to be safe.
    """
    entries: dict[str, str] = {}

    for lang in LANGUAGES:
        sitemap_path = SCRIPT_DIR / f"Sitemap{lang.upper()}.aspx"
        raw      = sitemap_path.read_text(encoding="utf-8")
        new_count = 0

        for block_m in URL_BLOCK_RE.finditer(raw):
            block    = block_m.group(1)
            all_urls = LOC_RE.findall(block) + HREF_RE.findall(block)

            for url in all_urls:
                m = CATEGORY_RE.search(url)
                if not m:
                    continue
                url_lang  = m.group(1)
                path      = m.group(2)          # e.g. "body-care/bath-shower-and-soaps"
                last_slug = path.split("/")[-1]
                key       = f"{url_lang}:{last_slug}"
                if key not in entries:
                    entries[key] = url
                    new_count += 1

        print(f"  [{lang.upper()}] +{new_count:,} new (lang, slug) pairs from sitemap")

    print(f"  Total unique (lang, slug) pairs: {len(entries):,}")
    return entries


# ---------------------------------------------------------------------------
# 3.  Slug → handle matching
# ---------------------------------------------------------------------------

def match_handle(slug: str, handles: list[str]) -> str | None:
    """
    Pass 1: exact match.
    Pass 2: reversed-word match — catches "bracelets-metal" → "metal-bracelets"
            and "wicca-tarot" → "tarot-wicca".
    Pass 3: slug-is-prefix-of-handle — catches "yogagurte" → "yogagurte-und-yogarad"
            (old sub-category slug merged into a broader Shopify handle).
            Returns the shortest matching handle to avoid false positives.
    Pass 4: fuzzy — full list, no prefix pre-filter.
             Needed because the old site dropped accented chars entirely
             (ä→nothing) while Shopify normalised them (ä→a), which can
             change the first characters: "rucherwerk" vs "raucherwerk".
    """
    handles_set = set(handles)

    # Pass 1: exact
    if slug in handles_set:
        return slug

    # Pass 2: reversed words
    rev = "-".join(slug.split("-")[::-1])
    if rev in handles_set:
        return rev

    # Pass 3: slug is a prefix of a handle (slug + "-" + more)
    prefix_matches = [h for h in handles if h.startswith(slug + "-")]
    if prefix_matches:
        return min(prefix_matches, key=len)   # shortest = most specific

    # Pass 4: fuzzy
    best_ratio  = 0.0
    best_handle = None
    for h in handles:
        ratio = difflib.SequenceMatcher(None, slug, h, autojunk=False).ratio()
        if ratio > best_ratio:
            best_ratio  = ratio
            best_handle = h

    return best_handle if best_ratio >= FUZZY_THRESHOLD else None


# ---------------------------------------------------------------------------
# 4.  Generate redirect CSVs
# ---------------------------------------------------------------------------

def generate_collection_redirects() -> None:
    print("\n=== Loading collection handles (from HTML parser) ===")
    lang_handles = load_collection_handles()

    print("\n=== Parsing sitemaps for /3/ category URLs ===")
    entries = parse_all_category_urls()

    print("\n=== Matching & writing redirects ===")

    out_writers: dict[str, tuple] = {}
    for lang in LANGUAGES:
        out_path = SCRIPT_DIR / f"collection_redirects_{lang}.csv"
        fh = open(out_path, "w", newline="", encoding="utf-8")
        w  = csv.writer(fh)
        w.writerow(["Redirect from", "Redirect to"])
        out_writers[lang] = (fh, w)

    unmatched_path = SCRIPT_DIR / "unmatched_collections.csv"
    matched   = 0
    unmatched = 0

    with open(unmatched_path, "w", newline="", encoding="utf-8") as uf:
        uw = csv.writer(uf)
        uw.writerow(["lang", "old_url", "slug"])

        for key, old_url in sorted(entries.items()):
            lang, last_slug = key.split(":", 1)
            handle = match_handle(last_slug, lang_handles.get(lang, []))

            if handle:
                from_path = old_url.split("phoeniximport.com", 1)[-1]
                new_url   = f"/collections/{handle}"
                out_writers[lang][1].writerow([from_path, new_url])
                matched += 1
            else:
                uw.writerow([lang, old_url, last_slug])
                unmatched += 1

    for lang in LANGUAGES:
        out_writers[lang][0].close()

    print(f"\n  Matched:   {matched:,}")
    print(f"  Unmatched: {unmatched:,}  (see unmatched_collections.csv)")

    print("\n=== Output files ===")
    for lang in LANGUAGES:
        p    = SCRIPT_DIR / f"collection_redirects_{lang}.csv"
        rows = sum(1 for _ in open(p)) - 1
        print(f"  collection_redirects_{lang}.csv  — {rows:,} redirects")
    rows = sum(1 for _ in open(unmatched_path)) - 1
    print(f"  unmatched_collections.csv        — {rows:,} unmatched slugs")


if __name__ == "__main__":
    generate_collection_redirects()
