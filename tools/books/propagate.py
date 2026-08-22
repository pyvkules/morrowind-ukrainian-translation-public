# -*- coding: utf-8 -*-
"""Перенести переклад книги на її близнюків з інших плагінів.

Та сама книга приходить із кількох плагінів і щоразу трохи інакша: десь \\r\\n
замість \\n, десь зайвий пробіл перед тегом. Хеш через це різний, і в черзі
книга висить двічі-тричі. Виміряно: у майже однакових копіях лежить близько
2 млн символів - чверть усього, що лишилося перекласти.

Що дозволяє перенести
---------------------
Гравець бачить не байти, а зверстану сторінку. Тому близнюкові НЕ потрібне
те саме розташування пробілів - йому потрібен той самий текст і та сама
послідовність тегів. Саме послідовність тегів і перевіряє CI (check_sources).

Переносимо у двох випадках, обидва потребують однакового підпису тегів:

  1. тексти збігаються після згортання пробілів - різниця суто в оформленні;
  2. тексти збігаються ще й після викидання розділових знаків - у плагінах
     різняться лише коми та крапки. Український текст має власну пунктуацію,
     тож на переклад це не впливає.

Далі не йдемо. Різниця бодай в одному СЛОВІ - це вже інша редакція; такі пари
скрипт показує окремо (--near), і їх перекладає людина.

    py tools\\books\\propagate.py            # показати, що перенесеться
    py tools\\books\\propagate.py --apply    # записати в uk_books.json
    py tools\\books\\propagate.py --near     # майже-близнюки: різниця в тексті
"""
import difflib
import io
import json
import os
import re
import sys
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                              errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
APPLY = '--apply' in sys.argv
NEAR = '--near' in sys.argv
WS = re.compile(r'\s+')


PUNCT = re.compile(r'[^\w<>=/"\s]', re.UNICODE)


def squash(text):
    """Текст без пробільних відмінностей: саме за ним визначаємо близнюків."""
    return WS.sub(' ', text).strip()


def bare(text):
    """Ще й без розділових знаків — другий, ширший рівень спорідненості.

    Кому чи крапку в українському тексті ми ставимо свою, тож різниця в них
    між англійськими копіями на переклад не впливає. Кутові дужки, лапки
    й скісну лишаємо: вони тримають розмітку.
    """
    return WS.sub(' ', PUNCT.sub('', text)).strip()


def main():
    src_path = os.path.join(HERE, '_source.json')
    if not os.path.isfile(src_path):
        print('нема _source.json — спершу py tools\\books\\extract_books.py --apply')
        return 1
    meta = json.load(open(os.path.join(HERE, 'books_meta.json'), encoding='utf-8'))
    src = json.load(open(src_path, encoding='utf-8'))
    ukp = os.path.join(HERE, 'uk_books.json')
    uk = json.load(open(ukp, encoding='utf-8'))
    comment = uk.pop('_comment', None)

    work = [k for k in src if not (meta.get(k, {}).get('notext')
                                   or meta.get(k, {}).get('devnote'))]

    moved = {'пробіли': 0, 'розділові': 0}
    waiting = chars = skipped = 0
    for level, key in (('пробіли', squash), ('розділові', bare)):
        groups = defaultdict(list)
        for k in work:
            groups[key(src[k])].append(k)
        for ks in groups.values():
            if len(ks) < 2:
                continue
            done = [k for k in ks if k in uk]
            left = [k for k in ks if k not in uk]
            if not left:
                continue
            if not done:
                if level == 'розділові':
                    # перекладемо одну — решта поїдуть слідом наступним запуском
                    waiting += len(left) - 1
                    chars += sum(meta[k]['chars'] for k in left[1:])
                continue
            base = done[0]
            for k in left:
                if meta[k]['tagsig'] != meta[base]['tagsig']:
                    skipped += 1      # теги переставлено — копіювати не можна
                    continue
                uk[k] = uk[base]
                moved[level] += 1
                if not APPLY and moved[level] <= 4:
                    print('  %-10s %-40s %6d символів'
                          % (level, meta[k]['title'][:38], meta[k]['chars']))

    print('перенесено: %d (різниця в пробілах) + %d (у розділових знаках)'
          % (moved['пробіли'], moved['розділові']))
    if skipped:
        print('пропущено (інші теги)   : %d' % skipped)
    print('чекають на свій оригінал: %d книг, %d символів' % (waiting, chars))

    if NEAR:
        print('\n-- майже-близнюки: різняться словом-двома, перенести не можна --')
        print('   (перекладіть перший, а в другому змініть саме це)')
        titles = defaultdict(list)
        for k in work:
            if k not in uk:
                titles[meta[k]['title']].append(k)
        rows = []
        for title, ks in titles.items():
            if len(ks) < 2:
                continue
            ks.sort(key=lambda k: meta[k]['chars'])
            a, b = bare(src[ks[0]]), bare(src[ks[1]])
            sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
            if sm.ratio() <= 0.98:
                continue
            edits = [(t, a[i1:i2], b[j1:j2])
                     for t, i1, i2, j1, j2 in sm.get_opcodes() if t != 'equal']
            rows.append((len(edits), title, len(ks),
                         sum(meta[k]['chars'] for k in ks), edits))
        rows.sort()
        for n_ed, t, n, c, edits in rows[:30]:
            print('  %-44s %d копій, %d символів' % (t[:42], n, c))
            for tag, x, y in edits[:3]:
                print('      %-8s %r -> %r' % (tag, x[:50], y[:50]))
        print('  разом майже-близнюків: %d назв, %d символів'
              % (len(rows), sum(r[3] for r in rows)))

    if not APPLY:
        print('(без --apply нічого не записано)')
        return 0
    if comment is not None:
        uk['_comment'] = comment
    json.dump(uk, open(ukp, 'w', encoding='utf-8'), ensure_ascii=False,
              indent=1, sort_keys=True)
    print('записано uk_books.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
