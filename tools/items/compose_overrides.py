# -*- coding: utf-8 -*-
"""Емітити uk_<cat>.json для категорій БЕЗ складального двигуна.

Інгредієнти, активатори й назви книг систематично не складаються (це переважно
власні/описові назви), тож переклад суто ручний через <cat>_overrides.json.
Цей скрипт лише переносить override -> uk_<cat>.json (у порядку появи в грі),
а ще пише tools/_remaining_<cat>.txt, щоб бачити, що лишилось.

    py compose_overrides.py            # діагностика
    py compose_overrides.py --apply
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
CATEGORIES = ['ingredient', 'activator', 'book_title',
              'class', 'race', 'faction', 'region']


def main():
    apply = '--apply' in sys.argv
    for cat in CATEGORIES:
        names = list(json.load(open(os.path.join(HERE, cat + '.json'), encoding='utf-8')))
        ov = {}
        ovp = os.path.join(HERE, cat + '_overrides.json')
        if os.path.isfile(ovp):
            ov = json.load(open(ovp, encoding='utf-8'))
            ov.pop('_comment', None)
        out = {n: ov[n] for n in names if n in ov}
        print('%-11s %4d / %4d  (%.0f%%)' % (cat, len(out), len(names),
                                             100.0 * len(out) / len(names) if names else 0))
        if apply:
            with open(os.path.join(HERE, 'uk_' + cat + '.json'), 'w', encoding='utf-8') as f:
                json.dump({k: out[k] for k in sorted(out)}, f, ensure_ascii=False, indent=1)
            rem = [n for n in names if n not in out]
            with open(os.path.join(HERE, '..', '_remaining_' + cat + '.txt'), 'w', encoding='utf-8') as f:
                f.write('\n'.join(rem))


if __name__ == '__main__':
    main()
