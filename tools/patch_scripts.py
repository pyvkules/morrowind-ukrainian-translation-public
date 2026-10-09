# -*- coding: utf-8 -*-
"""Текст, що живе не в діалогах, а просто в скриптах.

    py tools\\patch_scripts.py           показати, скільки й що лишилося
    py tools\\patch_scripts.py --apply   вписати переклад у зібрані плагіни

Два джерела, обидва в джерелі скрипта:

    Say "звук" "текст"        субтитр під озвучкою
    MessageBox "текст" "ОК"   спливне вікно з кнопками

Жодне з них не є записом INFO, тож ні rebuild_esm, ні patch_plugins їх не
бачать. Через це українською була вся гра, а підписи й віконця лишалися
англійськими: пробудження на кораблі, уся видача паперів у Сейда Нін,
підказки навчання, питання вибору класу, благословення в храмі, список
міст у перевізника, кнопки ОК і Так.

На машині перекладача дірка непомітна. Збірка там починається з
`tools/base.esm`, а в ньому давній переклад уже колись переписав частину
цих рядків; у гравця ж під рукою чиста англійська гра зі Steam.

Правимо **джерело** (SCTX), а не байт-код (SCDT): OpenMW перекомпільовує
скрипти з джерела, і rename_topics давно робить так само.

Що перевіряється перед записом
------------------------------
1. у перекладі немає подвійних лапок - вони обірвали б рядок у скрипті
   й зламали б компіляцію;
2. немає ялинок - шрифт їх не малює;
3. підстановки (%g, %.0f, %s) ті самі й у тому самому порядку: MessageBox
   підставляє в них числа, і зайва чи загублена зламає вивід;
4. усе кодується в cp1251.
"""
import io
import json
import os
import re
import struct
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                              errors='replace', write_through=True)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths

MODROOT = paths.MOD_ROOT
APPLY = '--apply' in sys.argv
WORDS = os.path.join(HERE, 'script_text.json')
# Написи, які автори лишили собі на налагодження: `INCREMENTING TIMER`,
# `TEST: PLAY MOVIE`, `spawned paper`. Гравець їх у звичайній грі не
# побачить, а перекладені вони виглядали б дивніше за англійські. Тримаємо
# окремо, щоб звіт не рахував їх за невиконану роботу.
SKIP = os.path.join(HERE, 'script_text_skip.json')
LEFTOVER = os.path.join(HERE, '_remaining_script_text.txt')

# `Say "звук" "текст"` і `Say, "звук", "текст"` - кома між доводами
# необов'язкова, і обидва написання трапляються в тих самих скриптах.
SAY = re.compile(r'(\bsay(?:done)?\s*,?\s*"[^"]*"\s*,?\s*")([^"]*)(")', re.I)
MBOX = re.compile(r'\bmessagebox\b', re.I)
LETTER = re.compile(r'[A-Za-z]')
FMT = re.compile(r'%[-+ #0-9.]*[A-Za-z]')
CYR = set(range(0x410, 0x450)) | {0x404, 0x406, 0x407, 0x454, 0x456, 0x457,
                                  0x490, 0x491}


def load_words():
    if not os.path.isfile(WORDS):
        return {}
    with open(WORDS, 'rb') as f:
        return json.loads(f.read().decode('utf-8-sig'))


def load_skip():
    if not os.path.isfile(SKIP):
        return set()
    with open(SKIP, 'rb') as f:
        return set(json.loads(f.read().decode('utf-8-sig')))


def cyrillic(s):
    return any(ord(c) in CYR for c in s)


def subrecords(body):
    sp = 0
    while sp + 8 <= len(body):
        st = body[sp:sp + 4]
        ssize = struct.unpack('<I', body[sp + 4:sp + 8])[0]
        yield st, body[sp + 8:sp + 8 + ssize]
        sp += 8 + ssize


def rebuild(subs):
    out = bytearray()
    for st, sd in subs:
        out += st + struct.pack('<I', len(sd)) + sd
    return bytes(out)


def check(uk, en, stats):
    """Чи можна це писати в скрипт. Повертає None, якщо ні."""
    if '"' in uk:
        stats['warn'] += 1
        print('  УВАГА подвійні лапки, пропущено: %r' % uk[:60])
        return None
    if '«' in uk or '»' in uk:
        stats['warn'] += 1
        print('  УВАГА ялинки, пропущено: %r' % uk[:60])
        return None
    if FMT.findall(en) != FMT.findall(uk):
        stats['warn'] += 1
        print('  УВАГА підстановки %r проти %r у %r'
              % (FMT.findall(en), FMT.findall(uk), en[:50]))
        return None
    try:
        uk.encode('cp1251')
    except UnicodeEncodeError as e:
        stats['warn'] += 1
        print('  УВАГА cp1251: %r %s' % (uk[:60], e))
        return None
    return uk


