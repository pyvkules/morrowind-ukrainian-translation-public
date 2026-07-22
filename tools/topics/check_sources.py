# -*- coding: utf-8 -*-
"""Перевірка самих текстів - без гри, без модів, без ESM.

Все, що можна перевірити, маючи лише вміст репозиторію, щоб CI ловив помилку до
того, як вона доїде до чиєїсь гри. Ігрові дані на раннері недоступні й не мають
бути доступні, тому цілісність ESM перевіряє validate_topics.py уже на машині гравця.

Що перевіряється:
  1. кожен індекс перекладу існує у відповідному англійському зрізі;
  2. жоден індекс не перекладено двічі в різних файлах;
  3. дві теми не отримали однакову назву - інакше вони зіллються в одну;
  4. усе кодується в cp1251, бо гра читає саме його;
  5. підстановки (%PCName, %Name, ...) збережено дослівно;
  6. ключі GMST існують в оригіналі.

Код виходу 1, якщо є хоч одна помилка.

Usage: py check_sources.py
"""
import glob
import io
import json
import os
import re
import sys
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.abspath(os.path.join(HERE, '..'))

TOKEN = re.compile(r'%[A-Za-z]+')
errors, warnings = [], []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def encodable(text, where):
    try:
        text.encode('cp1251')
    except UnicodeEncodeError as e:
        bad = text[e.start:e.end]
        err('%s: не кодується в cp1251: %r у %r' % (where, bad, text[:60]))


# ---------------------------------------------------------------- 1-2, 4-5: зрізи
def check_slices():
    pairs = 0
    for src_path in sorted(glob.glob(os.path.join(TOOLS, 'src', '*.json'))):
        name = os.path.splitext(os.path.basename(src_path))[0]
        uk_paths = sorted(glob.glob(os.path.join(TOOLS, 'uk', name + '.json'))
                          + glob.glob(os.path.join(TOOLS, 'uk', name + '_p*.json')))
        if not uk_paths:
            continue
        src = json.load(open(src_path, encoding='utf-8'))
        seen = {}
        for p in uk_paths:
            uk = json.load(open(p, encoding='utf-8'))
            for k, v in uk.items():
                where = '%s[%s]' % (os.path.basename(p), k)
                try:
                    i = int(k)
                except ValueError:
                    err('%s: індекс не число' % where)
                    continue
                if not 0 <= i < len(src):
                    err('%s: індекс поза межами (зріз має %d рядків)' % (where, len(src)))
                    continue
                if i in seen:
                    err('%s: індекс уже перекладено у %s' % (where, seen[i]))
                seen[i] = os.path.basename(p)
                encodable(v, where)
                want = sorted(set(TOKEN.findall(src[i])))
                got = sorted(set(TOKEN.findall(v)))
                if want != got:
                    lost = set(want) - set(got)
                    extra = set(got) - set(want)
                    if lost:
                        err('%s: втрачено підстановки %s' % (where, ', '.join(sorted(lost))))
                    if extra:
                        warn('%s: зайві підстановки %s' % (where, ', '.join(sorted(extra))))
                pairs += 1
    return pairs


# ---------------------------------------------------------------- 1-4: теми
def check_topics():
    src = json.load(open(os.path.join(HERE, 'dial_topics.json'), encoding='utf-8'))
    seen, translated = {}, {}
    for p in sorted(glob.glob(os.path.join(HERE, 'uk_dial_topics*.json'))):
        for k, v in json.load(open(p, encoding='utf-8')).items():
            where = '%s[%s]' % (os.path.basename(p), k)
            i = int(k)
            if not 0 <= i < len(src):
                err('%s: індекс теми поза межами' % where)
                continue
            if i in seen:
                err('%s: тема %d уже перекладена у %s' % (where, i, seen[i]))
            seen[i] = os.path.basename(p)
            encodable(v, where)
            if not v.strip():
                err('%s: порожня назва теми' % where)
            translated[i] = v

    # Частину тем перейменував ще давній переклад, тож у dial_topics.json вони вже
    # українською. Коли ми перекладаємо їхній англійський відповідник тим самим
    # рядком, обидва записи DIAL зливаються в одну тему - і це навмисно, бо це
    # та сама тема, розрізана надвоє. legacy_en_ids.json перелічує саме ці пари.
    legacy = {}
    legacy_path = os.path.join(HERE, 'legacy_en_ids.json')
    if os.path.isfile(legacy_path):
        legacy = {k.lower(): v.lower()
                  for k, v in json.load(open(legacy_path, encoding='utf-8')).items()}

    names = defaultdict(list)
    for i, en in enumerate(src):
        names[(translated.get(i) or en).lower()].append(en)
    for name, sources in sorted(names.items()):
        if len(sources) < 2:
            continue
        intended = all(s.lower() == name or legacy.get(s.lower()) == name for s in sources)
        if intended:
            continue
        err('дві теми дістали однакову назву %r: %s' % (name, ', '.join(sources)))

    missing = [i for i in range(len(src)) if i not in translated]
    cyr = re.compile('[А-Яа-яЄІЇҐєіїґ]')
    real = [i for i in missing if not cyr.search(src[i])]
    if real:
        warn('тем без перекладу: %d (перша: %r)' % (len(real), src[real[0]]))
    return len(translated), len(src)


# ---------------------------------------------------------------- 6: GMST
def check_gmst():
    g = os.path.join(TOOLS, 'gmst')
    en = json.load(open(os.path.join(g, 'gmst_en.json'), encoding='utf-8'))
    uk = json.load(open(os.path.join(g, 'uk_gmst.json'), encoding='utf-8'))
    uk.pop('_comment', None)
    for k, v in uk.items():
        if k not in en:
            err('uk_gmst.json: немає такого налаштування в оригіналі: %s' % k)
            continue
        encodable(v, 'uk_gmst.json[%s]' % k)
        want = sorted(set(TOKEN.findall(en[k])))
        got = sorted(set(TOKEN.findall(v)))
        lost = set(want) - set(got)
        if lost:
            err('uk_gmst.json[%s]: втрачено підстановки %s' % (k, ', '.join(sorted(lost))))
    return len(uk), len(en)


pairs = check_slices()
topics_done, topics_all = check_topics()
gmst_done, gmst_all = check_gmst()

print('перекладених рядків у зрізах : %d' % pairs)
print('теми діалогів                : %d / %d' % (topics_done, topics_all))
print('рядки інтерфейсу             : %d перекладено з %d наявних' % (gmst_done, gmst_all))
print()
for w in warnings:
    print('  ? %s' % w)
for e in errors:
    print('  ! %s' % e)
print()
print('помилок: %d, попереджень: %d' % (len(errors), len(warnings)))
raise SystemExit(1 if errors else 0)
