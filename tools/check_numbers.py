# -*- coding: utf-8 -*-
"""Чи не розійшлися числа: в оригіналі одна сума, у перекладі інша.

Навіщо
------
`inherit.py` і `reuse.py` переносять готовий переклад на репліку, що
відрізняється від уже перекладеної дрібницею. Доки `letters()` викидала цифри
разом із розділовими знаками, `500 септимів` і `100 септимів` зводилися до
того самого ряду - і запис діставав переклад із чужою сумою. «Patch for
Purists» саме винагороди й виправляє, тож чотири такі суми встигли потрапити
в наш переклад, і жодна інша перевірка їх не бачила: текст правильний
український, підстановки на місці, латиниці нема.

Діру заткнуто (цифри лишилися в `letters()`, а `only_typos` не заміняє слів
із цифрами), але клас помилки лишається можливим - руками теж можна набрати
не ту суму. Тому тут окрема охорона.

Що вважаємо помилкою
--------------------
Тільки **підміну**: в оригіналі є число, якого нема в перекладі, І в перекладі
є число, якого нема в оригіналі. Самого лише зникнення числа замало - книги
часто пишуть його словом («Тисяча духів Старого Сироду», «п'ятирічна війна»),
і це свідомий вибір, а не втрата.

Розділові знаки в тисячах не рахуються: `11,111` і `11 111` - те саме число.

    py tools\\check_numbers.py          # 0 - усе гаразд, 1 - є розбіжності
"""
import glob
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                              errors='replace', write_through=True)

HERE = os.path.dirname(os.path.abspath(__file__))
NUM = re.compile(r'\d[\d\s,. ]*\d|\d')


def load(path):
    with open(path, 'rb') as f:
        raw = f.read()
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return json.loads(raw.decode('utf-16'))
    return json.loads(raw.decode('utf-8-sig'))


def nums(text):
    """Числа тексту без роздільників тисяч: `11,111` і `11 111` - те саме."""
    return set(re.sub(r'[\s,. ]', '', m.group(0)) for m in NUM.finditer(text))


def swapped(en, uk):
    """Число підмінено іншим (а не просто записано словом)."""
    a, b = nums(en), nums(uk)
    return (a - b) and (b - a)


def main():
    bad = 0
    for path in sorted(glob.glob(os.path.join(HERE, 'src', '*.json'))):
        name = os.path.basename(path)[:-5]
        src = load(path)
        if not isinstance(src, list):
            continue
        uk = {}
        for q in sorted(glob.glob(os.path.join(HERE, 'uk', name + '.json'))
                        + glob.glob(os.path.join(HERE, 'uk', name + '_p*.json'))):
            uk.update(load(q))
        for i, en in enumerate(src):
            v = uk.get(str(i))
            if isinstance(en, str) and v and swapped(en, v):
                bad += 1
                print('%s:%d  %s -> %s' % (name, i, sorted(nums(en)), sorted(nums(v))))
                print('   EN %s' % en[:150].replace('\r\n', ' '))
                print('   UK %s' % v[:150].replace('\r\n', ' '))

    books = os.path.join(HERE, 'books')
    src = load(os.path.join(books, '_source.json'))
    uk = load(os.path.join(books, 'uk_books.json'))
    for k, en in sorted(src.items()):
        v = uk.get(k)
        if v and swapped(en, v):
            bad += 1
            print('книга %s  %s -> %s'
                  % (k[:10], sorted(nums(en))[:12], sorted(nums(v))[:12]))

    print('розбіжностей у числах: %d' % bad)
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
