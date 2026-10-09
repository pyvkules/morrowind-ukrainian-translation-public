# -*- coding: utf-8 -*-
"""Субтитри, що живуть не в діалогах, а в скриптах.

    py tools\\patch_say.py           показати, скільки й що лишилося
    py tools\\patch_say.py --apply   вписати переклад у зібрані плагіни

Чому це окремо від усього іншого
--------------------------------
Команда `Say "звук" "текст"` сама малює субтитр, і текст лежить просто в
джерелі скрипта. Це не запис INFO, тож ні rebuild_esm, ні patch_plugins
його не бачать. Через це українською була вся гра, а підписи під озвучкою
лишалися англійськими: пробудження на кораблі, уся видача паперів у
Сейда Нін, привітання Дагота Ура, смерть Альмалексії, Полювання Гірсіна.

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
3. усе кодується в cp1251.
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
WORDS = os.path.join(HERE, 'say.json')
LEFTOVER = os.path.join(HERE, '_remaining_say.txt')

# `Say "звук" "текст"` і `Say, "звук", "текст"` - кома між доводами
# необов'язкова, і обидва написання трапляються в тих самих скриптах.
SAY = re.compile(r'(\bsay(?:done)?\s*,?\s*"[^"]*"\s*,?\s*")([^"]*)(")',
                 re.I)
LETTER = re.compile(r'[A-Za-z]')
CYR = set(range(0x410, 0x450)) | {0x404, 0x406, 0x407, 0x454, 0x456, 0x457,
                                  0x490, 0x491}


def load_words():
    if not os.path.isfile(WORDS):
        return {}
    with open(WORDS, 'rb') as f:
        return json.loads(f.read().decode('utf-8-sig'))


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
    try:
        uk.encode('cp1251')
    except UnicodeEncodeError as e:
        stats['warn'] += 1
        print('  УВАГА cp1251: %r %s' % (uk[:60], e))
        return None
    return uk


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

                def swap(m):
                    en = m.group(2).strip()
                    # Порожній субтитр або сама пунктуація: таким `Say`
                    # просто програє звук, не показуючи нічого. У вихідній
                    # грі таких 68 з однією крапкою - перекладати нічого.
                    if not en or cyrillic(en) or not LETTER.search(en):
                        return m.group(0)
                    stats['seen'] += 1
                    uk = words.get(en)
                    if not uk:
                        stats['left'][en] = stats['left'].get(en, 0) + 1
                        return m.group(0)
                    uk = check(uk, en, stats)
                    if uk is None:
                        return m.group(0)
                    stats['done'] += 1
                    return m.group(1) + uk + m.group(3)

                new_text, cnt = SAY.subn(swap, text)
                if cnt and new_text != text:
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
    print('перекладів у say.json: %d' % len(words))
    dirs, contents = paths.read_modlist()
    resolved = paths.resolve_plugins(dirs)

    stats = {'seen': 0, 'done': 0, 'warn': 0, 'left': {}}
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
    print('субтитрів у скриптах : %d' % stats['seen'])
    print('вписано переклад     : %d' % stats['done'])
    print('лишилось англійських : %d (унікальних %d)'
          % (sum(stats['left'].values()), len(stats['left'])))
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
