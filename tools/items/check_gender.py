# -*- coding: utf-8 -*-
"""Чи узгоджено рід у вивісках крамниць зі статтю самого NPC.

Вивіска — це активатор виду «Ім'я: професія» («Ірґола: лихварка»). Професія
має стояти в тому роді, що й власник, інакше гравець читає «Бервен: торговець»
про жінку. На око це не ловиться: імен три тисячі, і за багатьма з них стать
не вгадаєш.

Стать беремо з самої гри: у записі NPC_ є підзапис FLAG, біт 0x0001 — жінка.
Тому скрипт потребує ігрових файлів і в CI не ходить - це локальна ревізія,
як extract_items.py.

    py tools\\items\\check_gender.py

Словник FEMALE нижче — це професії, що мають окрему жіночу форму. Як додасте
нову вивіску з професією, якої тут немає, впишіть її сюди, інакше перевірка
мовчки її пропустить.
"""
import io
import json
import os
import struct
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                              errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, TOOLS)
import paths

FEMALE = {
    'торговець': 'торговка', 'лихвар': 'лихварка', 'книгар': 'книгарка',
    'зброяр': 'зброярка', 'коваль': 'ковалька', 'аптекар': 'аптекарка',
    'алхімік': 'алхімічка', 'зачарувальник': 'зачарувальниця',
    'спорядник': 'спорядниця', 'кравець': 'кравчиня', 'пекар': 'пекарка',
    'корчмар': 'корчмарка', 'шинкар': 'шинкарка', 'цілитель': 'цілителька',
    'жрець': 'жриця', 'маг': 'магиня', 'ювелір': 'ювелірка',
    'мисливець': 'мисливиця', 'писар': 'писарка', 'слуга': 'служниця',
}


def subrecords(body):
    sp = 0
    while sp + 8 <= len(body):
        st = body[sp:sp + 4]
        n = struct.unpack('<I', body[sp + 4:sp + 8])[0]
        yield st, body[sp + 8:sp + 8 + n]
        sp += 8 + n


def npcs(data):
    """(ім'я, жінка?) для кожного запису NPC_ у файлі."""
    pos, end = 0, len(data)
    while pos + 16 <= end:
        rtype = data[pos:pos + 4]
        size = struct.unpack('<I', data[pos + 4:pos + 8])[0]
        if rtype == b'NPC_':
            name, flags = '', None
            for st, sd in subrecords(data[pos + 16:pos + 16 + size]):
                raw = sd[:-1] if sd.endswith(b'\0') else sd
                if st == b'FNAM':
                    name = raw.decode('cp1251', 'replace')
                elif st == b'FLAG' and len(sd) >= 4:
                    flags = struct.unpack('<I', sd[:4])[0]
            if name and flags is not None:
                yield name, bool(flags & 0x0001)
        pos += 16 + size


def main():
    dirs, contents = paths.read_modlist()
    resolved = paths.resolve_plugins(dirs)
    gender = {}
    for nm in contents:
        p = resolved.get(nm.lower())
        if p and os.path.isfile(p):
            for name, female in npcs(open(p, 'rb').read()):
                gender[name] = female          # пізніший плагін перекриває

    act = json.load(open(os.path.join(HERE, 'uk_activator.json'),
                         encoding='utf-8'))
    act.pop('_comment', None)

    bad = []
    for en, uk in act.items():
        if ':' not in en or ':' not in uk:
            continue
        who = en.split(':', 1)[0].strip()
        who_uk, prof = uk.split(':', 1)
        prof = prof.strip().lower()
        if gender.get(who) and prof in FEMALE:
            bad.append((en, uk, '%s: %s' % (who_uk.strip(), FEMALE[prof])))

    print('NPC зі статтю з гри : %d (жінок %d)'
          % (len(gender), sum(1 for v in gender.values() if v)))
    print('вивісок перевірено  : %d' % sum(1 for e in act if ':' in e))
    for en, uk, fix in sorted(bad):
        print('  %-34s %-30s -> %s' % (en, uk, fix))
    print('чоловічий рід для жінки: %d' % len(bad))
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
