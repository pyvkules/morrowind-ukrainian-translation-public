# -*- coding: utf-8 -*-
"""Озвучені репліки: ті, що гравець бачить субтитром.

    py tools\\dialogue\\voiced.py left            де їх скільки лишилось
    py tools\\dialogue\\voiced.py next <зріз> [N] наступні неперекладені

Виписка така сама, як у `batch.py next`, тож партія пишеться і застосовується
звичайним ходом: `py tools\\dialogue\\batch.py apply <зріз> <файл>`.

Навіщо окремо від batch.py
--------------------------
Репліка типу Voice зі звуковим файлом малюється плавним написом просто під
час ходіння: привітання, бурмотіння, вигуки в бою. Гравець бачить її, навіть
коли з тим НПЦ жодного разу не заговорив. Абзац у книжці він може не
побачити ніколи.

Через це рахувати решту роботи самими рядками оманливо. Вимір на 4 жовтня:
**1038 неперекладених рядків на 37 тисяч знаків** дають **усі 2753
англійські субтитри** в грі. Це 5,8 відсотка решти реплік за обсягом. Один
рядок тут править у середньому 2,7 місця в грі, бо та сама фраза стоїть у
багатьох плагінах, на різні раси й фракції.

Чому тип беремо зі зібраних плагінів, а не зі зрізів
---------------------------------------------------
У зрізі лежить сам текст, без типу: `extract_infos.py` зводить однакові
рядки в один і губить, звідки вони. Тип знає тільки плагін, тож читаємо
зібрані плагіни в корені репозиторію. Збірка там уже є завжди, коли є що
перекладати.
"""
import glob
import io
import json
import os
import struct
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                              errors='replace', write_through=True)

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(TOOLS, '..'))
SRC = os.path.join(TOOLS, 'src')
UK = os.path.join(TOOLS, 'uk')

PLUGIN_EXT = ('.esm', '.esp', '.omwaddon')
VOICE = 1                 # DIAL/DATA: 0 тема, 1 озвучена, 2 вітання...
CYR = set(range(0x410, 0x450)) | {0x404, 0x406, 0x407, 0x454, 0x456, 0x457,
                                  0x490, 0x491}


def records(data):
    pos, n = 0, len(data)
    while pos + 16 <= n:
        size = struct.unpack('<I', data[pos + 4:pos + 8])[0]
        yield data[pos:pos + 4].decode('ascii', 'replace'), \
            data[pos + 16:pos + 16 + size]
        pos += 16 + size


def subs(body):
    pos, n = 0, len(body)
    while pos + 8 <= n:
        size = struct.unpack('<I', body[pos + 4:pos + 8])[0]
        yield body[pos:pos + 4].decode('ascii', 'replace'), \
            body[pos + 8:pos + 8 + size]
        pos += 8 + size


def zstr(b):
    return b.split(b'\0')[0].decode('cp1251', 'replace')


def flat(s):
    return ' '.join(s.split())


def load(path):
    with open(path, 'rb') as f:
        raw = f.read()
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return json.loads(raw.decode('utf-16'))
    return json.loads(raw.decode('utf-8-sig'))


def voiced_texts():
    """Англійські тексти озвучених реплік з усіх зібраних плагінів.

    Беремо лише ті, що мають SNAM: без звукового файла субтитра немає.
    """
    found = set()
    for name in sorted(os.listdir(ROOT)):
        if not name.lower().endswith(PLUGIN_EXT):
            continue
        try:
            with open(os.path.join(ROOT, name), 'rb') as f:
                data = f.read()
        except OSError:
            continue
        is_voice = False
        for rtype, body in records(data):
            if rtype == 'DIAL':
                is_voice = False
                for st, sb in subs(body):
                    if st == 'DATA' and sb:
                        is_voice = sb[0] == VOICE
            elif rtype == 'INFO' and is_voice:
                text = snam = ''
                for st, sb in subs(body):
                    if st == 'NAME':
                        text = zstr(sb)
                    elif st == 'SNAM':
                        snam = zstr(sb)
                if text.strip() and snam \
                        and not any(ord(c) in CYR for c in text):
                    found.add(flat(text))
    return found


def parts(name):
    return sorted(glob.glob(os.path.join(UK, name + '.json'))
                  + glob.glob(os.path.join(UK, name + '_p*.json')))


def uk_of(name):
    uk = {}
    for p in parts(name):
        uk.update(load(p))
    return uk


def pending(name, voiced):
    """Неперекладені озвучені рядки зрізу: [(номер, текст)]."""
    src = load(os.path.join(SRC, name + '.json'))
    if not isinstance(src, list):
        return []
    uk = uk_of(name)
    return [(i, s) for i, s in enumerate(src)
            if isinstance(s, str) and s.strip() and not uk.get(str(i))
            and flat(s) in voiced]


def slices():
    for p in sorted(glob.glob(os.path.join(SRC, '*.json'))):
        name = os.path.basename(p)[:-5]
        if not name.endswith('.topics'):
            yield name


def cmd_left(argv):
    voiced = voiced_texts()
    print('озвучених англійських текстів у збірці: %d' % len(voiced))
    rows = []
    for name in slices():
        left = pending(name, voiced)
        if left:
            rows.append((len(left), sum(len(s) for _, s in left), name))
    rows.sort(reverse=True)
    print('%-34s %8s %9s' % ('зріз', 'рядків', 'знаків'))
    for n, chars, name in rows:
        print('%-34s %8d %9d' % (name, n, chars))
    print('%-34s %8d %9d' % ('разом', sum(r[0] for r in rows),
                             sum(r[1] for r in rows)))


def cmd_next(argv):
    name = argv[0]
    n = int(argv[1]) if len(argv) > 1 else 40
    left = pending(name, voiced_texts())
    print('%s: озвучених без перекладу %d' % (name, len(left)))
    for i, s in left[:n]:
        print('--- %d\n%s' % (i, s))


def main():
    cmds = {'left': cmd_left, 'next': cmd_next}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(__doc__)
        return 1
    cmds[sys.argv[1]](sys.argv[2:])
    return 0


if __name__ == '__main__':
    sys.exit(main())
