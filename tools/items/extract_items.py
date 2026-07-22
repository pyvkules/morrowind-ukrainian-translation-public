# -*- coding: utf-8 -*-
"""Collect the display name (FNAM) of every named record in the modlist.

One file per category so batches stay reviewable, plus a combined index. Names that
are already Ukrainian are recorded separately - they must never be re-translated.

Writes items/<category>.json  { "English name": occurrences }
and   items/_summary.json     per-category counts.

Usage: py extract_items.py
"""
import json
import os
import re
import struct
import sys
import io
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..')))
import paths

MODROOT = paths.MOD_ROOT

CATEGORIES = {
    b'ARMO': 'armour', b'WEAP': 'weapon', b'CLOT': 'clothing', b'MISC': 'misc',
    b'BOOK': 'book_title', b'INGR': 'ingredient', b'ALCH': 'potion',
    b'APPA': 'apparatus', b'LOCK': 'lockpick', b'PROB': 'probe',
    b'REPA': 'repair', b'LIGH': 'light', b'CONT': 'container', b'DOOR': 'door',
    b'ACTI': 'activator', b'NPC_': 'npc', b'CREA': 'creature', b'SPEL': 'spell',
    b'CLAS': 'class', b'FACT': 'faction', b'RACE': 'race', b'BSGN': 'birthsign',
    b'REGN': 'region',
}
CYR = re.compile('[А-Яа-яЄІЇҐєіїґ]')

dirs, contents = paths.read_modlist()
resolved = paths.resolve_plugins(dirs)

names = {v: Counter() for v in CATEGORIES.values()}
names['cell'] = Counter()

for c in contents:
    local = os.path.join(MODROOT, c)
    path = local if os.path.isfile(local) else resolved.get(c.lower())
    if not path or not os.path.isfile(path):
        continue
    raw = open(path, 'rb').read()
    pos, n = 0, len(raw)
    while pos + 16 <= n:
        rtype = raw[pos:pos + 4]
        size = struct.unpack('<I', raw[pos + 4:pos + 8])[0]
        cat = CATEGORIES.get(rtype)
        if cat or rtype == b'CELL':
            body = raw[pos + 16:pos + 16 + size]
            want = b'NAME' if rtype == b'CELL' else b'FNAM'
            sp = 0
            while sp + 8 <= len(body):
                st = body[sp:sp + 4]
                ssize = struct.unpack('<I', body[sp + 4:sp + 8])[0]
                if st == want:
                    txt = body[sp + 8:sp + 8 + ssize].split(b'\0')[0]
                    txt = txt.decode('cp1251', 'replace').strip()
                    if txt:
                        names[cat or 'cell'][txt] += 1
                    break
                sp += 8 + ssize
        pos += 16 + size

summary = []
for cat, counter in sorted(names.items()):
    done = {k: v for k, v in counter.items() if CYR.search(k)}
    todo = {k: v for k, v in counter.items() if not CYR.search(k)}
    json.dump({k: todo[k] for k in sorted(todo)},
              open(os.path.join(HERE, cat + '.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    summary.append((len(todo), cat, len(done), sum(len(k) for k in todo)))

summary.sort(reverse=True)
json.dump([{'category': c, 'todo': t, 'already_uk': d, 'chars': ch}
           for t, c, d, ch in summary],
          open(os.path.join(HERE, '_summary.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

print('%-14s %8s %10s %8s' % ('CATEGORY', 'todo', 'already uk', 'chars'))
for t, c, d, ch in summary:
    print('%-14s %8d %10d %8d' % (c, t, d, ch))
print('%-14s %8d %10d %8d' % ('TOTAL', sum(s[0] for s in summary),
                              sum(s[2] for s in summary), sum(s[3] for s in summary)))
