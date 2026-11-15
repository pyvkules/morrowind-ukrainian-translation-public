# -*- coding: utf-8 -*-
"""Річ у завданні зветься так, як вона зветься в торбі - перевірка без правил.

`dialogue/item_words.py` робить те саме, але за правилами, які треба написати
рукою: доти, доки хтось не завважить розходження, його ніхто не ловить. Саме
так чотири гриби Аджири мали по три назви кожен - у торбі «Сяйлива сироїжка»,
в темі «Сяйлива Русула», а в журналі «світної сироїжки». Гравець читає
завдання, шукає в торбі назву, якої там немає, і завдання провисає.

Тут те саме питання ставиться само. Беремо назву речі зі словника, шукаємо
репліки, де **англійський** першотвір цю річ називає, і дивимося, чи згадана
вона в українському тексті бодай якоюсь формою своєї словникової назви.
Відмінки ловимо тим самим матчером, що й теми (`topics/forms.py`).

Переклад має право перефразувати, тож частина знахідок - не помилки. Законні
перелічені у `quest_names_ok.json` з поясненням, чому.

    py tools\\items\\quest_names.py            # перелік розходжень
    py tools\\items\\quest_names.py --all      # і ті, що в списку дозволених

Вихід 1, якщо знайшлося розходження поза списком.
"""
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(TOOLS, 'topics'))
import forms

SRC = os.path.join(TOOLS, 'src')
UK = os.path.join(TOOLS, 'uk')
OK = os.path.join(HERE, 'quest_names_ok.json')

# Словники, де лежать назви речей, які гравець тримає в руках.
DICTS = ('weapon', 'armour', 'clothing', 'misc', 'ingredient', 'container',
         'apparatus', 'potion', 'lockpick', 'probe', 'light', 'book_title')

# Назва мусить бути досить своєрідна, щоб її згадка в тексті щось значила.
# «Gold» або «Key» трапляються всюди й самі по собі не кажуть ні про що.
TOO_COMMON = set('''gold key ring robe shirt pants shoes boots belt
cup bowl plate fork spoon knife candle lamp lantern book note letter
scroll paper map torch bottle flask cloth skin bone dust salt water
wine ale beer bread meat cheese egg flower leaf seed root'''.split())


def load(path):
    return json.loads(io.open(path, encoding='utf-8-sig').read())


def item_names():
    """англійська назва -> українська, лише ті, що варто перевіряти."""
    out = {}
    for name in DICTS:
        for fn in ('uk_%s.json' % name, '%s_overrides.json' % name):
            p = os.path.join(HERE, fn)
            if not os.path.isfile(p):
                continue
            for en, uk in load(p).items():
                if en.startswith('_') or not isinstance(uk, str):
                    continue
                words = re.findall(r"[A-Za-z']+", en)
                if len(words) < 2:
                    continue            # однослівну назву в тексті не відрізнити
                if all(w.lower() in TOO_COMMON for w in words):
                    continue
                if len(en) < 8:
                    continue
                out[en] = uk
    return out


def slices():
    """(зріз, англійські рядки, українські рядки) - як в item_words.py."""
    for path in sorted(glob.glob(os.path.join(SRC, '*.json'))):
        name = os.path.basename(path)[:-5]
        if name.endswith('.topics'):
            continue
        src = load(path)
        if not isinstance(src, list):
            continue
        uk = {}
        for part in sorted(glob.glob(os.path.join(UK, name + '.json'))
                           + glob.glob(os.path.join(UK, name + '_p*.json'))):
            uk.update(load(part))
        yield name, src, uk


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  newline='\n')
    show_all = '--all' in sys.argv
    allow = load(OK) if os.path.isfile(OK) else {}
    names = item_names()
    pats = forms.build(set(names.values()))
    # англійську назву шукаємо цілим словосполученням, незалежно від регістру
    rx = {en: re.compile(r'\b' + re.escape(en) + r'\b', re.I) for en in names}

    # Сім тисяч назв проти тридцяти шести тисяч реплік у лоб - це години.
    # Тож спершу покажчик: найрідкісніше слово назви -> самі назви. Для рядка
    # беремо лише ті назви, чиє рідкісне слово в ньому взагалі є, і тільки їх
    # і міряємо взірцем.
    WORD = re.compile(r"[A-Za-z']+")
    freq = {}
    for en in names:
        for w in WORD.findall(en.lower()):
            freq[w] = freq.get(w, 0) + 1
    index = {}
    for en in names:
        ws = WORD.findall(en.lower())
        rare = min(ws, key=lambda w: freq[w])
        index.setdefault(rare, []).append(en)

    found, skipped, heads = 0, 0, {}
    for sl, src, uk in slices():
        for i, s in enumerate(src):
            t = uk.get(str(i))
            if not isinstance(s, str) or not isinstance(t, str):
                continue
            words = set(WORD.findall(s.lower()))
            cand = []
            for w in words:
                cand.extend(index.get(w, ()))
            for en in cand:
                want = names[en]
                if not rx[en].search(s):
                    continue
                if want.lower() in t.lower():
                    continue
                if want in pats and forms.find(t, want, pats):
                    continue
                # Перевіряти всю назву цілком - майже самий шум: переклад має
                # право сказати «гуарячі шкури» там, де річ зветься «Шкури
                # гуарів», і гравець її однаково впізнає. А от коли зникає
                # головне слово, впізнати вже нічого: саме так «Сяйлива
                # сироїжка» ставала «Сяйливою Русулою». Тож питаємо лише
                # про останнє слово назви - в цьому словнику воно й несе суть.
                head = (re.findall(u'[%s]{4,}' % forms.CYR, want) or [None])[-1]
                if head is None:
                    continue
                if head not in heads:
                    rx2, stems = forms.pattern(head)
                    heads[head] = (rx2, stems)
                rx2, stems = heads[head]
                if rx2 is None or forms.find(t, head, {head: [(rx2, stems, False)]}):
                    continue
                key = '%s:%d:%s' % (sl, i, en)
                if key in allow and not show_all:
                    skipped += 1
                    continue
                found += 1
                print(u'%s %d: %s -> чекали «%s»%s'
                      % (sl, i, en, want, '  [дозволено]' if key in allow else ''))
                print(u'  en %s' % ' '.join(s.split())[:170])
                print(u'  uk %s' % ' '.join(t.split())[:170])
    print(u'речей, названих у завданні не так, як у торбі: %d'
          % (found - (skipped if show_all else 0)))
    if skipped:
        print(u'дозволених пропущено: %d' % skipped)
    return 1 if found and not show_all else 0


if __name__ == '__main__':
    sys.exit(main())
