# -*- coding: utf-8 -*-
"""Write the Ukrainian GMST strings into every plugin that defines them.

A GMST can be redefined by any plugin loaded later, so translating only
Morrowind.esm is not enough - the last definition in load order is the one the game
uses. Every plugin that carries a translated setting gets its STRV rewritten and a
copy written to the mod root, where the VFS shadows the original.

Reads each plugin from the mod root if a copy already lives there, so this composes
with patch_plugins.py and topics/rename_topics.py; run it after them.

Usage: py patch_gmst.py [--apply]
"""
import json
import os
import re
import struct
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..')))
import paths

MODROOT = paths.MOD_ROOT
APPLY = '--apply' in sys.argv

uk = json.load(open(os.path.join(HERE, 'uk_gmst.json'), encoding='utf-8'))
uk.pop('_comment', None)
ours = len(uk)

# 821 налаштувань переклав ще давній ukrajinizator; absorb_base.py витяг їх із
# base.esm сюди, щоб той 80-мегабайтний файл більше не був потрібен для збірки.
legacy_path = os.path.join(HERE, '..', 'legacy', 'gmst.json')
legacy = {}
if os.path.isfile(legacy_path):
    legacy = json.load(open(legacy_path, encoding='utf-8'))
    for k, v in legacy.items():
        uk.setdefault(k, v)          # наш власний переклад має пріоритет
print('translated GMSTs: %d (%d наших + %d давніх)' % (len(uk), ours, len(uk) - ours))

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
        if rtype == b'GMST':
            subs = list(subrecords(body))
            gid = None
            for st, sd in subs:
                if st == b'NAME':
                    gid = sd.split(b'\0')[0].decode('cp1251', 'replace')
            new = uk.get(gid)
            if new is not None:
                for i, (st, sd) in enumerate(subs):
                    if st != b'STRV':
                        continue
                    z = sd.endswith(b'\0')
                    try:
                        b = new.encode('cp1251')
                    except UnicodeEncodeError as e:
                        stats['warn'] += 1
                        print('  WARN cp1251:', gid, repr(new[:60]), e)
                        b = new.encode('cp1251', 'replace')
                    subs[i] = (st, b + b'\0' if z else b)
                    stats['written'] += 1
                    stats['ids'].add(gid)
                body = b''.join(st + struct.pack('<I', len(sd)) + sd for st, sd in subs)
                size = len(body)
        out += rtype + struct.pack('<I', size) + header_rest + body
        pos += 16 + struct.unpack('<I', data[pos + 4:pos + 8])[0]
    return bytes(out)


total = {'written': 0, 'warn': 0, 'ids': set()}
touched = []
for c in contents:
    local = os.path.join(MODROOT, c)
    path = local if os.path.isfile(local) else resolved.get(c.lower())
    if not path or not os.path.isfile(path):
        continue
    raw = open(path, 'rb').read()
    if b'GMST' not in raw:
        continue
    before = total['written']
    new = process(raw, total)
    if total['written'] > before:
        touched.append((total['written'] - before, c))
        if APPLY:
            with open(os.path.join(MODROOT, os.path.basename(path)), 'wb') as f:
                f.write(new)

touched.sort(reverse=True)
print()
for cnt, c in touched:
    print('%-52s %5d' % (c[:52], cnt))
print()
print('plugins changed  : %d' % len(touched))
print('STRV rewrites    : %d' % total['written'])
print('distinct settings: %d / %d' % (len(total['ids']), len(uk)))
missing = sorted(set(uk) - total['ids'])
if missing:
    print('never found in any plugin: %d' % len(missing))
    for m in missing[:20]:
        print('   -', m)
print('encode warnings  : %d' % total['warn'])
print('mode             : %s' % ('APPLIED' if APPLY else 'DRY RUN (use --apply)'))
