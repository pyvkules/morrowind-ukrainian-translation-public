# -*- coding: utf-8 -*-
"""Та сама проза під іншою розміткою: пересадити переклад у чужий скелет.

`propagate.py` переносить переклад лише тоді, коли підпис тегів у копій
збігається. Це слушна обережність, але через неї цілий клас копій лишався
поза механізмом: проза в них слово в слово та сама, а теги різні. Найчастіше
це мапи - той самий підпис під іншим файлом картинки:

    Map of Skyrim   <IMG SRC="tr\\map_skyrim.dds" ...>
    Map of Skyrim   <IMG SRC="pc\\pc_map_skyrim.dds" ...>

Виміряно: таких пар у вже перекладеному 18, і кожну довелося набивати руками.

Що робимо
---------
Книгу розкладаємо на чергу шматків: теги і текст між ними. Якщо в двох книг
послідовність **текстових** шматків однакова (з точністю до пробілів), то
переклад однієї можна перекласти в скелет другої: беремо ЇЇ теги і ЇЇ
пробіли, а текст підставляємо перекладений.

Підпис тегів у результаті - це підпис самої цільової книги, тож перевірка
`check_sources` лишається чинною й нічого не послаблюється.

Чого НЕ робимо
--------------
Якщо різняться самі слова - це інша редакція книги, і пересадка тут була б
підміною. Такі пари й далі показує `propagate.py --near`, і їх править людина.

    py tools\\books\\transplant.py            # показати, що пересадиться
    py tools\\books\\transplant.py --apply    # записати в uk_books.json
"""
import io
import json
import os
import re
import sys
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                              errors='replace', write_through=True)

HERE = os.path.dirname(os.path.abspath(__file__))
APPLY = '--apply' in sys.argv
PIECE = re.compile(r'(<[^>]+>)')
WS = re.compile(r'\s+')
PUNCT = re.compile(r'[^\w<>=/\s]', re.UNICODE)


def pieces(text):
    """Книга як черга шматків: теги і текст між ними, у порядку файлу."""
    return PIECE.split(text)


def runs(text, key=False):
    """Лише текстові шматки, знеособлені до пробілів; порожні відкидаємо.

    `key=True` викидає ще й розділові знаки - саме за таким виглядом ми
    вирішуємо, чи це та сама проза. Плагіни розходяться комами й лапками
    (то пряма ", то криві “ ”), а українська пунктуація однаково своя.
    """
    out = []
    for i, p in enumerate(pieces(text)):
        if i % 2:
            continue                      # непарні - це самі теги
        s = WS.sub(' ', PUNCT.sub('', p) if key else p).strip()
        if s:
            out.append(s)
    return out


def graft(target_en, source_uk):
    """Скелет цільової книги + перекладений текст із книги-донора."""
    want = runs(source_uk)
    out, n = [], 0
    for i, p in enumerate(pieces(target_en)):
        if i % 2 or not WS.sub(' ', p).strip():
            out.append(p)
            continue
        if n >= len(want):
            return None
        head = p[:len(p) - len(p.lstrip())]
        tail = p[len(p.rstrip()):]
        out.append(head + want[n] + tail)
        n += 1
    if n != len(want):
        return None
    return ''.join(out)


def main():
    src_path = os.path.join(HERE, '_source.json')
    if not os.path.isfile(src_path):
        print('нема _source.json - спершу py tools\\books\\extract_books.py --apply')
        return 1
    with io.open(src_path, encoding='utf-8-sig') as f:
        src = json.load(f)
    with io.open(os.path.join(HERE, 'books_meta.json'), encoding='utf-8-sig') as f:
        meta = json.load(f)
    ukp = os.path.join(HERE, 'uk_books.json')
    with io.open(ukp, encoding='utf-8-sig') as f:
        uk = json.load(f)
    comment = uk.pop('_comment', None)

    work = [k for k in src if not (meta.get(k, {}).get('notext')
                                   or meta.get(k, {}).get('devnote'))]
    groups = defaultdict(list)
    for k in work:
        r = runs(src[k], key=True)
        if r:
            groups[tuple(r)].append(k)

    grafted = mismatch = 0
    chars = 0
    for ks in groups.values():
        if len(ks) < 2:
            continue
        done = [k for k in ks if uk.get(k)]
        left = [k for k in ks if not uk.get(k)]
        if not done or not left:
            continue
        base = done[0]
        if len(runs(uk[base])) != len(runs(src[base])):
            mismatch += 1        # перекладач змінив кількість абзаців
            continue
        for k in left:
            new = graft(src[k], uk[base])
            if new is None:
                mismatch += 1
                continue
            uk[k] = new
            grafted += 1
            chars += meta[k]['chars']
            if grafted <= 12:
                print('  %-44s <- %s  %6d символів'
                      % (meta[k]['title'][:44], meta[base]['title'][:26],
                         meta[k]['chars']))

    print()
    print('пересаджено: %d книг, %d символів' % (grafted, chars))
    if mismatch:
        print('не вдалося (абзаци не сходяться): %d' % mismatch)
    if APPLY and grafted:
        if comment is not None:
            uk['_comment'] = comment
        with open(ukp, 'w', encoding='utf-8') as f:
            json.dump(uk, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write('\n')
        print('ЗАПИСАНО uk_books.json')
    elif not APPLY:
        print('(без --apply нічого не записано)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
