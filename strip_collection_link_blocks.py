#!/usr/bin/env python3
r"""
strip_collection_link_blocks.py
--------------------------------
Removes the pipe-separated "collection link block" from every Shopify
collection description — in the primary locale AND in every translated locale —
and dumps everything it removed to a JSON file so the blocks can be put back
later (or re-implemented somewhere else).

Why
---
The blocks were added during the Shopify migration by
collection-link-block-generator.html / text-to-links-generator.html.  With the
current menu structure they spray internal link equity across ~250 collections,
which dilutes the pages we actually want ranking.  Pulling them out is
reversible: everything removed is kept verbatim in the JSON dump.

What counts as a link block
---------------------------
The pipe is the anchor, exactly as intended.  A container (<p>, then <div>,
then <strong>/<b>) qualifies when ALL of these hold:

  * it contains at least --min-links links to a collection — /collections/<handle>
    (relative, locale-prefixed like /de/collections/..., or absolute), or the
    bare handle the migration-era blocks use, e.g. href="kaarsen-en-sfeerlichten",
  * at least --min-collection-ratio of its links are collection links,
  * its text OUTSIDE the links contains no letters or digits — only
    separators/whitespace, so running prose with inline links is never touched,
  * that outside text holds at least (number of links - 1) pipe characters.

That last rule is what makes this safe to run store-wide: a real sentence with
a link in it always leaves words behind and is rejected.  Use `--self-test` to
see the detector's behaviour on a set of positive and negative samples.

Usage (PowerShell, run from Downloads — the usual way we run this)
------------------------------------------------------------------
  cd $env:USERPROFILE\Downloads

  # Grab the latest copy of this script from GitHub into Downloads:
  #   iwr https://raw.githubusercontent.com/phoenix-import/phoenix-import.github.io/main/strip_collection_link_blocks.py -OutFile strip_collection_link_blocks.py

  # Set the token for THIS window only (it disappears when you close it).
  # Needs an Admin API token with read/write_products + read/write_translations.
  $env:SHOPIFY_TOKEN = "shpat_xxxxxxxxxxxxxxxxxxxxxxxx"

  # 1. Look first — writes the JSON dump, changes nothing in the store.
  python strip_collection_link_blocks.py scan --report found.csv

  # 2. Strip for real (same dump is written, then the store is updated).
  python strip_collection_link_blocks.py apply

  # 3. If we ever want them back.
  python strip_collection_link_blocks.py restore --backup collection-link-blocks.json

  # No token needed for this one — checks the detector against sample HTML.
  python strip_collection_link_blocks.py --self-test

If `python` is not recognised, try `py` instead. On macOS/Linux the token line
is `export SHOPIFY_TOKEN=shpat_...` and the command is `python3`.

IMPORTANT: the JSON dump is written next to wherever you run this, so from
Downloads it lands in Downloads. That file is the ONLY way to put the blocks
back — move it somewhere safe once the run is done, or point --out at a proper
folder from the start.

Handy flags: --handles a,b,c   --limit 20   --locales de,fr   --report out.csv
             --token shpat_...  (instead of the environment variable)

Where the token comes from
--------------------------
  Shopify admin > Settings > Apps and sales channels > Develop apps >
  (the app we use for these scripts) > API credentials > Admin API access
  token.  Same shpat_... token the console scripts prompt for, as long as the
  translation scopes are ticked under Configuration > Admin API integration.

Notes / limitations
-------------------
  * Market-specific translations (translations bound to a market rather than
    just a locale) are NOT read or written; only the plain per-locale ones are.
  * `apply` updates the primary description first, then re-reads the fresh
    translatable-content digest before registering each locale, so translations
    are never marked "outdated" by our own edit.
  * `restore` refuses to overwrite anything that changed in the store since the
    dump was taken, unless --force is given.
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser

DEFAULT_SHOP = "manibhadra-phoeniximport.myshopify.com"
DEFAULT_API_VERSION = "2025-10"
TARGET_KEY = "body_html"          # the collection description
# Used when the token lacks read_locales; override with --primary-locale/--locales.
FALLBACK_PRIMARY_LOCALE = "nl"
FALLBACK_LOCALES = ["en", "de", "fr", "it", "es"]
CONTAINER_TAGS = ("p", "div", "strong", "b")

# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

COLLECTION_HREF_RE = re.compile(
    r"^(?:https?:)?(?://[^/]+)?(?:/[a-z]{2}(?:-[a-z]{2})?)?/collections/[^/?#\s]+",
    re.I,
)
# Legacy migration blocks link with the bare handle and no /collections/ prefix,
# e.g. href="kaarsen-en-sfeerlichten". Handle-shaped means: no scheme, no slash,
# no dot, no query — which rules out page/file links like "register.aspx".
BARE_HANDLE_HREF_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*/?$", re.I)
ALNUM_RE = re.compile(r"[^\W_]", re.UNICODE)


class _BlockParser(HTMLParser):
    """Splits a chunk of HTML into its <a> links and the text around them."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.residual = []
        self._depth = 0
        self._cur = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            if self._depth == 0:
                self._cur = {"href": dict(attrs).get("href", "") or "", "text": []}
            self._depth += 1

    def handle_endtag(self, tag):
        if tag == "a" and self._depth > 0:
            self._depth -= 1
            if self._depth == 0 and self._cur is not None:
                self.links.append({
                    "href": self._cur["href"],
                    "text": " ".join("".join(self._cur["text"]).split()),
                })
                self._cur = None

    def handle_data(self, data):
        if self._depth > 0 and self._cur is not None:
            self._cur["text"].append(data)
        else:
            self.residual.append(data)

    @property
    def residual_text(self):
        return "".join(self.residual)


