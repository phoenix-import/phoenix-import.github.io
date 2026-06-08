#!/usr/bin/env python3
"""Copy Suite translation I/O — read/write the translation file (CSV or XLSX)
with the Python standard library only (no openpyxl / pandas needed).

  python3 translate_io.py extract <infile> [cells.json]
      -> detects the base-language column, writes the cells needing translation.

  python3 translate_io.py apply <infile> [done.json] [outfile]
      -> applies translations ({id: text}) and writes <infile>-filled.<ext>,
         reporting any remaining [[TR]] (non-zero exit if any remain).

The agent translates between the two steps: read the cells JSON, write
/tmp/translate_done.json mapping each cell id to its translation.
"""
import csv, json, os, re, sys, zipfile
import xml.etree.ElementTree as ET

LANGS = ['NL', 'EN', 'DE', 'FR', 'IT', 'ES']
MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
RELS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG_RELS = 'http://schemas.openxmlformats.org/package/2006/relationships'


def is_tr(v):
    return str(v).strip().startswith('[[TR')


# ---------- column-letter helpers ----------
def col_to_idx(letters):
    n = 0
    for ch in letters:
        if ch.isalpha():
            n = n * 26 + (ord(ch.upper()) - 64)
    return n - 1

def idx_to_col(i):
    s = ''
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s

def xesc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# ---------- XLSX read ----------
def read_xlsx(path):
    z = zipfile.ZipFile(path)
    names = z.namelist()
    shared = []
    if 'xl/sharedStrings.xml' in names:
        root = ET.fromstring(z.read('xl/sharedStrings.xml'))
        for si in root.findall(f'{{{MAIN}}}si'):
            shared.append(''.join(t.text or '' for t in si.iter(f'{{{MAIN}}}t')))

    # first sheet target via workbook rels (fallback to sheet1.xml)
    sheet_path = 'xl/worksheets/sheet1.xml'
    try:
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        first = wb.find(f'{{{MAIN}}}sheets/{{{MAIN}}}sheet')
        rid = first.get(f'{{{RELS}}}id')
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        for rel in rels:
            if rel.get('Id') == rid:
                tgt = rel.get('Target')
                sheet_path = ('xl/' + tgt) if not tgt.startswith('/') else tgt.lstrip('/')
                break
    except Exception:
        pass
    if sheet_path not in names:
        sheet_path = next((n for n in names if n.startswith('xl/worksheets/')), sheet_path)

    root = ET.fromstring(z.read(sheet_path))
    grid = []
    maxcol = 0
    for row in root.iter(f'{{{MAIN}}}row'):
        cells = {}
        for c in row.findall(f'{{{MAIN}}}c'):
            ref = c.get('r') or ''
            col = col_to_idx(''.join(ch for ch in ref if ch.isalpha())) if ref else len(cells)
            t = c.get('t')
            v = c.find(f'{{{MAIN}}}v')
            istag = c.find(f'{{{MAIN}}}is')
            if t == 's' and v is not None:
                val = shared[int(v.text)]
            elif t == 'inlineStr' and istag is not None:
                val = ''.join(x.text or '' for x in istag.iter(f'{{{MAIN}}}t'))
            elif v is not None:
                val = v.text or ''
            else:
                val = ''
            cells[col] = val
            maxcol = max(maxcol, col)
        grid.append(cells)
    if not grid:
        return [], []
    header = [grid[0].get(i, '') for i in range(maxcol + 1)]
    rows = []
    for cells in grid[1:]:
        rows.append({header[i]: cells.get(i, '') for i in range(maxcol + 1) if header[i] != ''})
    return [h for h in header if h != ''], rows


