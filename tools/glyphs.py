# -*- coding: utf-8 -*-
"""Які символи шрифт узагалі вміє намалювати.

cp1251 - лише половина перевірки. Символ може чудово закодуватися в cp1251
і все одно не з'явитися в грі, бо в шрифті немає гліфа: рушій намалює порожнечу
або квадратик. Саме так сталося з лапками:

    «  U+00AB   у cp1251 є (0xAB), у Pelagiad гліфа НЕМАЄ
    »  U+00BB   у cp1251 є (0xBB), у Pelagiad гліфа НЕМАЄ
    „  U+201E   у cp1251 є (0x84), у Pelagiad гліфа НЕМАЄ
    “  U+201C   є і там, і там
    ”  U+201D   є і там, і там

Тобто питомо українські лапки «ялинки» й нижня лапка „ у цій грі не працюють,
а працює пара “ ”. Це не вибір стилю, а обмеження шрифту.

Покриття читаємо просто з cmap у TTF, без сторонніх бібліотек, - щоб перевірка
залишалася чинною, якщо шрифт колись перепатчать.

    py tools\\glyphs.py            # показати покриття розділових знаків
    py tools\\glyphs.py "текст"    # що з цього рядка не намалюється
    py tools\\glyphs.py --dump     # оновити font_coverage.json (для CI)

Самих .ttf у git немає - вони походять від гри. Тому покриття лежить поруч
у font_coverage.json, як books_meta.json біля книг: раннер перевіряє за ним,
а локально ми читаємо шрифт напряму й тримаємо файл свіжим.
"""
import io
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
FONTS = os.path.join(REPO, 'Fonts')
DUMP = os.path.join(HERE, 'font_coverage.json')

# чим замінювати те, чого шрифт не має. Ключ -> що ставимо натомість
SUBST = {
    '«': '“', '»': '”',     # ялинки -> наявна пара лапок
    '„': '“',               # нижня лапка -> верхня
    '‹': '“', '›': '”',
    'ʼ': "'", '’': "'", '‘': "'",   # усі апострофи -> ASCII
    ' ': ' ',          # нерозривний пробіл
    '‑': '-',          # нерозривний дефіс
}


def _coverage(path):
    data = open(path, 'rb').read()
    ntables = struct.unpack('>H', data[4:6])[0]
    cmap_off = None
    for i in range(ntables):
        p = 12 + i * 16
        if data[p:p + 4] == b'cmap':
            cmap_off = struct.unpack('>I', data[p + 8:p + 12])[0]
    if cmap_off is None:
        return None
    chars = set()
    n = struct.unpack('>H', data[cmap_off + 2:cmap_off + 4])[0]
    for i in range(n):
        p = cmap_off + 4 + i * 8
        sub = cmap_off + struct.unpack('>I', data[p + 4:p + 8])[0]
        fmt = struct.unpack('>H', data[sub:sub + 2])[0]
        if fmt == 0:
            chars.update(c for c in range(256) if data[sub + 6 + c])
        elif fmt == 4:
            segx2 = struct.unpack('>H', data[sub + 6:sub + 8])[0]
            seg = segx2 // 2
            ends = struct.unpack('>%dH' % seg, data[sub + 14:sub + 14 + segx2])
            sp = sub + 16 + segx2
            starts = struct.unpack('>%dH' % seg, data[sp:sp + segx2])
            for s, e in zip(starts, ends):
                if e != 0xFFFF:
                    chars.update(range(s, e + 1))
        elif fmt == 6:
            first, cnt = struct.unpack('>HH', data[sub + 6:sub + 10])
            chars.update(range(first, first + cnt))
        elif fmt == 12:
            ngroups = struct.unpack('>I', data[sub + 12:sub + 16])[0]
            for g in range(ngroups):
                q = sub + 16 + g * 12
                s, e = struct.unpack('>II', data[q:q + 8])
                chars.update(range(s, min(e, 0x2E00) + 1))
    return chars


_cache = None


def _ranges(chars):
    out, chars = [], sorted(chars)
    for c in chars:
        if out and c == out[-1][1] + 1:
            out[-1][1] = c
        else:
            out.append([c, c])
    return out


def from_fonts():
    """Символи, які вміють намалювати ВСІ шрифти мода.

    Перетин, а не об'єднання: інтерфейс і книги малюються різними шрифтами,
    тож безпечно лише те, що є в кожному.
    """
    sets = []
    for fn in sorted(os.listdir(FONTS)) if os.path.isdir(FONTS) else []:
        if fn.lower().endswith('.ttf'):
            c = _coverage(os.path.join(FONTS, fn))
            if c:
                sets.append(c)
    return set.intersection(*sets) if sets else set()


def covered():
    """Покриття зі шрифтів, а якщо їх нема (CI) - із font_coverage.json."""
    global _cache
    if _cache is None:
        _cache = from_fonts()
        if not _cache and os.path.isfile(DUMP):
            d = json.load(open(DUMP, encoding='utf-8'))
            _cache = {c for lo, hi in d['ranges'] for c in range(lo, hi + 1)}
    return _cache


def missing(text):
    """Символи рядка, яких у шрифті немає (пробіли й переводи рядка не рахуємо)."""
    have = covered()
    return {c for c in text
            if ord(c) not in have and c not in '\r\n\t '}


PAIR = re.compile('[«„]([^«»„“”]*)[»“]')


def fix(text):
    """Замінити те, що має відому заміну. Решту не чіпаємо - це має побачити людина.

    Пари лапок обробляємо ПЕРШИМИ й цілком: посимвольна заміна дала б з «„текст“»
    рядок «“текст“» - дві однакові відкривні лапки замість пари.
    """
    if PAIR.search(text):
        text = PAIR.sub('“\\1”', text)
    for bad, good in SUBST.items():
        if bad in text:
            text = text.replace(bad, good)
    return text


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='replace')
    if '--dump' in sys.argv:
        have = from_fonts()
        if not have:
            print('шрифтів не знайдено — нема з чого писати font_coverage.json')
            return 1
        with open(DUMP, 'w', encoding='utf-8') as f:
            json.dump({'_comment': 'спільне покриття Fonts/*.ttf; '
                                   'оновити: py tools\\glyphs.py --dump',
                       'ranges': _ranges(have)}, f, ensure_ascii=False, indent=1)
        print('font_coverage.json: %d гліфів, %d діапазонів'
              % (len(have), len(_ranges(have))))
        return 0
    have = covered()
    print('шрифтів у Fonts/: %s' % ', '.join(
        fn for fn in sorted(os.listdir(FONTS)) if fn.lower().endswith('.ttf')))
    print('спільних гліфів : %d' % len(have))
    if len(sys.argv) > 1:
        bad = missing(sys.argv[1])
        print('не намалюється  : %s' % (
            ' '.join('%s U+%04X' % (c, ord(c)) for c in sorted(bad))
            if bad else 'нічого, рядок чистий'))
        return 0
    print()
    for c in '«»„“”‘’\'"—–…№§•·¬±°':
        print('  %s U+%04X  %s' % (c, ord(c),
                                   'є' if ord(c) in have else 'НЕМАЄ'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
