#!/usr/bin/env python3
"""
generate_404_redirects.py
--------------------------
Reads matching/404s/redirects_cleaned (1).xlsx (type_3_category sheet only,
i.e. /3/ category src_urls) and the six Shopify collection sitemaps in
matching/404s/, then writes one redirect CSV per language to matching/404s/.

Output format (identical to what Shopify's importer expects):
    Redirect from,Redirect to
    /nl/3/some-old-category/slug.aspx,/collections/shopify-handle

Matching strategy per row (first hit wins):
  1. SRC_OVERRIDES  – explicit src_slug → handle (brand pages, encoding issues)
  2. Exact tgt_slug – old-site already resolved to a slug that's live in Shopify
  3. Exact src_slug – old slug matches Shopify handle exactly
  4. TGT_OVERRIDES  – tgt_slug maps to a known replacement handle
  5. Fuzzy tgt_slug – difflib ratio ≥ FUZZY_THRESHOLD (catches accent/umlaut diffs)
  6. Fuzzy src_slug – same
  Unresolved rows → 404s/unresolved_redirects.csv
"""

import csv
import difflib
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import openpyxl  # pip install openpyxl

SCRIPT_DIR = Path(__file__).parent
DATA_DIR   = SCRIPT_DIR / "404s"
LANGUAGES  = ["de", "en", "es", "fr", "it", "nl"]
FUZZY_THRESHOLD = 0.80

# ---------------------------------------------------------------------------
# Manual overrides keyed on (lang, tgt_slug)
# Used when the old-site tgt_slug doesn't exist in Shopify but we know where
# it should go (removed brand lines, renamed categories, etc.)
# ---------------------------------------------------------------------------
TGT_OVERRIDES: dict[tuple[str, str], str] = {
    # Yoga clothing collections were removed; map to parent yoga collection
    ("nl", "alle-yogakleding"):             "yoga",
    ("de", "alle-yogakleidung"):            "yoga-produkte",
    ("en", "all-yoga-clothing"):            "yoga-gear",
    ("es", "todas-la-ropas-de-yoga"):       "articulos-de-yoga",
    ("fr", "tous-les-vtements-de-yoga"):    "accessoires-de-yoga",
    ("it", "tutto-per-labbigliamento-yoga"):"prodotti-yoga",
    # Women's yoga clothing (also removed)
    ("nl", "yoga-kleding-dames"):           "yoga",
    ("de", "yogakleidung-damen"):           "yoga-produkte",
    ("en", "yoga-wear-women"):              "yoga-gear",
    ("es", "ropa-de-yoga-para-mujeres"):    "articulos-de-yoga",
    ("fr", "yoga-vtements-femmes"):         "accessoires-de-yoga",
    ("it", "abbigliamento-yoga-donna"):     "prodotti-yoga",
    # Plain "yoga" as tgt (yoga bags etc.) → parent yoga per language
    ("de", "yoga"):                         "yoga-produkte",
    ("en", "yoga"):                         "yoga-gear",
    ("es", "yoga"):                         "articulos-de-yoga",
    ("fr", "yoga"):                         "accessoires-de-yoga",
    ("it", "yoga"):                         "prodotti-yoga",
    # Thangkas / tapestries / banners (category removed; map to textiles)
    ("de", "tapisserien-und-stranddecke"):  "textilien",
    ("en", "banners-wall-hangings-beachtowels"): "textiles",
    ("es", "banderas-tapices-y-toallas-de-playa"): "tejidos",
    ("fr", "bannires-tentures-murales-et-coussins"): "tissus",
    ("it", "stendardi-arazzi-teli"):        "tessuti",
    # Planet Pure brand removed; map to body-care parent
    ("nl", "planet-pure-reinigingsproducten"):   "lichaamsverzorging",
    ("de", "planet-pure-reinigungsprodukte"):    "korperpflege",
    ("en", "planet-pure-cleaning-products"):     "body-care-products",
    ("es", "planet-pure-productos-de-limpieza"): "cuidado-del-cuerpo",
    ("fr", "planet-pure-produits-de-nettoyage"): "soin-du-corps",
    ("it", "planet-pure-prodotti-per-la-pulizia"): "cura-del-corpo",
    # IT "healthy lifestyle" catch-all tgt
    ("it", "articoli-per-una-vita-sana"):   "gezonde-leefstijl",
}

