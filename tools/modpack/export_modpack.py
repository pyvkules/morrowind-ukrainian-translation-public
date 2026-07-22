# -*- coding: utf-8 -*-
"""Capture the working profile as a portable modpack definition.

A modpack is a recipe, not a pile of files: which mods, in which order, with which
settings. This exports exactly that from a machine where the pack already works, so
install_modpack.py can rebuild the same profile anywhere. The mods themselves are
never copied - they are fetched from their own sources at install time.

Every absolute path is rewritten to a token so the definition is machine independent:

    {morrowind}   the Steam (or GOG, or retail) Morrowind installation
    {openmw}      the OpenMW engine directory
    {mods}        where the mod collections are unpacked
    {modpack}     this repository, which must stay LAST so it shadows everything

Writes modpack/modlist.json and copies the profile's own settings files.

Usage: py export_modpack.py [--cfg <openmw.cfg>]
"""
import json
import os
import re
import shutil
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..')))
import paths

OUT = os.path.join(paths.MOD_ROOT, 'modpack')
PROFILE_FILES = ['settings.cfg', 'shaders.yaml', 'lightconfig.toml', 'input_v3.xml']

cfg_path = paths.openmw_cfg()
profile_dir = os.path.dirname(cfg_path)

lines = []
for raw in open(cfg_path, encoding='utf-8', errors='replace'):
    raw = raw.rstrip('\r\n')
    if raw.strip():
        lines.append(raw)

data_dirs = [l[5:].strip('"') for l in lines if l.startswith('data=')]

# --- work out the tokens from the paths actually present ---
morrowind = next((d for d in data_dirs if d.lower().endswith('data files')), None)
openmw_dir = os.path.abspath(os.path.join(paths.MOD_ROOT, '..', '..'))


def collection_root(d):
    """The directory that holds a whole mod collection, e.g. E:\\Morrowind."""
    parts = os.path.normpath(d).split(os.sep)
    return os.sep.join(parts[:2]) + os.sep if len(parts) > 2 else None


counts = {}
for d in data_dirs:
    r = collection_root(d)
    if r and (not morrowind or not d.lower().startswith(morrowind.lower())):
        counts[r] = counts.get(r, 0) + 1
mods_root = max(counts, key=counts.get) if counts else None

TOKENS = [(paths.MOD_ROOT, '{modpack}'),
          (openmw_dir, '{openmw}'),
          (morrowind, '{morrowind}'),
          (mods_root, '{mods}')]
TOKENS = [(os.path.normpath(p).rstrip(os.sep), t) for p, t in TOKENS if p]
TOKENS.sort(key=lambda pt: -len(pt[0]))


def tokenize(p):
    np = os.path.normpath(p)
    for root, tok in TOKENS:
        if np.lower() == root.lower():
            return tok
        if np.lower().startswith(root.lower() + os.sep):
            return tok + '/' + np[len(root) + 1:].replace(os.sep, '/')
    return np.replace(os.sep, '/')


# --- collections: which mod bundles this pack is built out of ---
collections = {}
for d in data_dirs:
    t = tokenize(d)
    if t.startswith('{mods}/'):
        name = t.split('/')[1]
        collections[name] = collections.get(name, 0) + 1

entries = []
for l in lines:
    if '=' not in l:
        continue
    key, val = l.split('=', 1)
    if key == 'data':
        entries.append({'k': 'data', 'v': tokenize(val.strip('"'))})
    else:
        entries.append({'k': key, 'v': val})

os.makedirs(OUT, exist_ok=True)
modlist = {
    'name': 'Morrowind Ukrainian Modpack',
    'based_on': sorted(collections, key=lambda k: -collections[k]),
    'collection_dirs': {k: collections[k] for k in sorted(collections,
                                                          key=lambda k: -collections[k])},
    'tokens': {
        '{morrowind}': 'Morrowind installation (Steam/GOG/retail), the folder holding "Data Files"',
        '{openmw}': 'OpenMW engine directory',
        '{mods}': 'where the mod collections are unpacked',
        '{modpack}': 'this repository - must be the LAST data entry',
    },
    'counts': {
        'data': sum(1 for e in entries if e['k'] == 'data'),
        'content': sum(1 for e in entries if e['k'] == 'content'),
        'fallback': sum(1 for e in entries if e['k'] == 'fallback'),
        'groundcover': sum(1 for e in entries if e['k'] == 'groundcover'),
    },
    'entries': entries,
}
json.dump(modlist, open(os.path.join(OUT, 'modlist.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

copied = []
pdir = os.path.join(OUT, 'profile')
os.makedirs(pdir, exist_ok=True)
for f in PROFILE_FILES:
    s = os.path.join(profile_dir, f)
    if os.path.isfile(s):
        shutil.copy2(s, os.path.join(pdir, f))
        copied.append(f)

last = [e['v'] for e in entries if e['k'] == 'data'][-1]
print('profile        : %s' % profile_dir)
print('data entries   : %d' % modlist['counts']['data'])
print('content entries: %d' % modlist['counts']['content'])
print('fallback       : %d' % modlist['counts']['fallback'])
print('collections    : %s' % ', '.join('%s (%d)' % (k, v)
                                        for k, v in modlist['collection_dirs'].items()))
print('profile files  : %s' % ', '.join(copied))
print('last data entry: %s %s' % (last, '(correct)' if last == '{modpack}'
                                  else '<-- MUST be {modpack}'))
