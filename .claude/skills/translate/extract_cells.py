#!/usr/bin/env python3
"""Copy Suite translation — extractor.

Reads a Copy Suite translation CSV, detects the base-language column (the one
with no [[TR]] sentinels), and writes every cell still needing translation to a
JSON file for the agent to fill.

Usage:  python3 extract_cells.py <translation.csv> [out.json]
Default out: /tmp/translate_cells.json
"""
import csv, json, sys

LANGS = ['NL', 'EN', 'DE', 'FR', 'IT', 'ES']


def is_tr(v):
    return str(v).strip().startswith('[[TR')


def main():
    if len(sys.argv) < 2:
        sys.exit('usage: extract_cells.py <translation.csv> [out.json]')
    path = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else '/tmp/translate_cells.json'

    with open(path, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit('No data rows in ' + path)

    cols = list(rows[0].keys())
    present = [L for L in LANGS if L in cols]
    if not present:
        sys.exit('No language columns (NL/EN/DE/FR/IT/ES) found. Is this a Copy Suite translation file?')

    # Base language = the column that is filled (no [[TR]]) in every row.
    base = None
    for L in present:
        if all((not is_tr(r.get(L, '')) and str(r.get(L, '')).strip()) for r in rows):
            base = L
            break
    if base is None:  # fallback: fewest sentinels
        base = min(present, key=lambda L: sum(is_tr(r.get(L, '')) for r in rows))

    cells = []
    for i, r in enumerate(rows):
        src = r.get(base, '')
        for L in present:
            if L == base:
                continue
            if is_tr(r.get(L, '')):
                cells.append({
                    'id': f'{i}|{L}',
                    'lang': L,
                    'block_id': r.get('BLOCK_ID', ''),
                    'segment': r.get('SEGMENT', ''),
                    'source': src,
                })

    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'file': path, 'base': base, 'langs': present,
                   'count': len(cells), 'cells': cells}, f, ensure_ascii=False, indent=2)

    print(f'base language : {base}')
    print(f'target langs  : {", ".join(L for L in present if L != base)}')
    print(f'cells to fill : {len(cells)}')
    print(f'wrote         : {out}')


if __name__ == '__main__':
    main()
