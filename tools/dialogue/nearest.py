# -*- coding: utf-8 -*-
"""Для кожної неперекладеної репліки — найближча вже перекладена.

Моди на кшталт «Context Matters» не пишуть репліки з нуля: вони беруть
ванільну відповідь і переписують її під конкретну фракцію, расу чи ранг.
`reuse.py` закриває лише ті, що різняться пунктуацією; решта — це та сама
думка іншими словами, і перекладати її заново означає ризикувати тим, що
ешлендер розкаже про юрти двома різними способами.

Скрипт для кожного рядка зрізу шукає найсхожіший англійський рядок, який уже
має переклад, і показує обидва. Далі людина бачить, що саме змінилося, і
править переклад точково, а не набирає абзац наново.

    py tools\\dialogue\\nearest.py <зріз> [поріг]   # поріг схожості, 0..1
    py tools\\dialogue\\nearest.py <зріз> --diff    # ще й показати зміни

Поріг за замовчуванням 0.6: нижче цього «схожість» уже не допомагає.
"""

import difflib
import glob
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                              errors='replace', write_through=True)

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
WORD = re.compile(r'[a-z0-9]+')


def load(path):
    with open(path, 'rb') as f:
        raw = f.read()
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return json.loads(raw.decode('utf-16'))
    return json.loads(raw.decode('utf-8-sig'))


def slices():
    """Усі зрізи: англійський рядок -> переклад, якщо він є."""
    done = {}
    todo = {}
    for path in sorted(glob.glob(os.path.join(TOOLS, 'src', '*.json'))):
        name = os.path.basename(path)[:-5]
        src = load(path)
        if not isinstance(src, list):
            continue
        uk = {}
        for p in sorted(glob.glob(os.path.join(TOOLS, 'uk', name + '.json'))
                        + glob.glob(os.path.join(TOOLS, 'uk', name + '_p*.json'))):
            uk.update(load(p))
        for i, en in enumerate(src):
            if not isinstance(en, str):
                continue
            tr = uk.get(str(i))
            if tr:
                done.setdefault(en, tr)
            else:
                todo.setdefault(name, []).append((i, en))
    return done, todo


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    show_diff = '--diff' in sys.argv
    if not args:
        print(__doc__)
        return 1
    want = args[0]
    cutoff = float(args[1]) if len(args) > 1 else 0.6

    done, todo = slices()
    rows = todo.get(want)
    if not rows:
        print('зріз %r або закритий, або його нема' % want)
        return 1

    # Спершу грубий відбір за спільними словами, тоді точне порівняння:
    # difflib на десятках тисяч рядків інакше думав би годину.
    index = {}
    for en in done:
        for w in set(WORD.findall(en.lower())):
            if len(w) > 3:
                index.setdefault(w, []).append(en)

    found = 0
    for i, en in rows:
        words = [w for w in set(WORD.findall(en.lower())) if len(w) > 3]
        seen = {}
        for w in words:
            for cand in index.get(w, ()):
                seen[cand] = seen.get(cand, 0) + 1
        pool = sorted(seen, key=lambda c: -seen[c])[:40]
        best, score = None, 0.0
        for cand in pool:
            s = difflib.SequenceMatcher(None, en, cand).ratio()
            if s > score:
                best, score = cand, s
        print('%s:%d  схожість %.2f' % (want, i, score))
        print('   НОВЕ  %s' % en)
        if best and score >= cutoff:
            found += 1
            print('   БУЛО  %s' % best)
            print('   ПЕР   %s' % done[best])
            if show_diff:
                for line in difflib.unified_diff(
                        best.split(), en.split(), lineterm='', n=0):
                    if line.startswith(('+', '-')) and not line.startswith(('+++', '---')):
                        print('     %s' % line)
        print()

    print('рядків: %d, з них мають близький уже перекладений: %d'
          % (len(rows), found))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
