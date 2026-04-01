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

# Per-language mappings: (lang, old_slug) -> new Shopify page slug
# Avoids cross-language conflicts where the same slug means different things
KNOWN_MAPPINGS = {
    # EN
    ("en", "frequently-asked-questions-faq"):  "faq",
    ("en", "login"):                           "account-login",
    ("en", "general-terms-and-conditions"):    "terms-and-conditions",
    ("en", "discount"):                        "discounts",
    ("en", "stock-notification-and-web-api"):  "stock-notification",
    ("en", "report-on-delivery-form"):         "report-on-delivery",
    ("en", "about-us"):                        "over-ons",
    ("en", "en-spirituele-kaarsen"):           "spirituele-kaarsen-groothandel",
    ("en", "en-bedrijfsvideo"):                "videos",
    ("en", "new-age-wholesale"):               "new-age-groothandel",
    ("en", "yogi-yogini-groothandel"):         "new-age-groothandel",
    # DE
    ("de", "allgemeine-geschftsbedingungen"):  "allgemeine-geschaftsbedingungen",
    ("de", "datenschutz--und-cookieerklrung"): "datenschutzerklarung",
    ("de", "reklamationsformular"):            "reklamation",
    ("de", "versenden-und-lieferzeit"):        "versand-und-lieferung",
    ("de", "newsletter"):                      "rundschreiben",
    ("de", "hufig-gestellte-fragen-faq"):      "faq",
    ("de", "einloggen"):                       "account-login",
    ("de", "vorratsmeldung"):                  "lagerbestands-benachrichtigung",
    ("de", "vorratinformation-und-web-api"):   "lagerbestands-benachrichtigung",
    ("de", "nachhaltige-unternehmertum"):      "nachhaltiges-unternehmertum",
    ("de", "%c3%bcber-uns"):                   "uber-uns",
    ("de", "new-age-grohandel"):               "new-age-groothandel",
    ("de", "yogi-yogini-groothandel"):         "new-age-groothandel",
    ("de", "de-spirituele-kaarsen"):           "spirituele-kaarsen-groothandel",
    ("de", "kerzengrohandel"):                 "spirituele-kaarsen-groothandel",
    ("de", "lieferant-fr-kerzen"):             "spirituele-kaarsen-groothandel",
    ("de", "de-witte-kaarsen-groothandel"):    "spirituele-kaarsen-groothandel",
    ("de", "de-bedrijfsvideo"):                "videos",
    # Proclaimer equivalents
    ("fr", "annonce"):  "proclaimer",
    ("it", "avviso"):   "proclaimer",
    ("es", "aviso"):    "proclaimer",
    # FR candles landing pages
    ("fr", "vente-en-gros-de-bougies"):              "spirituele-kaarsen-groothandel",
    ("fr", "fournisseur-grossiste-de-bougies-en-vrac"): "spirituele-kaarsen-groothandel",
    ("fr", "fr-witte-kaarsen-groothandel"):          "spirituele-kaarsen-groothandel",
    # FR
    ("fr", "termes-et-conditions-gnrales"):             "termes-et-conditions",
    ("fr", "confidentialit-et-cookie"):                 "confidentialite-et-cookie",
    ("fr", "rapport-sur-la-livraison"):                 "rapport-de-livraison",
    ("fr", "confirmation--la-livraison"):               "rapport-de-livraison",
    ("fr", "conditions-dexpedition-et-de-livraison"):   "conditions-despedition-et-de-livraison",
    ("fr", "se-connecter"):                             "account-login",
    ("fr", "foire-aux-questions-faq"):                  "faq",
    ("fr", "newsletter"):                               "bulletin",
    ("fr", "service-client%c3%a8le"):                   "service-clientele",
    ("fr", "service-clientle"):                         "service-clientele",
    ("fr", "qui-sommes-nous"):                          "quis-sommes-nous",
    ("fr", "informations-sur-la-socit"):                "informations-sur-la-societe",
    ("fr", "notification-de-stock-et-web-api"):         "avis-de-stocks",
    ("fr", "gadget-davis-de-rapprovisionnement"):       "avis-de-stocks",
    ("fr", "grossiste-new-age"):                        "new-age-groothandel",
    ("fr", "yogi-yogini-groothandel"):                  "new-age-groothandel",
    ("fr", "fr-spirituele-kaarsen"):                    "spirituele-kaarsen-groothandel",
    ("fr", "fr-bedrijfsvideo"):                         "videos",
    # ES
    ("es", "trminos-generales-y-condiciones"):          "terminos-generales",
    ("es", "politica-de-privacidad-y-cookies"):         "privacidad-y-cookies",
    ("es", "inicia-sesin"):                             "account-login",
    ("es", "preguntas-frecuentes-faq"):                 "faq",
    ("es", "informacin-de-la-compaa"):                  "informacion-de-la-compania",
    ("es", "notificacin-de-stock-y-web-api"):           "notificacion-de-stock",
    ("es", "new-age-al-por-mayor"):                     "new-age-groothandel",
    ("es", "yogi-yogini-groothandel"):                  "new-age-groothandel",
    ("es", "es-spirituele-kaarsen"):                    "spirituele-kaarsen-groothandel",
    ("es", "es-bedrijfsvideo"):                         "videos",
    ("es", "venta-al-por-mayor-de-velas"):              "spirituele-kaarsen-groothandel",
    ("es", "proveedor-de-velas-al-por-mayor"):          "spirituele-kaarsen-groothandel",
    ("es", "es-witte-kaarsen-groothandel"):             "spirituele-kaarsen-groothandel",
    ("es", "advertencia-para-reposicin"):               "notificacion-de-stock",
    ("es", "boletn-informativo"):                       "boletin",
    ("es", "boletn"):                                   "boletin",
    ("es", "atencin-al-cliente"):                       "atencion-al-cliente",
    # IT
    ("it", "termini-e-condizioni-generali"):            "termine-e-condizioni",
    ("it", "domande-frequenti-faq"):                    "faq",
    ("it", "informazioni-aziendaz"):                    "informazioni-azienda",
    ("it", "servizio-clienti"):                         "assistenza-clienti",
    ("it", "notifica-stock-e-web-api"):                 "notifica-delle-scorte",
    ("it", "reclami"):                                  "modulo-reclami",
    ("it", "newsletter"):                               "bollettino",
    ("it", "new-age-allingrosso"):                       "new-age-groothandel",
    ("it", "yogi-yogini-groothandel"):                  "new-age-groothandel",
    ("it", "it-spirituele-kaarsen"):                    "spirituele-kaarsen-groothandel",
    ("it", "it-bedrijfsvideo"):                         "videos",
    ("it", "commercio-allingrosso-di-candele"):         "spirituele-kaarsen-groothandel",
    ("it", "fornitore-di-candele-allingrosso"):         "spirituele-kaarsen-groothandel",
    ("it", "it-witte-kaarsen-groothandel"):             "spirituele-kaarsen-groothandel",
    ("it", "login"):                                    "account-login",
    ("it", "avviso-riassortimento"):                    "notifica-delle-scorte",
    # NL
    ("nl", "privacy--en-cookieverklaring"):             "privacy-en-cookieverklaring",
    ("nl", "reclamatieformulier"):                      "reclamatie",
    ("nl", "veelgestelde-vragen-faq"):                  "faq",
    ("nl", "inloggen"):                                 "account-login",
    ("nl", "voorraadnotificatie-en-web-api"):           "voorraadnotificatie",
    ("nl", "duurzaam-ondernemen"):                      "duurzaam-verpakken",
    ("nl", "bedrijfsvideo"):                            "videos",
    ("nl", "spirituele-kaarsen"):                       "spirituele-kaarsen-groothandel",
    ("nl", "yogi-yogini-groothandel"):                  "new-age-groothandel",
    ("nl", "kaarsen-groothandel"):                      "spirituele-kaarsen-groothandel",
    ("nl", "kaarsen-leverancier-in-bulk"):              "spirituele-kaarsen-groothandel",
    ("nl", "witte-kaarsen-groothandel"):                "spirituele-kaarsen-groothandel",
    # EN candles landing pages
    ("en", "candles-wholesaler"):                       "spirituele-kaarsen-groothandel",
    ("en", "bulk-wholesale-candles-supplier"):          "spirituele-kaarsen-groothandel",
    ("en", "en-witte-kaarsen-groothandel"):             "spirituele-kaarsen-groothandel",
}

