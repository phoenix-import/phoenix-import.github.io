"""
clean_base.py — Step 1 of the translation pipeline.

Part A: Clear any pre-existing values in 'Translated content'.
Part B: Delete non-spec rows from the base file.

Non-spec categories (deleted):
  json_dict              — Any JSON dict (app config, plugin data, rich text, block refs)
                           Product spec metafields use arrays or primitives, never dicts.
  json_array_en_category — JSON arrays containing English category tag phrases
                           (e.g. ["Candles and candle holders","Organic products"])
  json_array_channel     — JSON arrays whose elements are all sales-channel / audience words
                           (Shop, Webshop, Wholesale, Yoga studio, Yoga, Meditation centre)
  plain_shopify_gid      — Shopify global ID references (gid://shopify/...)
  plain_seo_title        — Contains SEO keywords (groothandel, bestel online, online bestellen,
                           b2b, phoenix import, leverancier) or ` | ` separator pattern
  plain_long_text        — Plain text longer than 100 chars
  plain_language_tag     — Language availability codes like NL/EN/DE/IT/FR/ES
  plain_sku              — Product identifier codes like 01647831L

Usage:
  python translations/clean_base.py
"""

import json
import re
import shutil
from pathlib import Path

import openpyxl

BASE_FILE = Path("translations/Mani_Bhadra_BV_-_Phoenix_Import_translations_Apr-13-2026.xlsx")
BACKUP_FILE = Path("translations/Mani_Bhadra_BV_-_Phoenix_Import_translations_Apr-13-2026_ORIGINAL.xlsx")

SEO_KEYWORDS = ["groothandel", "bestel online", "online bestellen", "b2b", "phoenix import", "leverancier", " | "]

# English words that appear in category tag metafields but never in Dutch product specs.
EN_CATEGORY_INDICATORS = [
    " and ", " or ", " with ", " for ", " of ", " the ",
    "products", "lifestyle", "holders", "gemstones", "jewelry",
    "organic", "candles", "statues", "stationery", "incense", "singing",
]

# Sales-channel / audience classification values — these are grouping tags, not product specs.
# A JSON array is deleted only when ALL its elements (lowercased) are in this set.
CHANNEL_WORDS = {"shop", "webshop", "wholesale", "yoga studio", "yoga", "meditation centre"}

RE_LANGUAGE_TAG = re.compile(r"^[A-Z]{2}(/[A-Z]{2})+$")
RE_SKU = re.compile(r"^[A-Z]{0,3}\d{5,}[A-Z]{0,2}$")
RE_SHOPIFY_GID = re.compile(r"^gid://shopify/")


def classify(value: str) -> str:
    """Return the delete-category for this value, or '' if the row should be kept."""
    v = value.strip()
    if not v:
        return ""  # blank default content — keep (edge case)

    # Try JSON first
    try:
        parsed = json.loads(v)
        if isinstance(parsed, dict):
            # All JSON dicts are app/plugin config, rich text, or block refs — never product specs.
            # Product spec metafields use arrays (json_array) or primitives (json_numeric).
            return "json_dict"
        if isinstance(parsed, list):
            v_lower = v.lower()
            if any(kw in v_lower for kw in EN_CATEGORY_INDICATORS):
                return "json_array_en_category"
            # Channel/audience tags: all elements must be known channel words
            if all(isinstance(el, str) and el.lower() in CHANNEL_WORDS for el in parsed):
                return "json_array_channel"
        # Lists and numbers: keep (specs)
        return ""
    except (json.JSONDecodeError, ValueError):
        pass

    # Plain text checks
    if RE_SHOPIFY_GID.match(v):
        return "plain_shopify_gid"

    v_lower = v.lower()
    for kw in SEO_KEYWORDS:
        if kw in v_lower:
            return "plain_seo_title"

    if len(v) > 100:
        return "plain_long_text"

    if RE_LANGUAGE_TAG.match(v):
        return "plain_language_tag"

    if RE_SKU.match(v):
        return "plain_sku"

    return ""  # keep


def main():
    if not BASE_FILE.exists():
        print(f"ERROR: Base file not found: {BASE_FILE}")
        return

    # --- Backup ---
    if BACKUP_FILE.exists():
        print(f"Backup already exists, skipping: {BACKUP_FILE}")
    else:
        shutil.copy2(BASE_FILE, BACKUP_FILE)
        print(f"Backup created: {BACKUP_FILE}")

    print(f"\nLoading: {BASE_FILE}")
    wb = openpyxl.load_workbook(BASE_FILE)
    ws = wb.active

    # --- Identify column indices (1-based) ---
    header = {cell.value: cell.column for cell in ws[1]}
    required = {"Default content", "Translated content"}
    missing = required - set(header)
    if missing:
        print(f"ERROR: Missing columns: {missing}")
        return

    col_default = header["Default content"]
    col_translated = header["Translated content"]

    total_rows = ws.max_row - 1  # exclude header
    print(f"Rows (excluding header): {total_rows}")

    # --- Part A: Clear pre-existing translations ---
    cleared = 0
    for row in ws.iter_rows(min_row=2):
        cell = row[col_translated - 1]
        if cell.value not in (None, ""):
            cell.value = None
            cleared += 1
    print(f"\nPart A — Pre-existing translations cleared: {cleared}")

    # --- Part B: Classify and delete non-spec rows ---
    counts = {}
    rows_to_delete = []  # collect row numbers to delete (descending order)

    for row in ws.iter_rows(min_row=2):
        default_cell = row[col_default - 1]
        value = str(default_cell.value) if default_cell.value is not None else ""
        category = classify(value)
        if category:
            counts[category] = counts.get(category, 0) + 1
            rows_to_delete.append(row[0].row)

    # Delete from bottom up to preserve row numbers
    rows_to_delete.sort(reverse=True)
    for row_num in rows_to_delete:
        ws.delete_rows(row_num)

    deleted_total = len(rows_to_delete)
    remaining = total_rows - deleted_total

    print(f"\nPart B — Rows deleted by category:")
    for cat, n in sorted(counts.items()):
        print(f"  {cat:<28} {n:>6}")
    print(f"  {'TOTAL deleted':<28} {deleted_total:>6}")
    print(f"  {'Rows remaining':<28} {remaining:>6}")

    # --- Save in-place ---
    wb.save(BASE_FILE)
    print(f"\nSaved cleaned file: {BASE_FILE}")
    print("\n⏸  Please visually inspect the cleaned file before running translate_specs.py.")


if __name__ == "__main__":
    main()
