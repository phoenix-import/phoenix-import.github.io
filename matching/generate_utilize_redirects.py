#!/usr/bin/env python3
"""
generate_utilize_redirects.py
------------------------------
Processes the `type_3_category` sheet of utilize_redirects_cleaned.xlsx.

Each row has:
  src_url – the original URL a visitor hit on the old phoeniximport.com site
  tgt_url – where the old site redirected them (another /3/ category URL)

We chain:
  src_url  →  tgt_url  →  (lookup)  →  Shopify /collections/{handle} URL

Matching strategy for tgt_url → Shopify URL:
  1. Exact lookup in existing collection_redirects_{lang}.csv
  2. Slug fuzzy match (4-pass: exact, reversed-word, prefix, fuzzy ≥0.80)
     against all Shopify collection handles for that language
  3. Parent category fallback: match the parent path segment against the
     16 main category handles (parsed from MAIN_NL in shopify-copy-parser-extended.html)

Deduplication: skip any src_url already present in collection_redirects_{lang}.csv.

Output files (same folder as this script):
  utilize_redirects_{lang}.csv   – Shopify-importable (Redirect from, Redirect to)
  unmatched_utilize.csv          – rows where no Shopify target could be found
  skipped_duplicates.csv         – src_urls already covered by existing collection redirects

Requirements: Python 3.9+, openpyxl (pip install openpyxl)
"""

import csv
import difflib
import json
import re
from pathlib import Path

import openpyxl

SCRIPT_DIR      = Path(__file__).parent
HTML_PATH       = SCRIPT_DIR.parent / "shopify-copy-parser-extended.html"
XLSX_PATH       = SCRIPT_DIR / "utilize_redirects_cleaned.xlsx"
LANGUAGES       = ["de", "en", "es", "fr", "it", "nl"]
FUZZY_THRESHOLD     = 0.80   # used for tgt-chain slug matching
SRC_FUZZY_THRESHOLD = 0.90   # stricter threshold for src slug matching to avoid
                              # false positives between similarly-named brands
                              # (e.g. yoga-wear-surya ≠ yoga-wear-satya)
# Minimum similarity between src slug and the chosen Shopify handle to be
# considered "high confidence".  Rows below this threshold are written to
# review_utilize.csv for manual checking.
REVIEW_SIM_THRESHOLD = 0.52

COLLECTIONS_RE = re.compile(r"const COLLECTIONS = (\{.*?\});", re.DOTALL)
MAIN_NL_RE     = re.compile(r"const MAIN_NL = (\[.*?\]);")
DOMAIN_RE      = re.compile(r"^https?://[^/]+")
LANG_RE        = re.compile(r"^/([a-z]{2})/")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    """Strip domain, lowercase, ensure .aspx suffix, strip trailing slash."""
    url = str(url).strip()
    url = DOMAIN_RE.sub("", url)
    url = url.rstrip("/")
    if url and not url.lower().endswith(".aspx"):
        url += ".aspx"
    return url.lower()


def extract_lang(rel_url: str) -> str | None:
    m = LANG_RE.match(rel_url)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# 1.  Load Shopify collection handles + main category handles
# ---------------------------------------------------------------------------

def load_handles() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """
    Returns:
      lang_handles  – {lang: [all collection handles]}
      main_handles  – {lang: [main category handles only, same 16 as MAIN_NL]}
    """
    html = HTML_PATH.read_text(encoding="utf-8")

    m = COLLECTIONS_RE.search(html)
    if not m:
        raise RuntimeError(f"Could not find COLLECTIONS constant in {HTML_PATH}")
    raw: dict[str, list[str]] = json.loads(m.group(1))

    m2 = MAIN_NL_RE.search(html)
    if not m2:
        raise RuntimeError(f"Could not find MAIN_NL constant in {HTML_PATH}")
    main_nl: list[str] = json.loads(m2.group(1))

    # Replicate the JS logic: find indices of MAIN_NL handles in COLLECTIONS.NL,
    # then look up the same indices in every other language list.
    nl_list     = raw.get("NL", [])
    main_indices = sorted(i for i, h in enumerate(nl_list) if h in set(main_nl))

    lang_handles: dict[str, list[str]] = {}
    main_handles: dict[str, list[str]] = {}

    for lang in LANGUAGES:
        key     = lang.upper()
        handles = [h for h in raw.get(key, []) if h]
        lang_handles[lang] = handles

        lang_list = raw.get(key, [])
        main_handles[lang] = [
            lang_list[i] for i in main_indices
            if i < len(lang_list) and lang_list[i]
        ]
        print(f"  [{key}] {len(handles):,} collection handles, "
              f"{len(main_handles[lang])} main categories")

    return lang_handles, main_handles


# ---------------------------------------------------------------------------
# 2.  Load existing collection_redirects CSVs as lookup dicts
# ---------------------------------------------------------------------------

