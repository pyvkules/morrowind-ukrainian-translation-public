# -*- coding: utf-8 -*-
"""Перекласти показувані назви записів у всіх плагінах.

Назви предметів, істот, персонажів, чарів і комірок лежать у підзаписі FNAM (а в
комірок - у NAME). Як і з GMST, будь-який пізніший плагін може перевизначити той
самий предмет і повернути англійську, тому заміна йде по всьому модлисту, а не
лише в Morrowind.esm.

Джерела перекладу, у порядку пріоритету:
    tools/items/uk_*.json    наш переклад     {англійська назва: українська}
    tools/legacy/name.json   давній переклад  (186 назв із base.esm)
    tools/legacy/cell.json   давній переклад  (5 комірок)

Комірки чіпаємо обережно: NAME у CELL - це водночас ідентифікатор, на який
посилаються скрипти й двері. Тому за замовчуванням комірки НЕ перейменовуються;
щоб увімкнути, потрібен явний --cells.

    py patch_names.py [--apply] [--cells]
"""
import glob
import io
import json
import os
import struct
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import paths

MODROOT = paths.MOD_ROOT
APPLY = '--apply' in sys.argv
CELLS = '--cells' in sys.argv

FNAM_TYPES = {b'ARMO', b'WEAP', b'CLOT', b'MISC', b'INGR', b'ALCH', b'NPC_',
              b'CREA', b'SPEL', b'CONT', b'DOOR', b'ACTI', b'LIGH', b'APPA',
              b'LOCK', b'PROB', b'REPA', b'CLAS', b'FACT', b'RACE', b'BSGN',
              b'REGN', b'BOOK'}

names = {}
for p in sorted(glob.glob(os.path.join(TOOLS, 'items', 'uk_*.json'))):
    names.update(json.load(open(p, encoding='utf-8')))
ours = len(names)
legacy = os.path.join(TOOLS, 'legacy', 'name.json')
if os.path.isfile(legacy):
    for k, v in json.load(open(legacy, encoding='utf-8')).items():
        names.setdefault(k, v)

cells = {}
legacy_cell = os.path.join(TOOLS, 'legacy', 'cell.json')
if CELLS and os.path.isfile(legacy_cell):
    cells = json.load(open(legacy_cell, encoding='utf-8'))

print('назв: %d (%d наших + %d давніх), комірок: %d'
      % (len(names), ours, len(names) - ours, len(cells)))

dirs, contents = paths.read_modlist()
resolved = paths.resolve_plugins(dirs)


def subrecords(body):
    sp = 0
    while sp + 8 <= len(body):
        st = body[sp:sp + 4]
        ssize = struct.unpack('<I', body[sp + 4:sp + 8])[0]
        yield st, body[sp + 8:sp + 8 + ssize]
        sp += 8 + ssize


def process(data, stats):
    out = bytearray()
    pos, n = 0, len(data)
    while pos + 16 <= n:
        rtype = data[pos:pos + 4]
        size = struct.unpack('<I', data[pos + 4:pos + 8])[0]
        header_rest = data[pos + 8:pos + 16]
        body = data[pos + 16:pos + 16 + size]

        table, tag = (None, None)
        if rtype in FNAM_TYPES:
            table, tag = names, b'FNAM'
        elif rtype == b'CELL' and cells:
            table, tag = cells, b'NAME'

        if table:
            subs = list(subrecords(body))
            dirty = False
            for i, (st, sd) in enumerate(subs):
                if st != tag:
                    continue
                z = sd.endswith(b'\0')
                cur = (sd[:-1] if z else sd).decode('cp1251', 'replace')
                new = table.get(cur)
                if new:
                    try:
                        b = new.encode('cp1251')
                    except UnicodeEncodeError as e:
                        stats['warn'] += 1
                        print('  WARN cp1251:', repr(new[:50]), e)
                        b = new.encode('cp1251', 'replace')
                    subs[i] = (st, b + b'\0' if z else b)
                    dirty = True
                    stats['written'] += 1
                break                      # лише перший FNAM/NAME запису
            if dirty:
                body = b''.join(s + struct.pack('<I', len(d)) + d for s, d in subs)
                size = len(body)

        out += rtype + struct.pack('<I', size) + header_rest + body
        pos += 16 + struct.unpack('<I', data[pos + 4:pos + 8])[0]
    return bytes(out)


total = {'written': 0, 'warn': 0}
touched = []
for c in contents:
    local = os.path.join(MODROOT, c)
    path = local if os.path.isfile(local) else resolved.get(c.lower())
    if not path or not os.path.isfile(path):
        continue
    raw = open(path, 'rb').read()
    before = total['written']
    new = process(raw, total)
    if total['written'] > before:
        touched.append((total['written'] - before, c))
        if APPLY:
            with open(os.path.join(MODROOT, os.path.basename(path)), 'wb') as f:
                f.write(new)

touched.sort(reverse=True)
for cnt, c in touched[:15]:
    print('%-52s %5d' % (c[:52], cnt))
if len(touched) > 15:
    print('... ще %d плагінів' % (len(touched) - 15))
print()
print('плагінів змінено : %d' % len(touched))
print('назв переписано  : %d' % total['written'])
print('помилок кодування: %d' % total['warn'])
print('режим            : %s' % ('APPLIED' if APPLY else 'DRY RUN (--apply)'))
