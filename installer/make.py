# -*- coding: utf-8 -*-
"""Зібрати ukrainizer-setup.exe — один файл, який можна просто віддати людині.

Усередину кладемо **тільки джерела перекладу й патчер** (див. `install.py`:
готовий Morrowind.esm — це дані Bethesda, а .ttf — чужий шрифт під OFL).
Список файлів той самий, що бачить git: 564 файли, ~29 МБ до стиснення.

    py installer/make.py            # зібрати
    py installer/make.py --clean    # зібрати з нуля
"""
import io
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))
BUILD = os.path.join(HERE, 'build')
PAYLOAD = os.path.join(BUILD, 'payload')
DIST = os.path.join(HERE, 'dist')
NAME = 'ukrainizer-setup'
ICON = os.path.join(HERE, 'icon.ico')

sys.path.insert(0, HERE)
import install                                   # noqa: E402 - той самий фільтр


def tracked_files():
    """Що git вважає нашим. Це і є межа між «наше» і «чуже»."""
    try:
        r = subprocess.run(['git', 'ls-files'], cwd=REPO, capture_output=True,
                           text=True, encoding='utf-8')
    except OSError:
        return None                              # без git беремо білий список
    if r.returncode != 0:
        return None
    return {os.path.normcase(os.path.normpath(l.strip()))
            for l in r.stdout.splitlines() if l.strip()}


def git_short():
    try:
        r = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=REPO,
                           capture_output=True, text=True, encoding='utf-8')
    except OSError:
        return '?'
    return r.stdout.strip() if r.returncode == 0 else '?'


def write_build_info(payload):
    """Покласти у вміст версію й стан перекладу.

    Робимо це тут, а не константою в коді: числа міняються з кожним пушем, і
    вписане руками застаріє наступного ж дня. `stats.py` рахує по зрізах у
    репозиторії, тож ігрові дані для цього не потрібні — CI теж упорається.
    """
    sys.path.insert(0, os.path.join(REPO, 'tools'))
    import stats                              # noqa: E402 - шлях щойно додано

    vd, vt, md, mt = stats.count()
    td, tt = stats.topics()
    info = {'version': time.strftime('%y.%m.%d'), 'commit': git_short(),
            'vanilla': [vd, vt], 'topics': [td, tt],
            'names': stats.names(), 'mods': [md, mt]}
    with io.open(os.path.join(payload, 'build.json'), 'w',
                 encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(info, ensure_ascii=False, indent=1))
    print('збірка %s (%s): базова гра %d/%d, теми %d/%d, назви %d, моди %d/%d'
          % (info['version'], info['commit'], vd, vt, td, tt,
             info['names'], md, mt))


def main():
    if '--clean' in sys.argv:
        for d in (BUILD, DIST, os.path.join(HERE, '__pycache__')):
            shutil.rmtree(d, ignore_errors=True)

    if os.path.isdir(PAYLOAD):
        shutil.rmtree(PAYLOAD, ignore_errors=True)
    os.makedirs(PAYLOAD, exist_ok=True)
    allow = tracked_files()
    if allow is None:
        print('git недоступний — беру вбудований білий список')
    n = install.copy_payload(REPO, PAYLOAD, allow)
    size = sum(os.path.getsize(os.path.join(r, f))
               for r, _, fs in os.walk(PAYLOAD) for f in fs)
    print('вміст: %d файлів, %.1f МБ' % (n, size / 1048576.0))
    write_build_info(PAYLOAD)

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--name', NAME,
        '--distpath', DIST,
        '--workpath', os.path.join(BUILD, 'work'),
        '--specpath', BUILD,
        '--add-data', PAYLOAD + os.pathsep + 'payload',
        # піктограма потрібна двічі: на самому файлі та всередині —
        # exe бере її з ресурсів, а вікно відкриває як файл
        '--icon', ICON,
        '--add-data', ICON + os.pathsep + '.',
        # patch_font вантажиться через runpy, тож статичний аналіз його імпортів
        # не бачить - fontTools треба забрати цілком
        '--collect-all', 'fontTools',
        '--noconfirm',
        os.path.join(HERE, 'install.py'),
    ]
    print('$ ' + ' '.join(cmd[-6:]))
    r = subprocess.run(cmd, cwd=HERE)
    if r.returncode != 0:
        return r.returncode

    exe = os.path.join(DIST, NAME + '.exe')
    if os.path.isfile(exe):
        print()
        print('готово: %s  (%.1f МБ)' % (exe, os.path.getsize(exe) / 1048576.0))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
