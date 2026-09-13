# -*- coding: utf-8 -*-
"""Одна англійська назва — два українські написання. Хто з них правий?

`q.py dup` показує розбіжність, але не каже, що виправляти. Голосувати мають
не словники (там кожен варіант трапляється раз), а **сам корпус**: репліки,
журнал і тексти книг. Гравець читає саме їх, тож написання, яке там уже
стоїть сотню разів, і є усталеним — а поодинокий інший варіант у словнику
предметів чи в темі діалогу є помилкою, хай навіть він з'явився першим.

Скрипт для кожної суперечки рахує входження кожного варіанта в корпусі
(разом із відмінковими формами: збіг шукаємо по основі без останніх двох
літер) і пропонує більшість. Де корпус мовчить — каже «корпус не знає»,
і рішення лишається за людиною: тоді працює таблиця транслітерації з
CONVENTIONS §4.

    py tools\\items\\settle_names.py            # усі суперечки з підказкою
    py tools\\items\\settle_names.py --quiet    # лише ті, де корпус має думку
"""

import glob
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import q  # noqa: E402  (той самий corpus(), щоб суперечки збігалися з `q.py dup`)

# q.py при імпорті вже перевів stdout на utf-8 — своєї обгортки не ставимо:
# друга закрила б першу.

# Де корпус помиляється більшістю — рішення записане тут, а не в голові.
SKIP = {
    # CONVENTIONS §5: святі Храму Меріс, Рілмс і Серин - жінки. Корпус
    # чотири рази написав «Святий Меріс»; це помилка, а не норма.
    'Saint Meris': 'Свята Меріс',
    # Ogdum, а не Ogdun: у корпусі тричі проскочила описка.
    'Lugrub gro-Ogdum': 'Луґруб ґро-Оґдум',
    # Плантація належить Орвасу Дрену, тож вона Дрен**а**. Корпус так і пише
    # частіше (18 проти 14), але голосування цього не бачить: «плантація Дрен»
    # є початком «плантація Дрена» і забирає його голоси собі.
    'Dren Plantation': 'Плантація Дрена',
}


def texts():
    """Усе, що гравець читає суцільним текстом: репліки, журнал, книги."""
    for path in sorted(glob.glob(os.path.join(TOOLS, 'uk', '*.json'))):
        d = load(path)
        if isinstance(d, dict):
            for v in d.values():
                if isinstance(v, str):
                    yield v
    books = os.path.join(TOOLS, 'books', 'uk_books.json')
    if os.path.isfile(books):
        d = load(books)
        if isinstance(d, dict):
            for v in d.values():
                if isinstance(v, str):
                    yield v


def load(path):
    with open(path, 'rb') as f:
        raw = f.read()
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return json.loads(raw.decode('utf-16'))
    return json.loads(raw.decode('utf-8-sig'))


WORD = re.compile(r'[^\W\d_]+', re.UNICODE)


def pattern(name, loose=True):
    """Регулярка, що ловить назву в будь-якому відмінку.

    Відмінюється хвіст кожного слова, і не конче останнього: «Виделка Жаху»
    в тексті стоїть як «Виделку Жаху». Тому кожне слово обрізаємо на літеру
    (довгі — на дві) і дозволяємо будь-яке закінчення.

    Короткі слова («Св.», «гра-») беремо як є: обрізати їх нема куди, а «Св»
    із хвостом «\w*» зловило б піввсесвіту. Якщо коротких слів уся назва
    («Тел Фір»), то `loose` вимикають — і шукають назву буквально.
    """
    if not loose:
        return re.compile(r'\b' + re.escape(name) + r'\w*', re.IGNORECASE | re.UNICODE)
    parts, solid = [], False
    for piece in re.split(r'(\W+)', name):
        if not WORD.fullmatch(piece or ''):
            parts.append(re.escape(piece))
            continue
        cut = piece[:-2] if len(piece) > 6 else (piece[:-1] if len(piece) > 4 else piece)
        if len(cut) < 4:
            parts.append(re.escape(piece))
            continue
        solid = True
        parts.append(re.escape(cut) + r'\w*')
    if not solid:
        return None
    return re.compile(''.join(parts), re.IGNORECASE | re.UNICODE)


def votes(variants, blob):
    """Голоси корпусу за кожен варіант.

    Обидва варіанти міряємо однією міркою. Інакше виходить кривда: «Тель Фір»
    має чотирилітерне «Тель» і рахується з хвостом, а «Тел Фір» — саме коротке,
    і без спільного правила дістав би нуль просто за те, що коротший.
    """
    pats = {v: pattern(v) for v in variants}
    loose = all(p is not None for p in pats.values())
    if loose:
        # Основа не сміє накривати сусіда. «Сиродил» обрізається до «Сирод»,
        # а це ловить і «Сиродіїл» - обидва варіанти дістали б чужі голоси.
        for v, rx in pats.items():
            if any(u != v and rx.fullmatch(u) for u in variants):
                loose = False
                break
    out = []
    for v in variants:
        rx = pats[v] if loose else pattern(v, False)
        out.append((len(rx.findall(blob)) if rx else 0, v))
    return out


