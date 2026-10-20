# -*- coding: utf-8 -*-
"""Річ у репліці зветься так, як вона зветься в торбі.

Гравець бере в руки предмет із назвою зі словника, а в журналі читає про нього
репліку. Якщо словник каже «срібна миска», а журнал — «срібна чаша», то це для
гравця дві різні речі, і доручення провисає. `q.py dup` такого не бачить: у
репліці англійського ключа немає, там лише проза.

Терміни лежать у `item_words.json`: англійське слово, очікуваний корінь і
корені, які для нього чужі. Законні винятки (те саме слово не про предмет)
лежать у `item_words_ok.json` з поясненням, чому воно там.

    py tools\\dialogue\\item_words.py

Вихід 1, якщо знайшлося хоч одне розходження.
"""
import codecs
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
SRC = os.path.join(TOOLS, 'src')
UK = os.path.join(TOOLS, 'uk')


def load(path):
    raw = open(path, 'rb').read()
    if raw[:2] in (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE):
        return json.loads(raw.decode('utf-16'))
    return json.loads(raw.decode('utf-8-sig'))


def slices():
    for path in sorted(glob.glob(os.path.join(SRC, '*.json'))):
        name = os.path.basename(path)[:-5]
        if name.endswith('.topics'):
            continue
        src = load(path)
        if not isinstance(src, list):
            continue
        uk = {}
        for part in sorted(glob.glob(os.path.join(UK, name + '.json'))
                           + glob.glob(os.path.join(UK, name + '_p*.json'))):
            uk.update(load(part))
        yield name, src, uk


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  newline='\n')
    terms = load(os.path.join(HERE, 'item_words.json'))
    allow = load(os.path.join(HERE, 'item_words_ok.json'))
    rules = []
    for t in terms:
        rules.append((t['en'],
                      re.compile(t['rx'], re.I),
                      re.compile(t['bad'], re.U),
                      t['want']))

    found = 0
    for name, src, uk in slices():
        ok = allow.get(name, {})
        for i, s in enumerate(src):
            t = uk.get(str(i))
            if not isinstance(s, str) or not isinstance(t, str):
                continue
            for en, rx, bad, want in rules:
                if not rx.search(s) or not bad.search(t):
                    continue
                if str(i) in ok:
                    continue
                found += 1
                print(u'%s %d: %s -> чекали «%s»' % (name, i, en, want))
                print(u'  en %s' % ' '.join(s.split())[:200])
                print(u'  uk %s' % ' '.join(t.split())[:200])
    print(u'речей, названих у репліці не так, як у торбі: %d' % found)
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main())
