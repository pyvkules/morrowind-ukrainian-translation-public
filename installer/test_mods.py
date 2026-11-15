# -*- coding: utf-8 -*-
"""Лічильник модів: чи він справді рахує, поки мод за модом з'являється.

Звернення №3: у режимі з модами автора лічильник стояв на «0 з 399» усю
найдовшу частину встановлення. Причина була на один рядок - `len(self.dirs)`
замість `len(self.items)` - але побачити її було годі: нитка лічильника
daemon, тож виняток у ній нікуди не доходив, нитка тихо кінчалася, і більше
ніхто нічого не казав. Саме через цю німоту перевірка тут і потрібна:
вона ганяє `Counter` на тимчасових теках, без гри й без умо.

    py installer/test_mods.py

Вихід 1, якщо хоч одна перевірка впала.
"""
import io
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mods

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                              errors='replace', write_through=True)

FAIL = []


def check(name, ok, note=''):
    print('%-4s %s%s' % ('ОК' if ok else 'ПАДЕ', name,
                         '' if ok else '  <- ' + note))
    if not ok:
        FAIL.append(name)


def test_counts_while_growing():
    """Поки теки з'являються, лічильник мусить рухатися, а не стояти на нулі."""
    root = tempfile.mkdtemp(prefix='ukr-counter-')
    try:
        names = ['mod%02d' % i for i in range(10)]
        seen = []
        c = mods.Counter(names,
                         lambda n: os.path.isdir(os.path.join(root, n)),
                         lambda have, total: seen.append((have, total)),
                         every=0.05,
                         on_error=lambda msg: seen.append(('ЗБІЙ', msg)))
        with c:
            for n in names:
                os.mkdir(os.path.join(root, n))
                time.sleep(0.08)
        bad = [s for s in seen if s[0] == 'ЗБІЙ']
        check('нитка лічильника не падає', not bad,
              bad[0][1] if bad else '')
        haves = [h for h, _t in seen if h != 'ЗБІЙ']
        check('лічильник не застряг на нулі', max(haves) > 0,
              'усі заміри нульові: %r' % (seen,))
        check('лічильник дорахував до всіх', max(haves) == len(names),
              'найбільше побачив %d із %d' % (max(haves), len(names)))
        totals = set(t for h, t in seen if h != 'ЗБІЙ')
        check('загальне число щоразу те саме', totals == {len(names)},
              'бачив загальні числа %r' % (totals,))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_error_reaches_the_log():
    """Як замір падає, про це мусить бути сказано, а не тихо нічого."""
    said = []

    def boom(_item):
        raise OSError('диск пішов')

    c = mods.Counter(['a', 'b'], boom, lambda h, t: None, every=0.05,
                     on_error=said.append)
    # перший замір у tell() іде через __enter__ і має право впасти назовні
    try:
        with c:
            time.sleep(0.2)
    except OSError:
        pass
    # а той, що в нитці, мусить дійти до журналу
    c2 = mods.Counter(['a'], boom, lambda h, t: None, every=0.05,
                      on_error=said.append)
    c2.have = 0
    c2.stop.clear()
    import threading
    th = threading.Thread(target=c2.run, daemon=True)
    th.start()
    time.sleep(0.25)
    c2.stop.set()
    th.join(timeout=1)
    check('про збій заміру сказано в журнал', said,
          'журнал порожній')
    check('про збій сказано один раз, а не щочетверті секунди',
          len([s for s in said if 'OSError' in s]) <= 1,
          'повторів: %d' % len(said))


test_counts_while_growing()
test_error_reaches_the_log()
print()
print('перевірок упало: %d' % len(FAIL))
sys.exit(1 if FAIL else 0)
