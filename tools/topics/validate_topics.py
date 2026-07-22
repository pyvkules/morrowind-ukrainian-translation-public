# -*- coding: utf-8 -*-
"""Check that the topic rename left the modlist self-consistent.

Verifies, over the plugins the game will actually load (mod-root copy wins):
  * every AddTopic argument resolves to a DIAL topic that exists;
  * every phrase in morrowind.top points at a topic id that exists;
  * reports topic ids still written in Latin script (i.e. missed by the rename).

Dangling AddTopic calls exist in vanilla too, so the number that matters is whether
it grew. Run with --baseline to measure the ORIGINAL plugins instead of ours.

Usage: py validate_topics.py [--baseline]
"""
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
BASELINE = '--baseline' in sys.argv

ADDTOPIC = re.compile(r'\bAddTopic\b[ \t,]*("?)([^"\r\n;]*?)\1(?=[ \t]*(?:;|\r?$))',
                      re.IGNORECASE | re.MULTILINE)
LATIN = re.compile('[A-Za-z]')

dirs, contents = paths.read_modlist()
resolved = paths.resolve_plugins(dirs)


def subrecords(body):
    sp = 0
    while sp + 8 <= len(body):
        st = body[sp:sp + 4]
        ssize = struct.unpack('<I', body[sp + 4:sp + 8])[0]
        yield st, body[sp + 8:sp + 8 + ssize]
        sp += 8 + ssize


topics = {}          # lowercased id -> display id
dup_sources = {}     # lowercased id -> number of DIAL records
calls = {}           # lowercased arg -> (arg, count)

for c in contents:
    local = os.path.join(MODROOT, c)
    path = resolved.get(c.lower()) if BASELINE else (local if os.path.isfile(local)
                                                     else resolved.get(c.lower()))
    if not path or not os.path.isfile(path):
        continue
    raw = open(path, 'rb').read()
    pos, n = 0, len(raw)
    while pos + 16 <= n:
        rtype = raw[pos:pos + 4]
        size = struct.unpack('<I', raw[pos + 4:pos + 8])[0]
        body = raw[pos + 16:pos + 16 + size]
        if rtype == b'DIAL':
            name = typ = None
            for st, sd in subrecords(body):
                if st == b'NAME':
                    name = sd.split(b'\0')[0].decode('cp1251', 'replace')
                elif st == b'DATA' and sd:
                    typ = sd[0]
            if typ == 0 and name:
                topics.setdefault(name.lower(), name)
                dup_sources[name.lower()] = dup_sources.get(name.lower(), 0) + 1
        elif rtype in (b'INFO', b'SCPT'):
            tag = b'BNAM' if rtype == b'INFO' else b'SCTX'
            for st, sd in subrecords(body):
                if st != tag:
                    continue
                text = sd.split(b'\0')[0].decode('cp1251', 'replace')
                for m in ADDTOPIC.finditer(text):
                    a = m.group(2).strip()
                    if a:
                        k = a.lower()
                        calls[k] = (a, calls.get(k, (a, 0))[1] + 1)
        pos += 16 + size

dangling = sorted(k for k in calls if k not in topics)
latin_ids = sorted(v for k, v in topics.items() if LATIN.search(v))

print('mode                     : %s' % ('BASELINE (original plugins)' if BASELINE
                                         else 'CURRENT (mod-root copies win)'))
print('distinct topic ids       : %d' % len(topics))
print('distinct AddTopic args   : %d' % len(calls))
print('dangling AddTopic args   : %d' % len(dangling))
for k in dangling[:30]:
    print('   ? %-40s x%d' % (calls[k][0][:40], calls[k][1]))
print('topic ids still in Latin : %d' % len(latin_ids))
for v in latin_ids[:30]:
    print('   -', v)

TOP = os.path.join(MODROOT, 'morrowind.top')
if not BASELINE and os.path.exists(TOP):
    bad = miss = total = 0
    for line in open(TOP, 'rb').read().split(b'\r\n'):
        if not line:
            continue
        total += 1
        parts = line.split(b'\t')
        if len(parts) != 2:
            bad += 1
            continue
        if parts[1].decode('cp1251', 'replace').lower() not in topics:
            miss += 1
            if miss <= 10:
                print('   .top -> unknown topic:', line.decode('cp1251', 'replace'))
    print('morrowind.top lines      : %d (malformed %d, unknown topic %d)'
          % (total, bad, miss))
