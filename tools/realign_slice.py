# -*- coding: utf-8 -*-
"""Полагодити зріз, у якому переклад з'їхав на один рядок.

Зріз - це масив англійських реплік, а переклад - словник «індекс -> український
текст». Якщо під час перекладу один рядок продублювався, всі наступні ключі
зсуваються, і кожна репліка після місця збою починає показувати чужий текст. Гра
при цьому не ламається - просто персонажі відповідають не те, - тому помітити це
на око майже неможливо.

Знаходить збій check_sources.py (втрачені підстановки на кшталт %PCName), а
підтверджує - порівняння довжин у вікні: український текст стабільно трохи довший
за англійський, тож правильний зсув видно за сумою відхилень.

    py realign_slice.py --slice topics01                      # діагностика
    py realign_slice.py --slice topics01 --drop 45 --apply    # прибрати дубль і зсунути

--drop N: ключ N - зайвий дубль; його видаляють, а все після нього зсувають на -1.
"""
import glob
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TOOLS = os.path.dirname(os.path.abspath(__file__))
RATIO = 1.05            # український текст трохи довший за англійський
WINDOW = 25
OFFSETS = (-2, -1, 0, 1)


def arg(flag, cast=str):
    for i, a in enumerate(sys.argv):
        if a == flag and i + 1 < len(sys.argv):
            return cast(sys.argv[i + 1])
    return None


def slice_files(name):
    """Файли перекладу зрізу в числовому порядку, а не в лексикографічному."""
    files = glob.glob(os.path.join(TOOLS, 'uk', name + '.json')) \
        + glob.glob(os.path.join(TOOLS, 'uk', name + '_p*.json'))

    def order(p):
        m = re.search(r'_p(\d+)\.json$', p)
        return int(m.group(1)) if m else 1
    return sorted(files, key=order)


def load(name):
    src = json.load(open(os.path.join(TOOLS, 'src', name + '.json'), encoding='utf-8'))
    files = slice_files(name)
    uk, sizes = {}, []
    for p in files:
        d = json.load(open(p, encoding='utf-8'))
        sizes.append(len(d))
        for k, v in d.items():
            uk[int(k)] = v
    return src, uk, files, sizes


def offset_runs(src, uk):
    """Для кожного ключа - найкращий зсув, усереднений по вікну сусідів."""
    keys = sorted(uk)

    def cost(i, d):
        j = i + d
        if not 0 <= j < len(src):
            return 1e6
        a, b = len(uk[i]), len(src[j]) * RATIO
        return abs(a - b) / max(a, b, 1.0)

    runs = []
    for n, i in enumerate(keys):
        win = keys[max(0, n - WINDOW // 2):n + WINDOW // 2 + 1]
        scores = {d: sum(cost(k, d) for k in win) / len(win) for d in OFFSETS}
        best = min(scores, key=scores.get)
        if runs and runs[-1][2] == best:
            runs[-1][1] = i
        else:
            runs.append([i, i, best])
    return [r for r in runs if r[1] - r[0] >= 3]


def write(name, uk, files, sizes):
    """Розкласти виправлений переклад назад по тих самих файлах."""
    items = sorted(uk.items())
    pos = 0
    for path, size in zip(files, sizes):
        take = min(size, len(items) - pos)
        chunk = items[pos:pos + take]
        pos += take
        with open(path, 'w', encoding='utf-8') as f:
            f.write('{\n')
            f.write(',\n'.join('"%d": %s' % (k, json.dumps(v, ensure_ascii=False))
                               for k, v in chunk))
            f.write('\n}\n')
    return pos


def main():
    name = arg('--slice')
    if not name:
        print(__doc__)
        return 1
    src, uk, files, sizes = load(name)
    print('%s: %d рядків в оригіналі, %d перекладено, %d файлів'
          % (name, len(src), len(uk), len(files)))
    for a, b, d in offset_runs(src, uk):
        print('   ключі %4d..%-4d зсув %+d  (%d)' % (a, b, d, b - a + 1))

    drop = arg('--drop', int)
    if drop is None:
        return 0
    if drop not in uk:
        print('! ключа %d немає' % drop)
        return 1
    if uk.get(drop) != uk.get(drop - 1):
        print('! ключ %d не є дублем ключа %d - зупиняюся, щоб не зіпсувати більше'
              % (drop, drop - 1))
        return 1
    print('\nключ %d дослівно дублює %d - видаляємо його й зсуваємо решту на -1'
          % (drop, drop - 1))

    fixed = {i: v for i, v in uk.items() if i < drop}
    for i in sorted(k for k in uk if k > drop):
        fixed[i - 1] = uk[i]
    print('після виправлення: %d записів (було %d)' % (len(fixed), len(uk)))
    for a, b, d in offset_runs(src, fixed):
        print('   ключі %4d..%-4d зсув %+d  (%d)' % (a, b, d, b - a + 1))

    if '--apply' not in sys.argv:
        print('\nпробний запуск - додайте --apply, щоб записати')
        return 0
    written = write(name, fixed, files, sizes)
    print('\nзаписано %d записів у %d файлів' % (written, len(files)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
