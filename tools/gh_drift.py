# -*- coding: utf-8 -*-
"""Одне слово, написане і через «г», і через «ґ».

§4 CONVENTIONS зводить `g` до **г**, та лишає ґ там, де корпус висловився
ясно, і саме через цей виняток у перекладі живуть обидві літери. Поки вони
обидві законні, лишається третя біда: те саме слово в різних місцях пишуть
по-різному. `Гаафінгар` у вивісці й `Гаафінґарська` у фракції - для гравця
дві різні назви, а `q.py dup` їх не бачить, бо ключі різні, і `name_drift`
теж, бо він ходить лише по іменах зі словника імен.

Тут питання ставиться по слову: беремо кожне слово з усіх перекладів,
зводимо ґ до г і дивимося, чи під одним стемом не лежать обидва написання.

Орківська частка `gro-/gra-` свідомо лишається відкритою (§4: ґро 122 : гро
73), тож вона в `GH_OPEN` і не рахується.

    py tools\\gh_drift.py            # усі слова з обома написаннями
    py tools\\gh_drift.py --min 5    # лише ті, де одне написання переважає 5:1

Вихід 1, якщо знайшлося хоч одне слово.
"""
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# Питання, свідомо лишені відкритими в §4.
GH_OPEN = (u'гро', u'гра',
           u'гро-', u'гра-')

WORD = re.compile(u'[А-ЯІЇЄҐ'
                  u'а-яіїєґ\']{3,}')
GE, ge = u'Ґ', u'ґ'
HE, he = u'Г', u'г'


def sources():
    yield from sorted(glob.glob(os.path.join(HERE, 'items', '*_overrides.json')))
    yield from sorted(glob.glob(os.path.join(HERE, 'topics', 'uk_dial_topics*.json')))
    yield from sorted(glob.glob(os.path.join(HERE, 'uk', '*.json')))
    p = os.path.join(HERE, 'books', 'uk_books.json')
    if os.path.isfile(p):
        yield p


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  newline='\n')
    ratio = 0
    if '--min' in sys.argv:
        ratio = float(sys.argv[sys.argv.index('--min') + 1])

    words = {}
    for p in sources():
        d = json.loads(io.open(p, encoding='utf-8-sig').read())
        vals = d.values() if isinstance(d, dict) else d
        for v in vals:
            if not isinstance(v, str):
                continue
            for w in WORD.findall(v):
                low = w.lower()
                key = low.replace(ge, he)
                words.setdefault(key, {})
                words[key][low] = words[key].get(low, 0) + 1

    found = 0
    rows = []
    for key, forms in words.items():
        if key in GH_OPEN:
            continue
        with_ge = [f for f in forms if ge in f]
        without = [f for f in forms if ge not in f]
        if not with_ge or not without:
            continue
        a = sum(forms[f] for f in with_ge)
        b = sum(forms[f] for f in without)
        hi, lo = max(a, b), min(a, b)
        if ratio and (lo == 0 or float(hi) / lo < ratio):
            continue
        rows.append((hi - lo, key, a, b, forms))
    rows.sort(reverse=True)
    for _d, key, a, b, forms in rows:
        found += 1
        print(u'%-24s ґ %-4d г %-4d  %s'
              % (key, a, b,
                 ', '.join('%s %d' % (f, n)
                           for f, n in sorted(forms.items(), key=lambda x: -x[1]))))
    print(u'слів, написаних і через г, і через ґ: %d' % found)
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main())
