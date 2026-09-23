# -*- coding: utf-8 -*-
"""Успадкувати переклад репліки, яку мод переписав із опискою, — за текстом.

Навіщо окремо від `inherit.py`
------------------------------
`inherit.py` шукає за **id запису**: мод перевизначив ванільний INFO, виправив
у ньому описку, і наш переклад через це став недосяжним. Але «Quest Voice
Greetings» та інші озвучувальні моди id не перевизначають — вони створюють
**нові** записи, переносячи в них ванільний текст. Описка при переносі така
сама, а id інший, тож `inherit.py` цих реплік не бачить узагалі.

Тому тут пара шукається **за текстом**: для кожної неперекладеної репліки —
найсхожіша вже перекладена.

Чому правило суворіше, ніж в `inherit.py`
-----------------------------------------
Там однаковий id **доводив**, що це той самий запис, і заміну будь-якого слова
на схоже можна було вважати опискою. Тут доказу нема: `Dren` і `Dram` — двоє
різних людей, а різниця між ними дві літери. Отже успадковуємо лише тоді, коли
відмінність не може змінити змісту:

* **англійська граматика** — артикль, пробіл, розділовий знак, `egg mine` ->
  `eggmine`. Після зведення обох до суцільного ряду літер (`letters()` в
  `inherit.py`) тексти збігаються;
* **описка в довгому слові** — `peace`/`piece`, `bought`/`brought`,
  `councilor`/`councillor`. Обидва слова з малої літери, обидва від п'яти
  літер, однакова перша літера, щонайбільше дві правки, і таких слів у репліці
  не більше двох.

Слова коротші за п'ять літер тут не заміняємо зовсім: `my`/`me` в одному
записі — описка, а в двох різних — цілком може бути змістом. Так само не
заміняємо слів із великої літери й із цифрами: це імена, місця й суми.

    py tools\\dialogue\\inherit_text.py            # показати, що успадкується
    py tools\\dialogue\\inherit_text.py --apply    # записати в uk/
    py tools\\dialogue\\inherit_text.py --near     # показати відкинуте поруч
"""
import glob
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import inherit                    # noqa: E402  (звідти ж і кодування stdout)

APPLY = '--apply' in sys.argv
NEAR = '--near' in sys.argv
MIN_WORD = 5                      # коротші слова не заміняємо взагалі
MAX_CHANGED = 2                   # скільки слів у репліці можна змінити
# Ряд літер коротший за це ні про що не свідчить: `50`, `-`, `1` зводяться до
# порожнього, і тоді будь-яка така репліка «збігається» з будь-якою іншою.
MIN_LETTERS = 2


def spelling_variant(x, y):
    """Чи це те саме слово з опискою, а не два різних слова."""
    if x == y:
        return True
    if len(x) < MIN_WORD or len(y) < MIN_WORD:
        return False              # my/me, is/as — надто коротке, щоб ручатися
    if x[:1] != y[:1]:
        return False              # інша перша літера — радше інше слово
    if inherit.DIGIT.search(x) or inherit.DIGIT.search(y):
        return False              # 100/200 — це сума, а не описка
    return inherit.edits(x, y) <= inherit.MAX_EDITS


def tokens(text):
    """Набір підстановок, з огляду на регістр.

    Спершу тут порівнювалося без регістру: мовляв, `%Class` і `%class` рушій
    підставляє однаково. Але `check_sources` звіряє точно, і успадкований
    переклад із `%class` замість `%Class` став помилкою цілісності — трьома
    одразу. Дешевше зберегти регістр, ніж домовлятися з перевіркою.
    """
    return sorted(inherit.TOKEN.findall(text))


def shouting(text):
    """Репліка суцільними великими — це позначка, а не мовлення.

    Та сама пастка, що в `reuse.py`: `NORD` збігався з `Nord?` і діставав
    переклад «Норде?» з питальним знаком, якого в оригіналі не було.
    """
    return text.upper() == text and text.lower() != text


