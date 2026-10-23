# -*- coding: utf-8 -*-
"""Підстановок у перекладі стільки ж, скільки в першотворі.

Гру підстановка цікавить дослівно: `%Name` вона міняє на ім'я мовця, `%PCName`
на ім'я гравця. Загубиш одну - гравець прочитає речення без підмета; додаси
зайву - побачить ім'я там, де його не казали.

Найлегше це губиться там, де каджіт говорить про себе в третій особі:
«%Name thinks %Name saw someone like that» українською проситься в одне
«%Name, здається, бачив», і підстановка тихо зникає.

`batch.py` таке ловить, але тільки в тому, що проходить через нього. Переклад,
скопійований від близнюка чи успадкований за id запису, його обминає, тож
перевірка потрібна окремо.

    py tools\\dialogue\\placeholders.py

Вихід 1, якщо знайшлося хоч одне розходження.
"""
import codecs
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
SRC = os.path.join(TOOLS, 'src')
UK = os.path.join(TOOLS, 'uk')

PH = re.compile(r'[%&][A-Za-z][A-Za-z0-9_]*')
# Амперсанд тут через описку мода: у Джанго стоїть «&PCName», і ми лишаємо її
# як є, бо зайва підстановка проти першотвору - це попередження в check_sources.


def load(path):
    raw = open(path, 'rb').read()
    if raw[:2] in (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE):
        return json.loads(raw.decode('utf-16'))
    return json.loads(raw.decode('utf-8-sig'))


def slices():
    for path in sorted(glob.glob(os.path.join(SRC, '*.json'))):
        name = os.path.basename(path)[:-5]
        src = load(path)
        if not isinstance(src, list):
            continue
        uk = {}
        for part in sorted(glob.glob(os.path.join(UK, name + '.json'))
                           + glob.glob(os.path.join(UK, name + '_p*.json'))):
            uk.update(load(part))
        if uk:
            yield name, src, uk


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='replace', write_through=True)
    found = 0
    for name, src, uk in slices():
        for i, s in enumerate(src):
            t = uk.get(str(i))
            if not isinstance(s, str) or not isinstance(t, str):
                continue
            want, have = sorted(PH.findall(s)), sorted(PH.findall(t))
            if want == have:
                continue
            found += 1
            print(u'%s %d: у першотворі %s, у перекладі %s'
                  % (name, i, ' '.join(want) or u'жодної',
                     ' '.join(have) or u'жодної'))
            print(u'  en %s' % ' '.join(s.split())[:200])
            print(u'  uk %s' % ' '.join(t.split())[:200])
    print(u'реплік із іншим набором підстановок: %d' % found)
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main())
