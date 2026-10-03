# -*- coding: utf-8 -*-
"""Партія перекладу реплік: виписати наступні, застосувати, перевірити.

    py tools\\dialogue\\batch.py next <зріз> [скільки]   наступні неперекладені
    py tools\\dialogue\\batch.py left                    скільки лишилось усюди
    py tools\\dialogue\\batch.py apply <зріз> <файл.txt> застосувати партію

Формат партії, по запису на рядок:

    1749|Do I know an anonymous|Чи знаю я якогось анонімного писаку?

Голова - перші кілька слів першотвору. Вона тут лише щоб зловити зсув на
одиницю: що саме перекладається, видно з виписки `next`, а не з цього
файла. Довшою її робити марно, самі витрати.

Повторюваний шматок оголошується раз і вставляється фігурними дужками:

    @WRITER=А тепер мені потрібна твоя поміч, щоб знайти того, хто пише.
    1304|We are quite satisfied|Із цією справою ти впорався. {WRITER}

Рядки з # і порожні пропускаються.

Чому простий текст, а не пайтон
-------------------------------
Партії довго писалися як пайтонівські словники. Вимір показав, що на
рядок перекладу йшло 284 байти друку, а самого перекладу в них було 157.
Решта - обв'яз: ключі, лапки й перенос на 72 колонки, бо сім переносів у
довгій репліці коштують сім відступів і чотирнадцять лапок. Тут переносу
немає зовсім, і виходить 207 байт на рядок замість 284.

Що перевіряється перед записом
------------------------------
1. голова збігається з початком першотвору (пробіли нормалізовано, бо в
   оригіналі після крапки то один, то два);
2. рядок ще не перекладено;
3. апостроф лише ASCII, ялинок немає - шрифт їх не малює;
4. набір підстановок (%PCName, %PCRank...) той самий, що в першотворі,
   дослівно, разом з чужим регістром на кшталт %PcName;
5. латинська літера не приліпилася до кирилиці («Лларисa» з латинським
   a): cp1251 цього не ловить, бо латинка в ньому теж є;
6. усе кодується в cp1251.
"""
import glob
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                              errors='replace', write_through=True)

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.abspath(os.path.join(HERE, '..'))
SRC = os.path.join(TOOLS, 'src')
UK = os.path.join(TOOLS, 'uk')

PH = re.compile(r'%[A-Za-z]+')
CYR = 'А-яЄІЇєіїҐґ'
MIX = re.compile('[%s][A-Za-z]|[A-Za-z][%s]' % (CYR, CYR))
DEF = re.compile(r'^@([A-Z][A-Z0-9_]*)=(.*)$')
HOLE = re.compile(r'\{([A-Z][A-Z0-9_]*)\}')


def load(path):
    with open(path, 'rb') as f:
        raw = f.read()
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return json.loads(raw.decode('utf-16'))
    return json.loads(raw.decode('utf-8-sig'))


def flat(s):
    return ' '.join(s.split())


def parts(name):
    """Куски перекладу зрізу: сам файл і всі _p1, _p2..."""
    return sorted(glob.glob(os.path.join(UK, name + '.json'))
                  + glob.glob(os.path.join(UK, name + '_p*.json')))


def uk_of(name):
    """Весь переклад зрізу, зведений з кусків.

    Читати лише `uk/<зріз>.json` не можна: великі зрізи розрізано, і тоді
    journal виглядає як 2367 неперекладених рядків, хоч там усе готове.
    """
    uk = {}
    for p in parts(name):
        uk.update(load(p))
    return uk


def left_of(name):
    src = load(os.path.join(SRC, name + '.json'))
    if not isinstance(src, list):
        return None, None
    uk = uk_of(name)
    return src, [(i, s) for i, s in enumerate(src)
                 if isinstance(s, str) and s.strip() and not uk.get(str(i))]


def cmd_next(argv):
    name = argv[0]
    n = int(argv[1]) if len(argv) > 1 else 40
    src, left = left_of(name)
    print('%s: без перекладу %d' % (name, len(left)))
    for i, s in left[:n]:
        print('--- %d\n%s' % (i, s))


def cmd_left(argv):
    rows = []
    for p in sorted(glob.glob(os.path.join(SRC, '*.json'))):
        name = os.path.basename(p)[:-5]
        src, left = left_of(name)
        if src and left:
            rows.append((len(left), len(src), name))
    rows.sort(reverse=True)
    for n, tot, name in rows:
        print('%6d з %6d  %s' % (n, tot, name))
    print('%6d усього' % sum(r[0] for r in rows))


def expand(text, const, ln):
    def sub(m):
        assert m.group(1) in const, 'рядок %d: немає {%s}' % (ln, m.group(1))
        return const[m.group(1)]
    return HOLE.sub(sub, text)


def parse(path):
    const, batch = {}, {}
    for ln, raw in enumerate(io.open(path, encoding='utf-8-sig'), 1):
        line = raw.rstrip('\r\n')
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        m = DEF.match(line)
        if m:
            const[m.group(1)] = expand(m.group(2), const, ln)
            continue
        bits = line.split('|')
        assert len(bits) >= 3, 'рядок %d: треба номер|голова|текст' % ln
        num, head, text = bits[0].strip(), bits[1].strip(), '|'.join(bits[2:])
        assert num.isdigit(), 'рядок %d: %r не номер' % (ln, num)
        i = int(num)
        assert i not in batch, 'рядок %d: номер %d уже був' % (ln, i)
        batch[i] = (head, expand(text.strip(), const, ln))
    return batch


def cmd_apply(argv):
    name, path = argv[0], argv[1]
    batch = parse(path)
    src = load(os.path.join(SRC, name + '.json'))
    pieces = parts(name)
    assert len(pieces) == 1, ('%s розрізано на %d кусків, пиши в потрібний'
                              % (name, len(pieces)))
    target = pieces[0]
    uk = load(target)
    was = len(uk)
    for i, (head, text) in sorted(batch.items()):
        assert flat(src[i]).startswith(flat(head)), \
            '%d: чекали %r, маємо %r' % (i, head, src[i][:200])
        assert not uk.get(str(i)), '%d: уже перекладено' % i
        assert '’' not in text and 'ʼ' not in text, '%d: апостроф' % i
        assert '«' not in text and '»' not in text, '%d: ялинки' % i
        assert sorted(PH.findall(src[i])) == sorted(PH.findall(text)), \
            '%d: підстановки %r проти %r' % (i, PH.findall(src[i]),
                                             PH.findall(text))
        assert not MIX.search(text), \
            '%d: латинка в слові %r' % (i, MIX.findall(text))
        text.encode('cp1251')
        uk[str(i)] = text
    with io.open(target, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(uk, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write('\n')
    total = sum(1 for en in src if isinstance(en, str) and en.strip())
    print('%s: було %d, додано %d, стало %d з %d'
          % (name, was, len(batch), len(uk), total))


def main():
    cmds = {'next': cmd_next, 'left': cmd_left, 'apply': cmd_apply}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(__doc__)
        return 1
    cmds[sys.argv[1]](sys.argv[2:])
    return 0


if __name__ == '__main__':
    sys.exit(main())