def _tag_spans(html, tag):
    """Outermost (start, end) spans of `tag`, nesting-aware for that tag."""
    spans, depth, start = [], 0, None
    pattern = re.compile(r"<(/?)%s\b[^>]*>" % tag, re.I | re.S)
    for m in pattern.finditer(html):
        if m.group(1) == "":
            if html[m.start():m.end()].rstrip().endswith("/>"):
                continue                      # self-closed, no content
            if depth == 0:
                start = m.start()
            depth += 1
        elif depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                spans.append((start, m.end()))
                start = None
    return spans


def is_collection_href(href):
    href = (href or "").strip()
    return bool(COLLECTION_HREF_RE.match(href) or BARE_HANDLE_HREF_RE.match(href))


def qualifies(chunk, min_links, min_ratio):
    """Return the link list if `chunk` is a pipe-separated collection link block."""
    parser = _BlockParser()
    parser.feed(chunk)
    parser.close()
    links = parser.links
    if len(links) < min_links:
        return None
    coll = [l for l in links if is_collection_href(l["href"])]
    if len(coll) < min_links:
        return None
    if len(coll) / len(links) < min_ratio:
        return None
    residual = parser.residual_text
    if ALNUM_RE.search(residual):
        return None                            # prose around the links -> not a block
    if residual.count("|") + residual.count("｜") < len(links) - 1:
        return None                            # not pipe-separated
    return links


def find_link_blocks(html, min_links=2, min_ratio=0.75):
    """All link blocks in `html`, as dicts with start/end/html/links."""
    if not html or "<a" not in html or "|" not in html:
        return []
    found = []
    for tag in CONTAINER_TAGS:
        for start, end in _tag_spans(html, tag):
            if any(start < b["end"] and end > b["start"] for b in found):
                continue                       # already inside an accepted block
            links = qualifies(html[start:end], min_links, min_ratio)
            if links is not None:
                found.append({
                    "tag": tag,
                    "start": start,
                    "end": end,
                    "html": html[start:end],
                    "links": links,
                })
    return sorted(found, key=lambda b: b["start"])


