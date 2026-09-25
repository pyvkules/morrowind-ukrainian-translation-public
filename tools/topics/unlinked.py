# -*- coding: utf-8 -*-
"""Які теми згадані в репліці, але не стали посиланням.

У ванілі назву теми видно в тексті синім і по ній клікають. У нас це робить
`mark_topics.py`: обгортає згадку в `@форма#`. Обгорнути можна лише те, що в
тексті справді написане тими самими словами, що й тема. Де переклад сказав
інакше, тема лише додається в перелік збоку, і гравець не бачить, що про це
можна спитати.

Цей звіт показує, на яких темах втрат найбільше, і що стоїть у тексті замість
них. Одне виправлення формулювання закриває сотні реплік, тому працювати варто
згори списку.

    py tools\\topics\\unlinked.py           # найгірші 40
    py tools\\topics\\unlinked.py 100       # скільки показати
    py tools\\topics\\unlinked.py --csv     # усе, для розбору
"""
import glob
import io
import json
import os
import re
import struct
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                              errors='replace', write_through=True)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..')))
import paths                                                    # noqa: E402

MODROOT = paths.MOD_ROOT
BASE_ESM = os.path.join(paths.TOOLS, 'base.esm')
CYR = 'а-щьюяєіїґА-ЩЬЮЯЄІЇҐ'
WORD = re.compile('[' + CYR + ']+')
AT = re.compile(r'@([^#]{1,80})#')
MAX_SUF = 3
VOWEL_END = set('аяоеєуюіи')
BAD_SUF = re.compile('^(у[юєяії]|ув|яч|ськ|цьк)')


def load(path):
    with open(path, 'rb') as f:
        raw = f.read()
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return json.loads(raw.decode('utf-16'))
    return json.loads(raw.decode('utf-8-sig'))


def records(raw):
    i, n = 0, len(raw)
    while i + 16 <= n:
        tag = raw[i:i + 4]
        size = struct.unpack_from('<I', raw, i + 4)[0]
        yield tag, raw[i + 16:i + 16 + size]
        i += 16 + size


def subrecs(body):
    i, n = 0, len(body)
    while i + 8 <= n:
        st = body[i:i + 4]
        size = struct.unpack_from('<I', body, i + 8 - 4)[0]
        yield st, body[i + 8:i + 8 + size]
        i += 8 + size


def _stem(word):
    low, n = word.lower(), len(word)
    if n >= 6 and low[-2:] in ('ий', 'ій'):
        return word[:-2]
    if n >= 5 and (low[-1] in VOWEL_END or low[-1] == 'ь'):
        return word[:-1]
    return word


# Закритий склад дає і, відкритий о або е: Дім -> Дому, ніч -> ночі.
ALT = {'і': 'іо', 'о': 'оі', 'е': 'еі'}


def _flex(stem):
    """Основа як взірець: остання голосна може чергуватися."""
    for i in range(len(stem) - 1, -1, -1):
        alt = ALT.get(stem[i].lower())
        if not alt:
            continue
        if i == len(stem) - 1:      # голосна в кінці не чергується
            break
        head = re.escape(stem[:i])
        tail = re.escape(stem[i + 1:])
        pick = alt.upper() + alt if stem[i].isupper() else alt
        return head + '[' + pick + ']' + tail
    return re.escape(stem)


def _pattern(name):
    parts, last, stems = [], 0, []
    for m in WORD.finditer(name):
        parts.append(re.escape(name[last:m.start()]))
        s = _stem(m.group(0))
        stems.append(s)
        parts.append(_flex(s) + '[' + CYR + ']{0,%d}' % MAX_SUF)
        last = m.end()
    parts.append(re.escape(name[last:]))
    body = ''.join(parts)
    if not body.strip():
        return None, []
    return re.compile(r'(?<![' + CYR + r'])(' + body + r')(?![' + CYR + r'])'), stems


def _suffix_ok(surface, stems):
    words = WORD.findall(surface)
    if len(words) != len(stems):
        return False
    return not any(BAD_SUF.match(w[len(s):].lower()) for w, s in zip(words, stems))


def build_maps():
    src = load(os.path.join(HERE, 'dial_topics.json'))
    uk = {}
    for p in sorted(glob.glob(os.path.join(HERE, 'uk_dial_topics*.json'))):
        for k, v in load(p).items():
            uk[int(k)] = v
    en2uk = {}
    for i, en in enumerate(src):
        if uk.get(i):
            en2uk[en.lower()] = uk[i]
    legacy = os.path.join(HERE, 'legacy_en_ids.json')
    if os.path.isfile(legacy):
        for en, ukid in load(legacy).items():
            en2uk.setdefault(en.lower(), ukid)
    pat = {}
    for topic in set(en2uk.values()):
        rx, stems = _pattern(topic)
        if rx is not None:
            pat[topic] = (rx, stems)
    ws = sorted({w for w in en2uk if len(w) >= 3}, key=len, reverse=True)
    en_re = re.compile(r'(?<!\w)(' + '|'.join(re.escape(w) for w in ws) + r')(?!\w)',
                       re.IGNORECASE)
    return en2uk, pat, en_re


def text_of(body):
    for st, sd in subrecs(body):
        if st == b'NAME':
            return sd.split(b'\0')[0].decode('cp1251', 'replace')
    return ''


def main():
    limit = 40
    for a in sys.argv[1:]:
        if a.isdigit():
            limit = int(a)
    en2uk, pat, en_re = build_maps()

    dirs, contents = paths.read_modlist()
    resolved = paths.resolve_plugins(dirs)

    loss = {}
    samples = {}
    total_ok = total_bad = 0
    for c in contents:
        orig = (BASE_ESM if c.lower() == 'morrowind.esm'
                and os.path.isfile(BASE_ESM) else resolved.get(c.lower()))
        ours = os.path.join(MODROOT, c)
        if not os.path.isfile(ours):
            ours = orig
        if not orig or not ours or not os.path.isfile(orig):
            continue
        a = list(records(open(orig, 'rb').read()))
        b = list(records(open(ours, 'rb').read()))
        if len(a) != len(b):
            continue
        for (tag, obody), (_t, nbody) in zip(a, b):
            if tag != b'INFO':
                continue
            en = text_of(obody)
            if not en:
                continue
            referenced = {en2uk[m.group(1).lower()] for m in en_re.finditer(en)
                          if m.group(1).lower() in en2uk}
            if not referenced:
                continue
            uk = text_of(nbody)
            here = set()
            for m in AT.finditer(uk):
                surf = m.group(1)
                for t in referenced:
                    rx_stems = pat.get(t)
                    if rx_stems and rx_stems[0].fullmatch(surf) \
                            and _suffix_ok(surf, rx_stems[1]):
                        here.add(t)
                        break
            for t in referenced:
                if t in here:
                    total_ok += 1
                else:
                    total_bad += 1
                    loss[t] = loss.get(t, 0) + 1
                    if len(samples.setdefault(t, [])) < 2 and uk:
                        samples[t].append(re.sub(r'\s+', ' ', uk)[:120])

    print('згадок клікабельних     : %d' % total_ok)
    print('згадок лише в переліку  : %d' % total_bad)
    print('тем, що втрачають клік  : %d' % len(loss))
    print()

    order = sorted(loss.items(), key=lambda kv: -kv[1])
    if '--csv' in sys.argv:
        for t, n in order:
            print('%d\t%s' % (n, t))
        return 0
    for t, n in order[:limit]:
        print('%5d  %s' % (n, t))
        for s in samples.get(t, []):
            print('         %s' % s)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
