# -*- coding: utf-8 -*-
"""Single source of truth for where things live, so no tool hardcodes a path.

Resolution order for the OpenMW config that describes the modlist:

  1. --cfg <path> on the command line
  2. the MWUK_OPENMW_CFG environment variable
  3. "openmw_cfg" in config.json next to the repository root
  4. auto-detection: the newest openmw.cfg found in the usual OpenMW profile
     locations, ignoring the one that ships next to openmw.exe

MOD_ROOT is always the repository root itself - that is the data directory OpenMW
loads us from, so the built files have to land there.
"""
import json
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
MOD_ROOT = os.path.abspath(os.path.join(TOOLS, '..'))
CONFIG = os.path.join(MOD_ROOT, 'config.json')


def _from_argv():
    for i, a in enumerate(sys.argv):
        if a == '--cfg' and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if a.startswith('--cfg='):
            return a[6:]
    return None


def _from_config():
    if os.path.exists(CONFIG):
        try:
            return json.load(open(CONFIG, encoding='utf-8')).get('openmw_cfg')
        except (ValueError, OSError):
            return None
    return None


def _autodetect():
    candidates = []
    roots = [os.path.join(os.environ.get('LOCALAPPDATA', ''), 'openmw'),
             os.path.join(os.path.expanduser('~'), 'Documents', 'My Games', 'OpenMW')]
    # a momw-configurator layout keeps one profile directory per modlist next to
    # the engine, which is where this repository normally lives
    engine = os.path.abspath(os.path.join(MOD_ROOT, '..', '..'))
    roots.append(engine)
    for root in roots:
        if not os.path.isdir(root):
            continue
        for entry in os.listdir(root):
            p = os.path.join(root, entry, 'openmw.cfg')
            if os.path.isfile(p):
                candidates.append(p)
        p = os.path.join(root, 'openmw.cfg')
        # skip the stock config shipped beside openmw.exe: it lists no mods
        if os.path.isfile(p) and root != engine:
            candidates.append(p)
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def openmw_cfg(required=True):
    path = _from_argv() or os.environ.get('MWUK_OPENMW_CFG') or _from_config() or _autodetect()
    if path:
        path = os.path.abspath(os.path.expandvars(os.path.expanduser(path)))
    if required and (not path or not os.path.isfile(path)):
        raise SystemExit(
            'Cannot find the modlist openmw.cfg.\n'
            'Set it once with any of:\n'
            '  * copy config.example.json to config.json and edit "openmw_cfg"\n'
            '  * set MWUK_OPENMW_CFG=<path to openmw.cfg>\n'
            '  * pass --cfg "<path to openmw.cfg>"')
    return path


def read_modlist(cfg=None):
    """Return (data_dirs, content_files) in load order, our own root excluded."""
    cfg = cfg or openmw_cfg()
    dirs, contents = [], []
    for line in open(cfg, encoding='utf-8', errors='replace'):
        line = line.strip()
        if line.startswith('data='):
            dirs.append(line[5:].strip('"'))
        elif line.startswith('content='):
            contents.append(line[8:])
    return dirs, contents


def resolve_plugins(dirs):
    """Map lowercased plugin filename -> full path, later data dirs winning.

    Our own MOD_ROOT is skipped so re-runs read the pristine originals.
    """
    resolved = {}
    for d in dirs:
        if os.path.abspath(d) == MOD_ROOT:
            continue
        try:
            entries = os.listdir(d)
        except OSError:
            continue
        for e in entries:
            resolved[e.lower()] = os.path.join(d, e)
    return resolved