def tidy(html):
    """Clean up what removing a trailing block leaves behind."""
    out = re.sub(r"\n{3,}", "\n\n", html)
    out = re.sub(r"(?:\s*<br\s*/?>)+\s*$", "", out, flags=re.I)
    out = re.sub(r"(?:\s*<p[^>]*>(?:\s|&nbsp;| |<br\s*/?>)*</p>)+\s*$", "", out, flags=re.I)
    return out.strip()


def strip_link_blocks(html, min_links=2, min_ratio=0.75):
    """-> (stripped_html, [blocks]).  Unchanged html when nothing qualifies."""
    blocks = find_link_blocks(html, min_links, min_ratio)
    if not blocks:
        return html, []
    out = html
    for b in reversed(blocks):
        out = out[:b["start"]] + out[b["end"]:]
    return tidy(out), blocks


# ---------------------------------------------------------------------------
# Shopify Admin GraphQL
# ---------------------------------------------------------------------------

class ShopifyError(RuntimeError):
    pass


class Shopify:
    def __init__(self, shop, token, api_version, verbose=False):
        self.shop = self._normalise(shop)
        self.token = token
        self.endpoint = "https://%s/admin/api/%s/graphql.json" % (self.shop, api_version)
        self.verbose = verbose
        self.calls = 0

    @staticmethod
    def _normalise(shop):
        shop = (shop or "").strip().rstrip("/")
        shop = re.sub(r"^https?://", "", shop)
        shop = shop.split("/")[0]
        if not shop.endswith(".myshopify.com"):
            shop += ".myshopify.com"
        return shop

    def gql(self, query, variables=None, attempt=0):
        body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Access-Token": self.token,
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < 5:
                time.sleep(2 ** attempt)
                return self.gql(query, variables, attempt + 1)
            raise ShopifyError("HTTP %s: %s" % (exc.code, exc.read().decode("utf-8", "replace")))
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt < 4:
                time.sleep(2 ** attempt)
                return self.gql(query, variables, attempt + 1)
            raise ShopifyError("network error: %s" % exc)

        self.calls += 1
        errors = payload.get("errors") or []
        throttled = any("THROTTLED" in json.dumps(e) for e in errors)
        if throttled and attempt < 6:
            wait = 1.5 * (attempt + 1)
            if self.verbose:
                print("  throttled — waiting %.1fs" % wait, file=sys.stderr)
            time.sleep(wait)
            return self.gql(query, variables, attempt + 1)
        if errors:
            raise ShopifyError(json.dumps(errors, indent=2))

        available = (payload.get("extensions", {}).get("cost", {})
                            .get("throttleStatus", {}).get("currentlyAvailable"))
        if isinstance(available, (int, float)) and available < 250:
            time.sleep(0.8)
        return payload.get("data") or {}

    # -- reads ------------------------------------------------------------
    def locales(self):
        """(primary, [others]), or (None, None) if the token can't read locales."""
        try:
            data = self.gql("{ shopLocales { locale primary published } }")
        except ShopifyError as exc:
            if "read_locales" in str(exc) or "read_markets_home" in str(exc):
                return None, None          # caller falls back to the defaults
            raise
        rows = data.get("shopLocales") or []
        primary = next((r["locale"] for r in rows if r.get("primary")), None)
        others = [r["locale"] for r in rows if not r.get("primary") and r.get("published")]
        return primary, others

    def collections(self, locales, page_size=25):
        """Yield {resource_id, handle, title, body_html, digest, translations{}}."""
        aliases = "\n          ".join(
            'L%d: translations(locale: "%s") { key value locale outdated }' % (i, loc)
            for i, loc in enumerate(locales)
        )
        query = """
        query($cursor: String) {
          translatableResources(resourceType: COLLECTION, first: %d, after: $cursor) {
            pageInfo { hasNextPage endCursor }
            nodes {
              resourceId
              translatableContent { key value digest }
              %s
            }
          }
        }
        """ % (page_size, aliases)
        cursor = None
        while True:
            conn = self.gql(query, {"cursor": cursor})["translatableResources"]
            for node in conn["nodes"]:
                content = {c["key"]: c for c in node["translatableContent"]}
                translations = {}
                for i, loc in enumerate(locales):
                    for tr in node.get("L%d" % i) or []:
                        if tr["key"] == TARGET_KEY:
                            translations[loc] = tr
                yield {
                    "resource_id": node["resourceId"],
                    "handle": (content.get("handle") or {}).get("value") or "",
                    "title": (content.get("title") or {}).get("value") or "",
                    "body_html": (content.get(TARGET_KEY) or {}).get("value") or "",
                    "digest": (content.get(TARGET_KEY) or {}).get("digest") or "",
                    "translations": translations,
                }
            if not conn["pageInfo"]["hasNextPage"]:
                return
            cursor = conn["pageInfo"]["endCursor"]

    def fresh_digest(self, resource_id, key=TARGET_KEY):
        data = self.gql(
            "query($id: ID!) { translatableResource(resourceId: $id) "
            "{ translatableContent { key digest } } }",
            {"id": resource_id},
        )
        for c in (data.get("translatableResource") or {}).get("translatableContent") or []:
            if c["key"] == key:
                return c["digest"]
        return None

    def live_values(self, resource_id, locales):
        """Current primary + translated body_html, for restore-time safety checks."""
        aliases = "\n        ".join(
            'L%d: translations(locale: "%s") { key value }' % (i, loc)
            for i, loc in enumerate(locales)
        )
        data = self.gql(
            """query($id: ID!) {
              translatableResource(resourceId: $id) {
                translatableContent { key value digest }
                %s
              }
            }""" % aliases,
            {"id": resource_id},
        )
        node = data.get("translatableResource") or {}
        content = {c["key"]: c for c in node.get("translatableContent") or []}
        values = {"__primary__": (content.get(TARGET_KEY) or {}).get("value") or "",
                  "__digest__": (content.get(TARGET_KEY) or {}).get("digest") or ""}
        for i, loc in enumerate(locales):
            values[loc] = next(
                (t["value"] for t in node.get("L%d" % i) or [] if t["key"] == TARGET_KEY), None)
        return values

    # -- writes -----------------------------------------------------------
    def update_description(self, collection_id, html):
        mutation = """
        mutation($input: CollectionInput!) {
          collectionUpdate(input: $input) {
            collection { id }
            userErrors { field message }
          }
        }"""
        variables = {"input": {"id": collection_id, "descriptionHtml": html}}
        try:
            result = self.gql(mutation, variables)
        except ShopifyError as exc:
            # Newer API versions split the id out of the input object.
            if "id" not in str(exc):
                raise
            mutation = """
            mutation($id: ID!, $input: CollectionInput!) {
              collectionUpdate(id: $id, input: $input) {
                collection { id }
                userErrors { field message }
              }
            }"""
            result = self.gql(mutation, {"id": collection_id,
                                         "input": {"descriptionHtml": html}})
        errs = result["collectionUpdate"]["userErrors"]
        if errs:
            raise ShopifyError(json.dumps(errs))

    def register_translations(self, resource_id, entries):
        """entries: [{locale, value, digest}]"""
        mutation = """
        mutation($resourceId: ID!, $translations: [TranslationInput!]!) {
          translationsRegister(resourceId: $resourceId, translations: $translations) {
            userErrors { field message }
          }
        }"""
        payload = [{"key": TARGET_KEY, "locale": e["locale"], "value": e["value"],
                    "translatableContentDigest": e["digest"]} for e in entries]
        result = self.gql(mutation, {"resourceId": resource_id, "translations": payload})
        errs = result["translationsRegister"]["userErrors"]
        if errs:
            raise ShopifyError(json.dumps(errs))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def build_plan(api, args, locales):
    """Read every collection, work out what would change. -> (plan, stats)."""
    wanted = {h.strip() for h in (args.handles or "").split(",") if h.strip()}
    plan, seen = [], 0

    for coll in api.collections(locales, page_size=args.page_size):
        if wanted and coll["handle"] not in wanted:
            continue
        seen += 1
        if args.limit and seen > args.limit:
            break

        entry = {
            "resource_id": coll["resource_id"],
            "handle": coll["handle"],
            "title": coll["title"],
            "primary": None,
            "translations": [],
        }

        after, blocks = strip_link_blocks(coll["body_html"], args.min_links, args.min_collection_ratio)
        if blocks:
            entry["primary"] = {
                "locale": args.primary_locale,
                "key": TARGET_KEY,
                "before": coll["body_html"],
                "after": after,
                "digest": coll["digest"],
                "blocks": [{"tag": b["tag"], "html": b["html"], "links": b["links"]} for b in blocks],
            }

        for loc, tr in sorted(coll["translations"].items()):
            t_after, t_blocks = strip_link_blocks(tr.get("value") or "",
                                                  args.min_links, args.min_collection_ratio)
            if t_blocks:
                entry["translations"].append({
                    "locale": loc,
                    "key": TARGET_KEY,
                    "before": tr.get("value") or "",
                    "after": t_after,
                    "outdated": bool(tr.get("outdated")),
                    "blocks": [{"tag": b["tag"], "html": b["html"], "links": b["links"]} for b in t_blocks],
                })

        if entry["primary"] or entry["translations"]:
            plan.append(entry)
        if args.verbose and seen % 50 == 0:
            print("  scanned %d collections…" % seen, file=sys.stderr)

    stats = {
        "collections_scanned": seen,
        "collections_with_blocks": len(plan),
        "primary_descriptions_changed": sum(1 for e in plan if e["primary"]),
        "translations_changed": sum(len(e["translations"]) for e in plan),
        "blocks_removed": sum(
            len(e["primary"]["blocks"]) if e["primary"] else 0 for e in plan
        ) + sum(len(t["blocks"]) for e in plan for t in e["translations"]),
        "links_removed": sum(
            len(b["links"])
            for e in plan
            for b in ((e["primary"]["blocks"] if e["primary"] else []) +
                      [bb for t in e["translations"] for bb in t["blocks"]])
        ),
    }
    return plan, stats


