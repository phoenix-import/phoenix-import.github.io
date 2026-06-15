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

## Block types (the copy "segments") — `BLOCK_TYPES`, 20 of them

In spreadsheet order (from `copy_types.xlsx`, columns B–S):
factual, evocative, **variant** (scent/colour — not in any template, added by
hand), sku, reach, weight_size, natural_disc, dye_disc, medical_disc,
content_list (list seed), ingredients (list seed), composition, technical,
esoteric, how_to_use, safety, brand_line, commercial, symbolism, **material**
(multi-select gemstone/natural library — see below; not in any template, added
by hand), **copied_html** (a raw-HTML `<textarea>` — paste markup straight from
existing product descriptions; used verbatim, free-text/translatable, with a live
render preview; nbsp stripped on input).

> **Non-breaking spaces:** `escText` (the serializer) converts U+00A0 → regular
> space so pasted nbsp never leaks into the output; `stripNbsp()` (U+00A0 *and*
> literal `&nbsp;`) is applied to the Copied HTML textarea input.

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
- **`material` block** (the gemstone/natural library) — a *fourth* canonical layer,
  but multi-select instead of single-pick. Data lives in `const MATERIALS` (148
  id-keyed entries: `name, ess` essence, `bel` beliefs, `ch/el/zo/pl`
  correspondences, `cat`). The block stores `block.mats` (ordered array of ids) and
  three **independent checkbox** flags: `block.matFull` (the beliefs paragraph —
  default **on**), `block.matShort` (the short essence line — default **off**), and
  `block.matAssoc` (the `Chakra: … | Element: … | Zodiac: … | Planet: …` line —
  default **off**). `renderMaterials(b, lang)` builds the canonical HTML — one `<p>`
  per material as `<strong>Name</strong> | {essence and/or beliefs}` (a pipe, not a
  colon or em-dash; the bold is the stone name *only*, inline, never a mini-header),
  with the correspondence line on its own `<br>` row when enabled. `canonicalText`
  returns it (so `isCanonical` is true and it is injected per language, excluded from
  the translation file). `buildMaterialRow(card, block)` is the card UI (mirrors
  `buildSkuRow`): the three Full/Short/Correspondences checkboxes, an ordered
  **drag-reorder** list of the picked materials, a **search box + collapsible
  checklist** grouped by category, and a live preview. `block.html` is kept synced to the base-language
  render, like SKU. **Content is English-only for now** (built "format first");
  each translatable field is a flat string that a later pass turns into a
  `{NL,EN,…}` object — `matPick()` already reads either shape, and the 4
  correspondence *labels* (`MAT_LABELS`) are localised for all six locales now.
- Those blocks **auto-fill** with the base-language canonical text when added.
- Switching base language refreshes *unedited* snippet blocks (`isUneditedSnippet`).
- **Crucially**, these are NEVER machine-translated. They are excluded from the
  translation file and **injected canonically per language** at final assembly
  (`blockTextForLang`). This is the one rule that keeps legal/standard wording
  byte-perfect.

---

## Adding content (cookbook)

All of these are **data edits** — find the `const` near the top of the
`<script>` and add an entry.

