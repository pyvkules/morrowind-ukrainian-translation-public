# -*- coding: utf-8 -*-
"""Скласти назви істот: [прикметник(и)] + базова істота, з узгодженням роду.

Бестіарій Morrowind систематичний: базові істоти (щур, гуар, центуріон, привид...)
повторюються з прикметниковими означеннями (заражений, викликаний, прадавній,
морозний...). Складаємо як зброю: прикметник узгоджуємо в роді/числі з родом
базового іменника. Власні назви (Dagoth ..., унікальні боси) і означення-іменники
(Ancestor Ghost) лишаємо ручному проходу.

Пише tools/items/uk_creature.json.
    py compose_creatures.py            # діагностика
    py compose_creatures.py --apply
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
END = {'m': 'ий', 'f': 'а', 'n': 'е', 'pl': 'і'}
GIDX = {'m': 0, 'f': 1, 'n': 2, 'pl': 3}

ADJ = {
    'Diseased': 'хвор', 'Infected': 'заражен', 'Summoned': 'викликан',
    'Dead': 'мертв', 'Blighted': 'моров', 'Frost': 'морозн', 'Snow': 'сніжн',
    'Wild': 'дик', 'Black': 'чорн', 'Giant': 'велетенськ', 'Bone': 'кістян',
    'Skeletal': 'кістян', 'Cave': 'печерн', 'Blind': 'сліп', 'Advanced': 'удосконален',
    'Armored': 'броньован', 'Ash': 'попеляст', 'Plague': 'чумн', 'Red': 'червон',
    'White': 'біл', 'Grey': 'сір', 'Gray': 'сір', 'Golden': 'золот',
    'Wounded': 'поранен', 'Rabid': 'скажен', 'Feral': 'здичавіл', 'Elder': 'старш',
    'Young': 'молод', 'Enslaved': 'поневолен', 'Corrupted': 'зіпсут',
    'Venomous': 'отруйн', 'Fire': 'вогнян', 'Storm': 'штормов', 'Ancestral': 'родов',
}
ADJ_FORMS = {
    'Greater': ['більший', 'більша', 'більше', 'більші'],
    'Lesser': ['менший', 'менша', 'менше', 'менші'],
    'Ancient': ['прадавній', 'прадавня', 'прадавнє', 'прадавні'],
    'Elder2': ['давній', 'давня', 'давнє', 'давні'],
}
BASE = {
    'Rat': ['щур', 'm'], 'Guar': ['гуар', 'm'], 'Wolf': ['вовк', 'm'],
    'Centurion': ['центуріон', 'm'], 'Bear': ['ведмідь', 'm'], 'Moth': ['міль', 'f'],
    'Spider': ['павук', 'm'], 'Beetle': ['жук', 'm'], 'Bonewalker': ['костохід', 'm'],
    'Guardian': ['страж', 'm'], 'Draugr': ['драугр', 'm'], 'Atronach': ['атронах', 'm'],
    'Butterfly': ['метелик', 'm'], 'Ghost': ['привид', 'm'], 'Champion': ['чемпіон', 'm'],
    'Netch': ['нетч', 'm'], 'Nix-Hound': ['нікс-гончак', 'm'], 'Scrib': ['скриб', 'm'],
    'Skeleton': ['скелет', 'm'], 'Queen': ['королева', 'f'], 'Dreugh': ['дреуг', 'm'],
    'Kagouti': ['кагуті', 'm'], 'Warrior': ['воїн', 'm'], 'Shalk': ['шальк', 'm'],
    'Sphere': ['сфера', 'f'], 'Alit': ['аліт', 'm'], 'Cephalopod': ['головоног', 'm'],
    'Lich': ['ліх', 'm'], 'Lord': ['володар', 'm'], 'Crab': ['краб', 'm'],
    'Fish': ['риба', 'f'], 'Troll': ['троль', 'm'], 'Mudcrab': ['грязьовий краб', 'm'],
    'Durzog': ['дурзог', 'm'], 'Goat': ['коза', 'f'], 'Monarch': ['монарх', 'm'],
    'Worker': ['робітник', 'm'], 'Scamp': ['скамп', 'm'], 'Grahl': ['грал', 'm'],
    'Fabricant': ['фабрикант', 'm'], 'Muskrat': ['ондатра', 'f'],
    'Parastylus': ['парастил', 'm'], 'Slaughterfish': ['риба-різник', 'f'],
    'Bonelord': ['кістяний володар', 'm'], 'Racer': ['літун', 'm'],
    'Skeever': ['злоскверн', 'm'], 'Rabbit': ['кріль', 'm'], 'Boar': ['вепр', 'm'],
    'Horker': ['горкер', 'm'], 'Zombie': ['зомбі', 'm'], 'Wraith': ['примара', 'f'],
    'Golem': ['голем', 'm'], 'Ghoul': ['гуль', 'm'], 'Dremora': ['дремора', 'm'],
    'Scarab': ['скарабей', 'm'], 'Hound': ['гончак', 'm'], 'Ogre': ['огр', 'm'],
    'Imp': ['імп', 'm'], 'Daedroth': ['даедрот', 'm'], 'Clannfear': ['кланфір', 'm'],
    'Hunger': ['ненажера', 'f'], 'Scamps': ['скампи', 'pl'],
}


def adj_form(word, gender):
    if word in ADJ_FORMS:
        return ADJ_FORMS[word][GIDX[gender]]
    stem = ADJ.get(word)
    return None if stem is None else stem + END[gender]


def compose(name):
    if any(c in name for c in '[]()_,'):
        return None
    toks = name.split()
    if len(toks) < 2:
        return None
    base = None
    if toks[-1] in BASE:
        base, take = BASE[toks[-1]], 1
    if base is None:
        return None
    noun, gender = base
    lead = toks[:-1]
    adjs = []
    for w in lead:
        f = adj_form(w, gender)
        if f is None:
            return None
        adjs.append(f)
    return ' '.join(adjs) + ' ' + noun


def main():
    apply = '--apply' in sys.argv
    names = list(json.load(open(os.path.join(HERE, 'creature.json'), encoding='utf-8')))
    out = {}
    for n in names:
        uk = compose(n)
        if uk:
            out[n] = uk
    print('складено %d / %d (%.0f%%)' % (len(out), len(names), 100.0 * len(out) / len(names)))
    for n in list(out)[:14]:
        print('    %-30s -> %s' % (n, out[n]))
    if apply:
        with open(os.path.join(HERE, 'uk_creature.json'), 'w', encoding='utf-8') as f:
            json.dump({k: out[k] for k in sorted(out)}, f, ensure_ascii=False, indent=1)
        print('ЗАПИСАНО uk_creature.json')


if __name__ == '__main__':
    main()