def write_dump(path, api, args, locales, plan, stats):
    dump = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "shop": api.shop,
        "api_version": args.api_version,
        "primary_locale": args.primary_locale,
        "locales": locales,
        "key": TARGET_KEY,
        "detector": {
            "min_links": args.min_links,
            "min_collection_ratio": args.min_collection_ratio,
            "container_tags": list(CONTAINER_TAGS),
            "requires_pipes": True,
        },
        "applied": bool(args.command == "apply" and not args.dry_run),
        "stats": stats,
        "collections": plan,
    }
    if os.path.exists(path):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        kept = "%s.%s.bak%s" % (os.path.splitext(path)[0], stamp, os.path.splitext(path)[1])
        os.replace(path, kept)
        print("Existing dump kept as %s (it is the only way to restore an earlier run)" % kept)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(dump, fh, ensure_ascii=False, indent=2)
    return dump


def write_report(path, plan):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["handle", "title", "locale", "blocks", "links", "removed_html"])
        for e in plan:
            rows = ([e["primary"]] if e["primary"] else []) + e["translations"]
            for row in rows:
                writer.writerow([
                    e["handle"], e["title"], row["locale"], len(row["blocks"]),
                    sum(len(b["links"]) for b in row["blocks"]),
                    " ".join(b["html"] for b in row["blocks"]),
                ])


