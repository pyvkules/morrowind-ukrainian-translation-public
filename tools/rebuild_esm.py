# -*- coding: utf-8 -*-
"""Rebuild Morrowind.esm with Ukrainian INFO texts.
Reads tools/base.esm + all tools/src/*.json + tools/uk/*.json pairs,
maps English text -> Ukrainian by slice index, writes ../Morrowind.esm.
Usage: py rebuild_esm.py
"""
import json
import os
import struct
import sys
import io
import glob

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import paths

OUT = os.path.join(TOOLS, '..', 'Morrowind.esm')


def find_base():
    """Звідки брати вихідний Morrowind.esm.

    Історично це був tools/base.esm - Morrowind.esm із давнім перекладом на 11%.
    absorb_base.py переніс той переклад у tools/legacy/*.json, тож тепер вистачає
    звичайного файлу зі Steam, і 80-мегабайтний base.esm у репозиторії не потрібен.
    """
    local = os.path.join(TOOLS, 'base.esm')
    if os.path.isfile(local):
        return local, 'tools/base.esm'
    dirs, _ = paths.read_modlist()
    for d in dirs:
        p = os.path.join(d, 'Morrowind.esm')
        if os.path.abspath(d) != paths.MOD_ROOT and os.path.isfile(p):
            return p, 'модліст'
    raise SystemExit('не знайдено вихідний Morrowind.esm ані в tools/, ані в модлисті')


BASE, base_kind = find_base()

# --- load translation memory: exact EN text -> UK text ---
memory = {}
for src_path in glob.glob(os.path.join(TOOLS, 'src', '*.json')):
    name = os.path.splitext(os.path.basename(src_path))[0]
    uk_paths = sorted(glob.glob(os.path.join(TOOLS, 'uk', name + '.json'))
                      + glob.glob(os.path.join(TOOLS, 'uk', name + '_p*.json')))
    if not uk_paths:
        continue
    src = json.load(open(src_path, encoding='utf-8'))
    for uk_path in uk_paths:
        uk = json.load(open(uk_path, encoding='utf-8'))
        for idx_str, translation in uk.items():
            idx = int(idx_str)
            if 0 <= idx < len(src) and translation and translation != src[idx]:
                memory[src[idx]] = translation
ours = len(memory)

# репліки, які переклав ще ukrajinizator - забрані з base.esm у tools/legacy/
legacy_info = os.path.join(TOOLS, 'legacy', 'info.json')
if os.path.isfile(legacy_info):
    for en, uk_text in json.load(open(legacy_info, encoding='utf-8')).items():
        memory.setdefault(en, uk_text)      # наш переклад має пріоритет

print('base: %s (%s)' % (os.path.basename(BASE), base_kind))
print('translation memory entries: %d (%d наших + %d давніх)'
      % (len(memory), ours, len(memory) - ours))

data = open(BASE, 'rb').read()
out = bytearray()
pos = 0
n = len(data)
replaced = 0
warn = 0

while pos + 16 <= n:
    rtype = data[pos:pos+4]
    size = struct.unpack('<I', data[pos+4:pos+8])[0]
    header_rest = data[pos+8:pos+16]
    body = data[pos+16:pos+16+size]

    if rtype == b'INFO':
        # rebuild body with possibly replaced NAME subrecord
        new_body = bytearray()
        sp = 0
        while sp + 8 <= len(body):
            st = body[sp:sp+4]
            ssize = struct.unpack('<I', body[sp+4:sp+8])[0]
            sdata = body[sp+8:sp+8+ssize]
            if st == b'NAME':
                had_null = sdata.endswith(b'\0')
                text = (sdata[:-1] if had_null else sdata).decode('cp1251', 'replace')
                if text in memory:
                    try:
                        enc = memory[text].encode('cp1251')
                    except UnicodeEncodeError as e:
                        warn += 1
                        print('WARN cp1251 fail:', repr(memory[text][:60]), e)
                        enc = memory[text].encode('cp1251', 'replace')
                    if had_null:
                        enc += b'\0'
                    sdata = enc
                    replaced += 1
            new_body += st + struct.pack('<I', len(sdata)) + sdata
            sp += 8 + ssize
        body = bytes(new_body)
        size = len(body)

    out += rtype + struct.pack('<I', size) + header_rest + body
    pos += 16 + struct.unpack('<I', data[pos+4:pos+8])[0]

with open(OUT, 'wb') as f:
    f.write(out)
print(f'INFO texts replaced: {replaced}, encode warnings: {warn}')
print(f'written: {OUT} ({len(out)} bytes)')
