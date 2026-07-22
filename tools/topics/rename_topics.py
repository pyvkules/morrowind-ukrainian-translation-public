# -*- coding: utf-8 -*-
"""Rename every dialogue TOPIC to its Ukrainian name across the whole modlist.

OpenMW shows the DIAL record's own id in the topic pane, so a topic can only appear
in Ukrainian if the record is renamed. The id is also what scripts pass to AddTopic,
so the same rename has to be applied to script source at the same time:

  * DIAL  (DATA[0] == 0, i.e. type Topic) -> NAME rewritten
  * INFO  BNAM  (result script source)    -> AddTopic arguments rewritten
  * SCPT  SCTX  (script source)           -> AddTopic arguments rewritten

Compiled bytecode (SCDT) is deliberately left alone: OpenMW recompiles from SCTX and
ignores Bethesda's compiled data, which is what makes the rename safe.

Journal (type 4), Greeting, Voice and Persuasion records are never touched.

Reads each plugin from the mod root if a patched copy already lives there (so this
composes with patch_plugins.py), otherwise from its original data dir; always writes
to the mod root, where the VFS shadows the original.

Usage: py rename_topics.py [--apply]
"""
import json
import glob
import os
import re
import struct
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace',
                              write_through=True)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..')))
import paths

MODROOT = paths.MOD_ROOT
APPLY = '--apply' in sys.argv

# --- topic map: english topic id (lowercased) -> ukrainian topic id ---
src = json.load(open(os.path.join(HERE, 'dial_topics.json'), encoding='utf-8'))
uk = {}
for p in sorted(glob.glob(os.path.join(HERE, 'uk_dial_topics*.json'))):
    for k, v in json.load(open(p, encoding='utf-8')).items():
        uk[int(k)] = v

rename = {}
for i, name in enumerate(src):
    t = uk.get(i)
    if t and t != name:
        rename[name.lower()] = t

# 19 topics were already renamed to Ukrainian by the earlier 11% ukrajinizator, so
# dial_topics.json only knows their Ukrainian id and their English AddTopic calls
# would be left dangling. topics_glossary.json still records the English name.
# A handful of topics were renamed to Ukrainian by the earlier 11% ukrajinizator, so
# no DIAL record carries their English name any more and dial_topics.json never saw
# it - but scripts still call AddTopic with the English id. Map those too.
legacy = json.load(open(os.path.join(HERE, 'legacy_en_ids.json'), encoding='utf-8'))
extra = 0
for phrase, topic in legacy.items():
    if phrase.lower() not in rename:
        rename[phrase.lower()] = topic
        extra += 1
print('topic renames loaded: %d (+%d legacy)' % (len(rename), extra))

# --- modlist ---
dirs, contents = paths.read_modlist()
resolved = paths.resolve_plugins(dirs)

# script source uses CRLF, so the end-of-argument lookahead has to tolerate the \r -
# without it only the last line of a multi-line script ever matched.
ADDTOPIC = re.compile(r'(\bAddTopic\b[ \t,]*)("?)([^"\r\n;]*?)(\2)(?=[ \t]*(?:;|\r?$))',
                      re.IGNORECASE | re.MULTILINE)

unknown = {}


def fix_script(text):
    """Rewrite AddTopic arguments in script source. Returns (new_text, count)."""
    n = [0]

    def sub(m):
        head, q, arg, q2 = m.group(1), m.group(2), m.group(3), m.group(4)
        target = rename.get(arg.strip().lower())
        if target is None:
            if arg.strip():
                unknown[arg.strip()] = unknown.get(arg.strip(), 0) + 1
            return m.group(0)
        n[0] += 1
        return head + '"' + target + '"'

    return ADDTOPIC.sub(sub, text), n[0]


def subrecords(body):
    sp = 0
    while sp + 8 <= len(body):
        st = body[sp:sp + 4]
        ssize = struct.unpack('<I', body[sp + 4:sp + 8])[0]
        yield st, body[sp + 8:sp + 8 + ssize]
        sp += 8 + ssize


def rebuild(subs):
    out = bytearray()
    for st, sd in subs:
        out += st + struct.pack('<I', len(sd)) + sd
    return bytes(out)


