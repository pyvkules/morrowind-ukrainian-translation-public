# -*- coding: utf-8 -*-
"""Rebuild the modpack profile on a machine from modpack/modlist.json.

Finds the Morrowind installation, the OpenMW engine and the unpacked mod collections,
substitutes them back into the recipe and writes a working openmw.cfg. Nothing is
downloaded and nothing of Bethesda's or the mod authors' is copied - this only wires
together what is already installed.

    py install_modpack.py                    # detect everything, report, change nothing
    py install_modpack.py --apply            # write the profile
    py install_modpack.py --morrowind <dir> --mods <dir> --openmw <dir> --profile <dir>

Anything not found is reported by name, so a missing collection is obvious rather
than showing up later as a crash on load.
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

RECIPE = os.path.join(paths.MOD_ROOT, 'modpack', 'modlist.json')
APPLY = '--apply' in sys.argv


def arg(flag):
    for i, a in enumerate(sys.argv):
        if a == flag and i + 1 < len(sys.argv):
            return os.path.abspath(sys.argv[i + 1])
    return None


# ---------------------------------------------------------------- detection
def steam_libraries():
    """Every Steam library folder, from the registry plus libraryfolders.vdf."""
    roots = []
    try:
        import winreg
        for hive, key in ((winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam'),
                          (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam')):
            try:
                with winreg.OpenKey(hive, key) as k:
                    for name in ('SteamPath', 'InstallPath'):
                        try:
                            roots.append(winreg.QueryValueEx(k, name)[0])
                        except OSError:
                            pass
            except OSError:
                pass
    except ImportError:
        pass

    libs = []
    for r in roots:
        r = os.path.normpath(r)
        libs.append(r)
        vdf = os.path.join(r, 'steamapps', 'libraryfolders.vdf')
        if os.path.isfile(vdf):
            try:
                text = open(vdf, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            libs += [p.replace('\\\\', '\\') for p in re.findall(r'"path"\s+"([^"]+)"', text)]
    seen, out = set(), []
    for l in libs:
        n = os.path.normpath(l)
        if n.lower() not in seen and os.path.isdir(n):
            seen.add(n.lower())
            out.append(n)
    return out


def find_morrowind():
    for lib in steam_libraries():
        d = os.path.join(lib, 'steamapps', 'common', 'Morrowind', 'Data Files')
        if os.path.isdir(d):
            return d
    for drive in 'CDEFGH':
        for p in (r'%s:\GOG Games\Morrowind\Data Files',
                  r'%s:\Program Files (x86)\Bethesda Softworks\Morrowind\Data Files'):
            d = p % drive
            if os.path.isdir(d):
                return d
    return None


def find_openmw():
    guess = os.path.abspath(os.path.join(paths.MOD_ROOT, '..', '..'))
    if os.path.isfile(os.path.join(guess, 'openmw.exe')):
        return guess
    for drive in 'CDEFGH':
        for p in (r'%s:\Program Files\OpenMW', r'%s:\Morrowind\OpenMW', r'%s:\OpenMW'):
            d = p % drive
            if os.path.isfile(os.path.join(d, 'openmw.exe')):
                return d
    return None


def find_mods(collections):
    """The directory that contains the named mod collections."""
    guess = os.path.abspath(os.path.join(paths.MOD_ROOT, '..', '..', '..'))
    candidates = [guess, os.path.dirname(guess)]
    for drive in 'CDEFGH':
        candidates.append(r'%s:\Morrowind' % drive)
    for c in candidates:
        if c and os.path.isdir(c) and all(os.path.isdir(os.path.join(c, n))
                                          for n in collections):
            return os.path.normpath(c)
    return None


# ---------------------------------------------------------------- main
recipe = json.load(open(RECIPE, encoding='utf-8'))
collections = recipe['based_on']

morrowind = arg('--morrowind') or find_morrowind()
openmw = arg('--openmw') or find_openmw()
mods = arg('--mods') or find_mods(collections)
profile = arg('--profile') or (os.path.join(openmw, 'ukrainian-modpack') if openmw else None)

print('%-12s %s' % ('Morrowind', morrowind or 'NOT FOUND'))
print('%-12s %s' % ('OpenMW', openmw or 'NOT FOUND'))
print('%-12s %s' % ('mods', mods or 'NOT FOUND'))
print('%-12s %s' % ('profile', profile or 'NOT FOUND'))
print('%-12s %s' % ('modpack', paths.MOD_ROOT))
print()

missing_roots = [n for n, v in (('Morrowind', morrowind), ('OpenMW', openmw),
                                ('mods', mods)) if not v]
if missing_roots:
    print('Cannot continue, not found: %s' % ', '.join(missing_roots))
    print('Pass them explicitly, e.g. --morrowind "D:\\...\\Morrowind\\Data Files"')
    raise SystemExit(1)

TOKENS = {'{morrowind}': morrowind, '{openmw}': openmw,
          '{mods}': mods, '{modpack}': paths.MOD_ROOT}


def resolve(v):
    for tok, real in TOKENS.items():
        if v == tok:
            return real
        if v.startswith(tok + '/'):
            return os.path.normpath(os.path.join(real, v[len(tok) + 1:].replace('/', os.sep)))
    return os.path.normpath(v)


out_lines, missing_dirs, resolved_dirs = [], [], []
for e in recipe['entries']:
    if e['k'] == 'data':
        d = resolve(e['v'])
        resolved_dirs.append(d)
        if not os.path.isdir(d):
            missing_dirs.append(d)
        out_lines.append('data="%s"' % d)
    else:
        out_lines.append('%s=%s' % (e['k'], e['v']))

available = set()
for d in resolved_dirs:
    try:
        for f in os.listdir(d):
            available.add(f.lower())
    except OSError:
        pass
missing_content = [e['v'] for e in recipe['entries']
                   if e['k'] == 'content' and e['v'].lower() not in available]

print('data dirs      : %d (%d missing)' % (len(resolved_dirs), len(missing_dirs)))
for d in missing_dirs[:15]:
    print('   missing dir : %s' % d)
if len(missing_dirs) > 15:
    print('   ... and %d more' % (len(missing_dirs) - 15))
print('content files  : %d (%d missing)'
      % (recipe['counts']['content'], len(missing_content)))
for c in missing_content[:15]:
    print('   missing file: %s' % c)
if len(missing_content) > 15:
    print('   ... and %d more' % (len(missing_content) - 15))

if APPLY:
    if missing_dirs or missing_content:
        print()
        print('Refusing to write a profile that is missing content - install the '
              'collections first: %s' % ', '.join(collections))
        raise SystemExit(1)
    os.makedirs(profile, exist_ok=True)
    cfg = os.path.join(profile, 'openmw.cfg')
    if os.path.isfile(cfg):
        shutil.copy2(cfg, cfg + '.bak')
        print('existing config backed up to %s.bak' % cfg)
    with open(cfg, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('\n'.join(out_lines) + '\n')
    src = os.path.join(paths.MOD_ROOT, 'modpack', 'profile')
    for name in os.listdir(src) if os.path.isdir(src) else []:
        dst = os.path.join(profile, name)
        if not os.path.exists(dst):
            shutil.copy2(os.path.join(src, name), dst)
    print()
    print('written: %s' % cfg)

print()
print('Steam launch options for Morrowind (Properties -> Launch Options):')
print('  "%s\\openmw.exe" --replace=config --config="%s" --user-data="%s" %%command%%'
      % (openmw, profile, profile))
print()
print('mode: %s' % ('APPLIED' if APPLY else 'DRY RUN (use --apply)'))
