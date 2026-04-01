"""
Match old phoeniximport.com /1/ and /2/ pages to new Shopify /pages/ URLs
and generate redirect CSVs per language.
"""

import re
import os
import csv

BASE = os.path.dirname(__file__)
SITEMAP = os.path.join(BASE, "SitemapEN.aspx")
LANGUAGES = ["en", "de", "fr", "es", "it", "nl"]

# NL is the Shopify default language — no lang prefix in URLs
NL_DEFAULT = True

# Manually resolved matches where slug differs between old and new
# Key: old slug, Value: new Shopify page slug
KNOWN_MAPPINGS = {
    # EN
    "frequently-asked-questions-faq":  "faq",
    "login":                           "account-login",
    "general-terms-and-conditions":    "terms-and-conditions",
    "discount":                        "discounts",
    "stock-notification-and-web-api":  "stock-notification",
    "report-on-delivery-form":         "report-on-delivery",
    "about-us":                        "over-ons",            # Shopify EN uses Dutch slug
    "en-spirituele-kaarsen":           "spirituele-kaarsen-groothandel",
    "en-bedrijfsvideo":                "videos",
    "new-age-wholesale":               "new-age-groothandel",
    "yogi-yogini-groothandel":         "new-age-groothandel",
    # FR
    "termes-et-conditions-gnrales":              "termes-et-conditions",
    "confidentialit-et-cookie":                  "confidentialite-et-cookie",
    "rapport-sur-la-livraison":                  "rapport-de-livraison",
    "confirmation--la-livraison":                "rapport-de-livraison",
    "conditions-dexpedition-et-de-livraison":    "conditions-despedition-et-de-livraison",
    "remises":                                   "remises",
    "donate":                                    "donations",
    "se-connecter":                              "account-login",
    "foire-aux-questions-faq":                   "faq",
    "newsletter":                                "bulletin",   # FR only — see per-lang override below
    "service-client%c3%a8le":                    "service-clientele",
    "qui-sommes-nous":                           "quis-sommes-nous",
    "informations-sur-la-socit":                 "informations-sur-la-societe",
    "notification-de-stock-et-web-api":          "avis-de-stocks",
    "gadget-davis-de-rapprovisionnement":        "avis-de-stocks",
    "grossiste-new-age":                         "new-age-groothandel",
    "fr-spirituele-kaarsen":                     "spirituele-kaarsen-groothandel",
    "fr-bedrijfsvideo":                          "videos",
    # ES
    "trminos-generales-y-condiciones":           "terminos-generales",
    "politica-de-privacidad-y-cookies":          "privacidad-y-cookies",
    "realizar-un-pedido":                        "realizar-un-pedido",
    "formas-de-pago":                            "formas-de-pago",
    "condiciones-de-entrega":                    "condiciones-de-entrega",
    "descuentos":                                "descuentos",
    "informe-sobre-la-entrega":                  "informe-sobre-la-entrega",
    "inicia-sesin":                              "account-login",
    "preguntas-frecuentes-faq":                  "faq",
    "informacin-de-la-compaa":                   "informacion-de-la-compania",
    "notificacin-de-stock-y-web-api":            "notificacion-de-stock",
    "new-age-al-por-mayor":                      "new-age-groothandel",
    "es-spirituele-kaarsen":                     "spirituele-kaarsen-groothandel",
    "es-bedrijfsvideo":                          "videos",
    # IT
    "termini-e-condizioni-generali":             "termine-e-condizioni",
    "privacy-e-cookie":                          "privacy-e-cookie",
    "effetuare-un-ordine":                       "effetuare-un-ordine",
    "pagamenti":                                 "pagamenti",
    "spedizione-e-consegna":                     "spedizione-e-consegna",
    "sconti":                                    "sconti",
    "modulo-reclami":                            "modulo-reclami",
    "domande-frequenti-faq":                     "faq",
    "informazioni-aziendaz":                     "informazioni-azienda",  # typo in old URL
    "servizio-clienti":                          "assistenza-clienti",
    "notifica-stock-e-web-api":                  "notifica-delle-scorte",
    "reclami":                                   "modulo-reclami",
    "new-age-allingrosso":                       "new-age-groothandel",
    "it-spirituele-kaarsen":                     "spirituele-kaarsen-groothandel",
    "it-bedrijfsvideo":                          "videos",
    # NL
    "algemene-leveringsvoorwaarden":             "algemene-leveringsvoorwaarden",
    "privacy--en-cookieverklaring":              "privacy-en-cookieverklaring",
    "bestellen":                                 "bestellen",
    "betalen":                                   "betalen",
    "verzenden-en-levertijd":                    "verzenden-en-levertijd",
    "reclamatieformulier":                       "reclamatie",
    "veelgestelde-vragen-faq":                   "faq",
    "inloggen":                                  "account-login",
    "voorraadnotificatie-en-web-api":            "voorraadnotificatie",
    "duurzaam-ondernemen":                       "duurzaam-verpakken",
    "bedrijfsvideo":                             "videos",
    "spirituele-kaarsen":                        "spirituele-kaarsen-groothandel",
}

# Pages that redirect to the homepage (path only, no /pages/)
HOMEPAGE_SLUGS = {"home", "inicio", "accueil"}

# Shopify homepage paths per language
HOMEPAGE_TARGET = {
    "en": "/en",
    "de": "/de",
    "fr": "/fr",
    "es": "/es",
    "it": "/it",
    "nl": "/",
}


