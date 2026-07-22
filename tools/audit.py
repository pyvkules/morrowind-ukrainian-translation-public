# -*- coding: utf-8 -*-
"""Count every translatable string in the whole load order, by category.

Feeds PROGRESS.md so the plan is built on measured numbers instead of guesses.
Counts unique strings, because duplicates across plugins are translated once and
fanned out by the exact-text translation memory.

Usage: py audit.py
"""
import os
import re
import struct
import sys
import io
import json
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', write_through=True)

CFG = r'E:\Morrowind\OpenMW\just-good-morrowind-plus\openmw.cfg'
MODROOT = r'E:\Morrowind\OpenMW\mods\ukrainian-l10n'

# record type -> (subrecord holding the human-readable string, category label)
NAMED = {
    b'NPC_': (b'FNAM', 'NPC / creature names'),
    b'CREA': (b'FNAM', 'NPC / creature names'),
    b'CONT': (b'FNAM', 'containers'),
    b'DOOR': (b'FNAM', 'doors'),
    b'ACTI': (b'FNAM', 'activators'),
    b'MISC': (b'FNAM', 'misc items'),
    b'WEAP': (b'FNAM', 'weapons'),
    b'ARMO': (b'FNAM', 'armour'),
    b'CLOT': (b'FNAM', 'clothing'),
    b'ALCH': (b'FNAM', 'potions'),
    b'INGR': (b'FNAM', 'ingredients'),
    b'LIGH': (b'FNAM', 'lights'),
    b'APPA': (b'FNAM', 'alchemy apparatus'),
    b'LOCK': (b'FNAM', 'lockpicks'),
    b'PROB': (b'FNAM', 'probes'),
    b'REPA': (b'FNAM', 'repair tools'),
    b'BOOK': (b'FNAM', 'book titles'),
    b'SPEL': (b'FNAM', 'spell names'),
    b'FACT': (b'FNAM', 'factions'),
    b'CLAS': (b'FNAM', 'classes'),
    b'RACE': (b'FNAM', 'races'),
    b'BSGN': (b'FNAM', 'birthsigns'),
    b'REGN': (b'FNAM', 'regions'),
}

buckets = defaultdict(set)

dirs, contents = [], []
for line in open(CFG, encoding='utf-8', errors='replace'):
    line = line.strip()
    if line.startswith('data='):
        dirs.append(line[5:].strip('"'))
    elif line.startswith('content='):
        contents.append(line[8:])
resolved = {}
for d in dirs:
    if os.path.abspath(d) == os.path.abspath(MODROOT):
        continue                      # our own patched copies would double-count
    try:
        for e in os.listdir(d):
            resolved[e.lower()] = os.path.join(d, e)
    except OSError:
        pass


def dec(b):
    return b.rstrip(b'\0').decode('cp1251', 'replace').strip()


for c in contents:
    p = resolved.get(c.lower())
    if not p or not os.path.isfile(p):
        continue
    try:
        d = open(p, 'rb').read()
    except OSError:
        continue
    i, L = 0, len(d)
    while i + 16 <= L:
        rt = d[i:i + 4]
        sz = struct.unpack_from('<I', d, i + 4)[0]
        if sz > L:
            break
        body = d[i + 16:i + 16 + sz]
        j = 0
        subs = {}
        while j + 8 <= len(body):
            st = body[j:j + 4]
            ss = struct.unpack_from('<I', body, j + 4)[0]
            subs.setdefault(st, body[j + 8:j + 8 + ss])
            j += 8 + ss
        if rt == b'INFO' and b'NAME' in subs:
            t = dec(subs[b'NAME'])
            if t:
                buckets['dialogue lines (INFO)'].add(t)
        elif rt == b'BOOK':
            if b'TEXT' in subs:
                t = dec(subs[b'TEXT'])
                if t:
                    buckets['book texts'].add(t)
            if b'FNAM' in subs:
                t = dec(subs[b'FNAM'])
                if t:
                    buckets['book titles'].add(t)
        elif rt == b'DIAL':
            if b'DATA' in subs and subs[b'DATA'][:1] == b'\x00' and b'NAME' in subs:
                t = dec(subs[b'NAME'])
                if t:
                    buckets['dialogue topics (DIAL)'].add(t)
        elif rt == b'GMST':
            if b'STRV' in subs:
                t = dec(subs[b'STRV'])
                if t:
                    buckets['UI strings (GMST)'].add(t)
        elif rt == b'CELL':
            if b'NAME' in subs:
                t = dec(subs[b'NAME'])
                if t:
                    buckets['cell / place names'].add(t)
        elif rt in NAMED:
            sub, label = NAMED[rt]
            if sub in subs:
                t = dec(subs[sub])
                if t:
                    buckets[label].add(t)
        i += 16 + sz

rows = sorted(buckets.items(), key=lambda kv: -len(kv[1]))
print('%-28s %8s %12s' % ('CATEGORY', 'UNIQUE', 'CHARS'))
print('-' * 52)
tot_n = tot_c = 0
for k, v in rows:
    ch = sum(len(x) for x in v)
    tot_n += len(v)
    tot_c += ch
    print('%-28s %8d %12d' % (k, len(v), ch))
print('-' * 52)
print('%-28s %8d %12d' % ('TOTAL', tot_n, tot_c))

json.dump({k: len(v) for k, v in buckets.items()},
          open(os.path.join(MODROOT, 'tools', 'audit_counts.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
