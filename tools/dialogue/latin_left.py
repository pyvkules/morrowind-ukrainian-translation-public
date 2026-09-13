# -*- coding: utf-8 -*-
"""Латиниця, що лишилася всередині вже перекладених реплік.

Репліку вважають перекладеною, щойно вона з'явилася в `uk/*.json`. Але назва
предмета всередині неї легко лишається англійською: очі бачать українське
речення й читають його як готове. У грі виходить найгірший можливий стан —
у журналі «Ring of Sanguine Fluid Evasion», а в інвентарі той самий перстень
уже українською, і завдання стає непрохідним.

`q.py dup` цього не бачить: англійський рядок один, переклад один.

Скрипт показує кожен такий рядок і, де може, підказує усталений переклад:
шукає в англійському оригіналі найдовший ключ зі словників предметів, книг
і тем, який накриває залишену латиницю.

    py tools\\dialogue\\latin_left.py            # зведення по файлах
    py tools\\dialogue\\latin_left.py <зріз>     # рядки одного зрізу
    py tools\\dialogue\\latin_left.py --all      # усі рядки
"""

import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)

TOKEN = re.compile(r'%[A-Za-z]+')          # %PCName, %Name — це не латиниця
LATIN = re.compile(r'[A-Za-z]{2,}')
ROMAN = re.compile(r'[IVXLCDM]+$')


def load(path):
    with open(path, 'rb') as f:
        raw = f.read()
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return json.loads(raw.decode('utf-16'))
    return json.loads(raw.decode('utf-8-sig'))


MARKER = re.compile(r'^\s*\*{3,}')


def latin_of(text):
    """Латинські слова поза підстановками й римськими цифрами.

    Рядки на кшталт `**** IF ГІЛЬДІЙСЬКИЙ ПРОВІДНИК ****` — це закладки для
    себе, які модер лишив між репліками; гравець їх не бачить, і «IF» там не
    англійське слово, а мітка фракції. Такі рядки пропускаємо.
    """
    if MARKER.match(text):
        return []
    return [w for w in LATIN.findall(TOKEN.sub(' ', text))
            if not ROMAN.match(w)]


def dictionaries():
    """Усі усталені пари англійська→українська назва, довші ключі першими."""
    pairs = {}
    for path in glob.glob(os.path.join(TOOLS, 'items', '*.json')):
        name = os.path.basename(path)
        if not (name.startswith('uk_') or name.endswith('_overrides.json')):
            continue
        d = load(path)
        if not isinstance(d, dict):
            continue
        for en, uk in d.items():
            if isinstance(uk, str) and uk and LATIN.search(en):
                pairs.setdefault(en, uk)
    src = load(os.path.join(TOOLS, 'topics', 'dial_topics.json'))
    uk = {}
    for path in glob.glob(os.path.join(TOOLS, 'topics', 'uk_dial_topics*.json')):
        uk.update(load(path))
    for i, topic in enumerate(src):
        t = uk.get(str(i))
        if t and LATIN.search(topic):
            pairs.setdefault(topic, t)
    return sorted(pairs.items(), key=lambda kv: -len(kv[0]))


def suggest(english, words, pairs):
    """Ключі словників, що накривають залишену латиницю цього рядка."""
    out = []
    seen = set()
    left = set(words)
    for en, uk in pairs:
        if not left:
            break
        if en in seen or en not in english:
            continue
        hit = set(LATIN.findall(en)) & left
        if not hit:
            continue
        seen.add(en)
        left -= hit
        out.append((en, uk))
    return out, sorted(left)


def rows():
    pairs = dictionaries()
    for path in sorted(glob.glob(os.path.join(TOOLS, 'uk', '*.json'))):
        name = os.path.basename(path)[:-5]
        slice_name = re.sub(r'_p\d+$', '', name)
        src_path = os.path.join(TOOLS, 'src', slice_name + '.json')
        src = load(src_path) if os.path.isfile(src_path) else []
        if not isinstance(src, list):
            src = []
        d = load(path)
        if not isinstance(d, dict):
            continue
        for key in sorted(d, key=lambda k: int(k) if k.isdigit() else 0):
            uk = d[key]
            if not isinstance(uk, str):
                continue
            words = latin_of(uk)
            if not words:
                continue
            i = int(key) if key.isdigit() else -1
            en = src[i] if 0 <= i < len(src) else ''
            found, orphan = suggest(en, words, pairs)
            yield slice_name, name, key, uk, found, orphan


def main():
    args = [a for a in sys.argv[1:]]
    show_all = '--all' in args
    args = [a for a in args if not a.startswith('--')]
    want = args[0] if args else None

    per_slice = {}
    orphans = {}
    total = 0
    for slice_name, fname, key, uk, found, orphan in rows():
        total += 1
        per_slice[slice_name] = per_slice.get(slice_name, 0) + 1
        for w in orphan:
            orphans[w] = orphans.get(w, 0) + 1
        if not (show_all or (want and slice_name == want)):
            continue
        print('%s:%s' % (fname, key))
        print('   %s' % uk)
        for en, tr in found:
            print('   %-44s -> %s' % (en, tr))
        if orphan:
            print('   ? без словника: %s' % ', '.join(orphan))

    if want or show_all:
        print()
    print('рядків із латиницею: %d' % total)
    if not (want or show_all):
        for name, n in sorted(per_slice.items(), key=lambda kv: -kv[1]):
            print('   %-46s %d' % (name, n))
    if orphans:
        top = sorted(orphans.items(), key=lambda kv: -kv[1])[:20]
        print('поза словниками: %s' % ', '.join('%s(%d)' % t for t in top))


if __name__ == '__main__':
    main()
