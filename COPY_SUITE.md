# Copy Suite — system notes & handoff

A handoff for the next iteration (of Claude, or of these tools). Copy Suite is a
single-file, dependency-light tool for assembling Shopify product copy from
modular blocks, translating it, and pushing it live. This doc captures the
architecture, decisions, and the reusable patterns so a sibling tool can start
from here.

---

## TL;DR

Phoenix Import (wholesale spiritual / wellness / lifestyle brand, Shopify store)
writes a lot of multi-language product copy. Copy Suite turns that into a
visual, modular, round-tripped pipeline:

```
Build copy in blocks        Export for translation        /translate (chat skill)        Import translations        Finalize → Shopify
(per product, base lang)  →  per-segment file (CSV/XLSX)  →  fills every [[TR]]         →  back into the tool       →  console-script + Paragon
   product-type templates      base filled, others [[TR]]     (HTML/-- preserved)           (matched by id)            (embedded Pipeline Gen)
   disclaimers auto-filled      disclaimers EXCLUDED                                          assembles all 6 locales,
                                                                                              injects canonical disclaimers
```

Everything lives in **one HTML file** (`copy-block-builder.html`, displayed as
"Copy Suite") plus a **skill** (`.claude/skills/translate/`).

---

## Files

| Path | Role |
|---|---|
| `copy-block-builder.html` | **Copy Suite (V1, live)**. Filename kept for stable URL/bookmarks; displayed name is "Copy Suite". localStorage key `copyBlockBuilder.project`. Linked in `index.html` under "Copy & content". |
| `copy-suite-v2.html` | **Copy Suite V2 sandbox** — identical clone, own key `copySuiteV2.project` (seeded once from V1), **not linked in index**. Point of departure for what's next. |
| `shopify-consoleimport.html` | **Pipeline Generator** (pre-existing). Consumes `SKU,LANG,TITLE,COPY` (CSV/XLSX) → Shopify console-script + two Paragon xlsx files. Its logic is embedded into Copy Suite's Finalize section. |
| `copy-to-html-writer.html` | Source of the reused contenteditable serializer + toolbar (`serializeNode`/`getHTML`). |
| `.claude/skills/translate/SKILL.md` | The `/translate` skill (file in → translated file back). |
| `.claude/skills/translate/translate_io.py` | Stdlib CSV+XLSX reader/writer + extract/apply. No openpyxl/pandas. |
| `index.html` | Tool hub. V1 linked; V2 deliberately not. |

External CDNs used by Copy Suite (client-side only): SheetJS (`xlsx`) and
PapaParse — same libs the Pipeline Generator uses.

---

## Data model (in the page's `project`, persisted to localStorage)

```js
project = {
  baseLang: 'NL',                 // language you write in; default NL (Shopify default)
  activeId: '<productId>',
  products: [{
    id, type,                     // type = a PRODUCT_TYPES key
    sku, title,                   // title may contain ' -- ' (display -- handle/SEO spec)
    titleT: { EN:'…', DE:'…' },   // per-language title translations (optional)
    blocks: [{
      id, type,                   // type = a BLOCK_TYPES key
      html,                       // base-language clean HTML (from the serializer)
      t: { EN:'…', DE:'…' }       // per-language block translations (optional)
    }]
  }]
}
```

Locales: `VALID_LOCALES = ['NL','EN','DE','FR','IT','ES']`. NL is mandatory for
the Pipeline Generator (every SKU needs an NL row).

---

## Block types (the copy "segments") — `BLOCK_TYPES`, 18 of them

In spreadsheet order (from `copy_types.xlsx`, columns B–S):
factual, evocative, **variant** (scent/colour — not in any template, added by
hand), sku, reach, weight_size, natural_disc, dye_disc, medical_disc,
content_list (list seed), ingredients (list seed), composition, technical,
esoteric, how_to_use, safety, brand_line, commercial, symbolism.

- Each block is a rich-text mini-editor; the toolbar + clean-HTML serializer are
  lifted from `copy-to-html-writer.html` (`escText`/`serializeNode`/`getHTML`).
- Shift+Enter = native `<br>`; segments are joined in output with `<br>` for
  white space between them.
- `LEGACY_BLOCK_KEYS` remaps old keys (`practical→factual`, drop `product_type`).

