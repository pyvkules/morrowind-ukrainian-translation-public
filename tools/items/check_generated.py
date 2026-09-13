# -*- coding: utf-8 -*-
"""Що зі скоєного руками не пережило перезбірки.

`uk_*.json` **складають** композитори, і `loc.py rebuild` запускає їх щоразу.
Правку, внесену просто у складений файл, наступна перезбірка мовчки стирає — і
не скаржиться, бо файл же й має перезаписуватися. Так одного разу пропало 116
імен NPC («Джентльмен Джим Стейсі» знову став «Гентлеман Джім Стацеі») і вся
родина Ash-*; помітив це один-єдиний запис, що зачепився за тему діалогу в
`q.py dup`.

Тут ми порівнюємо версію з git із тим, що лежить у робочому каталозі після
перезбірки, і показуємо кожну розбіжність. Порядок такий:

    py tools\\loc.py rebuild
    py tools\\items\\check_generated.py

Порожній вихід — усе гаразд. Кожен показаний рядок означає одне з двох: або це
ваша свідома правка цієї партії (тоді вона мусить бути в `*_overrides.json`,
інакше зникне), або перезбірка щойно з'їла чужу правку.

Код виходу 1, якщо є розбіжності — щоб можна було поставити в CI.
"""
import glob
import io
import json
import os
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                              errors='replace', write_through=True)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def main():
    total = 0
    for path in sorted(glob.glob(os.path.join(HERE, 'uk_*.json'))):
        base = os.path.basename(path)
        rel = 'tools/items/' + base
        raw = subprocess.run(['git', 'show', 'HEAD:' + rel], cwd=ROOT,
                             capture_output=True)
        if raw.returncode != 0:
            continue                  # файл ще не в git
        head = json.loads(raw.stdout.decode('utf-8-sig'))
        with io.open(path, encoding='utf-8-sig') as f:
            now = json.load(f)
        if not isinstance(head, dict) or not isinstance(now, dict):
            continue
        diff = {k: (now.get(k), v) for k, v in head.items() if now.get(k) != v}
        if not diff:
            continue
        ov = base[3:-5] + '_overrides.json'
        has_ov = os.path.isfile(os.path.join(HERE, ov))
        print('%s  (%d)  ->  %s' % (base, len(diff), ov if has_ov
                                    else 'НЕМА файлу overrides'))
        for k, (gen, was) in sorted(diff.items())[:10]:
            print('   %-34s зараз %-28s у git %s' % (k, gen, was))
        if len(diff) > 10:
            print('   ... ще %d' % (len(diff) - 10))
        total += len(diff)
    if total:
        print()
        print('розбіжностей зі складеним: %d' % total)
        print('кожну треба або закріпити в *_overrides.json, або пояснити')
        return 1
    print('складені словники збігаються з git: 0 розбіжностей')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
