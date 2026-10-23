# -*- coding: utf-8 -*-
"""Заповнити рядки зрізу, чий англійський текст відрізняється від уже
перекладеного **лише розділовими знаками й регістром**.

Навіщо
------
«Patch for Purists» перевизначає ванільні репліки, виправляючи в них
пунктуацію: `....` на `...`, `Hmmm...well` на `Hmmm... well`, зайвий
апостроф, кому. `inherit.py` таких не бере, бо він іде за id запису й
вимагає, щоб різнилися тільки слова; `same_text_fill.py` теж, бо для
нього текст мусить збігтися слово в слово разом із пунктуацією.

А для гравця це той самий рядок. Рівень рівності тут такий самий, який
`books/propagate.py` уже вважає безпечним для книг (рівень 2: згорнути
пробіли **і** викинути пунктуацію).

Що робить із перекладом
-----------------------
Копіює переклад близнюка й заразом зводить `....` і довші хвости точок
до `...`, бо саме це мод і виправляв. Більше нічого не змінює: якщо в
перекладі є щось, що правки потребує, це видно з `--show`.

    py tools\\dialogue\\near_text_fill.py <зріз>           # показати лік
    py tools\\dialogue\\near_text_fill.py <зріз> --show    # показати пари
    py tools\\dialogue\\near_text_fill.py <зріз> --apply   # записати
"""
import codecs
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
SRC, UK = os.path.join(TOOLS, 'src'), os.path.join(TOOLS, 'uk')

PUNCT = re.compile(r"[^0-9a-z%&_]+")
DOTS = re.compile(r'\.{4,}')


def load(path):
    raw = open(path, 'rb').read()
    if raw[:2] in (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE):
        return json.loads(raw.decode('utf-16'))
    return json.loads(raw.decode('utf-8-sig'))


def key(s):
    """Те саме речення, якщо лишити самі літери, цифри й підстановки."""
    return PUNCT.sub(' ', s.lower()).strip()


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='replace', write_through=True)
    name = sys.argv[1]
    apply = '--apply' in sys.argv
    show = '--show' in sys.argv

    done = {}
    for path in sorted(glob.glob(os.path.join(SRC, '*.json'))):
        n = os.path.basename(path)[:-5]
        if n.endswith('.topics') or n == name:
            continue
        src = load(path)
        if not isinstance(src, list):
            continue
        for part in sorted(glob.glob(os.path.join(UK, n + '.json'))
                           + glob.glob(os.path.join(UK, n + '_p*.json'))):
            uk = load(part)
            for k, v in uk.items():
                i = int(k) if k.isdigit() else -1
                if i < 0 or i >= len(src) or not isinstance(src[i], str):
                    continue
                if isinstance(v, str) and v.strip():
                    done.setdefault(key(src[i]), (n, i, v))

    src = load(os.path.join(SRC, name + '.json'))
    hit = 0
    for part in sorted(glob.glob(os.path.join(UK, name + '.json'))
                       + glob.glob(os.path.join(UK, name + '_p*.json'))):
        uk = load(part)
        was = len(uk)
        for i, s in enumerate(src):
            if not isinstance(s, str) or not s.strip() or uk.get(str(i)):
                continue
            twin = done.get(key(s))
            if not twin:
                continue
            hit += 1
            text = DOTS.sub('...', twin[2])
            if show:
                print('%s:%d <- %s:%d' % (name, i, twin[0], twin[1]))
                print('   %s' % ' '.join(text.split())[:150])
            if apply:
                uk[str(i)] = text
        if apply and len(uk) != was:
            with io.open(part, 'w', encoding='utf-8', newline='\n') as f:
                json.dump(uk, f, ensure_ascii=False, indent=1, sort_keys=True)
                f.write('\n')
            print('%s: було %d, стало %d'
                  % (os.path.basename(part), was, len(uk)))
    print('рядків, що різняться лише пунктуацією: %d%s'
          % (hit, '' if apply else ' (без --apply не записано)'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
