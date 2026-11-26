# -*- coding: utf-8 -*-
"""Партія перекладу книг: виписати наступні, застосувати, перевірити.

    py tools\\books\\batch.py next [скільки] [--from N]   наступні неперекладені
    py tools\\books\\batch.py only <хеш,хеш>              саме ці книги
    py tools\\books\\batch.py apply <файл.txt> [--force]  застосувати партію

Формат партії
-------------
Шапка книги, далі рядки `<шматок>.<рядок>|<переклад>`:

    ### 14baeb218524e75c 751 Tattered note
    3.1|Видіння оракула розповіло про вхід до загублених печер Мамеї...
    5.1|Список спорядження:

Перекладач дає **самі слова**. Теги, переноси й відступи при складанні
беруться з `_source.json`, тож ані підпис послідовності тегів, ані розкладку
сторінки зламати неможливо.

Чому номер двоскладовий
-----------------------
Між двома тегами може стояти кілька рядків, розділених самим `\\r\\n` без
`<BR>`: так зверстано списки в «Імперській кухні» і **всі загадки** в
«Кендголській книзі». Якщо такий шматок виписати одним рядком, переклад
складеться в суцільний абзац, і загадка втратить форму вірша.

Що перевіряється перед записом
------------------------------
1. набір шматків збігається з першотвором (нічого не забуто й не зайве);
2. число й підпис послідовності тегів ті самі;
3. переносів рядка стільки ж, скільки в першотворі;
4. даедричні фрагменти на місці: той шрифт малює латиницю рунами;
5. усе кодується в cp1251;
6. немає знаків, яких наші шрифти не малюють. Ялинки виправляємо самі, як це
   робить `loc.py` (`glyphs.SUBST`), решту показуємо як помилку;
7. латинська літера не приліпилася до кирилиці. cp1251 цього не ловить, бо
   латинка в ньому теж є, а деякі знаки ще й тихо підміняються: `á` це 0xE1,
   тобто в грі вийшло б «б». Одного разу так і сталося: «хováються» з
   латинськими `o`, `v` і наголошеним `a`.
"""
import codecs
import glob
import hashlib
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TAG = re.compile(r'<[^>]*>')
NL = re.compile(r'(\r\n|\n|\r)')
WS = re.compile(r'^([ \t]*)(.*?)([ \t]*)$', re.S)

# « » „ ’ ‘ № - у cp1251 є, а гліфів у наших шрифтах немає;
# робоча пара лапок - “ ” (CONVENTIONS §3).
BAD = u'«»„’‘№'
FIR = {u'«': u'“', u'»': u'”'}

# Слово, у якому кирилиця стоїть поруч із латиницею або з наголошеною
# літерою. Теги тут уже не заважають: перевіряємо самі шматки перекладу.
MIX = re.compile(u'[^\\s]*(?:[Ѐ-ӿ][^\\s]*[A-Za-zÀ-ſ]'
                 u'|[A-Za-zÀ-ſ][^\\s]*[Ѐ-ӿ])[^\\s]*')

# Латинські літери, що мають кириличного двійника тієї самої форми. Усередині
# кириличного слова вибір однозначний, тож такі чинимо самі. Решту латиниці
# (`á`, `ü`, `w`…) лишаємо падати: там двійника немає й треба питати автора.
LOOKALIKE = {u'a': u'а', u'c': u'с', u'e': u'е', u'i': u'і', u'o': u'о',
             u'p': u'р', u'x': u'х', u'y': u'у', u'A': u'А', u'B': u'В',
             u'C': u'С', u'E': u'Е', u'H': u'Н', u'I': u'І', u'K': u'К',
             u'M': u'М', u'O': u'О', u'P': u'Р', u'T': u'Т', u'X': u'Х'}
# Двійник правиться тільки там, де поруч у тому самому слові стоїть кирилиця.
LOOKALIKE_RE = re.compile(
    u'(?<=[Ѐ-ӿ])[%s]|[%s](?=[Ѐ-ӿ])'
    % (u''.join(LOOKALIKE), u''.join(LOOKALIKE)))


