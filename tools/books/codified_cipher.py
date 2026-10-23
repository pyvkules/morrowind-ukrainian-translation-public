# -*- coding: utf-8 -*-
"""Шифр трьох томів «Кодифікованого права»: Віженер ключем NUMINIT.

Книга сама каже, що ключі - «пильно бережена таємниця Гільдії
правозаступників», і частоти літер спершу схожі на випадковий набір
(індекс збігів 0,044 проти 0,066 в англійській). Та це Віженер із ключем
на сім літер: розгадано підйомом на гору за квадрограмами, узятими з
самих англійських книг Морровінда - той самий реєстр і словник.

Том I складено з двох шматків: до 463-ї літери ключ іде від N, далі
від T, як у томі III, бо хвіст тому I - це той самий текст, що й том III.

CONVENTIONS §7 велить розгаданий шифр перекласти й зашифрувати наново
тим самим способом по українській абетці. Ключ НУМІНІТ, абетка на 33
літери, апострофи й риски лишаються на місці, як у першотворі.

    py tools\books\codified_cipher.py decode        # відкритий текст
    py tools\books\codified_cipher.py encode <файл> # зашифрувати переклад

Файл для encode: рядки `<зсув ключа>|<український відкритий текст>`.
Зсуви: том I перший шматок 0, другий 6, том II 1, том III 6.
"""
import io
import json
import os
import re
import sys

REPO = r'E:\Morrowind\OpenMW\mods\morrowind-ukrainian-translation\tools\books'
KW = 'NUMINIT'
UK = u'\u0410\u0411\u0412\u0413\u0490\u0414\u0415\u0404\u0416\u0417\u0418\u0406\u0407\u0419\u041a\u041b\u041c\u041d\u041e\u041f\u0420\u0421\u0422\u0423\u0424\u0425\u0426\u0427\u0428\u0429\u042c\u042e\u042f'
UKKEY = u'\u041d\u0423\u041c\u0406\u041d\u0406\u0422'   # НУМІНІТ
BOOKS = {
    'Codified Law, Vol. I': [(0, 463, 0), (463, None, 6)],
    'Codified Law, Vol. II': [(0, None, 1)],
    'Codified Law, Vol. III': [(0, None, 6)],
}


def load(name):
    return json.loads(io.open(os.path.join(REPO, name), encoding='utf-8-sig').read())


def plan(title):
    return BOOKS[title]


def decode(raw, parts):
    """Розшифрувати, зберігши пробіли й риски."""
    out, n = [], 0
    for ch in raw:
        if not ('A' <= ch <= 'Z'):
            out.append(ch)
            continue
        for a, b, r in parts:
            if n >= a and (b is None or n < b):
                k = KW[(r + n - a) % 7]
                break
        out.append(chr((ord(ch) - 65 - (ord(k) - 65)) % 26 + 65))
        n += 1
    return ''.join(out)


def encode_uk(text, rot=0):
    """Зашифрувати український відкритий текст тим самим способом."""
    out, n = [], 0
    for ch in text:
        up = ch.upper()
        if up not in UK:
            out.append(ch)
            continue
        k = UKKEY[(rot + n) % 7]
        i = (UK.index(up) + UK.index(k)) % len(UK)
        out.append(UK[i])
        n += 1
    return ''.join(out)


def main():
    src, meta = load('_source.json'), load('books_meta.json')
    if sys.argv[1] == 'decode':
        for title in BOOKS:
            h = [x for x, v in meta.items() if v['title'] == title][0]
            body = re.sub(r'<[^>]*>', ' ', src[h])
            raw = body[body.rfind(']') + 1:]
            print('=== %s' % title)
            print(' '.join(decode(raw, plan(title)).split()))
            print()
    else:
        for ln in io.open(sys.argv[2], encoding='utf-8'):
            ln = ln.rstrip('\n')
            if not ln.strip() or ln.startswith('#'):
                continue
            rot, text = ln.split('|', 1)
            print(encode_uk(text, int(rot)))


if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  write_through=True)
    main()
