# -*- coding: utf-8 -*-
"""Заповнити ті рядки зрізу, чий англійський текст **слово в слово** такий
самий, як уже перекладений рядок в іншому зрізі.

Це безпечно за тим самим правилом, що його пильнує `q.py dup`: один
англійський рядок - один переклад. Якщо тексти збігаються після згортання
пробілів, то й переклад мусить бути той самий, інакше в гру потрапить
випадковий із двох.

    py tools\dialogue\same_text_fill.py <зріз>            # показати, скільки таких
    py tools\dialogue\same_text_fill.py <зріз> --apply    # записати
"""
import codecs
import glob
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', newline='\n')
TOOLS = r'E:\Morrowind\OpenMW\mods\morrowind-ukrainian-translation\tools'
SRC, UK = os.path.join(TOOLS, 'src'), os.path.join(TOOLS, 'uk')


def load(p):
    raw = open(p, 'rb').read()
    if raw[:2] in (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE):
        return json.loads(raw.decode('utf-16'))
    return json.loads(raw.decode('utf-8-sig'))


def flat(s):
    return ' '.join(s.split())


name = sys.argv[1]
apply = '--apply' in sys.argv

done = {}
for path in sorted(glob.glob(os.path.join(SRC, '*.json'))):
    n = os.path.basename(path)[:-5]
    if n.endswith('.topics') or n == name:
        continue
    src = load(path)
    if not isinstance(src, list):
        continue
    for part in sorted(glob.glob(os.path.join(UK, n + '.json'))
                       + glob.glob(os.path.join(UK, n + '_p*.json'))):
        uk = load(part)
        for k, v in uk.items():
            i = int(k) if k.isdigit() else -1
            if i < 0 or i >= len(src) or not isinstance(src[i], str):
                continue
            if isinstance(v, str) and v.strip():
                done.setdefault(flat(src[i]), (n, i, v))

src = load(os.path.join(SRC, name + '.json'))
hit = 0
for part in sorted(glob.glob(os.path.join(UK, name + '.json'))
                   + glob.glob(os.path.join(UK, name + '_p*.json'))):
    uk = load(part)
    was = len(uk)
    for i, s in enumerate(src):
        if not isinstance(s, str) or not s.strip() or uk.get(str(i)):
            continue
        twin = done.get(flat(s))
        if not twin:
            continue
        hit += 1
        if apply:
            uk[str(i)] = twin[2]
    if apply and len(uk) != was:
        with io.open(part, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(uk, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write('\n')
        print(u'%s: було %d, стало %d' % (os.path.basename(part), was, len(uk)))
print(u'рядків слово в слово: %d%s' % (hit, '' if apply else ' (без --apply не записано)'))