def push_changes(api, plan, verbose=False, value_key="after"):
    """Apply `value_key` ('after' to strip, 'before' to restore) to the store."""
    ok, failed = 0, []
    for i, entry in enumerate(plan, 1):
        label = entry["handle"] or entry["resource_id"]
        try:
            if entry.get("primary"):
                api.update_description(entry["resource_id"], entry["primary"][value_key])
            if entry.get("translations"):
                digest = api.fresh_digest(entry["resource_id"])
                if not digest:
                    raise ShopifyError("no %s digest returned" % TARGET_KEY)
                api.register_translations(entry["resource_id"], [
                    {"locale": t["locale"], "value": t[value_key], "digest": digest}
                    for t in entry["translations"]
                ])
            ok += 1
            if verbose or i % 25 == 0:
                print("  %d/%d %s" % (i, len(plan), label), file=sys.stderr)
        except ShopifyError as exc:
            failed.append({"handle": label, "error": str(exc)})
            print("  FAILED %s: %s" % (label, exc), file=sys.stderr)
    return ok, failed


def cmd_scan_or_apply(args):
    api = Shopify(args.shop, args.token, args.api_version, args.verbose)
    primary, others = api.locales()
    if primary is None and others is None:
        primary, others = FALLBACK_PRIMARY_LOCALE, list(FALLBACK_LOCALES)
        print("Note: token can't read shopLocales (no read_locales scope), so falling\n"
              "      back to the standard set — primary '%s', translated %s.\n"
              "      Override with --primary-locale / --locales if that's not right."
              % (primary, ", ".join(others)))
    args.primary_locale = args.primary_locale or primary or FALLBACK_PRIMARY_LOCALE
    if args.locales:
        wanted = {l.strip() for l in args.locales.split(",") if l.strip()}
        others = [l for l in others if l in wanted]
    print("Shop %s — primary '%s', translated %s"
          % (api.shop, args.primary_locale, ", ".join(others) or "(none)"))

    plan, stats = build_plan(api, args, others)

    print("\nScanned %(collections_scanned)d collections."
          "\n  %(collections_with_blocks)d contain a link block"
          "\n  %(primary_descriptions_changed)d primary descriptions to change"
          "\n  %(translations_changed)d translated descriptions to change"
          "\n  %(blocks_removed)d blocks / %(links_removed)d links total" % stats)

    write_dump(args.out, api, args, others, plan, stats)
    print("\nDump written to %s" % args.out)
    if args.report:
        write_report(args.report, plan)
        print("Report written to %s" % args.report)

    if args.command != "apply":
        print("\nDry run — nothing was written to the store. Re-run with 'apply' to strip.")
        return 0
    if not plan:
        print("\nNothing to strip.")
        return 0
    if not args.yes:
        answer = input("\nStrip these from %d collections? [y/N] " % len(plan)).strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted — store untouched, dump kept.")
            return 1

    print("\nApplying…")
    ok, failed = push_changes(api, plan, args.verbose, value_key="after")
    args.dry_run = False
    write_dump(args.out, api, args, others, plan, stats)
    print("\nDone. %d collections updated, %d failed." % (ok, len(failed)))
    return 1 if failed else 0


