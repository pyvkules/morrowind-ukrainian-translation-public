# -*- coding: utf-8 -*-
"""Зробити з icon.png піктограму встановлювача.

Навіщо окремий скрипт
---------------------
Pillow за звичкою пише всі розміри в .ico як PNG. Провідник Windows на це
показує звичайний значок замість нашого: PNG усередині .ico він розуміє
тільки на 256 пікселях, а все менше чекає класичним BMP. Тож збираємо файл
самі: BMP для малих розмірів, PNG для 256, бо BMP такого розміру важив би
чверть мегабайта.

Зовнішню рамку обтинаємо на 7 відсотків. На 16 і 32 пікселях вона з'їдає
половину поля, а читатися має середній знак.

    py installer/make_icon.py                 # з installer/icon.png
    py installer/make_icon.py --from <файл>   # або з іншого джерела
"""
import io
import os
import struct
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PNG = os.path.join(HERE, 'icon.png')
ICO = os.path.join(HERE, 'icon.ico')
SIZES = [16, 24, 32, 48, 64, 128, 256]
TRIM = 0.07


def frame(img, size):
    """Одне зображення так, як його зрозуміє Windows."""
    one = img.resize((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    if size >= 256:
        one.save(buf, format='PNG', optimize=True)
        return buf.getvalue(), 32
    # змішувати формати в одному файлі Pillow не вміє, тож просимо в нього
    # .ico з єдиним розміром і забираємо звідти саме тіло
    one.save(buf, format='ICO', sizes=[(size, size)], bitmap_format='bmp')
    raw = buf.getvalue()
    _, _, _, _, _, bits, length, off = struct.unpack_from('<BBBBHHII', raw, 6)
    return raw[off:off + length], bits


def main():
    src = PNG
    for i, a in enumerate(sys.argv):
        if a == '--from' and i + 1 < len(sys.argv):
            src = sys.argv[i + 1]
    if not os.path.isfile(src):
        print('немає файлу %s' % src)
        return 1

    img = Image.open(src).convert('RGBA')
    if src != PNG:
        img.resize((512, 512), Image.LANCZOS).save(PNG, format='PNG',
                                                   optimize=True)
        print('джерело збережено як %s' % os.path.basename(PNG))

    dx, dy = int(img.width * TRIM), int(img.height * TRIM)
    img = img.crop((dx, dy, img.width - dx, img.height - dy))

    parts = [(size,) + frame(img, size) for size in SIZES]
    offset = 6 + 16 * len(parts)
    table = b''
    for size, body, bits in parts:
        table += struct.pack('<BBBBHHII', size & 0xFF, size & 0xFF, 0, 0,
                             1, bits, len(body), offset)
        offset += len(body)
    with io.open(ICO, 'wb') as f:
        f.write(struct.pack('<HHH', 0, 1, len(parts)) + table
                + b''.join(body for _, body, _ in parts))

    print('%s: %d зображень, %.1f КБ'
          % (os.path.basename(ICO), len(parts),
             os.path.getsize(ICO) / 1024.0))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
