---
name: translate
description: Fill in translations for a Phoenix Import Copy Suite translation file. Use when the user has exported a per-segment translation CSV (e.g. phoenix-translate.csv) from the Copy Suite / Copy Block Builder and wants every [[TR]] blank filled with localized copy (NL/EN/DE/FR/IT/ES), preserving HTML and the `--` title delimiter, producing a filled CSV ready to re-import. Trigger on requests like "translate this export", "fill the translation file", "/translate".
---

# /translate — Copy Suite translation filler

Fill every `[[TR]]` cell in a Copy Suite translation file with the correct
localized text, then verify none remain. The `[[TR]]` sentinel makes the job
deterministic: the run is only done when zero `[[TR]]` cells are left.

## The file

A CSV exported from the Copy Suite ("Export for translation"). Columns:

```
SKU, BLOCK_ID, SEGMENT, NL, EN, DE, FR, IT, ES
```

- One row per translatable segment, plus a `(title)` row per product
  (`BLOCK_ID = title`).
- Exactly one language column is the **base** — fully filled, the source text.
- The other language columns contain either an existing translation or the
  sentinel `[[TR]]`, meaning "translate me".
- Disclaimer / REACH segments are **not** in this file — they are canonical and
  injected per language by the Copy Suite, so you never translate them here.

## Procedure

### 1. Locate the file
Use the path the user gave. Otherwise find the newest `*translate*.csv` in the
working directory. If it is an `.xlsx`, ask the user to re-export as CSV (these
scripts use CSV). Confirm the file has the columns above.

### 2. Extract the blanks
Run the bundled extractor (it lives in this skill's directory):

```
python3 extract_cells.py <translation.csv>
```

It prints the detected **base language** and the number of cells to fill, and
writes `/tmp/translate_cells.json`:

```json
{ "base": "NL", "langs": ["NL","EN","DE","FR","IT","ES"], "count": 42,
  "cells": [ { "id": "3|EN", "lang": "EN", "block_id": "id_ab12", "segment": "Evocative description", "source": "<p>…base text…</p>" }, … ] }
```

Read that JSON.

### 3. Translate every cell
For each entry in `cells`, translate `source` (written in `base`) into `lang`,
following the rules below. Build a map `{ id: translated_text }` and write it to
`/tmp/translate_done.json` (valid JSON, UTF-8). Every `id` from the extract MUST
appear exactly once.

### 4. Apply
```
python3 apply_translations.py <translation.csv>
```
It writes `<translation>-filled.csv` (all cells quoted, same shape) and prints
the count of remaining `[[TR]]`. It exits non-zero if any remain.

### 5. Verify & report
The job is done only when `remaining [[TR]]: 0`. If any remain, translate the
missing ids and re-apply. Then tell the user the filled file path and a short
per-language count, and remind them to **Import translations** back into the
Copy Suite.

## Translation rules

- **Context:** Phoenix Import is a wholesale spiritual / wellness / lifestyle
  brand (incense, singing bowls, gemstones, candles, yoga, essential oils, …).
  Tone = clear, evocative e-commerce product copy. Localize naturally; do not
  translate word-for-word.
- **Languages:** NL Dutch, EN English, DE German, FR French, IT Italian,
  ES Spanish.
- **Preserve all HTML exactly.** Only translate human-readable text. Keep every
  tag and attribute: `<p>`, `<br>`, `<ul>`/`<li>`, `<strong>`, `<em>`,
  `<h2>`/`<h3>`, etc. For links, translate the link text but keep
  `href="…"` unchanged. Keep HTML entities (`&amp;`, `&lt;`, …) intact.
- **Titles** (`BLOCK_ID = title`) are plain text and may contain ` -- ` which
  splits the display title from the handle/SEO spec. Keep the ` -- ` delimiter
  and translate both sides; never add or remove it.
- **Do not translate** brand names, product-line names, or established proper
  nouns (e.g. *Nag Champa*, *Palo Santo*, *Aromafume*, *Song of India*). Keep
  SKUs, numbers, dimensions and units as-is.
- Preserve leading punctuation/symbols (e.g. a leading `*`).
- If a `source` is empty, output an empty string (never `[[TR]]`).
- Output the localized text only — no surrounding quotes (the script handles CSV
  quoting).

## Notes
- Idempotent: cells that already hold a translation (not `[[TR]]`) are left
  untouched, so re-running only fills new blanks.
- For large files, still produce one complete `/tmp/translate_done.json`; the
  apply step's `[[TR]]` count is the source of truth for completion.
