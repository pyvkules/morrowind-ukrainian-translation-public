# -*- coding: utf-8 -*-
"""Перенести наявний переклад на репліки, що різняться лише пунктуацією.

Та сама здогадка, що спрацювала на книгах. «Patch for Purists» та інші фікси
переписують репліки базової гри, виправляючи описку, кому чи подвійний пробіл,
- і по тексту вони вже не збігаються зі зрізом, хоч це та сама репліка.
`patch_plugins.py` шукає переклад за **точним** англійським текстом, тож для
нього це різні рядки, і репліка лишається англійською в грі.

Знеособлюємо пунктуацію й пробіли і шукаємо збіг. Виміряно: так закривається
916 реплік на 117 тис. символів, найбільше в Patch for Purists (460) і
PR Voice Overhaul (333).

Чого НЕ переносимо
------------------
Підстановки (%PCName, %Name) і теми в @...# несуть зміст, тому в знеособленні
вони лишаються. Якщо їхній набір у двох реплік різний, це не та сама репліка -
пропускаємо, хоч би як решта збігалася.

І окремо - рядки СУЦІЛЬНИМИ ВЕЛИКИМИ. Знеособлення не зважає на регістр (це
потрібно, бо фікси правлять саме регістр: `ashlands` -> `Ashlands`), але через
це `NORD` збігався з `Nord?` і діставав переклад «Норде?» - з питальним знаком,
якого в оригіналі нема. У `FMI_ServiceRefusal_Contraband` такі великі слова
(NORD, REDGUARD, KHAJIIT, HELMET) - позначки, а не мовлення. Тож коли одна
репліка вся велика, а друга ні, це різні речі.

Usage: py reuse.py [--apply]
"""
import glob
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.abspath(os.path.join(HERE, '..'))

WS = re.compile(r'\s+')
PUNCT = re.compile(r'[^\w@#%\s]', re.UNICODE)
TOKEN = re.compile(r'%[A-Za-z]+')
TOPIC = re.compile(r'@([^#]*)#')


def load_json(path):
    raw = open(path, 'rb').read()
    for enc in ('utf-8-sig', 'utf-16', 'cp1251'):
        try:
            return json.loads(raw.decode(enc))
        except (UnicodeDecodeError, ValueError):
            continue
    raise ValueError('не можу прочитати ' + path)


def bare(t):
    return WS.sub(' ', PUNCT.sub('', t)).strip().lower()


def marks(t):
    """Те, що мусить збігтися точно: підстановки, теми і «весь рядок великими»."""
    letters = [c for c in t if c.isalpha()]
    shout = bool(letters) and all(c.isupper() for c in letters)
    return (tuple(sorted(set(TOKEN.findall(t)))),
            tuple(sorted(set(m.strip().lower() for m in TOPIC.findall(t)))),
            shout)


def slices():
    """(ім'я зрізу, англійські тексти, {індекс: переклад}, файл для дозапису)."""
    for sp in sorted(glob.glob(os.path.join(TOOLS, 'src', '*.json'))):
        name = os.path.splitext(os.path.basename(sp))[0]
        src = load_json(sp)
        if not isinstance(src, list):
            continue
        paths = sorted(glob.glob(os.path.join(TOOLS, 'uk', name + '.json'))
                       + glob.glob(os.path.join(TOOLS, 'uk', name + '_p*.json')))
        done = {}
        for p in paths:
            for k, v in json.load(open(p, encoding='utf-8')).items():
                done[int(k)] = v
        yield name, src, done, (paths[-1] if paths
                                else os.path.join(TOOLS, 'uk', name + '.json'))


def main():
    apply = '--apply' in sys.argv

    memory = {}
    for name, src, done, _ in slices():
        for i, uk in done.items():
            if 0 <= i < len(src):
                memory.setdefault((bare(src[i]), marks(src[i])), uk)

    total, skipped = 0, 0
    for name, src, done, out in slices():
        add = {}
        for i, en in enumerate(src):
            if i in done:
                continue
            key = (bare(en), marks(en))
            if key in memory:
                add[str(i)] = memory[key]
        if not add:
            continue
        total += len(add)
        print('%-34s +%d' % (name, len(add)))
        if apply:
            d = json.load(open(out, encoding='utf-8')) if os.path.isfile(out) else {}
            d.update(add)
            json.dump(d, open(out, 'w', encoding='utf-8'), ensure_ascii=False,
                      indent=1, sort_keys=True)

    print('\nперенесено: %d%s' % (total, '' if apply else '  (пробний запуск)'))


main()
