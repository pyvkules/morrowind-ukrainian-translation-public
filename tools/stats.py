# -*- coding: utf-8 -*-
"""Скільки перекладено — у двох рядках, без ігрових даних.

Потрібно для опису релізу: CI не має ні гри, ні модів, тож рахуємо по тому, що
лежить у репозиторії — зрізи `tools/src` проти перекладів `tools/uk`.

    py tools\\stats.py            # людині
    py tools\\stats.py --md       # рядок для опису релізу
"""
import glob
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Зрізи базової гри. Решта (`mod_*`) — це моди, і їхній стан залежить від того,
# які моди в гравця стоять, тож рахуємо окремо.
VANILLA = ('greeting_', 'topics', 'journal', 'voice_', 'persuasion', 'service')


def load(path):
    with open(path, 'rb') as f:
        raw = f.read()
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return json.loads(raw.decode('utf-16'))
    return json.loads(raw.decode('utf-8-sig'))


def count():
    van_done = van_tot = mod_done = mod_tot = 0
    for path in sorted(glob.glob(os.path.join(HERE, 'src', '*.json'))):
        name = os.path.basename(path)[:-5]
        src = load(path)
        if not isinstance(src, list):
            continue
        uk = {}
        for q in sorted(glob.glob(os.path.join(HERE, 'uk', name + '.json'))
                        + glob.glob(os.path.join(HERE, 'uk', name + '_p*.json'))):
            uk.update(load(q))
        done = sum(1 for i, en in enumerate(src)
                   if isinstance(en, str) and uk.get(str(i)))
        tot = sum(1 for en in src if isinstance(en, str))
        if name.startswith(VANILLA):
            van_done += done
            van_tot += tot
        else:
            mod_done += done
            mod_tot += tot
    return van_done, van_tot, mod_done, mod_tot


def topics():
    src = os.path.join(HERE, 'topics', 'dial_topics.json')
    tot = len(load(src)) if os.path.isfile(src) else 0
    uk = {}
    for p in glob.glob(os.path.join(HERE, 'topics', 'uk_dial_topics*.json')):
        uk.update(load(p))
    return len(uk), tot


def names():
    n = 0
    for p in glob.glob(os.path.join(HERE, 'items', 'uk_*.json')):
        try:
            d = load(p)
        except ValueError:
            continue
        n += len([k for k in d if k != '_comment'])
    return n


def main():
    # Вивід перемикаємо тут, а не при імпорті: `installer/make.py`
    # імпортує цей модуль заради чисел, і підміняти йому stdout не можна.
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='replace', write_through=True)
    vd, vt, md, mt = count()
    td, tt = topics()
    pct = 100.0 * vd / vt if vt else 0
    if '--md' in sys.argv:
        print('| | |')
        print('|---|---:|')
        print('| базова гра (діалоги) | **%.0f%%** (%d / %d) |' % (pct, vd, vt))
        print('| теми діалогів | **%d / %d** |' % (td, tt))
        print('| назви предметів і персонажів | **%d** |' % names())
        print('| репліки модів | %d / %d |' % (md, mt))
        return 0
    print('базова гра  %d / %d  (%.0f%%)' % (vd, vt, pct))
    print('теми        %d / %d' % (td, tt))
    print('назви       %d' % names())
    print('моди        %d / %d' % (md, mt))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