def safe_pair(new, old):
    """Чи можна взяти переклад `old` для репліки `new`."""
    if tokens(new) != tokens(old):
        return False              # набір підстановок різний
    if shouting(new) != shouting(old):
        return False              # позначка проти мовлення
    ln = inherit.letters(new)
    if len(ln) >= MIN_LETTERS and ln == inherit.letters(old):
        return True               # різниця суто англограматична
    a, b = inherit.WORD.findall(new), inherit.WORD.findall(old)
    if len(a) != len(b):
        return False              # слово додано або викинуто
    changed = 0
    for x, y in zip(a, b):
        if x == y:
            continue
        if x.lower() != x or y.lower() != y:
            return False          # велика літера — ім'я, а не описка
        changed += 1
        if changed > MAX_CHANGED or not spelling_variant(x.lower(), y.lower()):
            return False
    return changed > 0


def main():
    mem = inherit.memory()
    where = inherit.slices()

    # Покажчик 1: суцільний ряд літер — ловить самі лише граматичні правки.
    by_letters = {}
    for en in mem:
        key = inherit.letters(en)
        if len(key) >= MIN_LETTERS:
            by_letters.setdefault(key, en)

    # Покажчик 2: слова, в межах однакової кількості слів. Описка міняє
    # щонайбільше MAX_CHANGED слів, тож спільних мусить лишитися майже все.
    buckets = defaultdict(lambda: defaultdict(list))
    for en in mem:
        ws = inherit.WORD.findall(en)
        b = buckets[len(ws)]
        for w in set(w.lower() for w in ws):
            b[w].append(en)

    safe, near = {}, []
    for en, (name, i) in sorted(where.items(), key=lambda kv: kv[1]):
        hit = by_letters.get(inherit.letters(en))
        if hit is not None and not safe_pair(en, hit):
            hit = None            # той самий ряд літер, але підстановки інші
        if hit is None:
            ws = inherit.WORD.findall(en)
            need = len(set(w.lower() for w in ws)) - MAX_CHANGED
            if need < 3:
                continue          # надто коротка репліка, щоб ручатися
            cnt = Counter()
            for w in set(w.lower() for w in ws):
                for cand in buckets[len(ws)].get(w, ()):
                    cnt[cand] += 1
            for cand, n in cnt.most_common(8):
                if n < need:
                    break
                if safe_pair(en, cand):
                    hit = cand
                    break
                near.append((name, i, en, cand))
        if hit is not None and hit != en:
            safe[en] = ((name, i), mem[hit], hit)

    print('можна успадкувати за текстом: %d реплік' % len(safe))
    by_slice = defaultdict(dict)
    for en, ((name, i), uk, _) in safe.items():
        by_slice[name][i] = uk
    for name in sorted(by_slice, key=lambda k: -len(by_slice[k])):
        print('  %-38s %d' % (name, len(by_slice[name])))

    if NEAR:
        print()
        for name, i, en, cand in near[:40]:
            print('%s:%d' % (name, i))
            print('   НОВЕ %s' % en[:120])
            print('   БУЛО %s' % cand[:120])
        return 0

    if not APPLY:
        print()
        for en, ((name, i), uk, hit) in list(safe.items())[:8]:
            print('%s:%d' % (name, i))
            print('   НОВЕ %s' % en[:110])
            print('   БУЛО %s' % hit[:110])
            print('   ПЕР  %s' % uk[:110])
        print('(без --apply нічого не записано)')
        return 0

    total = 0
    for name, items in sorted(by_slice.items()):
        found = sorted(glob.glob(os.path.join(TOOLS, 'uk', name + '.json'))
                       + glob.glob(os.path.join(TOOLS, 'uk', name + '_p*.json')))
        out = found[-1] if found else os.path.join(TOOLS, 'uk', name + '.json')
        d = inherit.load(out) if os.path.isfile(out) else {}
        for i, uk in items.items():
            d[str(i)] = uk
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write('\n')
        print('  %-34s +%d -> %s' % (name, len(items), os.path.basename(out)))
        total += len(items)
    print('успадковано: %d' % total)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
