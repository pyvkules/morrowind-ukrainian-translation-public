# -*- coding: utf-8 -*-
"""Витягти репліки INFO з усього модліста в нові зрізи.

Навіщо це окремо від make_slices.py
-----------------------------------
`make_slices.py` працює з `corpus.json`, а той покриває лише базову гру: 17 617
унікальних текстів, усі вже в `src/`. Решта реплік живе в 403 плагінах модліста,
і туди ще ніхто не заглядав. Виміряно: **16 615 англійських реплік на 2,44 млн
символів у 65 плагінах** - Tribunal, Bloodmoon, Patch for Purists, Tamriel_Data
та інші.

І ще: `make_slices.py` пише в `src/topics01..10.json`, тобто **перезаписує**
наявні зрізи. Індекси в `uk/topics01_p*.json` після цього вказували б на інші
рядки, і весь переклад тем поїхав би. Тому новий видобувач пише **тільки під
новими іменами** `mod_*.json` і ніколи не чіпає старих.

Індекси - навіки
----------------
Переклад прив'язаний до **номера рядка** у зрізі, тож порядок мусить бути
відтворюваний і незмінний: плагіни в порядку завантаження, записи в порядку
файлу, дублікати - за першою появою. Якщо зріз уже існує, новий список мусить
починатися рівно з нього; інакше скрипт падає і нічого не пише, бо зсув індексів
мовчки зіпсував би весь переклад цього зрізу.

Що НЕ потрапляє у зріз
----------------------
Репліки, у яких уже є кирилиця: їх переклав давній переклад просто в плагіні,
і робити з ними нічого. Таких 17 129 - здебільшого це сам Morrowind.esm.

Usage: py extract_infos.py [--apply]
"""
import glob
import io
import json
import os
import re
import struct
import sys
from collections import OrderedDict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.abspath(os.path.join(HERE, '..'))
CFG = r'E:\Morrowind\OpenMW\just-good-morrowind-plus\openmw.cfg'
MODROOT = r'E:\Morrowind\OpenMW\mods\ukrainian-l10n'

CYR = re.compile('[А-Яа-яЄІЇҐєіїґ]')
BIG = 60          # від скількох реплік плагін дістає власний зріз


def load_json(path):
    raw = open(path, 'rb').read()
    for enc in ('utf-8-sig', 'utf-16', 'cp1251'):
        try:
            return json.loads(raw.decode(enc))
        except (UnicodeDecodeError, ValueError):
            continue
    raise ValueError('не можу прочитати ' + path)


def dec(b):
    return b.rstrip(b'\0').decode('cp1251', 'replace').strip()


def slug(name):
    """Ім'я плагіна -> частина імені файлу: тільки латиниця, цифри й підкреслення."""
    s = re.sub(r'\.(esp|esm)$', '', name, flags=re.I)
    s = re.sub(r'[^A-Za-z0-9]+', '_', s).strip('_').lower()
    return re.sub(r'_+', '_', s)[:40] or 'plugin'


def infos(data):
    """Тексти INFO/NAME у порядку файлу."""
    i, L = 0, len(data)
    while i + 16 <= L:
        rt = data[i:i + 4]
        sz = struct.unpack_from('<I', data, i + 4)[0]
        if sz > L:
            break
        if rt == b'INFO':
            body = data[i + 16:i + 16 + sz]
            j, subs = 0, {}
            while j + 8 <= len(body):
                st = body[j:j + 4]
                ss = struct.unpack_from('<I', body, j + 4)[0]
                subs.setdefault(st, body[j + 8:j + 8 + ss])
                j += 8 + ss
            if b'NAME' in subs:
                t = dec(subs[b'NAME'])
                if t:
                    yield t
        i += 16 + sz


def main():
    apply = '--apply' in sys.argv

    covered = set()
    for f in sorted(glob.glob(os.path.join(TOOLS, 'src', '*.json'))):
        covered.update(load_json(f))

    dirs, contents = [], []
    for line in open(CFG, encoding='utf-8', errors='replace'):
        line = line.strip()
        if line.startswith('data='):
            dirs.append(line[5:].strip('"'))
        elif line.startswith('content='):
            contents.append(line[8:])
    resolved = {}
    for d in dirs:
        if os.path.abspath(d) == os.path.abspath(MODROOT):
            continue                # наші ж пропатчені копії подвоїли б рахунок
        try:
            for e in os.listdir(d):
                resolved[e.lower()] = os.path.join(d, e)
        except OSError:
            pass

    # порядок завантаження -> порядок файлу -> перша поява
    seen = set()
    per_plugin = OrderedDict()
    for c in contents:
        p = resolved.get(c.lower())
        if not p or not os.path.isfile(p):
            continue
        try:
            data = open(p, 'rb').read()
        except OSError:
            continue
        for t in infos(data):
            if t in covered or t in seen or CYR.search(t):
                continue
            seen.add(t)
            per_plugin.setdefault(c, []).append(t)

    # великі плагіни - власний зріз; дрібнота - в один спільний
    slices, misc = OrderedDict(), []
    for c, texts in per_plugin.items():
        if len(texts) >= BIG:
            slices['mod_' + slug(c)] = texts
        else:
            misc.extend(texts)
    if misc:
        slices['mod_misc'] = misc

    total = sum(len(v) for v in slices.values())
    chars = sum(len(t) for v in slices.values() for t in v)
    print('плагінів із новими репліками : %d' % len(per_plugin))
    print('зрізів буде                  : %d' % len(slices))
    print('реплік                       : %d' % total)
    print('символів                     : %d' % chars)
    print()

    bad = False
    for name, texts in slices.items():
        path = os.path.join(TOOLS, 'src', name + '.json')
        old = load_json(path) if os.path.isfile(path) else []
        # старі індекси недоторканні: новий список мусить починатися зі старого
        if old and texts[:len(old)] != old:
            print('!! %-34s ЗСУВ ІНДЕКСІВ - не чіпаю' % name)
            bad = True
            continue
        print('%-34s %6d рядків (%+d)' % (name, len(texts), len(texts) - len(old)))
        if apply:
            json.dump(texts, open(path, 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=0)

    if bad:
        raise SystemExit('\nє зріз зі зсувом індексів - нічого не записано для нього')
    if not apply:
        print('\n(пробний запуск; --apply щоб записати)')


main()