def slug_from_url(url):
    m = re.search(r"/([^/]+?)(?:\.aspx)?$", url)
    return m.group(1) if m else ""


def parse_old_pages(sitemap_path):
    """Return list of {lang, type, url, slug} for /1/ and /2/ entries."""
    with open(sitemap_path, encoding="utf-8") as fh:
        content = fh.read()

    blocks = re.findall(r"<url>(.*?)</url>", content, re.DOTALL)
    pages = []

    for block in blocks:
        loc_match = re.search(r"<loc>(.*?)</loc>", block)
        loc = loc_match.group(1).strip() if loc_match else ""

        alternates = {}
        for m in re.finditer(r'hreflang="([^"]+)"\s+href="([^"]+)"', block):
            lang = m.group(1).strip().lower()
            url = m.group(2).strip()
            if lang in LANGUAGES:
                alternates[lang] = url

        all_urls = list(alternates.values()) + ([loc] if loc else [])
        seg = None
        for u in all_urls:
            m = re.search(r"/(\d+)/", u)
            if m:
                seg = m.group(1)
                break

        if seg not in ("1", "2"):
            continue

        # Add one entry per language
        for lang, url in alternates.items():
            pages.append({
                "lang":  lang,
                "type":  seg,
                "url":   url,
                "slug":  slug_from_url(url),
                "loc":   loc,
            })

        # Also add the canonical loc if it's the bare root domain
        if loc == "https://www.phoeniximport.com":
            pages.append({
                "lang":  "root",
                "type":  "1",
                "url":   loc,
                "slug":  "home",
                "loc":   loc,
            })

    # Deduplicate per lang+url
    seen = set()
    deduped = []
    for p in pages:
        key = (p["lang"], p["url"])
        if key not in seen:
            seen.add(key)
            deduped.append(p)

    return deduped


def parse_shopify_pages(lang):
    """Return set of slugs available on Shopify for this language."""
    fname = os.path.join(BASE, f"Shopify_pages_{lang.upper()}.xml")
    if not os.path.exists(fname):
        return None, f"File not found: {fname}"

    with open(fname, encoding="utf-8") as fh:
        content = fh.read()

    urls = re.findall(r"<loc>([^<]+)</loc>", content)
    slugs = {}
    for url in urls:
        # Only keep actual /pages/ URLs
        m = re.search(r"/pages/([^?<\s]+)", url)
        if m:
            slug = m.group(1).rstrip("/")
            slugs[slug] = url
    return slugs, None


def old_path(url):
    """Return just the path from a full URL."""
    m = re.match(r"https?://[^/]+(/.+)", url)
    return m.group(1) if m else url


def new_path(lang, shopify_slug):
    if lang == "nl":
        return f"/pages/{shopify_slug}"
    return f"/{lang}/pages/{shopify_slug}"


def match_lang(lang, old_pages, shopify_slugs):
    matched = []
    unmatched = []

    lang_pages = [p for p in old_pages if p["lang"] == lang]

    # Also handle root domain redirect
    if lang == "en":
        lang_pages_extra = [p for p in old_pages if p["lang"] == "root"]
        lang_pages = lang_pages + lang_pages_extra

    for p in lang_pages:
        slug = p["slug"]
        src = old_path(p["url"]) if p["lang"] != "root" else "/"

        # Homepage redirects
        if slug in HOMEPAGE_SLUGS or p["lang"] == "root":
            target = HOMEPAGE_TARGET.get(lang if p["lang"] != "root" else "en", "/")
            matched.append((src, target, "homepage"))
            continue

        # Exact match
        if slug in shopify_slugs:
            matched.append((src, new_path(lang, slug), "exact"))
            continue

        # Known mapping
        if slug in KNOWN_MAPPINGS:
            mapped = KNOWN_MAPPINGS[slug]
            if mapped in shopify_slugs:
                matched.append((src, new_path(lang, mapped), "mapped"))
                continue
            else:
                # Mapping defined but target not in Shopify pages
                unmatched.append((src, slug, f"mapped→{mapped} (not in Shopify)"))
                continue

        unmatched.append((src, slug, "no match"))

    return matched, unmatched


def write_csv(path, rows, header):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def main():
    old_pages = parse_old_pages(SITEMAP)

    all_unmatched = []

    for lang in LANGUAGES:
        shopify_slugs, err = parse_shopify_pages(lang)
        if err:
            print(f"[{lang.upper()}] WARNING: {err}")
            continue
        if not shopify_slugs:
            print(f"[{lang.upper()}] WARNING: No /pages/ URLs found — check the XML file.")
            continue

        matched, unmatched = match_lang(lang, old_pages, shopify_slugs)

        out_path = os.path.join(BASE, f"pages_redirects_{lang}.csv")
        write_csv(out_path, [(r[0], r[1]) for r in matched], ["Redirect from", "Redirect to"])
        print(f"[{lang.upper()}] {len(matched):2d} matched  |  {len(unmatched):2d} unmatched  → {os.path.basename(out_path)}")

        for src, slug, reason in unmatched:
            all_unmatched.append((lang.upper(), src, slug, reason))

    # Write combined unmatched report
    unmatched_path = os.path.join(BASE, "pages_unmatched.csv")
    write_csv(unmatched_path, all_unmatched, ["Language", "Old URL", "Old Slug", "Reason"])
    print(f"\nUnmatched written to: {os.path.basename(unmatched_path)}")


if __name__ == "__main__":
    main()
