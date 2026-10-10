# -*- coding: utf-8 -*-
"""Записи в дереві реплік, які не перекладаються, і чому.

Навіщо
------
У дереві реплік живуть не лише репліки. Моди тримають там і службові речі:

* **розділювачі** - запис із назвою на зразок
  `FMI - LEGION, DWEMER WEAPONS------------------...`, щоб у редакторі
  розділ було видно оком;
* **уламки умов** - `Goblet10`, `Axe_Soultrap`, `Grieves`, `L`, `R`, `50`,
  `00`: частини ідентифікаторів речей, за якими мод розпізнає контрабанду;
* **присвоєння змінних** - `FMIHandinEBONY = 1`;
* **позначки розділів великими літерами** - `PUBLICANS`, `NON-DUNMER`,
  `RAVEN ROCK`, `END OF KHAJIIT`.

Гравець цього не бачить ніколи. Перекладений `Goblet10` у кращому разі
нічого не змінить, у гіршому зіб'є модові розпізнавання речі. А в підрахунку
залишку вони створюють хибне відчуття роботи: `mod_fmi_servicerefusal_contraband`
показував 105 неперекладених рядків, і всі 105 були оце.

Як вирішуємо
------------
Два правила, обидва мусять бути очевидні з самого рядка:

1. **Розділювач** - десять і більше дефісів підряд. Таке в репліці не
   трапляється: там тире, а не частокіл.
2. **Явний список** - `skip.json`, по зрізу й номеру рядка, з причиною.

Усе інше перекладається. Правило «коротке - значить службове» тут навмисне
відсутнє: «Прощавай.» теж коротке.

    py tools/dialogue/skip.py <зріз>     # що пропущено в зрізі й чому
    py tools/dialogue/skip.py            # скільки пропущено всюди
"""
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.abspath(os.path.join(HERE, '..'))
SRC = os.path.join(TOOLS, 'src')
LIST = os.path.join(HERE, 'skip.json')

RULE = re.compile(r'-{10,}')


def load(path):
    with open(path, 'rb') as f:
        raw = f.read()
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return json.loads(raw.decode('utf-16'))
    return json.loads(raw.decode('utf-8-sig'))


def explicit():
    """Явні пропуски: {зріз: {номер: причина}}."""
    if not os.path.isfile(LIST):
        return {}
    return load(LIST)


def skipped(name, text, index, table=None):
    """Чи цей рядок зрізу свідомо не перекладається."""
    if RULE.search(text):
        return 'розділювач у дереві реплік'
    if table is None:
        table = explicit()
    return table.get(name, {}).get(str(index))


def main():
    # Обгортку ставимо тут, а не при імпорті: batch.py імпортує цей модуль,
    # і друга обгортка над тим самим буфером закривала б першу.
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='replace', write_through=True)
    table = explicit()
    names = sys.argv[1:]
    if not names:
        names = sorted(os.path.basename(p)[:-5]
                       for p in glob.glob(os.path.join(SRC, '*.json')))
        verbose = False
    else:
        verbose = True
    total = 0
    for name in names:
        path = os.path.join(SRC, name + '.json')
        if not os.path.isfile(path):
            print('немає зрізу: ' + name)
            continue
        src = load(path)
        if not isinstance(src, list):
            continue
        rows = [(i, s, skipped(name, s, i, table))
                for i, s in enumerate(src) if isinstance(s, str)]
        rows = [r for r in rows if r[2]]
        if not rows:
            continue
        total += len(rows)
        print('%s: %d' % (name, len(rows)))
        if verbose:
            for i, s, why in rows:
                print('  %5d  %-34s %s' % (i, s[:34].replace('\n', ' '), why))
    print('пропущено всього: %d' % total)
    return 0


if __name__ == '__main__':
    sys.exit(main())
