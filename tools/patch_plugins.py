# -*- coding: utf-8 -*-
"""Apply the existing Ukrainian translation memory to the OTHER modlist plugins.

Many plugins (Tribunal.esm, Bloodmoon.esm, Patch for Purists.esm, voice mods...)
load AFTER Morrowind.esm and re-supply the SAME English INFO text, which overrides
our translated Morrowind.esm. This script rewrites those INFO NAME subrecords using
the translation memory built from tools/src + tools/uk, and writes patched copies
into the mod root so the VFS (our data dir is last) shadows the originals.

No new translation is produced - only text we already translated is transferred.

Usage: py patch_plugins.py [--apply]
       without --apply it only reports what would change (dry run).
"""
import json
import os
import struct
import sys
import io
import glob
import shutil

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

TOOLS = paths.TOOLS
MODROOT = paths.MOD_ROOT
APPLY = '--apply' in sys.argv

# never touch these: Morrowind.esm has its own pipeline (rebuild_esm.py)
SKIP = {'morrowind.esm'}

# --- translation memory: exact EN text -> UK text (same logic as rebuild_esm.py) ---
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
print('translation memory entries:', len(memory))

# --- resolve modlist: data dirs (later wins) + content order ---
dirs, contents = paths.read_modlist()
resolved = paths.resolve_plugins(dirs)   # our own output is skipped, so re-runs are idempotent


def patch(data):
    """Return (new_bytes, replaced, warnings) rewriting INFO NAME text."""
    out = bytearray()
    pos, n = 0, len(data)
    replaced = warn = 0
    while pos + 16 <= n:
        rtype = data[pos:pos + 4]
        size = struct.unpack('<I', data[pos + 4:pos + 8])[0]
        header_rest = data[pos + 8:pos + 16]
        body = data[pos + 16:pos + 16 + size]
        if rtype == b'INFO':
            new_body = bytearray()
            sp = 0
            while sp + 8 <= len(body):
                st = body[sp:sp + 4]
                ssize = struct.unpack('<I', body[sp + 4:sp + 8])[0]
                sdata = body[sp + 8:sp + 8 + ssize]
                if st == b'NAME':
                    had_null = sdata.endswith(b'\0')
                    text = (sdata[:-1] if had_null else sdata).decode('cp1251', 'replace')
                    if text in memory:
                        try:
                            enc = memory[text].encode('cp1251')
                        except UnicodeEncodeError as e:
                            warn += 1
                            print('  WARN cp1251:', repr(memory[text][:60]), e)
                            enc = memory[text].encode('cp1251', 'replace')
                        sdata = enc + b'\0' if had_null else enc
                        replaced += 1
                new_body += st + struct.pack('<I', len(sdata)) + sdata
                sp += 8 + ssize
            body = bytes(new_body)
            size = len(body)
        out += rtype + struct.pack('<I', size) + header_rest + body
        pos += 16 + struct.unpack('<I', data[pos + 4:pos + 8])[0]
    return bytes(out), replaced, warn


total_rep = total_warn = 0
touched = []
for c in contents:
    if c.lower() in SKIP:
        continue
    src = resolved.get(c.lower())
    if not src or not os.path.isfile(src):
        continue
    try:
        raw = open(src, 'rb').read()
    except OSError:
        continue
    if b'INFO' not in raw:
        continue
    new, rep, warn = patch(raw)
    if rep:
        total_rep += rep
        total_warn += warn
        touched.append((rep, c))
        if APPLY:
            dst = os.path.join(MODROOT, os.path.basename(src))
            with open(dst, 'wb') as f:
                f.write(new)

touched.sort(reverse=True)
print()
print('%-50s %s' % ('PLUGIN', 'lines restored'))
for rep, c in touched:
    print('%-50s %6d' % (c[:50], rep))
print()
print('plugins patched : %d' % len(touched))
print('lines restored  : %d' % total_rep)
print('encode warnings : %d' % total_warn)
print('mode            : %s' % ('APPLIED (written to mod root)' if APPLY else 'DRY RUN (use --apply)'))