def load_collection_lookups() -> dict[str, dict[str, str]]:
    """Returns {lang: {relative_path_lower: shopify_url}}."""
    lookups: dict[str, dict[str, str]] = {}
    for lang in LANGUAGES:
        path = SCRIPT_DIR / f"collection_redirects_{lang}.csv"
        d: dict[str, str] = {}
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                d[row["Redirect from"].strip().lower()] = row["Redirect to"].strip()
        lookups[lang] = d
        print(f"  [{lang.upper()}] {len(d):,} existing collection redirects loaded")
    return lookups


# ---------------------------------------------------------------------------
# 3.  Slug → handle matching  (from generate_collection_redirects.py)
# ---------------------------------------------------------------------------

def match_handle(slug: str, handles: list[str],
                 threshold: float = FUZZY_THRESHOLD) -> str | None:
    """
    Pass 1: exact match.
    Pass 2: reversed-word match (bracelets-metal → metal-bracelets).
    Pass 3: slug is prefix of handle — returns shortest match.
    Pass 4: fuzzy (SequenceMatcher ratio ≥ threshold).
    """
    handles_set = set(handles)

    if slug in handles_set:
        return slug

    rev = "-".join(slug.split("-")[::-1])
    if rev in handles_set:
        return rev

    prefix_matches = [h for h in handles if h.startswith(slug + "-")]
    if prefix_matches:
        return min(prefix_matches, key=len)

    best_ratio  = 0.0
    best_handle = None
    for h in handles:
        ratio = difflib.SequenceMatcher(None, slug, h, autojunk=False).ratio()
        if ratio > best_ratio:
            best_ratio  = ratio
            best_handle = h

    return best_handle if best_ratio >= threshold else None


def match_handle_direct(slug: str, handles: list[str]) -> str | None:
    """
    Non-fuzzy matching only (Passes 1–3): exact, reversed-word, prefix.
    Used for src_slug matching so we only take unambiguous direct hits.
    """
    handles_set = set(handles)

    if slug in handles_set:
        return slug

    rev = "-".join(slug.split("-")[::-1])
    if rev in handles_set:
        return rev

    prefix_matches = [h for h in handles if h.startswith(slug + "-")]
    if prefix_matches:
        return min(prefix_matches, key=len)

    return None


# ---------------------------------------------------------------------------
# 4.  Main processing
# ---------------------------------------------------------------------------

