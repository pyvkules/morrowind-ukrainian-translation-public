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
# Ванільні написи не однобарвні: згори світле золото, донизу теплий оранж.
# Через це вони й читаються помаранчевими, а рівна заливка виглядала блідо.
# стан -> (колір угорі, колір унизу, зсув по вертикалі)
STATES = {
    '': ((246, 208, 130), (186, 116, 46), 0),
    # Рушій тримає підсвітку на кнопці, що має фокус клавіатури, навіть коли
    # курсор деінде. Тож різниця тут стримана: помітна під мишею, але не
    # кричить, коли просто висить на одному пункті.
    '_over': ((255, 233, 172), (214, 148, 66), 0),
    '_pressed': ((178, 134, 72), (128, 80, 32), 1),
}


def gradient(mask, top, bottom):
    """Залити маску напису вертикальним переходом згори вниз."""
    box = mask.getbbox()
    if box is None:
        return Image.new('RGBA', mask.size, (0, 0, 0, 0))
    y0, y1 = box[1], max(box[3] - 1, box[1] + 1)
    ramp = Image.new('RGB', (1, mask.height))
    for y in range(mask.height):
        k = min(1.0, max(0.0, (y - y0) / float(y1 - y0)))
        ramp.putpixel((0, y), tuple(
            int(top[i] + (bottom[i] - top[i]) * k) for i in range(3)))
    out = ramp.resize(mask.size).convert('RGBA')
    out.putalpha(mask)
    return out


def inked(size, draw_into):
    """Намалювати напис маскою, тоді залити його градієнтом і тінню."""
    mask = Image.new('L', size, 0)
    draw_into(ImageDraw.Draw(mask), 255)
    return mask


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
    '_idle': ((242, 200, 122), (180, 110, 44), 0),
    '_over': ((255, 230, 166), (212, 146, 64), 0),
    '_pressed': ((172, 128, 68), (124, 78, 30), 1),
}
BOOK_H = 32
BOOK_PAD = 3                 # поле з боків, щоб напис не торкався краю


BOOK_SIZE = 19               # спільна висота літер на всіх кнопках


def draw_word(word, font, size, top, bottom, dy, maxw):
    """Напис однакової висоти. Задовге слово стискаємо вшир, а не дрібнимо.

    Інакше «Щоденник» довелося б малювати вдвічі меншим за «Теми», і кнопки
    перестали б виглядати одним набором.
    """
    wide = (size[0] * 3, size[1])
    mask = Image.new('L', wide, 0)
    d = ImageDraw.Draw(mask)
    l, t, r, b = d.textbbox((0, 0), word, font=font)
    d.text((9 - l, 3 - t), word, font=font, fill=255)
    box = mask.getbbox()
    mask = mask.crop(box)

    strip = Image.new('RGBA', mask.size, (0, 0, 0, 0))
    shadow = Image.new('RGBA', mask.size, (0, 0, 0, 0))
    shadow.putalpha(mask.point(lambda v: v * 140 // 255))
    strip.paste(shadow, (1, 1), shadow)
    ink = gradient(mask, top, bottom)
    strip.paste(ink, (0, 0), ink)
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
        for suffix, (top, bottom, dy) in BOOK_STATES.items():
            im = draw_word(word, font, (width, BOOK_H), top, bottom, dy, maxw)
            im.save(os.path.join(out_dir,
                                 'tx_menubook_%s%s.dds' % (name, suffix)))
            made += 1
        print('  %-15s %s' % (name, word))
    for name, word in sorted(SCROLL.items()):
        im = draw_word(word, font, (64, BOOK_H), (242, 200, 122),
                       (180, 110, 44), 0, 64 - 2 * BOOK_PAD)
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
    probe2 = ImageDraw.Draw(Image.new('L', (8, 8)))
    for name, word in sorted(WORDS.items()):
        l, t, r, b = probe2.textbbox((0, 0), word, font=font)
        x = (SIZE[0] - (r - l)) // 2 - l
        for suffix, (top, bottom, dy) in STATES.items():
            y = BAND[1] + (BAND[3] - BAND[1] - (b - t)) // 2 - t + dy
            mask = Image.new('L', SIZE, 0)
            ImageDraw.Draw(mask).text((x, y), word, font=font, fill=255)
            im = Image.new('RGBA', SIZE, (0, 0, 0, 0))
            shadow = Image.new('RGBA', SIZE, (0, 0, 0, 0))
            shadow.putalpha(mask.point(lambda v: v * 150 // 255))
            im.paste(shadow, (2, 2), shadow)
            ink = gradient(mask, top, bottom)
            im.paste(ink, (0, 0), ink)
            im.save(os.path.join(OUT, 'menu_%s%s.dds' % (name, suffix)))
            made += 1
        print('  %-9s %s' % (name, word))
    made += make_book(FONT, OUT)
    print('записано %d файлів у %s' % (made, OUT))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