def enc(s, stats):
    try:
        return s.encode('cp1251')
    except UnicodeEncodeError as e:
        stats['warn'] += 1
        print('  WARN cp1251:', repr(s[:60]), e)
        return s.encode('cp1251', 'replace')


def process(data, stats):
    out = bytearray()
    pos, n = 0, len(data)
    while pos + 16 <= n:
        rtype = data[pos:pos + 4]
        size = struct.unpack('<I', data[pos + 4:pos + 8])[0]
        header_rest = data[pos + 8:pos + 16]
        body = data[pos + 16:pos + 16 + size]

        if rtype in (b'DIAL', b'INFO', b'SCPT'):
            subs = list(subrecords(body))
            dirty = False

            if rtype == b'DIAL':
                is_topic = any(st == b'DATA' and sd and sd[0] == 0 for st, sd in subs)
                if is_topic:
                    for i, (st, sd) in enumerate(subs):
                        if st != b'NAME':
                            continue
                        z = sd.endswith(b'\0')
                        cur = (sd[:-1] if z else sd).decode('cp1251', 'replace')
                        stats['topics'] += 1
                        new = rename.get(cur.lower())
                        if new:
                            b = enc(new, stats)
                            subs[i] = (st, b + b'\0' if z else b)
                            dirty = True
                            stats['renamed'] += 1
                        else:
                            stats['untouched_topics'].add(cur)
            else:
                tag = b'BNAM' if rtype == b'INFO' else b'SCTX'
                for i, (st, sd) in enumerate(subs):
                    if st != tag:
                        continue
                    z = sd.endswith(b'\0')
                    text = (sd[:-1] if z else sd).decode('cp1251', 'replace')
                    new_text, cnt = fix_script(text)
                    if cnt:
                        b = enc(new_text, stats)
                        subs[i] = (st, b + b'\0' if z else b)
                        dirty = True
                        stats['addtopic'] += cnt

            if dirty:
                body = rebuild(subs)
                size = len(body)

        out += rtype + struct.pack('<I', size) + header_rest + body
        pos += 16 + struct.unpack('<I', data[pos + 4:pos + 8])[0]
    return bytes(out)


total = {'topics': 0, 'renamed': 0, 'addtopic': 0, 'warn': 0, 'untouched_topics': set()}
touched = []
for c in contents:
    local = os.path.join(MODROOT, c)
    path = local if os.path.isfile(local) else resolved.get(c.lower())
    if not path or not os.path.isfile(path):
        continue
    raw = open(path, 'rb').read()
    if b'DIAL' not in raw and b'SCPT' not in raw:
        continue
    before = dict(total)
    before_set = len(total['untouched_topics'])
    new = process(raw, total)
    ren = total['renamed'] - before['renamed']
    add = total['addtopic'] - before['addtopic']
    if ren or add:
        touched.append((ren + add, ren, add, c))
        if APPLY:
            with open(os.path.join(MODROOT, os.path.basename(path)), 'wb') as f:
                f.write(new)

touched.sort(reverse=True)
print()
print('%-46s %8s %9s' % ('PLUGIN', 'topics', 'AddTopic'))
for _, ren, add, c in touched[:30]:
    print('%-46s %8d %9d' % (c[:46], ren, add))
if len(touched) > 30:
    print('... and %d more' % (len(touched) - 30))

print()
print('plugins changed        : %d' % len(touched))
print('DIAL topics seen       : %d' % total['topics'])
print('DIAL topics renamed    : %d' % total['renamed'])
print('AddTopic args rewritten: %d' % total['addtopic'])
print('encode warnings        : %d' % total['warn'])
print('topic ids with no translation: %d' % len(total['untouched_topics']))
for t in sorted(total['untouched_topics'])[:25]:
    print('   -', t)
if unknown:
    print('AddTopic args with no matching topic: %d' % len(unknown))
    for k, v in sorted(unknown.items(), key=lambda kv: -kv[1])[:15]:
        print('   ? %-40s x%d' % (k[:40], v))
print('mode                   : %s' % ('APPLIED' if APPLY else 'DRY RUN (use --apply)'))
