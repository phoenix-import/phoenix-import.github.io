---
name: translate
description: Fill in translations for Phoenix Import Copy Suite copy, conversationally. Use when the user pastes (or uploads) a Copy Suite "translation JSON" — items with a base-language `source` and target-language fields marked [[TR]] — and wants every [[TR]] filled with localized copy (EN/DE/FR/IT/ES, or whichever targets), preserving HTML and the `--` title delimiter. Return the completed JSON for them to paste back into Copy Suite via "Import translations". Trigger on "/translate", "translate this export", "fill the translation JSON".
---

# /translate — Copy Suite translation (works in plain chat)

The user works in a normal chat, with no shell or files: they click **Copy JSON**
in Copy Suite, paste that JSON to you, you fill every `[[TR]]`, and you return the
completed JSON in a code block. They paste it back via **Import translations**.

Do everything inline — do **not** write scripts or expect files on disk.

## Input — the translation JSON
```json
{
  "base": "NL",
  "targets": ["EN", "DE", "FR", "IT", "ES"],
  "count": 2,
  "items": [
    { "sku": "123", "id": "title", "segment": "(title)",
      "source": "Klankschaal -- 10cm Messing",
      "EN": "[[TR]]", "DE": "[[TR]]", "FR": "[[TR]]", "IT": "[[TR]]", "ES": "[[TR]]" },
    { "sku": "123", "id": "id_ab12", "segment": "Evocative description",
      "source": "<p>Een prachtige, met de hand gehamerde schaal.</p>",
      "EN": "[[TR]]", "DE": "[[TR]]", "FR": "[[TR]]", "IT": "[[TR]]", "ES": "[[TR]]" }
  ]
}
```
- `source` is the text in the `base` language.
- Each target-language field holds either a finished translation or `[[TR]]` = translate me.
- Disclaimers / REACH are **not** present — Copy Suite injects those canonically, so
  they are never translated here.

## What to do
1. For each item, for each `target` field whose value is `[[TR]]`, replace it with
   the translation of `source` into that language. Leave any field that already has
   a translation untouched (idempotent).
2. Return the **complete JSON object** — same shape, same keys, same order — inside a
   single ```json code block, so the user can copy it straight back.
3. **Self-check before sending: there must be no `[[TR]]` anywhere in your output.**
   That is the done signal. If you cannot fit the whole batch in one reply, fill as
   many items as you can, return that partial JSON, say which `sku`s still contain
   `[[TR]]`, and continue in the next message.

## Translation rules
- **Context:** Phoenix Import is a wholesale spiritual / wellness / lifestyle brand
  (incense, singing bowls, gemstones, candles, yoga, essential oils, …). Write
  natural, evocative e-commerce product copy — localize, don't translate word-for-word.
- **Languages:** EN English, DE German, FR French, IT Italian, ES Spanish. The base
  is usually NL Dutch (sometimes EN).
- **Preserve all HTML exactly.** Only translate human-readable text. Keep every tag
  and attribute: `<p>`, `<br>`, `<ul>`/`<li>`, `<strong>`/`<em>`, `<h2>`/`<h3>`. For
  links, translate the visible text but keep `href="…"` unchanged. Keep HTML entities
  (`&amp;`, `&lt;`, …) intact.
- **Titles** (`"id": "title"`) may contain ` -- ` separating the display title from
  the handle/SEO spec. Keep the ` -- ` and translate both sides; never add or remove it.
- **Do not translate** brand names, product-line names, or established proper nouns
  (*Nag Champa*, *Palo Santo*, *Aromafume*, *Song of India*, …). Keep SKUs, numbers,
  dimensions and units as-is.
- Preserve leading punctuation/symbols (e.g. a leading `*`).
- If a `source` is empty, return an empty string (never `[[TR]]`).

## Capacity
~30 products per batch is comfortable in one paste and one reply. For larger sets,
work in chunks; the "no `[[TR]]` left" check is the completion signal each time.

## If given a CSV/XLSX instead
The user may paste CSV rows (columns `SKU, BLOCK_ID, SEGMENT, NL, EN, DE, FR, IT, ES`).
The same rules apply — fill each `[[TR]]` cell from the base column and return the
completed CSV. JSON is preferred; it round-trips most reliably.
