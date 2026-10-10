# -*- coding: utf-8 -*-
"""Тема зветься так, а в репліках її звуть інакше.

Навіщо
------
Тему гравець бачить двічі: у списку тем і всередині репліки, де на неї веде
посилання. Обидва написання беруться з різних місць - перше з
`uk_dial_topics*.json`, друге з перекладу самої репліки, - і вони розходилися:

* `Estate Sale` - тема «розпродаж маєтку», а в п'ятьох репліках «розпродаж майна»;
* `Brallion's Ring` - тема «перстень Брелліона», а в прозі п'ятнадцять «Бралліона»;
* `Mordrin Hanin` - тема «Ханін», а в прозі двадцять дев'ять «Ганін»;
* `Reavers` - тема «Грабіжники», а в Бладмуні це «наскочники».

Наслідок не косметичний: `mark_topics.py` робить клікабельною ту згадку, що
збігається з назвою теми. Не збіглася - посилання немає, і гравець читає про
«розпродаж майна», а в списку тем шукає «розпродаж маєтку».

`name_drift.py` цього не бачить: він порівнює написання **в прозі**, а назва
теми лежить у словнику й у прозу не потрапляє.

Як шукаємо
----------
1. Беремо тему, англійська назва якої має велику літеру: власна назва, ім'я,
   назва речі. Для таких розбіжність це помилка, а не переказ.
2. Знаходимо перекладені репліки, чий **англійський** текст містить цю
   англійську назву (менше трьох - замало даних, пропускаємо).
3. Кожне слово української назви від п'яти літер шукаємо в тих перекладах за
   першими чотирма літерами - відмінок міняє хвіст, а не початок.
4. Слова немає в жодному перекладі - тема зветься інакше, ніж проза.

Що в `topic_prose_ok.json`
--------------------------
Теми-фрази, де переклад свідомо переказав думку іншими словами: `Daedra
worship` - тема «поклоніння даедра», а в репліках «шанувальники даедра». Це не
назва речі, посилання там і не потрібне. Кожен запис з причиною.

    py tools/topics/topic_prose.py        # 0 - чисто, 1 - є розбіжності
"""
import codecs
import glob
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                              errors='replace', write_through=True)

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.abspath(os.path.join(HERE, '..'))
SRC = os.path.join(TOOLS, 'src')
UK = os.path.join(TOOLS, 'uk')

MIN_LINES = 3      # менше - замало даних
MIN_WORD = 5       # коротке слово надто часто збігається випадково
PREFIX = 4         # за початком слова, бо відмінок міняє хвіст
MIN_TEXT = 25      # короткі рядки це самі назви, а не проза


def load(path):
    with open(path, 'rb') as f:
        raw = f.read()
    if raw[:2] in (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE):
        return json.loads(raw.decode('utf-16'))
    return json.loads(raw.decode('utf-8-sig'))


def topics():
    """Англійська назва теми -> українська."""
    src = load(os.path.join(HERE, 'dial_topics.json'))
    uk = {}
    for path in sorted(glob.glob(os.path.join(HERE, 'uk_dial_topics*.json'))):
        for key, val in load(path).items():
            uk[int(key)] = val
    return [(en, uk[i]) for i, en in enumerate(src) if i in uk]


def prose():
    """Пари «англійський рядок -> переклад» з усіх зрізів, у нижньому регістрі."""
    pairs = []
    for path in sorted(glob.glob(os.path.join(SRC, '*.json'))):
        name = os.path.basename(path)[:-5]
        tr = {}
        for part in sorted(glob.glob(os.path.join(UK, name + '.json'))
                           + glob.glob(os.path.join(UK, name + '_p*.json'))):
            tr.update(load(part))
        if not tr:
            continue
        rows = load(path)
        if not isinstance(rows, list):
            continue
        for i, text in enumerate(rows):
            ours = tr.get(str(i))
            if ours and isinstance(text, str) and len(text) >= MIN_TEXT:
                pairs.append((text.lower(), ours.lower()))
    return pairs


def proper(en):
    """Власна назва: велика літера не лише на початку речення."""
    return any(c.isupper() for c in en[1:]) or en[0].isupper()


def main():
    allow_path = os.path.join(HERE, 'topic_prose_ok.json')
    allow = set(load(allow_path)) if os.path.isfile(allow_path) else set()
    pairs = prose()
    if len(pairs) < 100:
        print('перекладених реплік надто мало (%d) - зрізів немає?' % len(pairs))
        return 0
    found = []
    for en, ours in topics():
        if len(en) < 5 or not proper(en) or en in allow:
            continue
        low = en.lower()
        hits = [t for s, t in pairs if low in s]
        if len(hits) < MIN_LINES:
            continue
        all_words = re.findall(r'[^\W\d_]+', ours.lower(), re.UNICODE)
        if not any(len(w) >= MIN_WORD for w in all_words):
            continue
        # У взірець ідуть усі слова, навіть короткі: без них поруч стояли б
        # «Джентльмен» і «Стейсі», а між ними в прозі є «Джим».
        words = [w[:PREFIX] for w in all_words]
        # назва мусить стояти в прозі цілою: слова поруч і в тому ж порядку,
        # лише з іншими хвостами. Інакше «розпродаж маєтку» вважався б знайденим
        # у репліці, де окремо є «розпродаж» і окремо «маєтку Тендас».
        rx = re.compile(r'\W+'.join(w + r'[^\W\d_]*' for w in words),
                        re.UNICODE)
        if any(rx.search(t) for t in hits):
            continue
        found.append((en, ours, ' '.join(words), len(hits), hits[0]))
    for en, ours, word, n, sample in found:
        print('%-30s %-30s немає «%s» у %d репліках'
              % (en, ours, word[:PREFIX], n))
        print('    %s' % sample[:110])
    print('тем, що розійшлися з прозою: %d' % len(found))
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main())
