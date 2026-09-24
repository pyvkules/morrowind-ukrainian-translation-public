# -*- coding: utf-8 -*-
"""Зняти з робочого профілю рецепт, придатний для чужої машини.

Навіщо
------
«Мій модліст» — це не офіційний список із Modding-OpenMW: профіль
`just-good-morrowind-plus` зібраний із чотирьох офіційних одразу
(`total-overhaul`, `expanded-vanilla`, `just-good-morrowind`,
`i-heart-vanilla`) плюс власний порядок завантаження. Відтворити його можна
тільки маючи сам `openmw.cfg` — 601 теку даних і 327 рядків порядку.

Тому возимо його як **рецепт**: той самий файл, де машинозалежні шляхи
замінено мітками. Інсталятор підставить свої.

    {МОДИ}  — тека, куди umo складає моди (у автора E:\\Morrowind)
    {ГРА}   — тека Data Files самої гри

Рядок нашого ж перекладу з рецепта викидаємо: інсталятор допише його сам,
останнім, бо виграє останній.

    py installer/make_recipe.py --from "<шлях до openmw.cfg>"
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'recipe', 'profile.cfg')
MODS = '{МОДИ}'
GAME = '{ГРА}'
OURS = 'morrowind-ukrainian-translation'


def arg(flag, default=None):
    for i, a in enumerate(sys.argv):
        if a == flag and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def value(line):
    return line.split('=', 1)[1].strip().strip('"') if '=' in line else ''


def main():
    src = arg('--from')
    if not src or not os.path.isfile(src):
        print('вкажи --from "<шлях до openmw.cfg>"')
        return 1

    lines = io.open(src, encoding='utf-8', errors='replace').read().splitlines()

    # Тека з модами — спільний корінь більшості тек даних; тека гри — та, де
    # лежить Morrowind.esm. Обидві знаходимо самі, щоб не вписувати руками.
    data = [value(l) for l in lines if l.strip().startswith('data=')]
    game = next((d for d in data
                 if os.path.isfile(os.path.join(d, 'Morrowind.esm'))), None)
    mods = os.path.commonpath([d for d in data
                               if game and os.path.normcase(d) != os.path.normcase(game)
                               and OURS not in d]) if data else None
    if not game or not mods:
        print('не вдалося визначити теку гри або модів')
        return 1
    print('тека модів : %s' % mods)
    print('тека гри   : %s' % game)

    out, dropped = [], 0
    for line in lines:
        s = line.strip()
        if s.startswith('data=') and OURS in s:
            dropped += 1                      # наш переклад допише інсталятор
            continue
        if s.startswith('data='):
            d = value(s)
            if os.path.normcase(d) == os.path.normcase(game):
                line = 'data="%s"' % GAME
            elif os.path.normcase(d).startswith(os.path.normcase(mods)):
                line = 'data="%s%s"' % (MODS, d[len(mods):])
        out.append(line)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(out) + '\n')

    kinds = {}
    for l in out:
        if '=' in l and not l.startswith('#'):
            kinds[l.split('=')[0]] = kinds.get(l.split('=')[0], 0) + 1
    print('записано %s' % OUT)
    print('  тек даних %d, порядок завантаження %d, налаштувань %d'
          % (kinds.get('data', 0), kinds.get('content', 0),
             kinds.get('fallback', 0)))
    print('  викинуто наших рядків: %d' % dropped)

    # Які офіційні списки треба поставити, щоб ці теки з'явилися
    # Нашу ж теку сюди не рахуємо: вона лежить під тим самим коренем, але це
    # не офіційний список, а те, що інсталятор допише сам.
    lists = sorted({d[len(mods):].strip(os.sep).split(os.sep)[0]
                    for d in data
                    if os.path.normcase(d).startswith(os.path.normcase(mods))
                    and d[len(mods):].strip(os.sep) and OURS not in d})
    print('  списки: %s' % ', '.join(lists))
    io.open(os.path.join(HERE, '..', 'recipe', 'lists.txt'), 'w',
            encoding='utf-8', newline='\n').write('\n'.join(lists) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
