# -*- coding: utf-8 -*-
"""Скласти назви заклять для систематичної частини.

Дві надійні моделі:
  1. пряма відповідність - назва закляття дослівно збігається з назвою магічного
     ефекту, яку ми вже переклали в GMST (Summon Scamp, Bound Dagger, Blind, ...);
  2. складання [дія] + [атрибут/стихія]: "Absorb Strength" -> «Поглинути силу»
     (дієслово + знахідний відмінок).
Плюс суфікс "[Ranged]" -> « (на відстані)».

Решту (власні назви, тірні префікси Wild/Greater/... , описові Acid Cloud) лишаємо
наступному проходу, тож вихід завжди коректний.

Пише tools/items/uk_spell.json.
    py compose_spells.py            # діагностика
    py compose_spells.py --apply
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
GMST = os.path.join(HERE, '..', 'gmst')

# дія -> дієслово (наказовий/інфінітив, як у назвах ефектів)
VERB = {'Absorb': 'Поглинути', 'Drain': 'Виснажити', 'Damage': 'Ушкодити',
        'Restore': 'Відновити', 'Fortify': 'Підсилити'}
# атрибут/стихія у ЗНАХІДНОМУ відмінку
ACC = {'Health': "здоров'я", 'Magicka': 'ману', 'Fatigue': 'запас сил',
       'Strength': 'силу', 'Intelligence': 'інтелект', 'Willpower': 'силу волі',
       'Agility': 'спритність', 'Speed': 'швидкість', 'Endurance': 'витривалість',
       'Personality': 'харизму', 'Luck': 'удачу', 'Spell Points': 'ману',
       'Fire': 'вогонь', 'Frost': 'мороз', 'Shock': 'блискавку', 'Poison': 'отруту'}


def effect_map():
    en = json.load(open(os.path.join(GMST, 'gmst_en.json'), encoding='utf-8'))
    uk = json.load(open(os.path.join(GMST, 'uk_gmst.json'), encoding='utf-8'))
    uk.pop('_comment', None)
    leg = {}
    p = os.path.join(HERE, '..', 'legacy', 'gmst.json')
    if os.path.isfile(p):
        leg = json.load(open(p, encoding='utf-8'))
    m = {}
    for k, e in en.items():
        if not k.startswith('sEffect'):
            continue
        v = uk.get(k) or leg.get(k)
        if v and re.search('[А-Яа-яЄІЇҐ]', v):
            m[e.lower()] = v
    return m


EFF = effect_map()
RANGED = re.compile(r'\s*\[Ranged\]\s*$')


def compose(name):
    ranged = bool(RANGED.search(name))
    core = RANGED.sub('', name).strip()
    uk = None
    if core.lower() in EFF:
        uk = EFF[core.lower()]
    else:
        toks = core.split()
        if len(toks) >= 2 and toks[0] in VERB and ' '.join(toks[1:]) in ACC:
            uk = VERB[toks[0]] + ' ' + ACC[' '.join(toks[1:])]
    if not uk:
        return None
    return uk + (' (на відстані)' if ranged else '')


def main():
    apply = '--apply' in sys.argv
    names = list(json.load(open(os.path.join(HERE, 'spell.json'), encoding='utf-8')))
    out = {}
    for n in names:
        uk = compose(n)
        if uk:
            out[n] = uk
    print('складено %d / %d (%.0f%%)' % (len(out), len(names), 100.0 * len(out) / len(names)))
    import random
    for n in list(out)[:6] + random.sample(list(out), min(6, len(out))):
        print('    %-30s -> %s' % (n, out[n]))
    if apply:
        with open(os.path.join(HERE, 'uk_spell.json'), 'w', encoding='utf-8') as f:
            json.dump({k: out[k] for k in sorted(out)}, f, ensure_ascii=False, indent=1)
        print('ЗАПИСАНО uk_spell.json')


if __name__ == '__main__':
    main()