# Fixed-path redirects: (lang, old_slug) -> full path
# Used for targets that are not /pages/ URLs (collections, homepage, etc.)
FIXED_TARGETS = {
    # Bestsellers → bestsellers collection
    ("en", "bestsellers"):           "/en/collections/bestsellers",
    ("de", "bestseller"):            "/de/collections/bestseller",
    ("fr", "les-plus-vendus"):       "/fr/collections/meilleures-ventes",
    ("es", "los-ms-vendidos"):       "/es/collections/mas-vendidos",
    ("it", "i-pi-venduti"):          "/it/collections/piu-venduti",
    ("nl", "bestsellers"):           "/collections/bestsellers",
    # Special offers → dedicated special offers collection
    ("en", "special-offers"):        "/en/collections/special-offers",
    ("de", "sonderangebote"):        "/de/collections/sonderangebote",
    ("fr", "offres-spciales"):       "/fr/collections/offres-speciales",
    ("es", "ofertas-especiales"):    "/es/collections/ofertas-especiales",
    ("it", "offerte-speciali"):      "/it/collections/offerte-speciali",
    ("nl", "speciale-aanbiedingen"): "/collections/speciale-aanbiedingen",
    # Monthly offers → dedicated monthly collection
    ("en", "offers-of-the-month"):   "/en/collections/monthly-deals",
    ("de", "angebote-des-monats"):   "/de/collections/monatsangebote",
    ("fr", "offres-mensuelles"):     "/fr/collections/offres-du-mois",
    ("es", "ofertas-del-mes"):       "/es/collections/ofertas-del-mes",
    ("it", "offerte-del-mese"):      "/it/collections/offerte-del-mese",
    ("nl", "maand-aanbieding"):      "/collections/maandaanbieding",
    # Certificaten → customer service page
    ("en", "en-certificaten"):   "/en/pages/customer-service",
    ("de", "de-certificaten"):   "/de/pages/kundenservice",
    ("fr", "fr-certificaten"):   "/fr/pages/service-clientele",
    ("es", "es-certificaten"):   "/es/pages/atencion-al-cliente",
    ("it", "it-certificaten"):   "/it/pages/assistenza-clienti",
    ("nl", "certificaten"):      "/pages/klantenservice",
    # Product range / catalogue → homepage
    ("en", "product-range"):   "/en",
    ("de", "sortiment"):       "/de",
    ("fr", "nos-produits"):    "/fr",
    ("es", "catlogo"):         "/es",
    ("it", "prodotti"):        "/it",
    ("nl", "assortiment"):     "/",
}
HOMEPAGE_SLUGS = {"home", "inicio", "accueil", "home"}  # covers en/de/it/nl, es, fr

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

        slug_lc = slug.lower()

        # Fixed-path target (collection, homepage, etc.)
        if (lang, slug_lc) in FIXED_TARGETS:
            matched.append((src, FIXED_TARGETS[(lang, slug_lc)], "fixed"))
            continue

        # Exact match
        if slug in shopify_slugs:
            matched.append((src, new_path(lang, slug), "exact"))
            continue

        # Known mapping (use lowercase slug for lookup to handle URL-encoding variants)
        if (lang, slug_lc) in KNOWN_MAPPINGS:
            mapped = KNOWN_MAPPINGS[(lang, slug_lc)]
            if mapped in shopify_slugs:
                matched.append((src, new_path(lang, mapped), "mapped"))
                continue
            else:
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
