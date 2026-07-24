# -*- coding: utf-8 -*-
"""Скласти назви зілль: [якість] зілля [ефект у родовому].

374 із 538 зілль - систематичні: [Bargain/Cheap/Standard/Quality/Exclusive] +
[ефект] (+ 'Potion'). Ефект - це стандартні магічні ефекти гри, назви яких ми вже
переклали в GMST. Складаємо «{якісне} зілля {ефект}», де прикметник якості - у
середньому роді (зілля - середній рід), а ефект - у родовому відмінку.

Решта 164 - власні назви напоїв (Cyrodiilic Brandy, Abecean Rum, Beer...) -
лишаємо наступному, ручному проходу.

Пише tools/items/uk_potion.json.
    py compose_potions.py            # діагностика
    py compose_potions.py --apply
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))

QUALITY = {'Bargain': 'копійчане', 'Cheap': 'дешеве', 'Standard': 'звичайне',
           'Quality': 'якісне', 'Exclusive': 'добірне', 'Fresh': 'свіже'}

# дія (називний, середній/абстрактний) -> український іменник
ACTIONS = {'Restore': 'відновлення', 'Fortify': 'підсилення',
           'Damage': 'ушкодження', 'Drain': 'виснаження', 'Absorb': 'поглинання'}
# атрибут/ціль у РОДОВОМУ відмінку
ATTR = {'Health': "здоров'я", 'Magicka': 'магії', 'Fatigue': 'запасу сил',
        'Strength': 'сили', 'Intelligence': 'інтелекту', 'Willpower': 'сили волі',
        'Agility': 'спритності', 'Speed': 'швидкості', 'Endurance': 'витривалості',
        'Personality': 'харизми', 'Luck': 'удачі', 'Attack': 'атаки',
        'Casting': 'чаротворення'}

# готові ефекти (родовий відмінок)
EXTRA = {
    'Cure Common Disease': 'зцілення поширеної хвороби',
    'Fire Resistance': 'опору вогню', 'Frost Resistance': 'опору морозу',
    'Shock Resistance': 'опору блискавці', 'Poison Resistance': 'опору отруті',
    'Magicka Resistance': 'опору магії', 'Disease Resistance': 'опору хворобам',
    'Blight Resistance': 'опору мору', 'Paralysis Resistance': 'опору паралічу',
    'Resist Frost': 'опору морозу',
    'Frost Shield': 'морозного щита', 'Fire Shield': 'вогняного щита',
    'Lightning Shield': 'блискавичного щита',
    'Invisibility': 'невидимості', 'Spell Absorption': 'поглинання чар',
    'Ashen Wind': 'попелястого вітру', 'Rising Force': 'підйомної сили',
    'Blindness': 'сліпоти', 'Burden': 'тягаря', 'Cacophony': 'какофонії',
    'Evasion': 'ухилення', 'Feather': 'легкості', 'Jump': 'стрибка',
    'Levitation': 'левітації', 'Light': 'світла', 'Night-Eye': 'нічного зору',
    'Paralyze': 'паралічу', 'Protection': 'захисту', 'Reflection': 'відбиття',
    'Shadow': 'тіні', 'Silence': 'німоти', 'Swift Swim': 'швидкого плавання',
}

QRE = re.compile(r'^(%s)\b' % '|'.join(QUALITY))


def effect(core):
    core = re.sub(r'^Potion of ', '', core.strip())
    core = re.sub(r' Potion$', '', core).strip()
    if core in EXTRA:
        return EXTRA[core]
    toks = core.split()
    if len(toks) >= 2 and toks[0] in ACTIONS and ' '.join(toks[1:]) in ATTR:
        return ACTIONS[toks[0]] + ' ' + ATTR[' '.join(toks[1:])]
    return None


def compose(name):
    m = QRE.match(name)
    if not m:
        return None
    qadj = QUALITY[m.group(1)]
    eff = effect(name[m.end():])
    if not eff:
        return None
    return '%s зілля %s' % (qadj, eff)


def main():
    apply = '--apply' in sys.argv
    names = list(json.load(open(os.path.join(HERE, 'potion.json'), encoding='utf-8')))
    out, miss = {}, []
    for n in names:
        uk = compose(n)
        if uk:
            out[n] = uk
        elif QRE.match(n):
            miss.append(n)
    print('складено %d / %d' % (len(out), len(names)))
    for n in list(out)[:8]:
        print('    %-34s -> %s' % (n, out[n]))
    if miss:
        print('якісні, але не розібрані (%d):' % len(miss))
        for n in miss[:15]:
            print('    ?', n)
    if apply:
        with open(os.path.join(HERE, 'uk_potion.json'), 'w', encoding='utf-8') as f:
            json.dump({k: out[k] for k in sorted(out)}, f, ensure_ascii=False, indent=1)
        print('ЗАПИСАНО uk_potion.json')


if __name__ == '__main__':
    main()