# ---------------------------------------------------------------------------
# Source-slug overrides – specific old-URL slugs with no good automatic match
# ---------------------------------------------------------------------------
SRC_OVERRIDES: dict[tuple[str, str], str] = {
    # Yoga towels – more specific than the generic yoga parent
    ("de", "yoga-handtcher"):               "yogamatten-und-handtucher",
    ("en", "yoga-towels"):                  "yoga-mats-and-towels",
    ("it", "teli-yoga"):                    "tappetini-e-teli-yoga",
    ("es", "toalla-de-yoga-antideslizante"):"esterillas-y-toallas-de-yoga",
    ("fr", "yoga-toile-antidrapante"):      "tapis-et-serviettes-de-yoga",
    # Yoga bags → yoga parent
    ("de", "yogataschen"):                  "yoga-produkte",
    ("en", "yoga-bags"):                    "yoga-gear",
    ("es", "bolsas-de-yoga"):               "articulos-de-yoga",
    ("fr", "sacs-de-yoga"):                 "accessoires-de-yoga",
    ("it", "borse-per-tappetini-yoga"):     "prodotti-yoga",
    # Yoga incense (DE handle is oddly named in Italian)
    ("de", "yoga-rucherwerk"):              "incenso-yoga",
    # IT brand sub-pages with no dedicated collection
    ("it", "holy-lama-gocce-di-spezie"):    "gezonde-leefstijl",
    ("it", "cd-e-dvd-per-il-rilassamento"): "gezonde-leefstijl",
    ("it", "t-fiore-doriente"):             "te-e-articoli-correlati",
    ("it", "t-numi-thee-biologico"):        "te-organici",
    ("it", "calamite-e-bamboline"):         "magneten-sleutelhangers-en-gelukspoppetjes",
    # ES keyrings and slippers (no dedicated collection)
    ("es", "llaveros"):                     "imanes-llaveros-y-munecos-de-la-suerte",
    ("es", "zapatillas"):                   "tejidos",
    ("fr", "pantoufles"):                   "tissus",
    # ES mountain T-shirts (brand gone)
    ("es", "camisetas-the-mountain"):       "tejidos",
    ("es", "camisetas-mountain"):           "tejidos",
    ("fr", "mountain-t-shirts"):            "tissus",
    # DE body-care brand pages
    ("de", "anas-crystal-skincare"):        "korperpflege",
    ("de", "alepeo-aleppo"):                "korperpflege",
    ("de", "maison-du-laurier-aleppo"):     "korperpflege",
    ("de", "skins-restaurant"):             "korperpflege",
    ("de", "cannacura-hanfprodukte"):       "korperpflege",
    # DE containers / packaging
    ("de", "container-dosen-schachteln"):   "behalter-schachteln-taschen",
    # Thangkas (src-level, in case tgt_slug is also different)
    ("de", "thangkas"):                     "textilien",
    ("de", "fahnen-strandtcher-und-thangkas"): "textilien",
    ("en", "thangkas"):                     "textiles",
    ("en", "banners-beach-towels-and-thangkas"): "textiles",
    ("es", "thangkas"):                     "tejidos",
    ("es", "banderas-lonas-y-tankas"):      "tejidos",
    ("fr", "thangkas"):                     "tissus",
    ("fr", "drapeaux-serviettes-de-plage-et-thankas"): "tissus",
    ("it", "stendardi-teli-e-thangka"):     "tessuti",
    ("it", "thangke"):                      "tessuti",
    # ES salt-lamp variants (accent/encoding differences in src)
    ("es", "lamparas-de-sal-y-ms"):         "lamparas-de-sal-y-mas",
    ("es", "lamparas-de-sal-y-de-selenita"):"lamparas-de-sal-y-mas",
    # ES professional pendulums (NL-named handle in ES sitemap)
    ("es", "pndulos-y-varillas-de-zahor"): "pendels-voor-professionals",
    # ES organic cushions
    ("es", "cojines-de-meditacin-orgnicos"): "cojines-de-meditacion-organicos",
    # FR organic cushions
    ("fr", "coussins-de-mditation-biologiques"): "coussins-de-meditation-ronds-biologiques",
    # IT tea
    ("it", "t-english-tea-shop-biologico"): "te-e-articoli-correlati",
    ("fr", "english-tea-shop-th-biologique"): "the-et-accessoires",
    ("es", "english-tea-shop-t-orgnico"):   "te-y-articulos-relacionados",
    ("fr", "th-or-tea"):                    "the-et-accessoires",
    ("fr", "th-solaris-biologique"):        "the-et-accessoires",
    ("it", "t-solaris-organico"):           "te-organici",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_handles(lang: str) -> list[str]:
    tree = ET.parse(DATA_DIR / f"sitemap_collections_{lang.upper()}.xml")
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    handles = []
    for loc in tree.findall("s:url/s:loc", ns):
        m = re.search(r"/collections/(.+)$", loc.text)
        if m:
            handles.append(m.group(1))
    return handles


def fuzzy_best(slug: str, handle_list: list[str], threshold: float) -> str | None:
    best_ratio, best_handle = 0.0, None
    for h in handle_list:
        r = difflib.SequenceMatcher(None, slug, h, autojunk=False).ratio()
        if r > best_ratio:
            best_ratio, best_handle = r, h
    return best_handle if best_ratio >= threshold else None


CAT_RE  = re.compile(r"(?:https?://[^/]+)?(/[a-z]{2}/3/.+?)\.aspx", re.IGNORECASE)
LANG_RE = re.compile(r"/([a-z]{2})/3/", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Loading Shopify collection handles …")
    handles: dict[str, list[str]] = {}
    hsets:   dict[str, set[str]]  = {}
    for lang in LANGUAGES:
        handles[lang] = get_handles(lang)
        hsets[lang]   = set(handles[lang])
        print(f"  [{lang.upper()}] {len(handles[lang])} handles")

    print("\nReading xlsx …")
    wb = openpyxl.load_workbook(DATA_DIR / "redirects_cleaned (1).xlsx", read_only=True)
    ws = wb["type_3_category"]
    rows = list(ws.iter_rows(values_only=True))
    print(f"  {len(rows) - 1} data rows (type_3_category)")

    writers: dict[str, tuple] = {}
    for lang in LANGUAGES:
        p  = DATA_DIR / f"404_redirects_{lang}.csv"
        fh = open(p, "w", newline="", encoding="utf-8")
        w  = csv.writer(fh)
        w.writerow(["Redirect from", "Redirect to"])
        writers[lang] = (fh, w)

    unresolved_path = DATA_DIR / "unresolved_redirects.csv"
    counts = {k: 0 for k in ("src_override", "exact_tgt", "exact_src",
                              "tgt_override", "fuzzy_tgt", "fuzzy_src",
                              "unresolved", "skip")}
    unresolved_rows: list[tuple] = []

    for row in rows[1:]:
        if not row or not row[1]:
            continue
        src = str(row[1])
        tgt = str(row[2]) if row[2] else ""

        sm = CAT_RE.search(src)
        if not sm:
            counts["skip"] += 1
            continue

        lang      = LANG_RE.search(src).group(1).lower()
        from_path = sm.group(1) + ".aspx"  # e.g. /nl/3/foo/bar.aspx
        src_slug  = sm.group(1).split("/")[-1]
        tm        = CAT_RE.search(tgt)
        tgt_slug  = tm.group(1).split("/")[-1] if tm else None

        h     = handles.get(lang, [])
        hset  = hsets.get(lang, set())
        handle: str | None = None
        method: str        = ""

        # 1. Source slug explicit override
        if (lang, src_slug) in SRC_OVERRIDES:
            handle = SRC_OVERRIDES[(lang, src_slug)]
            method = "src_override"

        # 2. Exact tgt match
        elif tgt_slug and tgt_slug in hset:
            handle = tgt_slug
            method = "exact_tgt"

        # 3. Exact src match
        elif src_slug in hset:
            handle = src_slug
            method = "exact_src"

        # 4. Tgt slug override
        elif tgt_slug and (lang, tgt_slug) in TGT_OVERRIDES:
            handle = TGT_OVERRIDES[(lang, tgt_slug)]
            method = "tgt_override"

        # 5. Fuzzy on tgt
        elif tgt_slug:
            fh = fuzzy_best(tgt_slug, h, FUZZY_THRESHOLD)
            if fh:
                handle = fh
                method = "fuzzy_tgt"

        # 6. Fuzzy on src
        if handle is None:
            fh = fuzzy_best(src_slug, h, FUZZY_THRESHOLD)
            if fh:
                handle = fh
                method = "fuzzy_src"

        if handle:
            counts[method] += 1
            writers[lang][1].writerow([from_path, f"/collections/{handle}"])
        else:
            counts["unresolved"] += 1
            unresolved_rows.append((lang, from_path, src_slug, tgt_slug))

    for lang in LANGUAGES:
        writers[lang][0].close()

    with open(unresolved_path, "w", newline="", encoding="utf-8") as uf:
        uw = csv.writer(uf)
        uw.writerow(["lang", "redirect_from", "src_slug", "tgt_slug"])
        uw.writerows(unresolved_rows)

    print("\n=== Results ===")
    for k, v in counts.items():
        print(f"  {k:<14}: {v}")
    print()
    for lang in LANGUAGES:
        p    = DATA_DIR / f"404_redirects_{lang}.csv"
        n    = sum(1 for _ in open(p)) - 1
        print(f"  404_redirects_{lang}.csv  — {n} redirects")
    print(f"  unresolved_redirects.csv — {len(unresolved_rows)} rows")


if __name__ == "__main__":
    main()