def cmd_restore(args):
    with open(args.backup, encoding="utf-8") as fh:
        dump = json.load(fh)
    api = Shopify(args.shop or dump.get("shop"), args.token,
                  args.api_version or dump.get("api_version"), args.verbose)
    wanted = {h.strip() for h in (args.handles or "").split(",") if h.strip()}
    plan = [e for e in dump["collections"] if not wanted or e["handle"] in wanted]

    # Only restore what still looks like we left it.
    safe, drifted = [], []
    for entry in plan:
        locales = [t["locale"] for t in entry["translations"]]
        live = api.live_values(entry["resource_id"], locales)
        changed = []
        if entry.get("primary") and live["__primary__"] != entry["primary"]["after"]:
            changed.append(args.primary_locale or dump.get("primary_locale") or "primary")
        for t in entry["translations"]:
            if live.get(t["locale"]) != t["after"]:
                changed.append(t["locale"])
        if changed and not args.force:
            drifted.append({"handle": entry["handle"], "locales": changed})
        else:
            safe.append(entry)

    print("%d collections in dump — %d restorable, %d changed since the dump"
          % (len(plan), len(safe), len(drifted)))
    for d in drifted:
        print("  skipping %s (edited since: %s)" % (d["handle"], ", ".join(d["locales"])))
    if not safe:
        return 0
    if not args.yes:
        answer = input("\nPut the link blocks back on %d collections? [y/N] " % len(safe)).strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            return 1

    ok, failed = push_changes(api, safe, args.verbose, value_key="before")
    print("\nDone. %d collections restored, %d failed." % (ok, len(failed)))
    return 1 if failed else 0


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

