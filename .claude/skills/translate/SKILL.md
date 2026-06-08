---
name: translate
description: Translate a Phoenix Import Copy Suite export file. Use when the user drops a CSV or XLSX translation file into the chat (exported from the Copy Suite via "Export for translation") and asks to translate it / fill it in / "/translate". Fills every [[TR]] cell with localized copy (NL/EN/DE/FR/IT/ES) — preserving HTML and the `--` title delimiter, leaving brand names and disclaimers untouched — and hands back the completed file to download and re-import.
---

# /translate — Copy Suite translation (file in → file back)

The user attaches a **CSV or XLSX** file exported from Copy Suite ("Export for
translation") and asks to translate it. You fill every `[[TR]]` cell and return
the completed file for them to download and re-import via "Import translations".

The work is split so file handling is bulletproof: two stdlib Python helpers do
the I/O (no openpyxl/pandas needed), and **you** do the translation in between.
The helpers live in this skill's directory next to this file.

## Procedure

1. **Find the file.** Use the file the user attached (its path is shown in the
   conversation, typically under the uploads directory). If unsure, list the
   newest `*.csv` / `*.xlsx` they referenced. CSV and XLSX are both supported.

2. **Extract the blanks:**
   ```
   python3 <skill-dir>/translate_io.py extract "<file>"
   ```
   It prints the detected base language + cell count and writes
   `/tmp/translate_cells.json`:
   ```json
   { "base":"NL", "langs":["NL","EN","DE","FR","IT","ES"], "count":42,
     "cells":[ {"id":"3|EN","lang":"EN","block_id":"id_ab12","segment":"Evocative description","source":"<p>…NL…</p>"}, … ] }
   ```
   Read that JSON.

3. **Translate.** For every cell, translate `source` (in `base`) into `lang`
   using the rules below. Write `/tmp/translate_done.json` as a flat map
   `{ "<id>": "<translated text>", … }` — every cell id, exactly once. Use the
   Write tool (valid JSON, UTF-8).

4. **Apply & verify:**
   ```
   python3 <skill-dir>/translate_io.py apply "<file>"
   ```
   It writes `<file>-filled.csv` and prints `remaining [[TR]]: N`, exiting
   non-zero if any remain. The job is done only at **0 remaining** — if not,
   translate the missing ids and re-apply.

5. **Hand back the file.** Surface `<file>-filled.csv` to the user with
   SendUserFile, and remind them to re-import it into Copy Suite ("Import
   translations"). (Output is CSV — Copy Suite imports it directly whether the
   upload was CSV or XLSX.)

## Translation rules
- **Context:** Phoenix Import — wholesale spiritual / wellness / lifestyle brand
  (incense, singing bowls, gemstones, candles, yoga, essential oils, …). Write
  natural, evocative e-commerce copy; localize, don't translate word-for-word.
- **Languages:** NL Dutch, EN English, DE German, FR French, IT Italian,
  ES Spanish. (Base is usually NL, sometimes EN.)
- **Preserve all HTML exactly.** Only translate visible text. Keep every tag and
  attribute: `<p>`, `<br>`, `<ul>`/`<li>`, `<strong>`/`<em>`, headings. For links
  translate the visible text only and keep `href` unchanged. Keep entities
  (`&amp;`, `&lt;`, …) intact.
- **Titles** (`block_id` = `title`) may contain ` -- ` separating the display
  title from the handle/SEO spec — keep the ` -- ` and translate both sides;
  never add or remove it.
- **Do not translate** brand / product-line names or established proper nouns
  (*Nag Champa*, *Palo Santo*, *Aromafume*, *Song of India*, …). Keep SKUs,
  numbers, dimensions and units as-is.
- Preserve leading punctuation/symbols (e.g. a leading `*`).
- Disclaimers (REACH, weight/size, natural, medical) are **not** in the file —
  Copy Suite injects those canonically per language. Don't worry about them.
- If a `source` is empty, output an empty string (never `[[TR]]`).

## Capacity
~30 products per batch is comfortable. For much larger files, translate in
chunks (write `/tmp/translate_done.json` incrementally and re-run `apply`); the
`remaining [[TR]]` count is the completion signal.
