# -*- coding: utf-8 -*-
"""Транслітерація власних імен (NPC) англ.->укр., з перекладом епітетів і ролей.

Імена в Morrowind змішані:
  * власні особові імена (Raril Giral, Collatinus Clanler) — транслітеруємо;
  * описові епітети (Whitebeard, Wave-Breaker, the Smith) — ПЕРЕКЛАДАЄМО;
  * загальні ролі (Bowman, Rogue Necromancer) — ПЕРЕКЛАДАЄМО.

Це чорновий двигун: вихід треба вичитувати. Усталені лорні імена й будь-що
криве кладемо в overrides (tools/items/npc_overrides.json) — воно має пріоритет.

    py translit.py            # показати зразок
    py translit.py --apply    # записати uk_npc.json
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))

# слова, які ПЕРЕКЛАДАЮТЬСЯ, а не транслітеруються (епітети, ролі, титули).
# Це лише РИШТУВАННЯ: остаточний варіант кожного пакета вичитується вручну.
WORDS = {
    'the': '', 'of': '', 'gro': 'ґро', 'gra': 'ґра',
    'whitebeard': 'Білобородий', 'fine-hair': 'Тонковолосий',
    'wave-breaker': 'Хвилелам', 'smith': 'Коваль', 'bowman': 'Лучник',
    'necromancer': 'Некромант', 'rogue': 'Відступник', 'guard': 'Вартовий',
    'trader': 'Торговець', 'bonebiter': 'Костогриз', 'fire-eye': 'Вогнеокий',
    'strong': 'Сильний', 'redoran': 'Редоран', 'wise': 'Мудрий',
    'blackheart': 'Чорносердий', 'bloodward': 'Кровострах', 'old': 'Старий',
    'young': 'Молодий', 'black': 'Чорний', 'white': 'Білий', 'red': 'Рудий',
    'the-cunning': 'Хитрий', 'cunning': 'Хитрий', 'brave': 'Хоробрий',
    'swift': 'Прудкий', 'quick': 'Прудкий', 'grey': 'Сивий', 'gray': 'Сивий',
    'ill-lit': '', 'necromancer,': 'Некромант', 'wild': 'Дикий',
    'jeweler': 'Ювелір', 'jeweller': 'Ювелір', 'admiral': 'Адмірал',
    'captain': 'Капітан', 'sergeant': 'Сержант', 'general': 'Генерал',
    'tall': 'Високий', 'one-eye': 'Одноокий', 'one-hand': 'Однорукий',
    'half-troll': 'Напівтроль', 'the-tongueless': 'Безъязикий',
    'healer': 'Цілитель', 'the-healer': 'Цілитель', 'wanderer': 'Мандрівник',
    'the-wanderer': 'Мандрівник', 'the-mad': 'Божевільний', 'mad': 'Божевільний',
    'the-fair': 'Прекрасний', 'fair': 'Прекрасний', 'lord': 'Лорд',
    'lady': 'Пані', 'king': 'Король', 'queen': 'Королева', 'saint': 'Святий',
}

# діграфи (спершу), потім поодинокі
DIGRAPHS = [('tch', 'ч'), ('sch', 'ш'), ('sh', 'ш'), ('ch', 'ч'), ('th', 'т'),
            ('ph', 'ф'), ('ck', 'к'), ('kh', 'х'), ('gh', 'г'), ('zh', 'ж'),
            ('ll', 'лл'), ('oo', 'у'), ('ee', 'і'), ('ou', 'у'), ('ay', 'ей'),
            ('ai', 'ай'), ('ei', 'ей'), ('ia', 'ія'), ('io', 'іо'),
            ('qu', 'кв'), ('x', 'кс'), ('yu', 'ю'), ('ya', 'я'), ('yo', 'йо')]
SINGLE = {'a': 'а', 'b': 'б', 'c': 'к', 'd': 'д', 'e': 'е', 'f': 'ф', 'g': 'ґ',
          'h': 'г', 'i': 'і', 'j': 'дж', 'k': 'к', 'l': 'л', 'm': 'м', 'n': 'н',
          'o': 'о', 'p': 'п', 'q': 'к', 'r': 'р', 's': 'с', 't': 'т', 'u': 'у',
          'v': 'в', 'w': 'в', 'x': 'кс', 'y': 'и', 'z': 'з', "'": "'", '-': '-'}


def translit_word(w):
    """Фонетична транслітерація: звучання лишаємо як в оригіналі, нічого не
    скорочуємо. Єдиний контекстний випадок — м'яка c перед e/i/y (Lucius->Луціус,
    Cyrodiil->Сиродііл), інакше c->к (Vivec->Вівек, Caius->Кайус)."""
    s = w.lower()
    out = []
    i = 0
    while i < len(s):
        for dg, rep in DIGRAPHS:
            if s.startswith(dg, i):
                out.append(rep)
                i += len(dg)
                break
        else:
            ch = s[i]
            if ch == 'c':
                nxt = s[i + 1] if i + 1 < len(s) else ''
                out.append('с' if nxt in ('e', 'i', 'y') else 'к')
            else:
                out.append(SINGLE.get(ch, ch))
            i += 1
    res = ''.join(out)
    # велика перша літера кожної частини через дефіс (Тімсар-Дадісун)
    return '-'.join(p[:1].upper() + p[1:] for p in res.split('-'))


def convert(name):
    if '<' in name or '>' in name:       # службові плейсхолдери лишаємо як є
        return name
    parts = re.split(r'(\s+)', name)     # зберегти пробіли
    out = []
    for p in parts:
        if not p.strip():
            out.append(p)
            continue
        low = p.lower()
        if low in WORDS:
            out.append(WORDS[low])
        elif low.startswith('gro-') or low.startswith('gra-'):
            pref = WORDS[low[:3]]
            out.append(pref + '-' + translit_word(p[4:]))
        else:
            out.append(translit_word(p))
    return re.sub(r'\s+', ' ', ' '.join(w for w in out if w != '')).strip()


def main():
    apply = '--apply' in sys.argv
    names = list(json.load(open(os.path.join(HERE, 'npc.json'), encoding='utf-8')))
    ov = {}
    op = os.path.join(HERE, 'npc_overrides.json')
    if os.path.isfile(op):
        ov = json.load(open(op, encoding='utf-8'))
        ov.pop('_comment', None)
    out = {}
    for n in names:
        out[n] = ov.get(n) or convert(n)
    if apply:
        with open(os.path.join(HERE, 'uk_npc.json'), 'w', encoding='utf-8') as f:
            json.dump({k: out[k] for k in sorted(out)}, f, ensure_ascii=False, indent=1)
        print('ЗАПИСАНО uk_npc.json:', len(out))
    else:
        import random
        random.seed(1)
        for n in random.sample(names, 40):
            print('  %-28s -> %s' % (n, out[n]))


if __name__ == '__main__':
    main()
