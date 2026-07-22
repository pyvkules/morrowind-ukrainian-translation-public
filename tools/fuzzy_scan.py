# -*- coding: utf-8 -*-
"""Measure how much of the remaining mod dialogue is a near-variant of base-game text.

Mods (Patch for Purists, voice mods, Django's Dialogue...) mostly *edit* vanilla lines:
fix a typo, change punctuation, add a clause. If a mod line is close enough to a line we
already translated, its translation can be reused instead of translating from scratch.

Stages, cheapest first:
  1. exact            - byte-identical to a base EN line (already handled by patch_plugins)
  2. normalised       - identical after case/space/punctuation folding
  3. fuzzy >= CUTOFF  - difflib ratio against same-length-bucket candidates

Usage: py fuzzy_scan.py [cutoff]     (default 0.90)
"""
import json
import os
import re
import struct
import sys
import io
import difflib
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TOOLS = os.path.dirname(os.path.abspath(__file__))
CFG = r'E:\Morrowind\OpenMW\just-good-morrowind-plus\openmw.cfg'
CUTOFF = float(sys.argv[1]) if len(sys.argv) > 1 else 0.90

corp = json.load(open(os.path.join(TOOLS, 'corpus.json'), encoding='utf-8'))
base_en = {e['text'] for e in corp if e.get('text')}


def norm(s):
    s = s.lower().replace('\r\n', ' ')
    s = re.sub(r"[^\w\s]", '', s, flags=re.UNICODE)
    return re.sub(r'\s+', ' ', s).strip()


base_norm = defaultdict(list)
for t in base_en:
    base_norm[norm(t)].append(t)

buckets = defaultdict(list)
for t in base_en:
    buckets[len(t) // 40].append(t)


def infos(path):
    d = open(path, 'rb').read()
    out, i, L = [], 0, len(d)
    while i + 16 <= L:
        tag = d[i:i + 4]
        sz = struct.unpack_from('<I', d, i + 4)[0]
        if sz > L:
            break
        if tag == b'INFO':
            body = d[i + 16:i + 16 + sz]
            j = 0
            while j + 8 <= len(body):
                st = body[j:j + 4]
                ss = struct.unpack_from('<I', body, j + 4)[0]
                if st == b'NAME':
                    try:
                        out.append(body[j + 8:j + 8 + ss].rstrip(b'\0').decode('cp1251'))
                    except Exception:
                        pass
                j += 8 + ss
        i += 16 + sz
    return out


dirs, contents = [], []
for line in open(CFG, encoding='utf-8', errors='replace'):
    line = line.strip()
    if line.startswith('data='):
        dirs.append(line[5:].strip('"'))
    elif line.startswith('content='):
        contents.append(line[8:])
resolved = {}
for d in dirs:
    try:
        for e in os.listdir(d):
            resolved[e.lower()] = os.path.join(d, e)
    except OSError:
        pass

mod_new = set()
for c in contents:
    if c.lower() == 'morrowind.esm':
        continue
    p = resolved.get(c.lower())
    if not p or not os.path.isfile(p):
        continue
    try:
        for t in infos(p):
            if t and t not in base_en:
                mod_new.add(t)
    except Exception:
        pass

print('genuinely new mod lines:', len(mod_new))

stage2 = [t for t in mod_new if norm(t) in base_norm]
rest = [t for t in mod_new if norm(t) not in base_norm]
print('stage 2 - identical after normalising : %d' % len(stage2))

matched = 0
examples = []
for t in rest:
    cands = buckets.get(len(t) // 40, []) + buckets.get(len(t) // 40 - 1, []) + buckets.get(len(t) // 40 + 1, [])
    if not cands:
        continue
    best = difflib.get_close_matches(t, cands, n=1, cutoff=CUTOFF)
    if best:
        matched += 1
        if len(examples) < 3:
            examples.append((t, best[0]))

print('stage 3 - fuzzy >= %.2f                : %d' % (CUTOFF, matched))
print()
print('REUSABLE  : %d  (%.0f%% of new lines)' % (len(stage2) + matched,
      100.0 * (len(stage2) + matched) / max(1, len(mod_new))))
print('still new : %d' % (len(mod_new) - len(stage2) - matched))
for a, b in examples:
    print('\n  MOD : %s' % a[:150])
    print('  BASE: %s' % b[:150])