# ---------- XLSX write (inline strings) ----------
def write_xlsx(path, header, rows):
    def cell(coli, rowi, val):
        return (f'<c r="{idx_to_col(coli)}{rowi}" t="inlineStr">'
                f'<is><t xml:space="preserve">{xesc(val)}</t></is></c>')
    out_rows = [header] + [[r.get(h, '') for h in header] for r in rows]
    body = []
    for ri, row in enumerate(out_rows, start=1):
        cells = ''.join(cell(ci, ri, v) for ci, v in enumerate(row))
        body.append(f'<row r="{ri}">{cells}</row>')
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             f'<worksheet xmlns="{MAIN}"><sheetData>' + ''.join(body) + '</sheetData></worksheet>')
    parts = {
        '[Content_Types].xml':
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>',
        '_rels/.rels':
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{PKG_RELS}">'
            f'<Relationship Id="rId1" Type="{RELS}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml':
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<workbook xmlns="{MAIN}" xmlns:r="{RELS}">'
            '<sheets><sheet name="Translate" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels':
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{PKG_RELS}">'
            f'<Relationship Id="rId1" Type="{RELS}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml': sheet,
    }
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data)


# ---------- format dispatch ----------
def read_table(path):
    if path.lower().endswith(('.xlsx', '.xls')):
        return read_xlsx(path)
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)

def write_table(path, header, rows):
    if path.lower().endswith(('.xlsx', '.xls')):
        write_xlsx(path, header, rows)
    else:
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=header, quoting=csv.QUOTE_ALL)
            w.writeheader()
            w.writerows(rows)


# ---------- subcommands ----------
def extract(infile, out='/tmp/translate_cells.json'):
    header, rows = read_table(infile)
    if not rows:
        sys.exit('No data rows in ' + infile)
    present = [L for L in LANGS if L in header]
    if not present:
        sys.exit('No language columns found — is this a Copy Suite translation file?')
    base = next((L for L in present
                 if all(not is_tr(r.get(L, '')) and str(r.get(L, '')).strip() for r in rows)), None)
    if base is None:
        base = min(present, key=lambda L: sum(is_tr(r.get(L, '')) for r in rows))
    cells = []
    for i, r in enumerate(rows):
        for L in present:
            if L != base and is_tr(r.get(L, '')):
                cells.append({'id': f'{i}|{L}', 'lang': L, 'block_id': r.get('BLOCK_ID', ''),
                              'segment': r.get('SEGMENT', ''), 'source': r.get(base, '')})
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'file': infile, 'base': base, 'langs': present,
                   'count': len(cells), 'cells': cells}, f, ensure_ascii=False, indent=2)
    print(f'format        : {"xlsx" if infile.lower().endswith((".xlsx",".xls")) else "csv"}')
    print(f'base language : {base}')
    print(f'targets       : {", ".join(L for L in present if L != base)}')
    print(f'cells to fill : {len(cells)}')
    print(f'wrote         : {out}')


def apply(infile, done='/tmp/translate_done.json', out=None):
    stem, ext = os.path.splitext(infile)
    # Always write CSV back: Copy Suite imports CSV reliably regardless of the
    # uploaded format, and CSV writing is dependency-free and lossless.
    out = out or (stem + '-filled.csv')
    header, rows = read_table(infile)
    with open(done, encoding='utf-8') as f:
        done_map = json.load(f)
    applied = 0
    for key, text in done_map.items():
        try:
            i_str, L = key.split('|', 1)
            i = int(i_str)
        except ValueError:
            continue
        if 0 <= i < len(rows) and L in header:
            rows[i][L] = text
            applied += 1
    write_table(out, header, rows)
    present = [L for L in LANGS if L in header]
    remaining = [(i + 2, L) for i, r in enumerate(rows) for L in present if is_tr(r.get(L, ''))]
    print(f'applied        : {applied} translation(s)')
    print(f'wrote          : {out}')
    print(f'remaining [[TR]]: {len(remaining)}')
    if remaining:
        print('  still blank   : ' + ', '.join(f'row{r} {L}' for r, L in remaining[:10])
              + (' ...' if len(remaining) > 10 else ''))
        sys.exit(1)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == 'extract':
        extract(sys.argv[2], *(sys.argv[3:4] or []))
    elif cmd == 'apply':
        apply(sys.argv[2], *(sys.argv[3:5] or []))
    else:
        sys.exit('unknown command: ' + cmd)


if __name__ == '__main__':
    main()
