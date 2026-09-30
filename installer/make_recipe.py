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

    write_skips(mods, out)
    return 0


def profile_mods(lines):
    """Які моди бере профіль: список -> теки модів.

    Шлях у профілі має вигляд {МОДИ}\\<список>\\<категорія>\\<мод>, іноді з
    підтекою. Нам потрібні перші три частини.
    """
    need = {}
    for line in lines:
        s = line.strip()
        if not (s.startswith('data=') and MODS in s):
            continue
        parts = [p for p in s.split(MODS, 1)[1].strip('"').split(os.sep) if p]
        if len(parts) >= 3:
            need.setdefault(parts[0], set()).add((parts[1], parts[2]))
    return need


def write_skips(mods_root, lines):
    """Моди, які umo причепить за підрядком, хоч профіль їх не бере.

    Інсталятор відбирає моди через `umo install --subset`, а той звіряє
    елемент із рядком «категорія-тека» як підрядок. Через це «TamrielData»
    тягне за собою «TamrielDataTextureUpscale» на двадцять гігабайтів.
    Такі збіги видно тільки тут, на машині, де стоять усі списки цілком,
    тож перелічуємо їх у рецепті.
    """
    need = profile_mods(lines)
    skips = []
    for name in sorted(need):
        root = os.path.join(mods_root, name)
        if not os.path.isdir(root):
            continue
        want = {mod for _cat, mod in need[name]}
        for cat in sorted(os.listdir(root)):
            cdir = os.path.join(root, cat)
            if not os.path.isdir(cdir):
                continue
            for mod in sorted(os.listdir(cdir)):
                if mod in want or not os.path.isdir(os.path.join(cdir, mod)):
                    continue
                s = ('%s-%s' % (cat, mod)).lower()
                if any(w.lower() in s for w in want):
                    skips.append('%s\t%s' % (name, mod))

    path = os.path.join(HERE, '..', 'recipe', 'skip.txt')
    io.open(path, 'w', encoding='utf-8', newline='\n').write(
        '\n'.join(skips) + ('\n' if skips else ''))
    total = sum(len(v) for v in need.values())
    print('  модів у профілі %d, зайвих збігів %d' % (total, len(skips)))


if __name__ == '__main__':
    raise SystemExit(main())
