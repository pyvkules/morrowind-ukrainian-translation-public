# -*- coding: utf-8 -*-
"""Та сама особа під двома іменами: Ахнассі й Аннассі, Грунді й Хрунді.

Навіщо
------
`q.py dup` порівнює переклади **за однаковим англійським ключем**. Але ім'я
живе не лише в словнику: воно розсипане по репліках, книгах і темах, де ключа
нема взагалі - є тільки номер рядка. Тому найпоширеніший різнобій він не
бачить: `Ahnassi` перекладено правильно в словнику, а в тридцятьох репліках
стоїть «Аннассі», і жодна пара ключів не збігається.

Як шукаємо
----------
Ключ, якого бракує, - це **англійське ім'я в оригіналі**. Зріз дає пари
«англійський рядок - наш переклад», тож:

1. беремо ім'я зі словника (`Ahnassi` -> «Ахнассі»);
2. знаходимо всі перекладені рядки, де це ім'я є в англійському тексті;
3. у їхніх перекладах шукаємо слово, схоже на словникове написання;
4. якщо таких написань більше одного - це розповзання.

Схожим вважаємо слово, що відрізняється від словникового щонайбільше двома
правками. Відмінки не заважають: написання групуємо за **початком** слова,
бо відмінок міняє хвіст («Вівек», «Вівека», «Вівеку» - одна група), а інше
написання - початок або середину («Ахнассі» проти «Аннассі»).

Звичайні слова відсіюємо просто: власне ім'я не пишеться з малої літери. Якщо
слово десь у корпусі трапляється з малої, це не ім'я, а «варта» чи «велика».

    py tools\\name_drift.py [мінімум входжень]   # 0 - усе гаразд, 1 - є пари
"""
import glob
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                              errors='replace', write_through=True)

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_LEN = 5                       # коротші імена надто часто збігаються
MIN_HITS = int(sys.argv[1]) if len(sys.argv) > 1 else 2
PREFIX = 4                        # за початком слова групуємо відмінки
MAX_EDITS = 2                     # далі це вже інше ім'я
UK_WORD = re.compile(r'[Ѐ-ӿ]{%d,}' % MIN_LEN)
EN_NAME = re.compile(r"\b[A-Z][a-z']{%d,}\b" % (MIN_LEN - 1))
# Англійські слова, що пишуться з великої, але іменами не є.
STOP = set('''The This That There They Then When What Where Which While With
Your Yours Their These Those Could Would Should About After Before Because
Every Other Another Please Thank Thanks Sorry Maybe Perhaps Something Someone
Nothing Never Always House Guild Temple Master Mister Lord Lady Great Little
Right Wrong First Second Third Money Guard Guards Order Legion Empire
Imperial Imperials'''.split())


def load(path):
    with open(path, 'rb') as f:
        raw = f.read()
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return json.loads(raw.decode('utf-16'))
    return json.loads(raw.decode('utf-8-sig'))


# Яка українська літера може стояти на початку слова, що передає цю
# англійську. Потрібно, щоб зіставляння слів у назві з двох слів не
# припасувало `Hlaalu` до «Вартовий» у «Hlaalu Guard» -> «Вартовий Хлаалу».
FIRST = {
    'a': 'аеі', 'b': 'б', 'c': 'ксцч', 'd': 'дз', 'e': 'еєі', 'f': 'ф',
    'g': 'гґдж', 'h': 'хг', 'i': 'іїи', 'j': 'джйж', 'k': 'к', 'l': 'л',
    'm': 'м', 'n': 'н', 'o': 'о', 'p': 'п', 'q': 'к', 'r': 'р', 's': 'сшз',
    't': 'тс', 'u': 'ую', 'v': 'в', 'w': 'ву', 'x': 'ксз', 'y': 'йія',
    'z': 'зжд',
}


def plausible(en, uk):
    """Чи може це українське слово передавати саме це англійське."""
    return uk[:1].lower() in FIRST.get(en[:1].lower(), '')