## Product types — `PRODUCT_TYPES`, 48 of them

Generated from `copy_types.xlsx` (each row = a type; marked columns = its default
blocks, in column order). Picking a type loads its template into the product
(replaces existing blocks after confirm). `generic` = blank; `other` = empty.
These are the standardized starting points (Statue, Incense, Metal singing bowl,
Essential oil, …).

## Standardized snippets — `SNIPPETS` + `TYPE_SNIPPETS` + `BLOCK_LIBRARIES`

Three layers of canonical (never-translated) text, resolved by `canonicalText(block, productType, lang)`:
- **`SNIPPETS`** (universal, per block type) — from `standardized_disclaimers.xlsx`:
  canonical text in all 6 languages for `reach`, `weight_size`, `natural_disc`,
  `dye_disc`, `medical_disc`.
- **`TYPE_SNIPPETS`** (per product type → per block) — from
  `warnings_and_how_to_use.xlsx`: `how_to_use` + `safety` text in all 6 languages
  for `incense`, `candle`, `essential_oil`, `incense_burner`. So those blocks are
  standardized *only* for those types; the same block type stays free-text for
  other product types.
- **`BLOCK_LIBRARIES`** (per block type → named entries, chosen per block via a
  dropdown) — `symbolism` (22 entries incl. Feng Shui, from `symbolism_boilerplate.xlsx`)
  and `commercial` (14 entries, from `Commercial_boilerplate.xlsx`). The block
  stores the chosen entry in `block.lib`; "Other" = free-text. Adding a block type
  to `BLOCK_LIBRARIES` automatically gives its cards a picker. `isCanonical(block,
  productType)` decides; resolution order is SNIPPETS → TYPE_SNIPPETS → library.
  (Note: `feng_shui_products`/`feng_shui_crystals` templates use `symbolism`, not
  `commercial` — their Feng Shui boilerplate lives in the symbolism library.)
- Those blocks **auto-fill** with the base-language canonical text when added.
- Switching base language refreshes *unedited* snippet blocks (`isUneditedSnippet`).
- **Crucially**, these are NEVER machine-translated. They are excluded from the
  translation file and **injected canonically per language** at final assembly
  (`blockTextForLang`). This is the one rule that keeps legal/standard wording
  byte-perfect.

---

## Segment translation round-trip + `/translate` skill

**Why segment-level (not translate the final blob):** disclaimers become a
deterministic exclude-then-inject (no fuzzy matching), each segment translates in
isolation, and the tool owns final assembly. Decided with the user.

**The translation file** (`buildTranslationRows` / CSV / XLSX): one row per
title + non-disclaimer block. Columns `SKU, BLOCK_ID, SEGMENT, NL, EN, DE, FR,
IT, ES`. Base column filled; other locales = sentinel `[[TR]]`. `BLOCK_ID` is the
stable block id (or `title`).

**Import** (`applyTranslations`): matches rows back by `SKU` + `BLOCK_ID`, stores
into `block.t[L]` / `product.titleT[L]`. Accepts CSV/XLSX file (PapaParse/SheetJS).

**Final assembly** (`buildFinalRows`): for each product × locale, title +
segments in order, disclaimers injected canonically, joined with `<br>`. Gated:
`buildParsed` only pushes a locale whose **title** is translated. NL title
required before generating the console-script.

**The skill** (`.claude/skills/translate/`): file-in → translated-file-back.
`translate_io.py extract <file>` detects base language + dumps `[[TR]]` cells to
`/tmp/translate_cells.json`; the agent writes translations to
`/tmp/translate_done.json`; `translate_io.py apply <file>` writes
`<file>-filled.csv` (always CSV — imports reliably) and **exits non-zero while
any `[[TR]]` remain** (the deterministic done-check). Reads CSV and XLSX with the
Python stdlib only (manual xlsx zip/XML parse + inline-string writer).

**Distribution gotcha:** Skills do NOT sync across surfaces. The repo copy serves
**Claude Code**; for **claude.ai chat** the user must upload the skill as a zip
under Settings → Capabilities (Pro/Max/Team/Enterprise, code execution on). A
zip was handed to the user.

---

## Shopify import contract (the target format — don't break it)

