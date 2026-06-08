#!/usr/bin/env python3
"""Copy Suite translation — applier.

Applies the agent's translations (JSON map {id: text}) back into the CSV and
writes <input>-filled.csv, then reports any remaining [[TR]] sentinels so the
job can be verified as complete.

Usage:  python3 apply_translations.py <translation.csv> [done.json] [out.csv]
Defaults: done.json = /tmp/translate_done.json,  out = <input>-filled.csv
"""
import csv, json, os, sys

LANGS = ['NL', 'EN', 'DE', 'FR', 'IT', 'ES']


def is_tr(v):
    return str(v).strip().startswith('[[TR')


def main():
    if len(sys.argv) < 2:
        sys.exit('usage: apply_translations.py <translation.csv> [done.json] [out.csv]')
    path = sys.argv[1]
    done_path = sys.argv[2] if len(sys.argv) > 2 else '/tmp/translate_done.json'
    stem, _ = os.path.splitext(path)
    out = sys.argv[3] if len(sys.argv) > 3 else stem + '-filled.csv'

    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)
    with open(done_path, encoding='utf-8') as f:
        done = json.load(f)

    applied = 0
    for key, text in done.items():
        try:
            i_str, L = key.split('|', 1)
            i = int(i_str)
        except ValueError:
            continue
        if 0 <= i < len(rows) and L in rows[i]:
            rows[i][L] = text
            applied += 1

    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows)

    present = [L for L in LANGS if L in (fields or [])]
    remaining = [(i + 2, L) for i, r in enumerate(rows)
                 for L in present if is_tr(r.get(L, ''))]

    print(f'applied        : {applied} translation(s)')
    print(f'wrote          : {out}')
    print(f'remaining [[TR]]: {len(remaining)}')
    if remaining:
        sample = ', '.join(f'row{r} {L}' for r, L in remaining[:10])
        print(f'  still blank   : {sample}{" ..." if len(remaining) > 10 else ""}')
        sys.exit(1)  # non-zero so the agent knows the job is not done


if __name__ == '__main__':
    main()
