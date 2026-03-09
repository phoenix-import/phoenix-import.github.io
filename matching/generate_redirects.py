#!/usr/bin/env python3
"""
generate_redirects.py
---------------------
Produces redirect CSVs (one per language) mapping old phoeniximport.com product
URLs to new Shopify /products/{handle} URLs.

Matching strategy
-----------------
The Shopify handles in the localized_handles_*.csv files are a cleaned/shortened
version of the old site URL slugs.  For every product URL block in the sitemap
we try, language by language, to find a handle whose text is a prefix of the
old slug (the old slug usually has extra dimension/weight info appended).

Priority order for matching:  EN → NL → DE → FR → ES → IT

Once the Shopify product Identification is found we look up the localized handle
for every language from the corresponding CSV.

Output files (written next to this script):
  redirects_de.csv, redirects_en.csv, redirects_es.csv,
  redirects_fr.csv, redirects_it.csv, redirects_nl.csv

Each CSV has two columns:
  old_url  – full old URL, e.g. https://www.phoeniximport.com/nl/4/8105/...aspx
  new_url  – Shopify path,  e.g. /products/meditatie-kussen-chakra-5

An extra file, unmatched_products.csv, lists SKUs that could not be matched.

Requirements:  Python 3.9+, no external libraries needed.
"""

import csv
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
LANGUAGES  = ["de", "en", "es", "fr", "it", "nl"]

# Priority order for slug-based matching (languages whose handles diverge least from the old slugs first)
MATCH_PRIORITY = ["en", "nl", "de", "fr", "es", "it"]

# ---------------------------------------------------------------------------
# 1.  Load localized handles  (EAN/Identification → localized handle per lang)
# ---------------------------------------------------------------------------
#
# CSV columns: Type, Identification, Field, Locale, Market, Status,
#              Default content (NL handle), Translated content (this lang's handle)
#
# The Identification is a Shopify product ID that is consistent across all
# language files — we use it as the cross-language join key.

def load_all_handles() -> tuple[
    dict[str, dict[str, str]],   # identification → {lang: handle}
    dict[str, list[tuple[str, str]]]  # lang → [(handle, identification)] sorted longest-first
]:
    """Return two lookup structures built from all localized_handles_*.csv files."""
    id_to_handles: dict[str, dict[str, str]] = {}   # id → {lang: handle}
    lang_index:    dict[str, list[tuple[str, str]]] = {}  # lang → sorted handle list

    for lang in LANGUAGES:
        lang_upper = lang.upper()
        csv_path   = SCRIPT_DIR / f"localized_handles_{lang_upper}.csv"

        # NL is the Shopify source locale: use "Default content" as the authoritative NL handle.
        # For other languages use "Translated content"; if empty, fall back to "Default content"
        # (meaning Shopify will serve the NL handle for that language — uncommon but possible).
        handles_for_lang: list[tuple[str, str]] = []

        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                identification  = row["Identification"].strip()
                default_content = row["Default content"].strip()
                translated      = row["Translated content"].strip()

                if lang == "nl":
                    handle = default_content or translated
                else:
                    handle = translated or default_content

                if not (identification and handle):
                    continue
                id_to_handles.setdefault(identification, {})[lang] = handle
                handles_for_lang.append((handle, identification))

        # Sort longest-first so prefix matching always finds the most specific match
        handles_for_lang.sort(key=lambda x: -len(x[0]))
        lang_index[lang] = handles_for_lang
        print(f"  [{lang_upper}] {len(handles_for_lang):,} handles loaded")

    return id_to_handles, lang_index


# ---------------------------------------------------------------------------
# 2.  Parse sitemap  →  {sku: {lang: full_url}}
# ---------------------------------------------------------------------------

PRODUCT_RE   = re.compile(r"https://[^/]+/([a-z]{2})/4/(\d+)/([^/\s\"<>]+)\.aspx")
URL_BLOCK_RE = re.compile(r"<url>(.*?)</url>", re.DOTALL)
HREF_RE      = re.compile(r'href="(https://[^"]+)"')
LOC_RE       = re.compile(r"<loc>(https://[^<]+)</loc>")