def generate_utilize_redirects() -> None:
    print("\n=== Loading Shopify handles ===")
    lang_handles, main_handles = load_handles()

    print("\n=== Loading existing collection redirect lookups ===")
    collection_lookup = load_collection_lookups()

    print("\n=== Processing type_3_category sheet ===")
    wb     = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
    ws     = wb["type_3_category"]
    rows   = list(ws.iter_rows(values_only=True))
    wb.close()

    header    = [str(c).strip() if c is not None else "" for c in rows[0]]
    src_idx   = header.index("src_url")
    tgt_idx   = header.index("tgt_url")

    # Open per-language output files
    out_writers: dict[str, tuple] = {}
    for lang in LANGUAGES:
        out_path = SCRIPT_DIR / f"utilize_redirects_{lang}.csv"
        fh = open(out_path, "w", newline="", encoding="utf-8")
        w  = csv.writer(fh)
        w.writerow(["Redirect from", "Redirect to"])
        out_writers[lang] = (fh, w)

    unmatched_path  = SCRIPT_DIR / "unmatched_utilize.csv"
    duplicates_path = SCRIPT_DIR / "skipped_duplicates.csv"
    review_path     = SCRIPT_DIR / "review_utilize.csv"

    stats = {"src_direct": 0, "src_fuzzy": 0, "exact": 0, "fuzzy": 0, "parent": 0,
             "unmatched": 0, "duplicate": 0, "skip": 0}

    with open(unmatched_path, "w", newline="", encoding="utf-8") as uf, \
         open(duplicates_path, "w", newline="", encoding="utf-8") as df, \
         open(review_path, "w", newline="", encoding="utf-8") as rf:

        uw = csv.writer(uf)
        uw.writerow(["sheet", "lang", "src_url", "tgt_url", "reason"])
        dw = csv.writer(df)
        dw.writerow(["lang", "src_url", "existing_target"])
        rw = csv.writer(rf)
        rw.writerow(["lang", "src_url", "tgt_url", "shopify_url", "match_pass",
                     "src_handle_similarity", "note"])

        for row in rows[1:]:
            src_raw = str(row[src_idx]).strip() if row[src_idx] is not None else ""
            tgt_raw = str(row[tgt_idx]).strip() if row[tgt_idx] is not None else ""

            if not src_raw or not tgt_raw:
                stats["skip"] += 1
                continue

            src_rel = normalize_url(src_raw)
            tgt_rel = normalize_url(tgt_raw)

            lang = extract_lang(src_rel) or extract_lang(tgt_rel)
            if not lang or lang not in LANGUAGES:
                uw.writerow(["type_3_category", lang or "?", src_raw, tgt_raw, "unknown lang"])
                stats["unmatched"] += 1
                continue

            # Dedup: skip if src_url is already covered by existing collection redirects
            existing = collection_lookup[lang].get(src_rel)
            if existing:
                dw.writerow([lang, src_rel, existing])
                stats["duplicate"] += 1
                continue

            src_slug = re.sub(r"\.aspx$", "", src_rel.split("/")[-1])
            shopify_url: str | None = None
            match_pass = "unmatched"

            # Step 1: try src_slug via non-fuzzy passes (exact / reversed / prefix).
            # These are unambiguous: the old src URL slug is a valid Shopify handle.
            handle = match_handle_direct(src_slug, lang_handles.get(lang, []))
            if handle:
                shopify_url = f"/collections/{handle}"
                match_pass  = "src_direct"

            # Step 1b: try src_slug via fuzzy pass (stricter SRC_FUZZY_THRESHOLD).
            # Catches brand-prefixed handles like maison-du-laurier-aleppo →
            # en-maison-du-laurier-aleppo (ratio 0.94) that pass 1-3 miss.
            # Stricter than tgt matching to avoid false positives between
            # similarly-named brands (e.g. yoga-wear-surya ≠ yoga-wear-satya).
            if shopify_url is None:
                handle = match_handle(src_slug, lang_handles.get(lang, []),
                                      threshold=SRC_FUZZY_THRESHOLD)
                if handle:
                    shopify_url = f"/collections/{handle}"
                    match_pass  = "src_fuzzy"

            # Step 2: exact lookup of tgt_rel in existing collection_redirects
            if shopify_url is None:
                shopify_url = collection_lookup[lang].get(tgt_rel)
                if shopify_url:
                    match_pass = "exact"

            # Step 3: slug fuzzy match on tgt_slug against all handles
            if shopify_url is None:
                tgt_slug = re.sub(r"\.aspx$", "", tgt_rel.split("/")[-1])
                handle   = match_handle(tgt_slug, lang_handles.get(lang, []))
                if handle:
                    shopify_url = f"/collections/{handle}"
                    match_pass  = "fuzzy"

            # Step 4: parent segment → main category fallback
            if shopify_url is None:
                # Path: /lang/3/parent/child.aspx → parts[3] is the parent
                path_parts  = tgt_rel.split("/")
                if len(path_parts) >= 4:
                    parent_slug = path_parts[3]
                    handle      = match_handle(parent_slug, main_handles.get(lang, []))
                    # Short slugs like "yoga" score poorly in fuzzy matching against
                    # translated handles like "articulos-de-yoga". Fall back to a
                    # word-boundary substring check (parent_slug appears as a whole
                    # dash-delimited word inside a main handle).
                    if not handle:
                        handle = next(
                            (h for h in main_handles.get(lang, [])
                             if parent_slug in h.split("-")),
                            None,
                        )
                    if handle:
                        shopify_url = f"/collections/{handle}"
                        match_pass  = "parent"

            if shopify_url:
                out_writers[lang][1].writerow([src_rel, shopify_url])
                stats[match_pass] += 1

                # Flag for review if the final handle is semantically distant from src slug
                if match_pass not in ("src_direct", "src_fuzzy"):
                    final_handle = shopify_url.replace("/collections/", "")
                    sim = difflib.SequenceMatcher(
                        None, src_slug, final_handle, autojunk=False
                    ).ratio()
                    if sim < REVIEW_SIM_THRESHOLD:
                        rw.writerow([lang, src_rel, tgt_rel, shopify_url, match_pass,
                                     f"{sim:.2f}", "src slug and chosen handle are dissimilar"])
            else:
                uw.writerow(["type_3_category", lang, src_raw, tgt_raw, "no match"])
                stats["unmatched"] += 1

    for lang in LANGUAGES:
        out_writers[lang][0].close()

    print(f"\n  Src direct match:  {stats['src_direct']:,}")
    print(f"  Src fuzzy match:   {stats['src_fuzzy']:,}")
    print(f"  Tgt exact match:   {stats['exact']:,}")
    print(f"  Tgt fuzzy match:   {stats['fuzzy']:,}")
    print(f"  Parent fallback:   {stats['parent']:,}")
    print(f"  Unmatched:         {stats['unmatched']:,}")
    print(f"  Skipped (dedup):   {stats['duplicate']:,}")
    print(f"  Skipped (empty):   {stats['skip']:,}")

    print("\n=== Output files ===")
    for lang in LANGUAGES:
        p = SCRIPT_DIR / f"utilize_redirects_{lang}.csv"
        count = sum(1 for _ in open(p)) - 1
        print(f"  utilize_redirects_{lang}.csv  — {count:,} redirects")
    um_count = sum(1 for _ in open(unmatched_path)) - 1
    dp_count = sum(1 for _ in open(duplicates_path)) - 1
    rv_count = sum(1 for _ in open(review_path)) - 1
    print(f"  unmatched_utilize.csv        — {um_count:,} rows")
    print(f"  skipped_duplicates.csv       — {dp_count:,} rows")
    print(f"  review_utilize.csv           — {rv_count:,} rows (check these manually)")


if __name__ == "__main__":
    generate_utilize_redirects()
