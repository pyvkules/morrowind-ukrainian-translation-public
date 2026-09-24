# -*- coding: utf-8 -*-
"""Поставити модліст автора й відтворити його профіль.

Як це працює
------------
«Мій модліст» — не офіційний список: профіль зібраний із чотирьох одразу
(`total-overhaul`, `expanded-vanilla`, `just-good-morrowind`,
`i-heart-vanilla`) плюс власний порядок завантаження на 327 рядків. Тому:

1. самі моди тягне `umo` — рідний завантажувач Modding-OpenMW. Він уміє
   реєструватися обробником посилань `nxm://`, тож із преміумом на Nexus качає
   сам, а без нього відкриває сторінки по черзі;
2. профіль складаємо з рецепта (`recipe/profile.cfg`), підставивши шляхи цієї
   машини замість міток `{МОДИ}` і `{ГРА}`.

Чого ми НЕ робимо
-----------------
Не качаємо самі моди й не возимо їх: це чужі файли з Nexus, і роздавати їх не
можна. Не качаємо й самі інструменти MOMW — сталої адреси в них немає, а
вгадана адреса тихо зламається. Якщо інструментів немає, кажемо, звідки взяти.
"""
import io
import os
import re
import subprocess

TOOLS = ('umo.exe', 'momw-configurator.exe')
SITE = 'https://modding-openmw.com/tools/'
HERE = os.path.dirname(os.path.abspath(__file__))


def recipe_dir(payload_root):
    return os.path.join(payload_root, 'recipe')


def wanted_lists(payload_root):
    p = os.path.join(recipe_dir(payload_root), 'lists.txt')
    if not os.path.isfile(p):
        return []
    return [l.strip() for l in io.open(p, encoding='utf-8') if l.strip()]


def find_tools():
    """Де лежить momw-tools-pack. Повертає теку або None."""
    seen = []
    for base in (os.path.dirname(HERE), os.getcwd(),
                 os.path.expanduser('~'), r'C:\games', r'E:\Morrowind'):
        seen.append(base)
        for sub in ('', 'momw-tools-pack-windows', 'momw-tools-pack',
                    'tools', 'Downloads'):
            d = os.path.join(base, sub) if sub else base
            if all(os.path.isfile(os.path.join(d, t)) for t in TOOLS):
                return d
    for drive in 'CDEFGH':
        d = r'%s:\momw-tools-pack-windows' % drive
        if all(os.path.isfile(os.path.join(d, t)) for t in TOOLS):
            return d
    return None


def umo_dirs(tools):
    """Куди umo складає моди — питаємо його самого, а не вгадуємо."""
    try:
        r = subprocess.run([os.path.join(tools, 'umo.exe'), 'info'],
                           capture_output=True, text=True, timeout=180,
                           encoding='utf-8', errors='replace')
    except (OSError, subprocess.SubprocessError):
        return None
    # `umo info` друкує рядок «basepath dir: <шлях>» — саме туди він і
    # складає моди. У різних людей тека різна, тож питаємо, а не гадаємо.
    for line in (r.stdout or '').splitlines():
        if 'basepath' in line.lower() and ':' in line:
            path = line.split(':', 1)[1].strip()
            if len(path) > 2 and path[1] == ':':
                return path
    return None

def install_lists(tools, lists, on_line):
    """Провести `umo install` по кожному списку. Це найдовша частина."""
    umo = os.path.join(tools, 'umo.exe')
    for name in lists:
        on_line('Завантажую список «%s» — це надовго.' % name)
        r = subprocess.run([umo, 'install', name])
        if r.returncode != 0:
            on_line('umo повернув %d на списку «%s»' % (r.returncode, name))
            return False
    return True


def write_profile(payload_root, cfg_path, mods_dir, game_dir, on_line):
    """Скласти openmw.cfg із рецепта, підставивши шляхи цієї машини."""
    src = os.path.join(recipe_dir(payload_root), 'profile.cfg')
    if not os.path.isfile(src):
        on_line('Рецепта профілю немає — нічого відтворювати.')
        return False
    text = io.open(src, encoding='utf-8').read()
    text = text.replace('{МОДИ}', mods_dir.rstrip('\\')) \
               .replace('{ГРА}', game_dir.rstrip('\\'))

    missing = 0
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('data='):
            d = s[5:].strip().strip('"')
            if not os.path.isdir(d):
                missing += 1
    if missing:
        on_line('Увага: %d тек із профілю ще немає — якісь моди не '
                'завантажилися.' % missing)

    if os.path.isfile(cfg_path):
        backup = cfg_path + '.before-modlist'
        if not os.path.exists(backup):
            io.open(backup, 'w', encoding='utf-8').write(
                io.open(cfg_path, encoding='utf-8', errors='replace').read())
            on_line('стару конфігурацію збережено як %s'
                    % os.path.basename(backup))
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
    io.open(cfg_path, 'w', encoding='utf-8', newline='\n').write(text)
    on_line('профіль записано: %s' % cfg_path)
    return True
