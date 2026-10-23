# -*- coding: utf-8 -*-
"""Де переклад книги втратив або додав перенос рядка.

У книгах Морровінда розкладку сторінки тримають не лише теги `<BR>`, а й
звичайні переноси всередині тексту: так зверстано списки в «Імперській
кухні» і всі загадки в «Кендголській книзі». Підпис тегів такої втрати не
бачить - тегів лишається стільки ж.

    py tools\books\linebreaks.py          # зведення
    py tools\books\linebreaks.py <хеш>    # по шматках: де саме розійшлося

Потрібен `_source.json`, тож у CI це не йде: там замість першотвору
стоїть поле `nl` у `books_meta.json`, яке звіряє `check_sources.py`.
"""
import io
import json
import os
import re
import sys

REPO = r'E:\Morrowind\OpenMW\mods\morrowind-ukrainian-translation\tools\books'
TAG = re.compile(r'<[^>]*>')
NL = re.compile(r'(\r\n|\n|\r)')


def load(name):
    return json.loads(io.open(os.path.join(REPO, name), encoding='utf-8-sig').read())


def texts(s):
    """Самі текстові шматки між тегами, по порядку."""
    out, pos = [], 0
    for m in TAG.finditer(s):
        out.append(s[pos:m.start()])
        pos = m.end()
    out.append(s[pos:])
    return out


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='replace', write_through=True)
    src, uk, meta = load('_source.json'), load('uk_books.json'), load('books_meta.json')
    uk.pop('_comment', None)
    one = sys.argv[1] if len(sys.argv) > 1 else None
    bad = 0
    for k, v in sorted(uk.items(), key=lambda kv: meta.get(kv[0], {}).get('title', '')):
        if k not in src:
            continue
        a, b = src[k].count('\n'), v.count('\n')
        if a == b:
            continue
        bad += 1
        if one and k != one:
            continue
        print('%s %-34s %d -> %d' % (k, meta[k]['title'], a, b))
        if not one:
            continue
        ta, tb = texts(src[k]), texts(v)
        for i, (ca, cb) in enumerate(zip(ta, tb)):
            na, nb = ca.count('\n'), cb.count('\n')
            if na != nb:
                print('  шматок %d: переносів %d -> %d' % (i, na, nb))
                print('    en %s' % repr(ca)[:300])
                print('    uk %s' % repr(cb)[:300])
    print('книг із іншою кількістю переносів: %d' % bad)


if __name__ == '__main__':
    main()