`shopify-consoleimport.html` expects rows `SKU, LANG, TITLE, COPY`, one per
(product × locale), and **requires an NL row per SKU**. Notable conventions
(reused verbatim in Copy Suite's embedded pipeline):
- `TITLE` may contain ` -- ` → `buildHandle` splits display title from the
  handle/SEO spec; `titleNoSpecs` strips it for the visible title; SEO meta uses
  the full `title_specs`.
- Console-script pushes NL via `productUpdate`, then non-NL via
  `translationsRegister` (fetches digests first). Run on the `*.myshopify.com`
  storefront domain.
- Paragon: `PRG_product_import.xlsx` (needs `status=Active`), then
  `PRG_associated_import.xlsx` (one `Vertaling` row per locale).

---

## Repo conventions / house style

- **Single-file vanilla HTML/CSS/JS per tool. No framework, no build step, no
  npm.** Match this for any sibling tool.
- House style: header bar `#68437B`; accent pink `#ca427e` / hover `#b33a6f`;
  Calibri font stack; `logo.png` links to `index.html`; bg `#f4f4f5`.
- New tools get a single `.html` file + an `<li>` in `index.html`'s relevant
  `<details>` section.

## Key design decisions (and why)

- **Segment round-trip over monolithic translate** — deterministic disclaimers,
  cleaner translations, tool owns assembly.
- **Disclaimers canonical, never translated** — legal text stays exact.
- **Output is always CSV from the skill** — sidesteps minimal-xlsx vs SheetJS
  reader risk; Copy Suite imports CSV reliably.
- **`[[TR]]` sentinel + zero-remaining check** — gives `/translate` a
  deterministic completion signal (user's idea).
- **Filename `copy-block-builder.html` kept on rename to "Copy Suite"** — stable
  URL/bookmarks/localStorage.
- **Per-product Type selector replaced the standalone "Product type" block.**

## Verification approach

No test harness in the repo; tools are client-side. Verified headlessly with
Node's `vm`: extract the inline `<script>`, stub a minimal DOM, and exercise pure
functions (`serializeNode`, `buildTranslationRows`, `applyTranslations`,
`buildFinalRows`, `buildParsed`, `buildScript`, snippet injection). Note the vm
quirk: top-level `let`/`const` (e.g. `project`) aren't readable as context
globals — drive state via `activeProduct()` and exported functions. The skill's
Python I/O was round-trip tested for CSV and XLSX (incl. a real Excel file).
Interactive DnD/buttons need a real browser.

---

## Reusable patterns (building blocks for the next tools)

These are the parts most likely to transplant into a sibling tool:
1. **Block builder core** — palette + drag-to-reorder stack + shared toolbar +
   contenteditable serializer (`serializeNode`/`getHTML`). Drag handle toggles
   `draggable` so contenteditable stays selectable.
2. **Type → template registry** (`PRODUCT_TYPES`) and **snippet library**
   (`SNIPPETS`) — config-driven defaults generated from spreadsheets.
3. **Segment round-trip translation** — per-unit file with `[[TR]]` sentinel +
   stable ids + `/translate` skill (stdlib CSV/XLSX io, deterministic done-check).
4. **Per-language storage** (`block.t`, `product.titleT`) + canonical-injection
   assembly.
5. **Embedded Pipeline Generator** — `buildParsed` → `buildDataBySku` →
   `buildScript` / Paragon, fed from in-memory rows instead of a file upload.

## Open threads / where V2 could go

- `dye_disc` has no standard wording yet (free-text).
- Snippet library could expand beyond disclaimers (brand/line boilerplate,
  commercial boilerplate variants) — same `SNIPPETS` pattern, with a picker.
- Optgroup grouping for the 48-item type dropdown (by category) if it feels long.
- Larger translation batches: chunking story for `/translate` is noted but
  untested at scale.
- The user has **other, similar tools planned** — V2 is the clean point of
  departure. The reusable patterns above are the intended starting kit.

## How to run / verify

Static files — open `copy-suite-v2.html` directly or via `python3 -m
http.server`. Build a product or two, Export for translation, run the file
through `/translate`, Import, then Finalize. For headless checks of pure logic,
use the Node `vm` pattern described above.
