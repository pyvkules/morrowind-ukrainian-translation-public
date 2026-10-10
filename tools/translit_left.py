# -*- coding: utf-8 -*-
"""Описова назва, яку переписали кирилицею замість перекласти.

Навіщо
------
«Used Clutter Salesman» потрапив у словник як «Усед Клуттер Салесман», а
«Big Head» як «Біг Геад» - і то при тому, що в журналі той самий аргоніанин
зветься «Велика Голова». Жодна наявна перевірка цього не бачила:

* `q.py dup` порівнює переклади за однаковим ключем, а тут ключ один;
* `name_drift.py` шукає схожі написання одного імені, а «Біг Геад» і
  «Велика Голова» не схожі зовсім - це різні слова, не різні написання.

Так виглядає машинна транслітерація, що проїхала по рядку, якого насправді
треба було перекласти. Гравець бачить напис над НПЦ латиницею навиворіт.

Як шукаємо
----------
1. Словник англійської беремо з самої гри: слово, що трапляється в репліках
   **з малої літери** щонайменше 30 разів, це звичайне слово, а не ім'я.
2. Для кожного слова ключа, яке є в тому словнику, рахуємо побуквенну
   транслітерацію і шукаємо її серед слів перекладу.
3. Збіг - знахідка: слово лишилося тим самим, тільки іншими літерами.

Лишається список запозичень, де транслітерація **і є** перекладом: форт,
легіон, амулет, катана, гуар, квама. Він у `LOAN` і дописується вручну -
автоматично відрізнити «амулет» від «салесмана» не можна.

    py tools/translit_left.py        # 0 - чисто, 1 - є знахідки
"""
import codecs
import collections
import glob
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                              errors='replace', write_through=True)

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'src')
MIN_FREQ = 30
NEAR = 0.65

# Файли назв: там живуть описові назви, і там траплялися помилки.
FILES = ['items/uk_npc.json', 'items/npc_overrides.json',
         'items/uk_creature.json', 'items/creature_overrides.json',
         'items/uk_class.json', 'items/class_overrides.json',
         'items/uk_misc.json', 'items/misc_overrides.json',
         'items/uk_armour.json', 'items/armour_overrides.json',
         'items/uk_weapon.json', 'items/weapon_overrides.json',
         'items/uk_clothing.json', 'items/clothing_overrides.json']

# Побуквенна транслітерація - така сама, якою машина й попсувала назви.
TAB = [('sch', 'ш'), ('sh', 'ш'), ('ch', 'ч'), ('th', 'т'), ('ph', 'ф'),
       ('ck', 'к'), ('kh', 'х'), ('zh', 'ж'), ('ya', 'я'), ('yu', 'ю'),
       ('ye', 'є'), ('yi', 'ї'), ('ee', 'і'), ('oo', 'у'), ('ou', 'у'),
       ('a', 'а'), ('b', 'б'), ('c', 'к'), ('d', 'д'), ('e', 'е'), ('f', 'ф'),
       ('g', 'г'), ('h', 'г'), ('i', 'і'), ('j', 'дж'), ('k', 'к'),
       ('l', 'л'), ('m', 'м'), ('n', 'н'), ('o', 'о'), ('p', 'п'),
       ('q', 'к'), ('r', 'р'), ('s', 'с'), ('t', 'т'), ('u', 'у'),
       ('v', 'в'), ('w', 'в'), ('x', 'кс'), ('y', 'и'), ('z', 'з')]

# Запозичення: транслітерація тут і є правильним перекладом.
LOAN = set('''
agent aloe alms amulet aren ashkhan assassin bar big boss both catacombs
clan company contract corprus cross daedra dagoth don draugr dreugh fell
figure flin form fort fortune general gra gro guar guy herd hero heroes
kagouti kanet katana kwama lah legion long lord lords mage magic magicka
man map marshmerrow mazte mere metal mine muck nature necromancer
necromancers necromancy netch nix orc order plans port rather relic robe
scamp seen shalk ship skooma sold standard star statue sujamma teleport
three throne urn vampire vampirism vera wine
'''.split())


def load(path):
    with open(path, 'rb') as f:
        raw = f.read()
    if raw[:2] in (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE):
        return json.loads(raw.decode('utf-16'))
    return json.loads(raw.decode('utf-8-sig'))


def translit(word):
    w = word.lower()
    out = []
    i = 0
    while i < len(w):
        for en, uk in TAB:
            if w.startswith(en, i):
                out.append(uk)
                i += len(en)
                break
        else:
            out.append(w[i])
            i += 1
    return ''.join(out)


def near(a, b):
    """Частка спільного початку: відмінок міняє хвіст, а не початок."""
    n = 0
    while n < len(a) and n < len(b) and a[n] == b[n]:
        n += 1
    return n / float(max(len(a), len(b)) or 1)


def vocabulary():
    """Звичайні англійські слова за самою грою."""
    freq = collections.Counter()
    for path in glob.glob(os.path.join(SRC, '*.json')):
        data = load(path)
        rows = data.values() if isinstance(data, dict) else data
        for s in rows:
            if isinstance(s, str):
                freq.update(re.findall(r'\b[a-z]{3,}\b', s))
    return set(w for w, n in freq.items() if n >= MIN_FREQ)


def main():
    vocab = vocabulary() - LOAN
    if len(vocab) < 500:
        print('словник гри надто малий (%d) - зрізів немає?' % len(vocab))
        return 0
    found = []
    for rel in FILES:
        path = os.path.join(HERE, *rel.split('/'))
        if not os.path.isfile(path):
            continue
        data = load(path)
        if not isinstance(data, dict):
            continue
        for key, val in sorted(data.items()):
            if not isinstance(val, str):
                continue
            words = [w for w in re.findall(r'[A-Za-z]+', key)
                     if w.lower() in vocab]
            if not words:
                continue
            ours = re.findall(r'[^\W\d_]+', val, re.UNICODE)
            for en in words:
                t = translit(en)
                for uk in ours:
                    if near(t, uk.lower()) > NEAR:
                        found.append((rel, key, val, en, uk))
                        break
    for rel, key, val, en, uk in found:
        print('%-30s %-32s %-32s %s -> %s' % (rel, key, val, en, uk))
    print('назв, переписаних замість перекладених: %d' % len(found))
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main())