def conflicts():
    variants = defaultdict(set)
    where = defaultdict(set)
    for name, k, v in q.corpus():
        variants[k].add(v)
        where[k].add(name)
    out = {}
    for k, vs in variants.items():
        norm = set(v[:1].upper() + v[1:] for v in vs)
        if len(norm) > 1:
            out[k] = (sorted(vs), sorted(where[k]))
    return out


def write(path, data):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write('\n')


def apply(fixes):
    """Записати переможця в кожен словник і в кожну тему, де стоїть інше.

    Тексти корпусу не чіпаємо: `--apply` працює лише там, де програлий варіант
    у корпусі не трапляється жодного разу, тож правити нема чого.
    """
    topics = None
    tpath = os.path.join(TOOLS, 'topics', 'dial_topics.json')
    if os.path.isfile(tpath):
        topics = {name: i for i, name in enumerate(load(tpath))}

    changed = 0
    for path in sorted(glob.glob(os.path.join(TOOLS, 'items', '*.json'))
                       + glob.glob(os.path.join(TOOLS, 'topics', 'uk_dial_topics*.json'))
                       + glob.glob(os.path.join(TOOLS, 'gmst', 'uk_*.json'))):
        name = os.path.basename(path)
        if name.startswith('_'):
            continue
        d = load(path)
        if not isinstance(d, dict):
            continue
        dirty = False
        if name.startswith('uk_dial_topics'):
            for en, win in fixes.items():
                i = topics.get(en) if topics else None
                if i is None:
                    continue
                k = str(i)
                if k in d and d[k] != win:
                    d[k] = win
                    dirty = True
                    changed += 1
        else:
            for en, win in fixes.items():
                if en in d and isinstance(d[en], str) and d[en] != win:
                    d[en] = win
                    dirty = True
                    changed += 1
        if dirty:
            write(path, d)
            print('   %s' % name)
    return changed


def caps(name):
    return sum(1 for w in WORD.findall(name) if w[:1].isupper())


def case_only(bad):
    """Суперечки, де різниця лише у великих літерах усередині назви.

    Український правопис лишає велику літеру першому слову, а всередині —
    тільки власним назвам. «Амулет Єдності» проти «Амулет єдності», «Гільдія
    Бійців» проти «Гільдія бійців» — тут нема чого зважувати корпусом: беремо
    варіант із меншою кількістю великих. Слово, велике в обох варіантах
    («Крижаний клинок **Монарха**»), таким і лишається.
    """
    out = {}
    for en, (vs, _) in bad.items():
        if len(set(v.lower() for v in vs)) != 1:
            continue
        out[en] = min(vs, key=lambda v: (caps(v), v))
    return out


def main():
    quiet = '--quiet' in sys.argv
    doit = '--apply' in sys.argv
    if '--case' in sys.argv:
        bad = conflicts()
        fixes = case_only(bad)
        for en in sorted(fixes):
            print('%-42s -> %s' % (en, fixes[en]))
        print('назв: %d' % len(fixes))
        if doit:
            print('змінено записів: %d' % apply(fixes))
        return
    bad = conflicts()
    blob = '\n'.join(texts())

    decided = mute = 0
    fixes = {}
    for en in sorted(bad):
        vs, where = bad[en]
        tally = votes(vs, blob)
        tally.sort(key=lambda t: -t[0])
        top, rest = tally[0], tally[1:]
        speaks = top[0] > 0 and top[0] != rest[0][0]
        clean = speaks and all(n == 0 for n, _ in rest)
        if en in SKIP:
            top, speaks, clean = (0, SKIP[en]), True, True
        if speaks:
            decided += 1
        else:
            mute += 1
        if clean:
            fixes[en] = top[1]
        if quiet and not speaks:
            continue
        if doit:
            continue
        mark = '=>' if clean else ('->' if speaks else ' ?')
        print('%s %-38s %s' % (mark, en, '  |  '.join(
            '%s (%d)' % (v, n) for n, v in tally)))
        print('   %-38s   у: %s' % ('', ', '.join(where)))

    if doit:
        print('переписую словники й теми (%d назв):' % len(fixes))
        print('змінено записів: %d' % apply(fixes))
        return

    print()
    print('суперечок: %d; корпус має думку про %d, мовчить про %d'
          % (len(bad), decided, mute))
    print('з них безпечних для --apply (програлого в корпусі нема): %d'
          % len(fixes))


if __name__ == '__main__':
    main()