> **V1/V2 sync — read this.** *While V2 is still a synced clone of V1 (the
> current state)*, apply every change to **both** files; they should stay
> identical except V2's 4 sandbox lines (title, header, `STORAGE_KEY`,
> `loadProject` seed). Shortcut: edit V1, then `cp copy-block-builder.html
> copy-suite-v2.html` and re-apply those 4 patches. **The moment V2 forks into
> the independent AI-writing tool, this convention ENDS:** maintain the two
> independently — never `cp` V1 over V2, and never propagate a change either
> direction. *How to tell which phase you're in:* `diff copy-block-builder.html
> copy-suite-v2.html` — if it's just the ~11 sandbox lines, V2 is still a clone
> (mirror edits); anything more means V2 has diverged (treat them as separate
> tools, edit only the one you mean).

After any edit, syntax-check with the Node `vm` pattern (see Verification).

When the user pastes raw HTML, **normalize it** first: decode entities to real
UTF-8 **but keep `&amp;`** (literal `&`, e.g. "Yogi & Yogini"), `<br />`→`<br>`,
strip Word/MSO `<span style>`/`class="MsoNormal"`, `<div>`→`<p>`, drop empty
`<p>`. If only NL is given, translate the other five (keep brand/product names,
`Chi`/`yin`/`yang`, etc.). All entries need all 6 of `NL,EN,DE,FR,IT,ES`.

| To add… | Edit | Shape | Notes |
|---|---|---|---|
| **Boilerplate dropdown entry** (symbolism/commercial) | `BLOCK_LIBRARIES.<blocktype>` | `key: { label: "Name", text: {NL,…,ES} }` (values = full HTML) | Most common. Quote keys that start with a digit (`"108"`, `"432_hz"`). |
| **Universal disclaimer** | `SNIPPETS` | `key: {NL,…,ES}` (values = **plain text**) | Auto-wrapped in `<p><em>…</em></p>` (italic). `key` must also be a `BLOCK_TYPES` key. |
| **Per-type how-to/safety** | `TYPE_SNIPPETS.<type>.<block>` | `{NL,…,ES}` (full HTML) | Canonical only for that product type; free-text elsewhere. |
| **Product type** | `PRODUCT_TYPES` | `key: { label: "Name", blocks: ["factual","sku",…] }` | `blocks` are `BLOCK_TYPES` keys, in display order. |
| **Block type** (new segment) | `BLOCK_TYPES` | `key: { label: "Name", seed: "text"\|"list" }` | Add a palette item automatically. |
| **SKU phrasing** | `SKU_TEMPLATE` | `{NL: "… {n} …", …}` | `{n}` = the quantity the user types. |
| **Material library entry** | `MATERIALS` | `{id, cat, name, ess, bel, ch, el, zo, pl}` | `id` unique; `cat` ∈ `MAT_CATS`. Fields are flat English strings now → a `{NL,…}` object once translated (`matPick` reads both). Empty correspondence = `""` (skipped in output). |

### Sorting / order (where things appear)
- **Boilerplate dropdowns** (symbolism, commercial): sorted **alphabetically by
  `label`** at render (`buildLibRow`), with **"Other (manual entry)" pinned
  first**. Data order doesn't matter.
- **Product-type dropdown**: **registry/insertion order** of `PRODUCT_TYPES` (not
  sorted) — `generic` first, `other` last by convention.
- **Block palette**: **insertion order** of `BLOCK_TYPES`.
- **Languages**: `VALID_LOCALES` order (`NL,EN,DE,FR,IT,ES`).

### After adding
- A library entry → its block type's cards already show the picker (any block
  type present in `BLOCK_LIBRARIES` gets one). Canonical = excluded from the
  translation file, injected per language at assembly.
- If a product type should *carry* a new block by default, also add that block
  key to the type's `blocks` array in `PRODUCT_TYPES`.



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

**Proofread re-ingest (Finalize):** the Finalize section is a 3-step flow —
**1. download for proofread** (CSV/XLSX = `buildFinalRows`), **2. upload proofread
final** (the file after the chat `/proofread` skill), **3. generate** script +
Paragon imports. The upload sets `proofreadFinal = {rows,name,count}` (parsed via
`readRows`, same `SKU,LANG,TITLE,COPY` shape); **`buildParsed` then sources from
`proofreadFinal` when set, else the live project**, so the proofread copy is what
actually gets pushed. A `#finSource` line shows which source is active; "Use live
project" (`clearProofBtn`) clears it. Editing blocks does *not* auto-invalidate an
uploaded file — clear it manually if you re-export.

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

## Open threads / backlog

Status: **V1 is approaching testing.** All universal disclaimers (incl. `dye_disc`),
the per-type How-to/Safety, the symbolism (22) and commercial (15) libraries, and the
number-only SKU field are in. Remaining / planned:

- **Excel product/title batch import + normalizer** (planned). Copy Suite already
  reads XLSX (SheetJS) and has the normalizer muscle from the snippet cleaning. Idea:
  one product per row (SKU + title), with a normalizer stripping *purchasing
  artefacts* (supplier prefixes, bracketed codes, "NIEUW", pack quantities, casing).
  Crux = defining the artefact rules; needs a sample of raw purchasing titles.
- **`grouptool` integration** (consider). Separate tool for product groupings. Decide
  by what it emits: if groupings feed the Shopify push (collections / Paragon
  associations) fold it into the pipeline; if not, just link it from the index.
- **Material block** — **built and fully translated (all 6 locales).** `material`
  block type + `MATERIALS` (148 entries, `name/ess/bel` as `{NL,EN,DE,FR,IT,ES}`
  objects) + `MAT_TERMS` (correspondence-token dictionary, translated at render via
  `matTransValue`) + `renderMaterials`/`buildMaterialRow` (multi-select, search,
  collapsible category checklist, drag-reorder, Full/Short/Correspondences
  checkboxes). Canonical multi-select (no free-text fallback — the 148-entry
  searchable list replaced that need). Output: one `<p>` per material,
  `<strong>Name</strong> | text`. Source content: `esoteric_materials_beliefs.xlsx`.
  *Not added to any `PRODUCT_TYPES` template yet* — it's a hand-added palette item;
  consider defaulting it onto gemstone/mala/chakra types. Re-translation/edits: the
  `/tmp/tr_*.py` + `/tmp/merge_mats.py` pipeline pattern (English source +
  per-id `{lang:{name,ess,bel}}` overrides → splice the const) is the clean way to
  revise a batch.
- 3 commercial entries (Selenite / Gemstone trees / Salt lamps) keep real `<ol>/<ul>`
  lists rather than inline `<br>` — left as lists pending the user's call.
- Pre-existing saved blocks don't retroactively pick up format changes (e.g. the
  disclaimer italics) until re-picked or a base-language toggle; fresh builds are fine.
- Optgroup grouping for the 48-item type dropdown (by category) if it feels long.
- Larger translation batches: chunking story for `/translate` noted but untested at scale.
- **V2 = independent AI writing tool** (next, left to Claude's judgement). Reuses this
  whole skeleton (block model, canonical-injection layer, segment round-trip, embedded
  pipeline). Start from this doc + `copy-suite-v2.html`.

## How to run / verify

Static files — open `copy-suite-v2.html` directly or via `python3 -m
http.server`. Build a product or two, Export for translation, run the file
through `/translate`, Import, then Finalize. For headless checks of pure logic,
use the Node `vm` pattern described above.
