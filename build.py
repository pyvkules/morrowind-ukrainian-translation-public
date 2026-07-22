# -*- coding: utf-8 -*-
"""Build the whole Ukrainian translation from source.

Everything the game loads is generated: the patched font, Morrowind.esm, the shadow
copies of the plugins that would otherwise re-supply English text, and the topic
keyword table. None of it is kept in version control - only the translation itself
and the code that applies it.

Order matters. patch_plugins reads the PRISTINE plugins from the modlist data dirs,
while rename_topics and patch_gmst read the copies already produced here, so running
patch_plugins after rename_topics would silently undo the topic rename.

    py build.py                 # find the modlist automatically
    py build.py --cfg <path>    # or point at a specific openmw.cfg
    py build.py --check         # build, then run the validators
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'tools'))
import paths

STEPS = [
    ('font', ['tools/patch_font.py'], 'Ukrainian glyphs into the UI font'),
    ('esm', ['tools/rebuild_esm.py'], 'Morrowind.esm with translated dialogue'),
    ('plugins', ['tools/patch_plugins.py', '--apply'], 'carry the translation into every other plugin'),
    ('forms', ['tools/topics/harvest_forms.py'], 'mine inflected topic forms from the corpus'),
    ('topics', ['tools/topics/rename_topics.py', '--apply'], 'rename dialogue topics and fix AddTopic'),
    ('gmst', ['tools/gmst/patch_gmst.py', '--apply'], 'translated interface strings'),
    ('top', ['tools/build_top.py'], 'morrowind.top keyword table'),
]
CHECKS = [
    ('validate', ['tools/topics/validate_topics.py'], 'topic integrity'),
]


def forms_are_stale():
    """Harvesting takes ~100s and only depends on the translated corpus and the
    topic names, so skip it unless one of those actually changed."""
    out = os.path.join(HERE, 'tools', 'topics', 'harvested_forms.json')
    if not os.path.isfile(out) or '--force-forms' in sys.argv:
        return True
    stamp = os.path.getmtime(out)
    for sub in (os.path.join('tools', 'uk'), os.path.join('tools', 'topics')):
        d = os.path.join(HERE, sub)
        for name in os.listdir(d) if os.path.isdir(d) else []:
            if name.endswith('.json') and name != 'harvested_forms.json':
                if os.path.getmtime(os.path.join(d, name)) > stamp:
                    return True
    return False


def run(script_args, cfg):
    cmd = [sys.executable, os.path.join(HERE, script_args[0].replace('/', os.sep))]
    cmd += script_args[1:]
    if cfg:
        cmd += ['--cfg', cfg]
    return subprocess.run(cmd, cwd=HERE, capture_output=True, text=True,
                          encoding='utf-8', errors='replace')


def main():
    cfg = paths.openmw_cfg()
    print('modlist config : %s' % cfg)
    print('output goes to : %s' % paths.MOD_ROOT)
    print()

    base = os.path.join(HERE, 'tools', 'base.esm')
    if not os.path.isfile(base):
        print('MISSING tools/base.esm - see README, the ESM step cannot run without it.')
        return 1

    steps = STEPS + (CHECKS if '--check' in sys.argv else [])
    skip_forms = not forms_are_stale()
    failed = []
    for name, script_args, what in steps:
        if name == 'forms' and skip_forms:
            print('%-9s %-52s%s' % (name, what, 'skip (up to date)'))
            continue
        t0 = time.time()
        sys.stdout.write('%-9s %-52s' % (name, what))
        sys.stdout.flush()
        r = run(script_args, cfg)
        ok = r.returncode == 0
        print('%s  %4.1fs' % ('ok  ' if ok else 'FAIL', time.time() - t0))
        if not ok:
            failed.append(name)
            print((r.stdout or '') + (r.stderr or ''))
        else:
            for line in (r.stdout or '').splitlines():
                low = line.lower()
                if ('warn' in low and ': 0' not in low) or 'still in latin' in low:
                    print('    ! ' + line.strip())

    print()
    if failed:
        print('FAILED: %s' % ', '.join(failed))
        return 1
    print('build complete - launch Morrowind as usual, nothing else to change.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