def load(name):
    path = os.path.join(HERE, name)
    raw = open(path, 'rb').read()
    if raw[:2] in (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE):
        return json.loads(raw.decode('utf-16'))
    return json.loads(raw.decode('utf-8-sig'))


def chunks(text):
    """Куски: парні - текст, непарні - теги."""
    out, pos = [], 0
    for m in TAG.finditer(text):
        out.append(text[pos:m.start()])
        out.append(m.group(0))
        pos = m.end()
    out.append(text[pos:])
    return out


def cores(text):
    """(номер шматка, номер рядка, значущий текст)."""
    out = []
    for i, c in enumerate(chunks(text)):
        if i % 2:
            continue
        for j, ln in enumerate(NL.split(c)):
            if j % 2:
                continue
            core = WS.match(ln).group(2)
            if core:
                out.append((i // 2, j // 2, core))
    return out


BASE = ('morrowind.esm', 'tribunal.esm', 'bloodmoon.esm',
        'patch for purists.esm')


def working(meta, uk):
    """Книги в роботі, ще не перекладені, у порядку черги.

    Спершу найкоротші - записки й листи йдуть швидко, а їх у модлисті
    значно більше за товсті томи. Та звернення від гравця показало, чим та
    черга погана: «половина книжок не перекладена, наприклад “Коротка
    історія Морровінду” та “Поступ істини”». Обидві - з базової гри, обидві
    довгі, обидві стояли в кінці черги за самим лише розміром. Назви книг
    перекладено всі, тож гравець бачить українську обкладинку й англійський
    текст під нею, і це виглядає як поламка.

    Тому першими тепер ідуть книги базової гри (з «Patch for Purists», який
    її тексти й виправляє): їх читає кожен, хто взагалі грає. Далі решта, і
    між ними раніше ті, чий текст лежить у кількох плагінах: що більше
    копій, то більше гравців цю книгу зустрінуть.
    """
    left = [k for k, m in meta.items()
            if not m.get('notext') and not m.get('devnote') and k not in uk]
    left.sort(key=lambda k: (0 if meta[k].get('plugin') in BASE else 1,
                             -meta[k].get('copies', 1),
                             meta[k]['chars'], meta[k]['title']))
    return left


def cmd_next(args):
    src, meta, uk = load('_source.json'), load('books_meta.json'), load('uk_books.json')
    uk.pop('_comment', None)
    want = int(next((a for a in args if a.isdigit()), 20))
    skip = int(args[args.index('--from') + 1]) if '--from' in args else 0
    left = working(meta, uk)
    print('# неперекладених книг у роботі: %d' % len(left))
    dump(src, meta, left[skip:skip + want])
    return 0


def cmd_only(args):
    src, meta = load('_source.json'), load('books_meta.json')
    dump(src, meta, [h for a in args for h in a.split(',') if h])
    return 0


def dump(src, meta, keys):
    for k in keys:
        print('### %s %d %s' % (k, meta[k]['chars'], meta[k]['title']))
        for i, j, core in cores(src[k]):
            print('%d.%d|%s' % (i, j, ' '.join(core.split())))
        print()


def cmd_apply(args):
    path = next(a for a in args if not a.startswith('--'))
    force = '--force' in args
    src, meta = load('_source.json'), load('books_meta.json')
    ukp = os.path.join(HERE, 'uk_books.json')
    uk = json.loads(io.open(ukp, encoding='utf-8-sig').read())

    batch, key, fixed, ratios, twins = {}, None, 0, [], 0
    for ln in io.open(path, encoding='utf-8'):
        ln = ln.rstrip('\n')
        if ln.startswith('###'):
            key = ln.split()[1]
            batch[key] = {}
            continue
        if not ln.strip() or ln.startswith('#'):
            continue
        num, text = ln.split('|', 1)
        for a, b in FIR.items():
            if a in text:
                text = text.replace(a, b)
                fixed += 1
        # Латиниця в кириличному слові - найчастіша описка в цих партіях
        # (за одну сесію шість разів, і щоразу це «i» замість «і»). Для
        # літер-двійників заміна однозначна, тож чинимо самі, як loc.py чинить
        # із ялинками, і лишаємо падати тільки те, де двійника немає: `á`, `ü`
        # і такі - там треба знати, що автор мав на думці.
        latin = LOOKALIKE_RE.sub(lambda m: LOOKALIKE[m.group(0)], text)
        if latin != text:
            twins += sum(1 for a, b in zip(text, latin) if a != b)
            text = latin
        mixed = MIX.findall(text)
        assert not mixed, ('%s %s: латиниця всередині кириличного слова: %s'
                           % (key, num, ', '.join(sorted(set(mixed)))))
        i, j = num.split('.')
        batch[key][(int(i), int(j))] = text

    done = 0
    for k, parts in batch.items():
        assert k in src, 'немає такої книги: %s' % k
        assert force or k not in uk, 'книга вже перекладена: %s' % k
        m = meta[k]
        cs = chunks(src[k])
        want = set((i, j) for i, j, _ in cores(src[k]))
        assert want == set(parts), (
            '%s: шматки не збігаються, бракує %s, зайве %s'
            % (m['title'], sorted(want - set(parts)), sorted(set(parts) - want)))

        out = []
        for i, c in enumerate(cs):
            if i % 2:
                out.append(c)
                continue
            pieces = NL.split(c)
            for j, ln in enumerate(pieces):
                if j % 2:
                    continue
                lead, core, tail = WS.match(ln).groups()
                if core:
                    pieces[j] = lead + parts[(i // 2, j // 2)] + tail
            out.append(''.join(pieces))
        text = ''.join(out)

        seq = TAG.findall(text)
        assert len(seq) == m['ntags'], '%s: тегів %d, треба %d' % (
            m['title'], len(seq), m['ntags'])
        sig = hashlib.sha1('|'.join(seq).encode('utf-8')).hexdigest()[:12]
        assert sig == m['tagsig'], '%s: теги змінені або переставлені' % m['title']
        assert text.count('\n') == src[k].count('\n'), (
            '%s: переносів %d, а в першотворі %d'
            % (m['title'], text.count('\n'), src[k].count('\n')))
        for span in m.get('daedric', []):
            assert span in text, '%s: втрачено даедричний %r' % (m['title'], span)
        text.encode('cp1251')
        for ch in BAD:
            assert ch not in text, '%s: знака %r шрифт не малює' % (m['title'], ch)
        uk[k] = text
        done += 1
        # Пропущене речення не ламає ні тегів, ні переносів - воно просто
        # зникає. Єдине, що його видає, - довжина: українська проза виходить
        # приблизно як англійська, тож різке просідання варто побачити.
        a = sum(len(c) for _i, _j, c in cores(src[k]))
        b = sum(len(c) for _i, _j, c in cores(text))
        # Межі не вгадані: по всіх 469 уже перекладених книгах понад 400 знаків
        # відношення лежить у 0.75-1.13, бо українська виходить трохи стисліша.
        if a > 400 and not 0.70 <= float(b) / a <= 1.35:
            ratios.append((float(b) / a, m['title'], a, b))

    with io.open(ukp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(uk, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write('\n')
    if fixed:
        print('ялинок виправлено на “ ”: %d' % fixed)
    if twins:
        print('латинських двійників у кириличних словах виправлено: %d' % twins)
    for r, title, a, b in sorted(ratios):
        print('УВАГА довжина %.2f: %s (%d -> %d знаків) - чи все перекладено?'
              % (r, title, a, b))
    print('додано книг: %d' % done)
    return 0


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='replace', write_through=True)
    cmds = {'next': cmd_next, 'only': cmd_only, 'apply': cmd_apply}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(__doc__)
        return 2
    return cmds[sys.argv[1]](sys.argv[2:])


if __name__ == '__main__':
    sys.exit(main())
