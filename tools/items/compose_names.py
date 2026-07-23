# -*- coding: utf-8 -*-
"""Скласти українські назви предметів із прикметників і типів.

Назви зброї, обладунку та одягу в Morrowind систематичні: [матеріал/якість]* [тип],
іноді з чарами "of X". Замість перекладати 5 тисяч рядків поштучно, складаємо їх із
невеликого словника (lexicon.json), узгоджуючи прикметник у роді/числі з головним
іменником типу: "Steel Cuirass" -> "сталева кіраса", "Iron Boots" -> "залізні чоботи".

Обережність понад повноту: перекладаємо лише назви, у яких КОЖЕН провідний токен -
відомий прикметник, а хвіст - відомий тип. Назви з "of X" чи невідомими словами
пропускаємо (їх візьме наступний прохід). Так вихід завжди коректний і перевірний.

Пише tools/items/uk_<category>.json  { "English name": "українська назва" }.

    py compose_names.py            # діагностика: покриття + приклади
    py compose_names.py --apply    # записати uk_*.json
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
LEX = json.load(open(os.path.join(HERE, 'lexicon.json'), encoding='utf-8'))
END = LEX['endings']
ADJ = LEX['adj']
ADJ_FORMS = LEX['adj_forms']
TYPES = LEX['types']
GENDER_IDX = {'m': 0, 'f': 1, 'n': 2, 'pl': 3}
CATEGORIES = ['weapon', 'armour', 'clothing']


def adj_form(word, gender):
    """Прикметник у потрібному роді, або None якщо слово невідоме."""
    if word in ADJ_FORMS:
        return ADJ_FORMS[word][GENDER_IDX[gender]]
    stem = ADJ.get(word)
    if stem is None:
        return None
    return stem + END[gender]


def match_type(tokens):
    """Знайти найдовший відомий тип у кінці; повернути (uk_noun, gender, n_tokens)."""
    for take in (3, 2, 1):
        if len(tokens) >= take:
            key = ' '.join(tokens[-take:])
            if key in TYPES:
                noun, gender = TYPES[key]
                return noun, gender, take
    return None


def compose(name):
    """Скласти українську назву або None, якщо не всі токени відомі."""
    if re.search(r'\bof\b', name):          # чари лишаємо на потім
        return None
    # прибрати оздоблення на кшталт зірочок або дужок
    clean = name.strip().strip('*').strip()
    if clean != name.strip() or '(' in clean or not clean:
        return None
    tokens = clean.split()
    m = match_type(tokens)
    if not m:
        return None
    noun, gender, take = m
    lead = tokens[:len(tokens) - take]
    if not lead:
        return None                          # сам тип без матеріалу - неоднозначно, пропускаємо
    adjs = []
    for w in lead:
        f = adj_form(w, gender)
        if f is None:
            return None                      # хоч один невідомий токен -> не чіпаємо
        adjs.append(f)
    return ' '.join(adjs) + ' ' + noun


def main():
    apply = '--apply' in sys.argv
    grand_done = grand_total = 0
    for cat in CATEGORIES:
        path = os.path.join(HERE, cat + '.json')
        names = list(json.load(open(path, encoding='utf-8')))
        out, samples = {}, []
        for n in names:
            uk = compose(n)
            if uk:
                out[n] = uk
                if len(samples) < 6:
                    samples.append((n, uk))
        grand_done += len(out)
        grand_total += len(names)
        print('%-9s %4d / %4d  (%.0f%%)' % (cat, len(out), len(names),
                                            100.0 * len(out) / len(names)))
        for en, uk in samples:
            print('    %-28s -> %s' % (en, uk))
        if apply:
            with open(os.path.join(HERE, 'uk_' + cat + '.json'), 'w', encoding='utf-8') as f:
                json.dump({k: out[k] for k in sorted(out)}, f, ensure_ascii=False, indent=1)
    print()
    print('РАЗОМ складено: %d / %d (%.0f%%)'
          % (grand_done, grand_total, 100.0 * grand_done / grand_total))
    print('режим: %s' % ('ЗАПИСАНО uk_*.json' if apply else 'проба (--apply щоб записати)'))


if __name__ == '__main__':
    main()
