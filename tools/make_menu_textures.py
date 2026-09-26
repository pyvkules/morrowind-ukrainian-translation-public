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


# --- кнопки книг, сувоїв і щоденника ----------------------------------------
# Це теж картинки з написом усередині: Take, Close, Journal, Quests і решта.
# Розкладка задає розмір віджета жорстко (64x32, декуди 48x32), тож слова
# мусять уміститися. Тому Cancel це «Відміна», а не «Скасувати».
BOOK = {
    'take': ('Взяти', 64),
    'close': ('Закрити', 64),
    'cancel': ('Відміна', 64),
    'next': ('Далі', 64),
    'prev': ('Назад', 64),
    'journal': ('Щоденник', 64),
    'options': ('Опції', 64),
    'topics': ('Теми', 64),
    'quests': ('Завдання', 64),
    'quests_active': ('Активні', 128),
    'quests_all': ('Усі', 128),
}
SCROLL = {'take': 'Взяти', 'close': 'Закрити'}
BOOK_STATES = {
    '_idle': ((188, 152, 96, 255), 0),
    '_over': ((226, 196, 132, 255), 0),
    '_pressed': ((146, 116, 70, 255), 1),
}
BOOK_H = 32
BOOK_PAD = 3                 # поле з боків, щоб напис не торкався краю


BOOK_SIZE = 19               # спільна висота літер на всіх кнопках


def draw_word(word, font, size, colour, dy, maxw):
    """Напис однакової висоти. Задовге слово стискаємо вшир, а не дрібнимо.

    Інакше «Щоденник» довелося б малювати вдвічі меншим за «Теми», і кнопки
    перестали б виглядати одним набором.
    """
    strip = Image.new('RGBA', (size[0] * 3, size[1]), (0, 0, 0, 0))
    d = ImageDraw.Draw(strip)
    l, t, r, b = d.textbbox((0, 0), word, font=font)
    d.text((10 - l, 4 - t), word, font=font, fill=(0, 0, 0, 140))
    d.text((9 - l, 3 - t), word, font=font, fill=colour)
    box = strip.getchannel('A').getbbox()
    strip = strip.crop(box)
    if strip.width > maxw:
        strip = strip.resize((maxw, strip.height), Image.LANCZOS)

    im = Image.new('RGBA', size, (0, 0, 0, 0))
    im.paste(strip, ((size[0] - strip.width) // 2,
                     (size[1] - strip.height) // 2 + dy), strip)
    return im


def make_book(font_path, out_dir):
    font = ImageFont.truetype(font_path, BOOK_SIZE)
    made = 0
    for name, (word, width) in sorted(BOOK.items()):
        maxw = width - 2 * BOOK_PAD
        for suffix, (colour, dy) in BOOK_STATES.items():
            im = draw_word(word, font, (width, BOOK_H), colour, dy, maxw)
            im.save(os.path.join(out_dir,
                                 'tx_menubook_%s%s.dds' % (name, suffix)))
            made += 1
        print('  %-15s %s' % (name, word))
    for name, word in sorted(SCROLL.items()):
        im = draw_word(word, font, (64, BOOK_H), (188, 152, 96, 255), 0,
                       64 - 2 * BOOK_PAD)
        im.save(os.path.join(out_dir, 'tx_scroll_%s.dds' % name))
        made += 1
        print('  %-15s %s (сувій)' % (name, word))
    return made


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
    made += make_book(FONT, OUT)
    print('записано %d файлів у %s' % (made, OUT))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