def parse_sitemap(sitemap_path: Path) -> dict[str, dict[str, str]]:
    """
    Returns {sku: {lang: full_url}} for every product URL block.
    Uses regex to avoid XML namespace-prefix issues.
    """
    raw   = sitemap_path.read_text(encoding="utf-8")
    skus: dict[str, dict[str, str]] = {}

    for block_m in URL_BLOCK_RE.finditer(raw):
        block    = block_m.group(1)
        all_urls = LOC_RE.findall(block) + HREF_RE.findall(block)

        for url in all_urls:
            m = PRODUCT_RE.search(url)
            if not m:
                continue
            lang, sku, _slug = m.group(1), m.group(2), m.group(3)
            skus.setdefault(sku, {})[lang] = url

    print(f"  {len(skus):,} product SKUs parsed from {sitemap_path.name}")
    return skus


# ---------------------------------------------------------------------------
# 3.  Match sitemap product to Shopify product via slug prefix
# ---------------------------------------------------------------------------

def find_identification(
    sku_langs: dict[str, str],          # {lang: full_url}
    lang_index: dict[str, list[tuple[str, str]]],
) -> str | None:
    """
    Tries each language in MATCH_PRIORITY order.  For each language, extracts the
    slug from the old URL and checks whether any Shopify handle is a prefix of it.
    Returns the Identification of the first match, or None.
    """
    for lang in MATCH_PRIORITY:
        old_url = sku_langs.get(lang)
        if not old_url:
            continue
        m = PRODUCT_RE.search(old_url)
        if not m:
            continue
        slug = m.group(3)  # e.g. "soap-holder-handmade-red-white-blue-13x9x35cm-195g"

        for handle, identification in lang_index.get(lang, []):
            if handle and slug.startswith(handle):
                return identification

    return None


# ---------------------------------------------------------------------------
# 4.  Generate redirect CSVs
# ---------------------------------------------------------------------------

def generate_redirects() -> None:
    print("\n=== Loading localized handles ===")
    id_to_handles, lang_index = load_all_handles()

    print("\n=== Parsing sitemap ===")
    sku_map = parse_sitemap(SCRIPT_DIR / "SitemapEN.aspx")

    print("\n=== Matching & writing redirects ===")

    # Open one output file per language
    out_writers: dict[str, tuple] = {}
    for lang in LANGUAGES:
        out_path = SCRIPT_DIR / f"redirects_{lang}.csv"
        fh = open(out_path, "w", newline="", encoding="utf-8")
        w  = csv.writer(fh)
        w.writerow(["old_url", "new_url"])
        out_writers[lang] = (fh, w)

    unmatched_path = SCRIPT_DIR / "unmatched_products.csv"
    with open(unmatched_path, "w", newline="", encoding="utf-8") as uf:
        uw = csv.writer(uf)
        uw.writerow(["sku", "en_slug", "nl_slug"])

        stats = {
            "matched": 0,
            "no_id":   0,  # slug prefix matching failed
            "no_handle": 0,  # ID found but no Shopify handle for a language
        }

        for sku, lang_urls in sku_map.items():
            identification = find_identification(lang_urls, lang_index)

            if identification is None:
                stats["no_id"] += 1
                en_slug = PRODUCT_RE.search(lang_urls.get("en", ""))
                nl_slug = PRODUCT_RE.search(lang_urls.get("nl", ""))
                uw.writerow([
                    sku,
                    en_slug.group(3) if en_slug else "",
                    nl_slug.group(3) if nl_slug else "",
                ])
                continue

            handles = id_to_handles.get(identification, {})

            for lang in LANGUAGES:
                old_url = lang_urls.get(lang)
                handle  = handles.get(lang)
                if old_url and handle:
                    new_url = f"/products/{handle}"
                    out_writers[lang][1].writerow([old_url, new_url])
                elif old_url and not handle:
                    stats["no_handle"] += 1

            stats["matched"] += 1

    for lang in LANGUAGES:
        out_writers[lang][0].close()

    print(f"\n  Matched:          {stats['matched']:,} / {len(sku_map):,} products")
    print(f"  No slug match:    {stats['no_id']:,}  (see unmatched_products.csv)")
    print(f"  Missing handle:   {stats['no_handle']:,}  (product exists but lang handle absent)")

    print("\n=== Output files ===")
    for lang in LANGUAGES:
        p    = SCRIPT_DIR / f"redirects_{lang}.csv"
        rows = sum(1 for _ in open(p)) - 1  # subtract header
        print(f"  redirects_{lang}.csv  — {rows:,} redirects")
    p = unmatched_path
    rows = sum(1 for _ in open(p)) - 1
    print(f"  unmatched_products.csv  — {rows:,} products")


if __name__ == "__main__":
    generate_redirects()
