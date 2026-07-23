# -*- coding: utf-8 -*-
"""Забрати давній переклад із base.esm у репозиторій - і більше його не потребувати.

Проєкт стартував від `base.esm` - це Morrowind.esm, у якому давній переклад
*ukrajinizator* уже переклав близько 11% гри. Файл важить 80 МБ, це дані Bethesda,
тож у репозиторії його немає - і через це на чистій машині збірка не проходить.

Насправді той файл несе всього ~45 тис. символів українського тексту. Цей скрипт
витягує їх у звичайні JSON поруч із рештою перекладу, після чого за основу можна
брати звичайний Morrowind.esm зі Steam.

Записи зіставляються ЗА ІДЕНТИФІКАТОРОМ, а не за позицією: інструмент, яким робили
той давній переклад, переставив частину записів місцями, тож у файлі base[2604]
відповідає vanilla[2601]. Позиційне зіставлення на цьому тихо зламалося б і
записало б переклад не до тих реплік.

    INFO  - за INAM (власний ідентифікатор репліки)
    решта - за NAME (ідентифікатор запису; показувана назва лежить у FNAM)
    GMST  - за NAME

    py absorb_base.py                 # діагностика
    py absorb_base.py --apply         # записати tools/legacy/*.json
"""
import io
import json
import os
import re
import struct
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import paths

BASE = os.path.join(TOOLS, 'base.esm')
LEGACY = os.path.join(TOOLS, 'legacy')
CYR = re.compile('[А-Яа-яЄІЇҐєіїґ]')

# тип запису -> (де ідентифікатор, де текст, як назвати вихідний файл)
KINDS = {
    b'INFO': (b'INAM', b'NAME', 'info'),
    b'BOOK': (b'NAME', b'TEXT', 'book_text'),
}
FNAM_TYPES = [b'ARMO', b'WEAP', b'CLOT', b'MISC', b'INGR', b'ALCH', b'NPC_',
              b'CREA', b'SPEL', b'CONT', b'DOOR', b'ACTI', b'LIGH', b'APPA',
              b'LOCK', b'PROB', b'REPA', b'CLAS', b'FACT', b'RACE', b'BSGN',
              b'REGN']
for t in FNAM_TYPES:
    KINDS[t] = (b'NAME', b'FNAM', 'name')
KINDS[b'BOOK_T'] = None          # заглушка, щоб BOOK не потрапив у назви двічі


def subrecs(body):
    i = 0
    while i + 8 <= len(body):
        tag = body[i:i + 4]
        sz = struct.unpack('<I', body[i + 4:i + 8])[0]
        yield tag, body[i + 8:i + 8 + sz]
        i += 8 + sz


def scan(path):
    """{kind: {record id: text}} плюс окремо GMST і назви книг."""
    raw = open(path, 'rb').read()
    out = {'info': {}, 'book_text': {}, 'name': {}, 'gmst': {}, 'cell': {}}
    pos, n = 0, len(raw)
    while pos + 16 <= n:
        rt = raw[pos:pos + 4]
        size = struct.unpack('<I', raw[pos + 4:pos + 8])[0]
        body = raw[pos + 16:pos + 16 + size]

        if rt == b'GMST':
            gid = val = None
            for st, sd in subrecs(body):
                if st == b'NAME':
                    gid = sd.split(b'\0')[0].decode('cp1251', 'replace')
                elif st == b'STRV':
                    val = sd.split(b'\0')[0].decode('cp1251', 'replace')
            if gid and val is not None:
                out['gmst'][gid] = val
        elif rt == b'CELL':
            nm, data = None, None
            for st, sd in subrecs(body):
                if st == b'NAME' and nm is None:
                    nm = sd.split(b'\0')[0].decode('cp1251', 'replace')
                elif st == b'DATA' and len(sd) >= 12:
                    data = struct.unpack('<iii', sd[:12])
            if nm:
                out['cell'][data or nm] = nm
        elif rt in KINDS and KINDS[rt]:
            id_tag, text_tag, kind = KINDS[rt]
            rid = txt = None
            for st, sd in subrecs(body):
                if st == id_tag and rid is None:
                    rid = sd.split(b'\0')[0].decode('cp1251', 'replace')
                elif st == text_tag and txt is None:
                    txt = sd.split(b'\0')[0].decode('cp1251', 'replace')
            if rid and txt:
                out[kind][rid] = txt
        pos += 16 + size
    return out


def find_vanilla():
    dirs, _ = paths.read_modlist()
    for d in dirs:
        p = os.path.join(d, 'Morrowind.esm')
        if os.path.abspath(d) != paths.MOD_ROOT and os.path.isfile(p):
            return p
    return None


def extract(kind, base_map, van_map):
    """Пари англійська -> українська для записів, спільних обом файлам.

    GMST ключуються за ідентифікатором налаштування, а не за англійським текстом:
    підписи на кшталт "Yes" повторюються в кількох налаштуваннях, тож текст як ключ
    злив би їх в одне. Решту застосовуємо заміною тексту, тому там ключ - оригінал.
    """
    by_id = kind == 'gmst'
    pairs, orphan, unchanged = {}, 0, 0
    for rid, btext in base_map.items():
        if not CYR.search(btext):
            unchanged += 1
            continue
        vtext = van_map.get(rid)
        if by_id:
            # налаштування, якого в чистій грі немає, приходить із Tribunal чи
            # Bloodmoon - воно все одно в модлисті, тож переклад не втрачаємо
            pairs[rid] = btext
            continue
        if vtext is None or CYR.search(vtext):
            orphan += 1
            continue
        pairs[vtext] = btext
    print('%-10s українських %4d -> зіставлено %4d, без пари %3d  (англійських %d)'
          % (kind, len(pairs) + orphan, len(pairs), orphan, unchanged))
    return pairs


def main():
    if not os.path.isfile(BASE):
        raise SystemExit('немає tools/base.esm - нічого забирати')
    van_path = find_vanilla()
    if not van_path:
        raise SystemExit('не знайдено ванільний Morrowind.esm у каталогах модліста')
    print('base   : %s' % BASE)
    print('vanilla: %s' % van_path)
    print()

    base, van = scan(BASE), scan(van_path)
    result = {}
    for kind in ('info', 'name', 'book_text', 'cell', 'gmst'):
        result[kind] = extract(kind, base[kind], van[kind])

    chars = sum(len(v) for d in result.values() for v in d.values())
    print()
    print('усього: %d пар, %d символів'
          % (sum(len(d) for d in result.values()), chars))

    if '--apply' not in sys.argv:
        print('пробний запуск - додайте --apply, щоб записати tools/legacy/')
        return 0

    os.makedirs(LEGACY, exist_ok=True)
    for kind, data in result.items():
        if not data:
            continue
        with open(os.path.join(LEGACY, kind + '.json'), 'w', encoding='utf-8') as f:
            json.dump({k: data[k] for k in sorted(data)}, f,
                      ensure_ascii=False, indent=1)
        print('  tools/legacy/%s.json  %d' % (kind, len(data)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
