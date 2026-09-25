# -*- coding: utf-8 -*-
"""Намалювати кнопки головного меню українською.

Навіщо
------
Слова в головному меню це не текст, а картинки: `textures\\menu_newgame.dds`
і решта. Жоден переклад рядків їх не зачіпає, тому меню лишалося англійським,
коли вже все інше було українською.

Розмір полотна важить більше за кегль. Рушій масштабує всю колонку кнопок так,
щоб вона влізла в екран, тож у ванільних 512x256, де напис займає трохи більше
половини, усе стискається до дрібного. Робимо полотно тісним по висоті.

Шрифт беремо свій же, `Fonts/MysticCards.ttf`: це гарнітура заголовків самої
гри, і ми вже дорисували їй Є І Ї Ґ. Пікселів Bethesda не чіпаємо, малюємо
з нуля.

    py tools/make_menu_textures.py
"""
import io
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                              errors='replace', write_through=True)
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'Textures')
FONT = os.path.join(ROOT, 'Fonts', 'MysticCards.ttf')

# Під написом лишаємо більше місця, ніж над ним: рушій ставить колонку кнопок
# від низу, і при тісному полотні весь список сповзав донизу.
SIZE = (512, 134)
BAND = (14, 4, 498, 108)

WORDS = {
    'newgame': 'Нова гра',
    'loadgame': 'Завантажити',
    'savegame': 'Зберегти',
    'options': 'Опції',
    'credits': 'Автори',
    'exitgame': 'Вихід',
    'return': 'Продовжити',
}
# стан -> (колір напису, зсув по вертикалі)
STATES = {
    '': ((196, 164, 106, 255), 0),
    # Рушій тримає підсвітку на кнопці, що має фокус клавіатури, навіть коли
    # курсор деінде. Тож різниця тут стримана: помітна під мишею, але не
    # кричить, коли просто висить на одному пункті.
    '_over': ((224, 194, 132, 255), 0),
    '_pressed': ((150, 122, 74, 255), 1),
}


def common_size(draw, words, font_path):
    """Один кегль на всі кнопки, інакше «Опції» вдвічі більші за «Зберегти»."""
    maxw, maxh = BAND[2] - BAND[0], BAND[3] - BAND[1]
    size = maxh
    while size > 8:
        font = ImageFont.truetype(font_path, size)
        if all(draw.textbbox((0, 0), w, font=font)[2]
               - draw.textbbox((0, 0), w, font=font)[0] <= maxw
               and draw.textbbox((0, 0), w, font=font)[3]
               - draw.textbbox((0, 0), w, font=font)[1] <= maxh
               for w in words):
            return font
        size -= 1
    raise SystemExit('жоден кегль не підходить')


def main():
    if not os.path.isfile(FONT):
        print('немає %s' % FONT)
        return 1
    os.makedirs(OUT, exist_ok=True)

    probe = ImageDraw.Draw(Image.new('RGBA', (8, 8)))
    font = common_size(probe, WORDS.values(), FONT)
    print('кегль: %d' % font.size)

    made = 0
    for name, word in sorted(WORDS.items()):
        for suffix, (colour, dy) in STATES.items():
            im = Image.new('RGBA', SIZE, (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            l, t, r, b = d.textbbox((0, 0), word, font=font)
            x = (SIZE[0] - (r - l)) // 2 - l
            y = BAND[1] + (BAND[3] - BAND[1] - (b - t)) // 2 - t + dy
            d.text((x + 2, y + 2), word, font=font, fill=(0, 0, 0, 150))
            d.text((x, y), word, font=font, fill=colour)
            im.save(os.path.join(OUT, 'menu_%s%s.dds' % (name, suffix)))
            made += 1
        print('  %-9s %s' % (name, word))
    print('записано %d файлів у %s' % (made, OUT))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