SAMPLES = [
    # (should_match, name, html)
    (True, "the real thing (7 links, p>strong)",
     '<p><strong><a href="/collections/edelsteen-hangers-gepolijst">Edelsteen hangers gepolijst</a> | '
     '<a href="/collections/edelsteen-hangers-ruw">Edelsteen hangers ruw</a> | '
     '<a href="/collections/hangers-edelsteen-geboord">Hangers edelsteen geboord</a> | '
     '<a href="/collections/edelsteen-armbanden">Edelsteen armbanden</a> | '
     '<a href="/collections/edelsteen-en-seleniet-lampen">Edelsteen en seleniet lampen</a> | '
     '<a href="/collections/edelsteen-oorbellen">Edelsteen oorbellen</a> | '
     '<a href="/collections/sieraden-accessoires">Sieraden accessoires</a></strong></p>'),
    (True, "locale-prefixed hrefs, no <strong>",
     '<p><a href="/de/collections/raeucherwerk">Räucherwerk</a> | '
     '<a href="/de/collections/salbei">Salbei</a></p>'),
    (True, "absolute hrefs, &nbsp; padding",
     '<p><strong><a href="https://www.phoeniximport.fr/collections/encens">Encens</a>&nbsp;|&nbsp;'
     '<a href="https://www.phoeniximport.fr/collections/sauge">Sauge</a></strong></p>'),
    (True, "bare <strong>, no wrapper",
     '<strong><a href="/collections/a">A</a> | <a href="/collections/b">B</a></strong>'),
    (True, "block with one non-collection link mixed in",
     '<p><a href="/collections/a">A</a> | <a href="/collections/b">B</a> | '
     '<a href="/collections/c">C</a> | <a href="/pages/over-ons">Over ons</a></p>'),
    (True, "bare handle hrefs, <strong> per link, pipes outside (migration-era)",
     '<p><strong><a href="kaarsen-en-sfeerlichten">Kaarsen en sfeerlichten</a></strong> | '
     '<strong><a href="wierook-witte-salie-en-houtskool">Wierook, witte salie en houtskool</a></strong> | '
     '<strong><a href="yoga">Yoga</a></strong> | <strong><a href="sieraden">Sieraden</a></strong></p>'),
    (False, "pipe-separated file/page links, not collections",
     '<p><a href="register.aspx">Registreren</a> | <a href="login.aspx">Inloggen</a></p>'),
    (False, "prose with inline links",
     '<p>Bekijk ook onze <a href="/collections/edelsteen-armbanden">edelsteen armbanden</a> en '
     '<a href="/collections/edelsteen-oorbellen">oorbellen</a> voor de complete set.</p>'),
    (False, "single link",
     '<p><a href="/collections/edelsteen-armbanden">Edelsteen armbanden</a></p>'),
    (False, "two links, no pipe",
     '<p><a href="/collections/a">A</a> <a href="/collections/b">B</a></p>'),
    (False, "pipe-separated product links, not collections",
     '<p><a href="/products/a">A</a> | <a href="/products/b">B</a></p>'),
    (False, "pipe-separated plain text, no links",
     '<p><strong>Edelsteen hangers | Edelsteen armbanden</strong></p>'),
]