def key(word):
    """Ключ групування: початок слова. Відмінок міняє хвіст, а не початок."""
    return word.lower()[:PREFIX]


def edits(a, b):
    """Відстань Левенштейна, рахуємо лише до MAX_EDITS + 1."""
    if abs(len(a) - len(b)) > MAX_EDITS:
        return MAX_EDITS + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
        if min(prev) > MAX_EDITS:
            return MAX_EDITS + 1
    return prev[-1]


def close(a, b):
    """Чи це те саме ім'я - у відмінку, з опискою або в іншому написанні."""
    return edits(a.lower(), b.lower()) <= MAX_EDITS


# Словники, де ключ може бути іменем, а не фразою. Додаткова умова - усі
# українські слова з великої: «Морений квама-робітник» так не пройде.
NAME_FILES = ('npc_overrides.json', 'uk_npc.json',
              'creature_overrides.json', 'uk_creature.json')
inside = defaultdict(lambda: defaultdict(set))


def dict_names():
    """Англійське ім'я -> українське написання зі словників."""
    out = {}
    for path in (glob.glob(os.path.join(HERE, 'items', 'uk_*.json'))
                 + glob.glob(os.path.join(HERE, 'items', '*_overrides.json'))):
        try:
            d = load(path)
        except ValueError:
            continue
        if not isinstance(d, dict):
            continue
        for k, v in d.items():
            if not isinstance(v, str) or k == '_comment':
                continue
            ek = [x[:-2] if x.endswith("'s") else x for x in EN_NAME.findall(k)]
            uw = UK_WORD.findall(v)
            # Ключ мусить **цілком** бути іменем. Інакше «Rock Beetle» дає
            # одне англійське слово `Beetle`, а «Beetle Shell» - «Панцир»,
            # і одне припасовується до другого.
            if ' '.join(ek) != k.replace("'s", '').strip():
                continue
            # Ім'я з одного слова беремо звідусіль.
            if len(ek) == 1 and len(uw) == 1 and ek[0] not in STOP:
                out.setdefault(ek[0], uw[0])
                inside[ek[0]][uw[0]].add(os.path.basename(path))
                continue
            # Ім'я з двох слів розбираємо по словах: `Dagoth Fovon` дає і
            # Dagoth, і Fovon. Без цього ціле гніздо лишалося невидимим -
            # 45 словникових «Даґот» проти 533 «Дагот» у текстах.
            #
            # Тільки в словниках імен і тільки коли ключ **цілком** є ім'ям:
            # назви чарів теж усі з великої, і «Absorb Health» припасувало б
            # «Health» до «здоров'я», а «Absorption» - до «чарів».
            if (os.path.basename(path) not in NAME_FILES
                    or len(ek) != len(uw)
                    or not all(w[:1].isupper() for w in uw)
                    or not all(plausible(e, u) for e, u in zip(ek, uw))):
                continue              # власне ім'я - усі слова з великої
            for e, u in zip(ek, uw):
                if e not in STOP:
                    out.setdefault(e, u)
                    inside[e][u].add(os.path.basename(path))
    return out


def dict_clash(inside, ok):
    """Розбіжність усередині самих словників.

    `q.py dup` її теж не бачить: ключі різні (`Dagoth Ur` і `Dagoth Fovon`),
    хоч ім'я те саме. Саме так 45 істот стали «Даґот», поки решта гри
    лишалася «Дагот».
    """
    rows = []
    for e, forms in inside.items():
        skip = {key(w) for w in ok.get(e, {}) if not w.startswith('_')}
        forms = {u: f for u, f in forms.items() if key(u) not in skip}
        if len({key(u) for u in forms}) > 1:
            rows.append((e, forms))
    return sorted(rows)