def translate(en, words, stats):
    """Переклад одного рядка в лапках, або None, якщо лишаємо як є."""
    en = en.strip()
    # Порожній рядок або сама пунктуація: такий Say лише програє звук,
    # а такий MessageBox нічого не пише. Перекладати нічого.
    if not en or cyrillic(en) or not LETTER.search(en):
        return None
    if en in stats['skip']:
        stats['skipped'] += 1
        return None
    stats['seen'] += 1
    uk = words.get(en)
    if not uk:
        stats['left'][en] = stats['left'].get(en, 0) + 1
        return None
    uk = check(uk, en, stats)
    if uk is None:
        return None
    stats['done'] += 1
    return uk


def fix_messagebox(line, words, stats):
    """Переписати всі рядки в лапках після MessageBox.

    Ідемо посимвольно, бо доводів буває скільки завгодно: саме
    повідомлення, далі кнопки, між ними можуть стояти змінні без лапок.
    Крапка з комою поза лапками починає коментар - далі не чіпаємо.
    """
    m = MBOX.search(line)
    if not m:
        return line
    out = [line[:m.end()]]
    rest = line[m.end():]
    i = 0
    while i < len(rest):
        c = rest[i]
        if c == ';':
            out.append(rest[i:])
            return ''.join(out)
        if c != '"':
            out.append(c)
            i += 1
            continue
        j = rest.find('"', i + 1)
        if j < 0:                       # лапка без пари, далі не чіпаємо
            out.append(rest[i:])
            return ''.join(out)
        inner = rest[i + 1:j]
        uk = translate(inner, words, stats)
        out.append('"' + (inner if uk is None else uk) + '"')
        i = j + 1
    return ''.join(out)


def fix_text(text, words, stats):
    lines = text.split('\n')
    for n, line in enumerate(lines):
        if MBOX.search(line):
            lines[n] = fix_messagebox(line, words, stats)
            continue

        def swap(m):
            uk = translate(m.group(2), words, stats)
            return m.group(0) if uk is None else m.group(1) + uk + m.group(3)

        lines[n] = SAY.sub(swap, line)
    return '\n'.join(lines)


def process(data, words, stats):
    out = bytearray()
    pos, n = 0, len(data)
    while pos + 16 <= n:
        rtype = data[pos:pos + 4]
        size = struct.unpack('<I', data[pos + 4:pos + 8])[0]
        header_rest = data[pos + 8:pos + 16]
        body = data[pos + 16:pos + 16 + size]

        if rtype == b'SCPT':
            subs = list(subrecords(body))
            dirty = False
            for i, (st, sd) in enumerate(subs):
                if st != b'SCTX':
                    continue
                z = sd.endswith(b'\0')
                text = (sd[:-1] if z else sd).decode('cp1251', 'replace')
                new_text = fix_text(text, words, stats)
                if new_text != text:
                    b = new_text.encode('cp1251', 'replace')
                    subs[i] = (st, b + b'\0' if z else b)
                    dirty = True
            if dirty:
                body = rebuild(subs)
                size = len(body)

        out += rtype + struct.pack('<I', size) + header_rest + body
        pos += 16 + struct.unpack('<I', data[pos + 4:pos + 8])[0]
    return bytes(out)


def main():
    words = load_words()
    print('перекладів у script_text.json: %d' % len(words))
    dirs, contents = paths.read_modlist()
    resolved = paths.resolve_plugins(dirs)

    stats = {'seen': 0, 'done': 0, 'warn': 0, 'left': {},
             'skip': load_skip(), 'skipped': 0}
    touched = []
    for c in contents:
        local = os.path.join(MODROOT, c)
        path = local if os.path.isfile(local) else resolved.get(c.lower())
        if not path or not os.path.isfile(path):
            continue
        raw = open(path, 'rb').read()
        if b'SCPT' not in raw:
            continue
        before = stats['done']
        new = process(raw, words, stats)
        if stats['done'] > before:
            touched.append((stats['done'] - before, c))
            if APPLY:
                with open(os.path.join(MODROOT, os.path.basename(path)),
                          'wb') as f:
                    f.write(new)

    touched.sort(reverse=True)
    print()
    print('%-46s %8s' % ('ПЛАГІН', 'вписано'))
    for n, c in touched[:25]:
        print('%-46s %8d' % (c[:46], n))
    print()
    print('написів у скриптах   : %d' % stats['seen'])
    print('вписано переклад     : %d' % stats['done'])
    print('лишилось англійських : %d (унікальних %d)'
          % (sum(stats['left'].values()), len(stats['left'])))
    print('навмисно лишено      : %d (налагоджувальні написи)'
          % stats['skipped'])
    print('попереджень          : %d' % stats['warn'])
    if not APPLY:
        print()
        print('(пробний запуск, нічого не записано; --apply щоб вписати)')

    if stats['left']:
        with io.open(LEFTOVER, 'w', encoding='utf-8', newline='\n') as f:
            for en, n in sorted(stats['left'].items(), key=lambda kv: -kv[1]):
                f.write('%d\t%s\n' % (n, en))
        print('неперекладені виписано у %s' % LEFTOVER)
    elif os.path.isfile(LEFTOVER):
        # Інакше вчорашній список лежав би поруч і брехав, що робота є.
        os.remove(LEFTOVER)
    return 1 if stats['warn'] else 0


if __name__ == '__main__':
    sys.exit(main())