FULL_DOC = (
    "<p>Onze edelsteen hangers zijn met zorg geselecteerd.</p>\n"
    "<p>Bekijk ook de <a href=\"/collections/edelsteen-armbanden\">armbanden</a>.</p>\n"
    '<p><strong><a href="/collections/a">A</a> | <a href="/collections/b">B</a> | '
    '<a href="/collections/c">C</a></strong></p>'
)


def self_test():
    failures = 0
    print("Detector self-test\n" + "-" * 60)
    for expected, name, html in SAMPLES:
        got = bool(find_link_blocks(html))
        mark = "ok  " if got == expected else "FAIL"
        if got != expected:
            failures += 1
        print("%s  %-45s expected=%s got=%s" % (mark, name[:45], expected, got))

    stripped, blocks = strip_link_blocks(FULL_DOC)
    expect = ("<p>Onze edelsteen hangers zijn met zorg geselecteerd.</p>\n"
              "<p>Bekijk ook de <a href=\"/collections/edelsteen-armbanden\">armbanden</a>.</p>")
    mark = "ok  " if (len(blocks) == 1 and stripped == expect) else "FAIL"
    if mark == "FAIL":
        failures += 1
        print("\n  got:      %r\n  expected: %r" % (stripped, expect))
    print("%s  %-45s (block removed, prose + inline link kept)" % (mark, "full description strip"))

    print("-" * 60)
    print("%d failure(s)" % failures)
    return 1 if failures else 0


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Strip pipe-separated collection link blocks from Shopify collections "
                    "(all locales) and dump them to JSON so they can be restored.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("command", nargs="?", default="scan",
                        choices=["scan", "apply", "restore"],
                        help="scan = read-only dry run (default); apply = strip; "
                             "restore = put the blocks back from a dump")
    parser.add_argument("--shop", default=os.environ.get("SHOPIFY_SHOP", DEFAULT_SHOP))
    parser.add_argument("--token", default=os.environ.get("SHOPIFY_TOKEN", ""),
                        help="Admin API token (shpat_...); or set SHOPIFY_TOKEN")
    parser.add_argument("--api-version", default=os.environ.get("SHOPIFY_API_VERSION",
                                                                DEFAULT_API_VERSION))
    parser.add_argument("--out", default="collection-link-blocks.json",
                        help="where to write the JSON dump (scan/apply)")
    parser.add_argument("--backup", help="JSON dump to restore from (restore)")
    parser.add_argument("--report", help="also write a CSV summary of what was found")
    parser.add_argument("--handles", help="comma-separated handles to limit the run to")
    parser.add_argument("--locales", help="comma-separated locales to touch (default: all published)")
    parser.add_argument("--primary-locale", default=None,
                        help="override the shop's primary locale label")
    parser.add_argument("--limit", type=int, default=0, help="stop after N collections")
    parser.add_argument("--page-size", type=int, default=25, help="collections per API page")
    parser.add_argument("--min-links", type=int, default=2,
                        help="minimum collection links for a block to qualify (default 2)")
    parser.add_argument("--min-collection-ratio", type=float, default=0.75,
                        help="minimum share of a block's links that must be collection links")
    parser.add_argument("--force", action="store_true",
                        help="restore even over descriptions edited since the dump")
    parser.add_argument("-y", "--yes", action="store_true", help="skip the confirmation prompt")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--self-test", action="store_true",
                        help="run the detector against sample HTML and exit (no network)")
    args = parser.parse_args()
    args.dry_run = args.command != "apply"

    if args.self_test:
        return self_test()
    if not args.token:
        parser.error("no Admin API token — pass --token or set SHOPIFY_TOKEN")
    if args.command == "restore":
        if not args.backup:
            parser.error("restore needs --backup <dump.json>")
        return cmd_restore(args)
    return cmd_scan_or_apply(args)


if __name__ == "__main__":
    sys.exit(main())
