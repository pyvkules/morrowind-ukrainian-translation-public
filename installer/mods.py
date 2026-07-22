# -*- coding: utf-8 -*-
"""Автоматичне встановлення самих модів.

Модпак стоїть на чотирьох колекціях із modding-openmw.com, і MOMW дає для них
власний завантажувач - =umo=. Він качає модліст, розпаковує архіви куди треба й
уміє оновлювати вже встановлене. Тому інсталятор нічого не везе з собою і нічого не
перепаковує: він викликає umo, а той бере моди з їхніх рідних джерел.

  * з акаунтом Nexus Premium встановлення повністю автоматичне;
  * без преміуму Nexus не віддає файли роботам - umo відкриває сторінку мода в
    браузері, а після натискання «Download» сам підхоплює файл. Кліків багато, але
    жодного ручного розпакування й розкладання по теках.

Це не обхід обмежень Nexus, а рівно той шлях, який MOMW і Nexus для цього й лишили.

    py mods.py --check
    py mods.py --install
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))

TOOLS_PACK_URL = ('https://modding-openmw.gitlab.io/momw-tools-pack/'
                  'momw-tools-pack-windows.zip')
UA = {'User-Agent': 'morrowind-ukrainian-modpack-installer'}


def collections():
    with open(os.path.join(REPO, 'modpack', 'modlist.json'), encoding='utf-8') as f:
        return json.load(f)['based_on']


def find_umo(extra_roots=()):
    """umo.exe з пакета інструментів MOMW, якщо він уже десь є."""
    candidates = []
    for root in list(extra_roots) + [os.path.abspath(os.path.join(REPO, '..', '..', '..')),
                                     os.path.join(REPO, 'tools-pack')]:
        if not root or not os.path.isdir(root):
            continue
        for name in os.listdir(root):
            if 'momw-tools-pack' in name.lower():
                p = os.path.join(root, name, 'umo.exe')
                if os.path.isfile(p):
                    candidates.append(p)
        p = os.path.join(root, 'umo.exe')
        if os.path.isfile(p):
            candidates.append(p)
    found = shutil.which('umo')
    if found:
        candidates.append(found)
    return candidates[0] if candidates else None


def fetch_tools_pack(dest=None, log=print):
    """Завантажити пакет інструментів MOMW - він поширюється вільно."""
    dest = dest or os.path.join(REPO, 'tools-pack')
    os.makedirs(dest, exist_ok=True)
    tmp = os.path.join(tempfile.gettempdir(), 'momw-tools-pack.zip')
    log('завантаження momw-tools-pack...')
    req = urllib.request.Request(TOOLS_PACK_URL, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, 'wb') as f:
        shutil.copyfileobj(r, f)
    with zipfile.ZipFile(tmp) as z:
        z.extractall(dest)
    os.remove(tmp)
    return find_umo([dest])


def run(cmd, log):
    log('$ ' + ' '.join(cmd))
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding='utf-8', errors='replace')
    for line in p.stdout:
        log('  ' + line.rstrip())
    return p.wait()


def check(log=print):
    umo = find_umo()
    if not umo:
        log('umo не знайдено - інсталятор завантажить momw-tools-pack сам')
        return None
    log('umo: %s' % umo)
    run([umo, 'check'], log)
    return umo


def install(premium=None, threads=8, log=print, only=None):
    """Встановити всі колекції модпаку. premium=None - хай umo вирішує сам."""
    umo = find_umo() or fetch_tools_pack(log=log)
    if not umo:
        log('! не вдалося отримати umo')
        return False

    if run([umo, 'check'], log) != 0:
        log('! umo повідомляє про брак залежностей - див. вивід вище')
        return False

    # обробник nxm:// потрібен, щоб підхоплювати завантаження з браузера
    run([umo, 'setup'], log)

    todo = only or collections()
    for name in todo:
        log('')
        log('== модліст %s ==' % name)
        cmd = [umo, 'install', '--sync', '--threads', str(threads)]
        if premium is True:
            cmd.append('--nexus-premium')
        elif premium is False:
            cmd.append('--no-nexus-premium')
        cmd.append(name)
        if run(cmd, log) != 0:
            log('! %s встановити не вдалося' % name)
            return False
    log('')
    log('усі колекції встановлено')
    return True


if __name__ == '__main__':
    if '--install' in sys.argv:
        prem = True if '--premium' in sys.argv else (
            False if '--no-premium' in sys.argv else None)
        raise SystemExit(0 if install(premium=prem) else 1)
    check()
