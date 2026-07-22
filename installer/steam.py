# -*- coding: utf-8 -*-
"""Find Steam's Morrowind and set its launch options, so the normal Steam shortcut
starts the modpack.

Steam keeps per-user launch options in userdata/<id>/config/localconfig.vdf. Steam
rewrites that file from memory when it exits, so editing it while Steam is running
loses the change - every writer here refuses to touch it unless Steam is closed, and
always leaves a .bak next to the original.
"""
import os
import re
import shutil
import subprocess

MORROWIND_APPID = '22320'


def _reg_values():
    out = []
    try:
        import winreg
    except ImportError:
        return out
    for hive, key in ((winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam'),
                      (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam'),
                      (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Valve\Steam')):
        try:
            with winreg.OpenKey(hive, key) as k:
                for name in ('SteamPath', 'InstallPath'):
                    try:
                        out.append(winreg.QueryValueEx(k, name)[0])
                    except OSError:
                        pass
        except OSError:
            pass
    return out


def steam_root():
    for p in _reg_values():
        p = os.path.normpath(p)
        if os.path.isdir(p):
            return p
    for c in (r'C:\Program Files (x86)\Steam', r'C:\Program Files\Steam'):
        if os.path.isdir(c):
            return c
    return None


def libraries():
    """Every Steam library folder."""
    root = steam_root()
    libs = [root] if root else []
    if root:
        vdf = os.path.join(root, 'steamapps', 'libraryfolders.vdf')
        if os.path.isfile(vdf):
            text = open(vdf, encoding='utf-8', errors='replace').read()
            libs += [p.replace('\\\\', '\\') for p in re.findall(r'"path"\s+"([^"]+)"', text)]
    seen, out = set(), []
    for l in libs:
        n = os.path.normpath(l)
        if n.lower() not in seen and os.path.isdir(n):
            seen.add(n.lower())
            out.append(n)
    return out


def morrowind_data_files():
    """The 'Data Files' directory of the Steam Morrowind install, or None."""
    for lib in libraries():
        d = os.path.join(lib, 'steamapps', 'common', 'Morrowind', 'Data Files')
        if os.path.isdir(d):
            return d
    return None


def is_running():
    try:
        out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq steam.exe'],
                             capture_output=True, text=True, timeout=20)
        return 'steam.exe' in (out.stdout or '').lower()
    except (OSError, subprocess.SubprocessError):
        return False


def localconfigs():
    """Every user's localconfig.vdf."""
    root = steam_root()
    if not root:
        return []
    base = os.path.join(root, 'userdata')
    if not os.path.isdir(base):
        return []
    found = []
    for uid in os.listdir(base):
        p = os.path.join(base, uid, 'config', 'localconfig.vdf')
        if os.path.isfile(p):
            found.append(p)
    return found


def launch_options(openmw_dir, profile_dir):
    return ('"%s" --replace=config --config="%s" --user-data="%s" %%command%%'
            % (os.path.join(openmw_dir, 'openmw.exe'), profile_dir, profile_dir))


def _find_app_block(text, appid):
    """Return (start, end) of the app's block body, or None.

    localconfig.vdf is nested key/value text; the app entry looks like
        "22320"
        {
            ... possibly nested ...
        }
    so the closing brace has to be found by counting depth, not by regex.
    """
    m = re.search(r'"%s"\s*\r?\n?\s*\{' % re.escape(appid), text)
    if not m:
        return None
    depth, i = 1, m.end()
    while i < len(text) and depth:
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
        i += 1
    return (m.end(), i - 1) if depth == 0 else None


def set_launch_options(options, appid=MORROWIND_APPID, dry_run=True):
    """Write LaunchOptions for the app in every Steam user profile.

    Returns a list of (path, status) where status is 'set', 'unchanged',
    'no-app-entry' or an error string.
    """
    if is_running() and not dry_run:
        raise RuntimeError('Steam is running - close Steam first, it overwrites '
                           'localconfig.vdf from memory when it exits.')
    results = []
    for path in localconfigs():
        try:
            text = open(path, encoding='utf-8', errors='replace').read()
        except OSError as e:
            results.append((path, 'error: %s' % e))
            continue
        span = _find_app_block(text, appid)
        if not span:
            results.append((path, 'no-app-entry'))
            continue
        start, end = span
        body = text[start:end]
        existing = re.search(r'("LaunchOptions"\s*)"((?:[^"\\]|\\.)*)"', body)
        escaped = options.replace('\\', '\\\\').replace('"', '\\"')
        if existing:
            if existing.group(2) == escaped:
                results.append((path, 'unchanged'))
                continue
            new_body = body[:existing.start()] + '%s"%s"' % (existing.group(1), escaped) \
                + body[existing.end():]
        else:
            indent = '\t\t\t\t\t'
            new_body = body.rstrip() + '\n%s"LaunchOptions"\t\t"%s"\n%s' % (
                indent, escaped, indent[:-1])
        if dry_run:
            results.append((path, 'would set'))
            continue
        shutil.copy2(path, path + '.bak')
        with open(path, 'w', encoding='utf-8', errors='replace', newline='') as f:
            f.write(text[:start] + new_body + text[end:])
        results.append((path, 'set'))
    return results
