# -*- coding: utf-8 -*-
"""Книги з однаковим ТЕКСТОМ, але різними НАЗВАМИ.

`propagate.py` і черга «найбільша група першою» групують книги за назвою. Через
це ціла родина копій лишалася невидимою: «Odral's History of the Empire 2» і
«Brief History of the Empire v 2» - той самий текст, що приїхав із двох різних
плагінів під двома різними обкладинками. Один переклад закриває обидві, але
дізнатися про це, дивлячись на назви, неможливо.

Тут групуємо за самим текстом, знеособленим до пробілів і розділових знаків, і
показуємо лише ті групи, де назви різні. Підпис послідовності тегів мусить
збігтися - інакше це не той самий запис, а схожий.

Знайдене НЕ переноситься автоматично: `propagate.py` навмисно не чіпає копій,
що різняться словами, і тут те саме. Скрипт лише каже, де шукати.

Usage: py same_text.py
"""
import io
import json
import os
import re
import sys
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(HERE, '_source.json')
if not os.path.isfile(src_path):
    raise SystemExit('нема _source.json - спершу py extract_books.py '
                     '(потрібна копія гри, тому в CI цього скрипта не ганяємо)')

src = json.load(open(src_path, encoding='utf-8'))
meta = json.load(open(os.path.join(HERE, 'books_meta.json'), encoding='utf-8'))
uk = json.load(open(os.path.join(HERE, 'uk_books.json'), encoding='utf-8'))
uk.pop('_comment', None)

WS = re.compile(r'\s+')
PUNCT = re.compile(r'[^\w<>=/"\s]', re.UNICODE)
CURLY = {'“': '"', '”': '"', '‘': "'", '’': "'"}


def bare(text):
    """Текст без розділових знаків і зайвих пробілів.

    PUNCT лишає " навмисно - вона тримає атрибути тегів. Тому криві лапки треба
    звести до прямих ЩЕ ДО зачистки: інакше копія з «"» і копія з «“» дадуть
    різні ключі, і Odral 1 з Brief History v1 не зійдуться, хоч це один текст.
    """
    for bad, good in CURLY.items():
        text = text.replace(bad, good)
    return WS.sub(' ', PUNCT.sub('', text)).strip()


groups = defaultdict(list)
for k, m in meta.items():
    # notext теж пропускаємо: без нього тут вічно висіла пара суцільно
    # даедричних сувоїв, яку перекласти неможливо в принципі
    if m.get('notext') or m.get('devnote') or not m.get('chars'):
        continue
    groups[(bare(src[k]), m['tagsig'])].append(k)

rows = []
for keys in groups.values():
    titles = {meta[k]['title'] for k in keys}
    if len(titles) < 2:
        continue                     # звичайні близнюки - їх уже видно за назвою
    left = [k for k in keys if k not in uk]
    if not left:
        continue
    rows.append((len(left), meta[keys[0]]['chars'], sorted(titles), keys))

rows.sort(key=lambda r: -r[0] * r[1])
free = 0
for n, chars, titles, keys in rows:
    have = [k for k in keys if k in uk]
    free += n * chars if have else (n - 1) * chars
    print('%2d незакритих x %6d  %s%s'
          % (n, chars, ' | '.join(t[:34] for t in titles),
             '   <- переклад уже є: ' + have[0] if have else ''))
    print('      %s' % ' '.join(keys))

print('\nгруп із різними назвами: %d, символів даром: %d' % (len(rows), free))
