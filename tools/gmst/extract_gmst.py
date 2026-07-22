# -*- coding: utf-8 -*-
"""Collect every string game setting (GMST) the modlist defines.

GMSTs are the game's own UI vocabulary: button captions, skill and attribute names,
loading hints, tooltips, the "you must equip..." style messages. They live in the ESM
records, not in OpenMW's l10n yaml, so they have to be translated here.

Only settings with a STRV (string value) subrecord are collected; the f* and i*
numeric settings are left alone.

Writes gmst_en.json  { "sSetting": "English text" } - last definition in load order
wins, which is what the game itself will use.
Also writes gmst_sources.json { "sSetting": ["plugin", ...] } for reference.

Usage: py extract_gmst.py
"""
import json
import os
import struct
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..')))
import paths

MODROOT = paths.MOD_ROOT
dirs, contents = paths.read_modlist()
resolved = paths.resolve_plugins(dirs)


def subrecords(body):
    sp = 0
    while sp + 8 <= len(body):
        st = body[sp:sp + 4]
        ssize = struct.unpack('<I', body[sp + 4:sp + 8])[0]
        yield st, body[sp + 8:sp + 8 + ssize]
        sp += 8 + ssize


values, sources = {}, {}
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
        if rtype == b'GMST':
            gid = text = None
            for st, sd in subrecords(raw[pos + 16:pos + 16 + size]):
                if st == b'NAME':
                    gid = sd.split(b'\0')[0].decode('cp1251', 'replace')
                elif st == b'STRV':
                    text = sd.split(b'\0')[0].decode('cp1251', 'replace')
            if gid and text is not None:
                values[gid] = text
                sources.setdefault(gid, []).append(c)
        pos += 16 + size

json.dump({k: values[k] for k in sorted(values)},
          open(os.path.join(HERE, 'gmst_en.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
json.dump({k: sources[k] for k in sorted(sources)},
          open(os.path.join(HERE, 'gmst_sources.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

chars = sum(len(v) for v in values.values())
multi = sum(1 for v in sources.values() if len(v) > 1)
print('string GMSTs        : %d' % len(values))
print('total characters    : %d' % chars)
print('defined by >1 plugin: %d' % multi)
