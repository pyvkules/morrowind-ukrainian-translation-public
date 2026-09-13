# -*- coding: utf-8 -*-
"""Довідка по вже перекладеному - щоб нова партія не суперечила старій.

Перекладаючи вручну, весь час треба питати «а як ми це вже називали?»: чи
Хлаалу, чи Глаалу; лихвар чи лихварка; як писали пропілони. Відповідь лежить у
двох десятках json-ів, і кожен разовий `py -c` - це окремий запит на дозвіл.
Тож усі такі питання ставимо одним скриптом зі сталим рядком запуску.

  py q.py key <підрядок> [...]   - як перекладено ключі, що містять підрядок
  py q.py val <підрядок> [...]   - де в перекладах трапляється цей рядок
  py q.py left <категорія> [N]   - перші N неперекладених назв категорії
  py q.py dup [N]                - той самий ключ з різними перекладами (перші N)

Пошук без урахування регістру; кілька підрядків - кілька незалежних питань.
"""
import glob
import io
import json
import os
import sys
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
LIMIT = 12


def topic_names():
    """Теми діалогів: у файлах перекладу ключ - це номер рядка, а не англійська.

    Через це `dup` роками не бачив цілого класу різнобою: та сама річ звалася
    в темі одним словом, а в словнику предметів іншим (Bitter Cup - «Гірка
    Чаша» проти «Гіркий келих»). Розгортаємо номер назад в англійську назву,
    і питання стає таким самим, як для предметів.
    """
    src = os.path.join(HERE, 'topics', 'dial_topics.json')
    if not os.path.isfile(src):
        return
    try:
        names = json.load(open(src, encoding='utf-8'))
    except (ValueError, OSError):
        return
    if not isinstance(names, list):
        return
    for path in sorted(glob.glob(os.path.join(HERE, 'topics', 'uk_dial_topics*.json'))):
        name = os.path.basename(path)
        try:
            data = json.load(open(path, encoding='utf-8'))
        except (ValueError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        for k, v in data.items():
            if not (isinstance(v, str) and k.isdigit()):
                continue
            i = int(k)
            if 0 <= i < len(names):
                yield name, names[i], v


def corpus():
    """Усі пари англійська->українська, які вже десь зафіксовані."""
    for pat in ('items/*.json', 'topics/uk_*.json', 'gmst/uk_*.json'):
        for path in sorted(glob.glob(os.path.join(HERE, pat))):
            name = os.path.basename(path)
            if name.startswith('_') or name.startswith('uk_dial_topics'):
                continue
            try:
                data = json.load(open(path, encoding='utf-8'))
            except (ValueError, OSError):
                continue
            if not isinstance(data, dict):
                continue
            for k, v in data.items():
                if isinstance(v, str) and k != '_comment':
                    yield name, k, v
    for row in topic_names():
        yield row


def by_key(needles):
    for needle in needles:
        low = needle.lower()
        print('== ключі з %r' % needle)
        seen, shown = set(), 0
        for name, k, v in corpus():
            if low in k.lower() and (k, v) not in seen:
                seen.add((k, v))
                print('   %-44s %s   [%s]' % (k, v, name))
                shown += 1
                if shown >= LIMIT:
                    break
        if not shown:
            print('   (нічого)')
        print()


def by_val(needles):
    """Небагато влучань - показуємо всі; багато - лише скільки і де.

    Обидва режими потрібні: «де ще ми написали Глаалу» вимагає повного списку,
    щоб виправити, а «скільки разом Хлаалу» - лише цифри, щоб обрати норму.
    """
    for needle in needles:
        low = needle.lower()
        print('== переклади з %r' % needle)
        rows = [(name, k, v) for name, k, v in corpus() if low in v.lower()]
        if not rows:
            print('   (нічого)')
        elif len(rows) <= 40:
            for name, k, v in rows:
                print('   %-40s %s   [%s]' % (k, v, name))
        else:
            hits = defaultdict(int)
            sample = {}
            for name, k, v in rows:
                hits[name] += 1
                sample.setdefault(name, (k, v))
            print('   разом %d' % len(rows))
            for name, n in sorted(hits.items(), key=lambda p: -p[1]):
                k, v = sample[name]
                print('   %4d  %-28s напр. %s -> %s' % (n, name, k, v))
        print()


def left(cat, limit):
    src = os.path.join(HERE, 'items', cat + '.json')
    done = os.path.join(HERE, 'items', 'uk_' + cat + '.json')
    if not os.path.isfile(src):
        print('немає %s' % src)
        return 1
    names = json.load(open(src, encoding='utf-8'))
    if isinstance(names, dict):
        names = list(names)
    have = json.load(open(done, encoding='utf-8')) if os.path.isfile(done) else {}
    rest = [n for n in names if n not in have]
    print('%s: лишилось %d з %d' % (cat, len(rest), len(names)))
    for n in rest[:limit]:
        print('   %s' % n)
    return 0


def dup(limit):
    """Одна англійська назва з різними українськими - джерело різнобою.

    Велику літеру на початку не рахуємо за розбіжність: композитори складають
    назву з малої, ручні переклади пишуться з великої, а patch_names.titled()
    однаково зводить усе до великої. Лишаємо видним тільки те, що справді
    потрапить у гру двома різними рядками.
    """
    variants = defaultdict(set)
    where = defaultdict(set)
    for name, k, v in corpus():
        variants[k].add(v[:1].upper() + v[1:])
        where[k].add(name)
    bad = {k: vs for k, vs in variants.items() if len(vs) > 1}
    print('розбіжностей: %d' % len(bad))
    for k in sorted(bad)[:limit]:
        print('   %-40s %s' % (k, ' | '.join(sorted(bad[k]))))
        print('   %-40s   у: %s' % ('', ', '.join(sorted(where[k]))))
    return 0


def main(argv):
    if not argv:
        print(__doc__)
        return 0
    cmd, args = argv[0], argv[1:]
    if cmd == 'key' and args:
        by_key(args)
    elif cmd == 'val' and args:
        by_val(args)
    elif cmd == 'left' and args:
        return left(args[0], int(args[1]) if len(args) > 1 else 60)
    elif cmd == 'dup':
        return dup(int(args[0]) if args else 60)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
