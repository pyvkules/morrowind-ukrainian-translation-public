# -*- coding: utf-8 -*-
"""Перевірка й застосування оновлень модпаку.

Версія лежить у version.json поруч із самим модпаком. Нові версії публікуються як
релізи публічного репозиторію; оновлення - це архів із перекладом і рецептом
модліста, а не з грою, тому важить кілька сотень кілобайт.

Оновлення застосовується атомарно: спершу все розпаковується в тимчасовий каталог
поруч, і лише коли розпакування вдалося, файли переносяться на місце. Якщо процес
уб'ють посеред завантаження, робочий модпак лишається цілим.

    py updater.py --check      # тільки подивитися, чи є новіша
    py updater.py --update     # завантажити й застосувати
"""
import json
import os
import shutil
import ssl
import sys
import tempfile
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))
VERSION_FILE = os.path.join(REPO, 'version.json')
API = 'https://api.github.com/repos/%s/releases/latest'
UA = {'User-Agent': 'morrowind-ukrainian-modpack-updater'}

# файли користувача, які оновлення ніколи не чіпає
KEEP = {'config.json'}


def local():
    try:
        with open(VERSION_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {'version': '0.0.0', 'public_repo': None}


def parse(v):
    out = []
    for part in str(v).lstrip('v').split('.'):
        digits = ''.join(c for c in part if c.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out + [0] * (3 - len(out)))[:3]


def newer(remote_v, local_v):
    return parse(remote_v) > parse(local_v)


def latest(repo=None, timeout=15):
    """Метадані останнього релізу, або None якщо недоступно."""
    repo = repo or local().get('public_repo')
    if not repo:
        return None
    req = urllib.request.Request(API % repo, headers=UA)
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            data = json.load(r)
    except Exception:                                   # noqa: BLE001
        return None                                     # без мережі - просто граємо
    asset = None
    for a in data.get('assets', []):
        if a.get('name', '').lower().endswith('.zip'):
            asset = a
            break
    return {
        'version': data.get('tag_name', '0.0.0'),
        'notes': data.get('body', ''),
        'url': asset['browser_download_url'] if asset else None,
        'size': asset.get('size') if asset else None,
        'page': data.get('html_url'),
    }


def check():
    cur = local()
    rel = latest()
    if not rel:
        return None
    return rel if newer(rel['version'], cur['version']) else None


def download(url, dest, progress=None):
    req = urllib.request.Request(url, headers=UA)
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r, open(dest, 'wb') as f:
        total = int(r.headers.get('Content-Length') or 0)
        done = 0
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    return dest


def apply(zip_path, log=print):
    """Розпакувати поруч, перевірити, і лише тоді перенести на місце."""
    staging = tempfile.mkdtemp(prefix='mwuk-update-', dir=os.path.dirname(REPO))
    try:
        with zipfile.ZipFile(zip_path) as z:
            for member in z.namelist():
                target = os.path.normpath(os.path.join(staging, member))
                if not target.startswith(os.path.normpath(staging) + os.sep) \
                        and target != os.path.normpath(staging):
                    raise RuntimeError('архів містить шлях за межі каталогу: %s' % member)
            z.extractall(staging)

        # архів може мати один кореневий каталог - зайти в нього
        entries = os.listdir(staging)
        root = os.path.join(staging, entries[0]) if len(entries) == 1 and \
            os.path.isdir(os.path.join(staging, entries[0])) else staging
        if not os.path.isfile(os.path.join(root, 'version.json')):
            raise RuntimeError('в архіві немає version.json - це не оновлення модпаку')

        moved = 0
        for dirpath, _dirnames, filenames in os.walk(root):
            rel = os.path.relpath(dirpath, root)
            for name in filenames:
                relname = os.path.normpath(os.path.join(rel, name))
                if relname in KEEP:
                    continue
                dst = os.path.join(REPO, relname)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(os.path.join(dirpath, name), dst)
                moved += 1
        log('оновлено файлів: %d' % moved)
        return True
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main():
    cur = local()
    print('встановлена версія: %s' % cur.get('version'))
    rel = latest()
    if not rel:
        print('не вдалося дізнатися останню версію (немає мережі або релізів)')
        return 0
    print('остання версія    : %s' % rel['version'])
    if not newer(rel['version'], cur['version']):
        print('оновлення не потрібне')
        return 0
    if '--update' not in sys.argv:
        print('є новіша версія. Запустіть з --update, щоб установити.')
        return 0
    if not rel['url']:
        print('у релізі немає zip-архіву: %s' % rel['page'])
        return 1
    tmp = os.path.join(tempfile.gettempdir(), 'mwuk-update.zip')
    print('завантаження...')
    download(rel['url'], tmp,
             lambda d, t: sys.stdout.write('\r  %d%%' % (100 * d // t) if t else ''))
    print()
    apply(tmp)
    print('оновлено до %s' % rel['version'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