def pairs():
    """Англійський рядок -> переклад, з усіх зрізів і книг."""
    out = []
    for path in sorted(glob.glob(os.path.join(HERE, 'src', '*.json'))):
        name = os.path.basename(path)[:-5]
        src = load(path)
        if not isinstance(src, list):
            continue
        uk = {}
        for q in sorted(glob.glob(os.path.join(HERE, 'uk', name + '.json'))
                        + glob.glob(os.path.join(HERE, 'uk', name + '_p*.json'))):
            uk.update(load(q))
        for i, en in enumerate(src):
            if isinstance(en, str) and uk.get(str(i)):
                out.append(('%s:%d' % (name, i), en, uk[str(i)]))
    src = load(os.path.join(HERE, 'books', '_source.json'))
    uk = load(os.path.join(HERE, 'books', 'uk_books.json'))
    for k, en in src.items():
        if uk.get(k):
            out.append(('книга %s' % k[:8], en, uk[k]))
    return out


def lowercase_words():
    """Слова, що десь у корпусі стоять з малої: це не імена."""
    out = set()
    for _, _, v in pairs.cache:
        for w in UK_WORD.findall(v):
            if not w[:1].isupper():
                out.add(w.lower())
    return out


def main():
    names = dict_names()
    pairs.cache = pairs()
    common = lowercase_words()
    # Усі відомі написання: якщо слово ближче до ІНШОГО словникового імені,
    # це не розповзання, а просто схожа назва. Дрен і Драм - двоє людей.
    known = defaultdict(list)
    for u in set(names.values()):
        known[u[:1].lower()].append(u.lower())
    # Хто де вжитий: англійське ім'я -> українське написання -> (скільки, де).
    used = defaultdict(lambda: defaultdict(Counter))
    place = defaultdict(lambda: defaultdict(list))
    for ref, en, v in pairs.cache:
        seen = set(x[:-2] if x.endswith("'s") else x for x in EN_NAME.findall(en))
        for e in seen:
            want = names.get(e)
            if not want:
                continue
            for w in UK_WORD.findall(v):
                if not w[:1].isupper() or w.lower() in common:
                    continue
                d = edits(w.lower(), want.lower())
                if d > MAX_EDITS:
                    continue
                wl = w.lower()
                rival = any(u[:PREFIX] != key(want) and edits(wl, u) < d
                            for u in known[wl[:1]]
                            if abs(len(u) - len(wl)) <= MAX_EDITS)
                if not rival:
                    used[e][key(w)][w] += 1
                    if len(place[e][key(w)]) < 2:
                        place[e][key(w)].append(ref)

    ok = load(os.path.join(HERE, 'name_drift_ok.json'))
    rows = []
    for e, forms in used.items():
        # Відомі збіги двох різних імен - у name_drift_ok.json, з поясненням.
        skip = {key(w) for w in ok.get(e, {}) if not w.startswith('_')}
        forms = {k: c for k, c in forms.items() if k not in skip}
        # Одиничне написання - це радше збіг із чужим іменем, ніж розповзання.
        # Словникове лишаємо завжди: саме воно може виявитися в меншості.
        forms = {k: c for k, c in forms.items()
                 if sum(c.values()) > 1 or k == key(names[e])}
        if len(forms) < 2:
            continue
        total = sum(sum(c.values()) for c in forms.values())
        if total < MIN_HITS:
            continue
        rows.append((total, e, forms))

    clash = dict_clash(inside, ok)
    for e, forms in clash:
        print('%s: словники самі розходяться' % e)
        for u, files in sorted(forms.items(), key=lambda kv: -len(kv[1])):
            print('   %-24s %s' % (u, ', '.join(sorted(files))[:70]))

    rows.sort(reverse=True)
    for total, e, forms in rows:
        want = names[e]
        print('%s (словник: %s)' % (e, want))
        for s, c in sorted(forms.items(), key=lambda kv: -sum(kv[1].values())):
            mark = ' <- словник' if close(want, next(iter(c))) and \
                key(want) == s else ''
            print('   %-28s %3d  %s%s'
                  % (', '.join(sorted(c)[:4]), sum(c.values()),
                     ', '.join(place[e][s]), mark))
    print('імен із двома написаннями: %d (з них у самих словниках: %d)'
          % (len(rows) + len(clash), len(clash)))
    return 1 if rows or clash else 0


if __name__ == '__main__':
    raise SystemExit(main())
