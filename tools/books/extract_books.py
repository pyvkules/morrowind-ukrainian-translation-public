# -*- coding: utf-8 -*-
"""Зібрати тексти книг усього модліста й підготувати їх до перекладу.

Назви книг (FNAM) уже готові й живуть в items/. Це про вміст сторінок - підзапис
TEXT у записах BOOK. Найбільший пласт модліста: ~8,5 млн символів, 62% обсягу.

Чому не зрізи, як у реплік діалогів
-----------------------------------
Зріз прив'язує переклад до порядкового номера, а номер залежить від того, які
плагіни і в якому порядку стоять у конкретного гравця. Для 2 327 книг із 327
плагінів це означало б, що в когось переклад ляже не на ту книгу. Тому ключ тут
- SHA-1 англійського тексту: він не збивається від зміни модліста й дозволяє не
тримати в репозиторії 8,5 МБ чужої прози.

Що куди лягає
-------------
  books_meta.json   у git: хеш -> {назва, довжина, теги}. Прози тут нема, лише
                    скелет розмітки - його вистачає, щоб CI перевірив переклад.
  uk_books.json     у git: хеш -> український текст. Власне переклад.
  _source.json      НЕ в git: хеш -> англійський текст, робоча копія з гри.

ВАЖЛИВО для перекладача: у тексті є розмітка - <BR>, <DIV ALIGN="CENTER">,
<FONT COLOR="000000">, <IMG SRC="...">. Її треба лишати дослівно й у тому самому
порядку, інакше сторінка розсиплеться. Перекладаються тільки слова між тегами.

    py extract_books.py            # порахувати
    py extract_books.py --apply    # оновити books_meta.json і _source.json
"""
import hashlib
import io
import json
import os
import re
import struct
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..')))
import paths

APPLY = '--apply' in sys.argv
TAG = re.compile(r'<[^>]*>')
# шрифт Daedric малює ЛАТИНСЬКІ літери як даедричні руни, тож кирилиця в ньому
# просто не намалюється: такі фрагменти лишаємо англійськими
DAEDRIC = re.compile(r'<FONT[^>]*FACE="Daedric"[^>]*>(.*?)(?=</FONT>|<FONT|$)',
                     re.S | re.I)


def key(text):
    return hashlib.sha1(text.encode('cp1251', 'replace')).hexdigest()[:16]


def tagsig(text):
    """Підпис послідовності тегів.

    Повний список тегів дав би 1,5 МБ метаданих на самих лише <BR>, а для
    перевірки досить знати, чи послідовність збереглася. Де саме вона поїхала,
    видно локально: у перекладача є _source.json.
    """
    seq = TAG.findall(text)
    return len(seq), hashlib.sha1('|'.join(seq).encode('utf-8')).hexdigest()[:12]


def daedric_spans(text):
    """Шматки, написані даедричним шрифтом. Їх перекладати не можна."""
    return [s.strip() for s in DAEDRIC.findall(text) if s.strip()]


def plain(text):
    """Що з книги взагалі можна перекласти.

    Знімаємо розмітку й даедричні руни. Якщо не лишилось нічого - у книзі нема
    читаного тексту: це або порожня заготовка, або сувій, чий весь напис
    намальовано рунами чи запечено в картинку <IMG SRC>. Перекладати там нема
    чого, тож такі книги не мають висіти в роботі.
    """
    rest = DAEDRIC.sub(' ', text)
    return TAG.sub(' ', rest).strip()


def subrecords(body):
    sp = 0
    while sp + 8 <= len(body):
        st = body[sp:sp + 4]
        ssize = struct.unpack('<I', body[sp + 4:sp + 8])[0]
        yield st, body[sp + 8:sp + 8 + ssize]
        sp += 8 + ssize


def books(data):
    """(назва, текст) для кожного запису BOOK у порядку появи."""
    pos, n = 0, len(data)
    while pos + 16 <= n:
        rtype = data[pos:pos + 4]
        size = struct.unpack('<I', data[pos + 4:pos + 8])[0]
        if rtype == b'BOOK':
            title, text = '', ''
            for st, sdata in subrecords(data[pos + 16:pos + 16 + size]):
                raw = sdata[:-1] if sdata.endswith(b'\0') else sdata
                if st == b'FNAM':
                    title = raw.decode('cp1251', 'replace')
                elif st == b'TEXT':
                    text = raw.decode('cp1251', 'replace')
            if text:
                yield title, text
        pos += 16 + size


def main():
    dirs, contents = paths.read_modlist()
    resolved = paths.resolve_plugins(dirs)

    source, meta = {}, {}
    files = 0
    for name in contents:
        path = resolved.get(name.lower())
        if not path or not os.path.isfile(path):
            continue
        files += 1
        for title, text in books(open(path, 'rb').read()):
            k = key(text)
            if k in source:
                continue
            source[k] = text
            ntags, sig = tagsig(text)
            meta[k] = {'title': title, 'chars': len(text),
                       'ntags': ntags, 'tagsig': sig}
            runes = daedric_spans(text)
            if runes:
                meta[k]['daedric'] = runes
            if not plain(text):
                meta[k]['notext'] = True

    done = {}
    ukp = os.path.join(HERE, 'uk_books.json')
    if os.path.isfile(ukp):
        done = json.load(open(ukp, encoding='utf-8'))
        done.pop('_comment', None)

    notext = [k for k in source if meta[k].get('notext')]
    work = [k for k in source if k not in notext]
    left = [k for k in work if k not in done]
    chars = sum(meta[k]['chars'] for k in work)
    print('плагінів прочитано : %d' % files)
    print('книг унікальних    : %d' % len(source))
    print('без читаного тексту: %d (руни, картинки, порожні заготовки)' % len(notext))
    print('до перекладу       : %d' % len(work))
    print('символів у роботі  : %d' % chars)
    print('перекладено        : %d / %d (%.0f%%)'
          % (len(work) - len(left), len(work),
             100.0 * (len(work) - len(left)) / len(work) if work else 0))
    if work:
        print('найдовша книга     : %d символів' % max(meta[k]['chars'] for k in work))

    if not APPLY:
        print('(без --apply нічого не записано)')
        return 0

    with open(os.path.join(HERE, 'books_meta.json'), 'w', encoding='utf-8') as f:
        json.dump({k: meta[k] for k in sorted(meta)}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(HERE, '_source.json'), 'w', encoding='utf-8') as f:
        json.dump({k: source[k] for k in sorted(source)}, f, ensure_ascii=False, indent=1)
    # найкоротші книги першими: записки й листи перекладаються швидко,
    # а їх у модлисті значно більше, ніж товстих томів
    with open(os.path.join(HERE, '..', '_remaining_books.txt'), 'w', encoding='utf-8') as f:
        for k in sorted(left, key=lambda k: meta[k]['chars']):
            flag = ' [даедричний шрифт]' if 'daedric' in meta[k] else ''
            f.write('%s  %6d  %s%s\n'
                    % (k, meta[k]['chars'], meta[k]['title'], flag))
    print('записано books_meta.json, _source.json, _remaining_books.txt')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
