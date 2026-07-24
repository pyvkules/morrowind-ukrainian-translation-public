# -*- coding: utf-8 -*-
"""Повернути теми, які загубилися разом із перекладом тексту.

OpenMW робить слово в репліці клікабельним, коли воно ДОСЛІВНО збігається з
ідентифікатором теми. Українська відмінює, тож "про Балмору" вже не збігається з
темою "Балмора" - і тема, яку в оригіналі можна було відкрити кліком, зникає.
Виміряно: 117 018 клікабельних згадок в оригіналі проти 29 289 у перекладі.

(`morrowind.top` тут не рятує: рушій OpenMW його НЕ читає - у виконуваному файлі
немає навіть такого рядка. Це була хибна гіпотеза.)

Рішення: не ламати українську мову заради збігу, а дописати тему явно. Для кожної
репліки дивимось, які теми підсвічував АНГЛІЙСЬКИЙ оригінал, і ті з них, що вже не
підсвічуються в перекладі, додаємо в скрипт-результат (`BNAM`) як AddTopic. Гравець
чує репліку - теми стають доступними, як і мало бути.

Оригінал і наша копія мають однаковий порядок записів (ми лише переписували вміст
підзаписів), тож ідемо по обох файлах паралельно.

    py link_topics.py            # діагностика: скільки тем повернемо
    py link_topics.py --apply
"""
import glob
import io
import json
import os
import re
import struct
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace',
                              write_through=True)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..')))
import paths

MODROOT = paths.MOD_ROOT
APPLY = '--apply' in sys.argv
MAX_PER_INFO = 8          # щоб не роздувати скрипти на рідкісних довгих репліках

# --- англійська назва теми -> українська ---
src = json.load(open(os.path.join(HERE, 'dial_topics.json'), encoding='utf-8'))
uk = {}
for p in sorted(glob.glob(os.path.join(HERE, 'uk_dial_topics*.json'))):
    for k, v in json.load(open(p, encoding='utf-8')).items():
        uk[int(k)] = v
en2uk = {}
for i, en in enumerate(src):
    t = uk.get(i)
    if t:
        en2uk[en.lower()] = t
legacy = os.path.join(HERE, 'legacy_en_ids.json')
if os.path.isfile(legacy):
    for en, ukid in json.load(open(legacy, encoding='utf-8')).items():
        en2uk.setdefault(en.lower(), ukid)


def alternation(words):
    """Один регекс на всі теми - інакше 2300 окремих пошуків на кожну репліку."""
    ws = sorted({w for w in words if len(w) >= 3}, key=len, reverse=True)
    if not ws:
        return None
    return re.compile(r'(?<!\w)(' + '|'.join(re.escape(w) for w in ws) + r')(?!\w)',
                      re.IGNORECASE)


EN_RE = alternation(en2uk.keys())

dirs, contents = paths.read_modlist()
resolved = paths.resolve_plugins(dirs)


def subrecs(body):
    i = 0
    while i + 8 <= len(body):
        t = body[i:i + 4]
        sz = struct.unpack('<I', body[i + 4:i + 8])[0]
        yield t, body[i + 8:i + 8 + sz]
        i += 8 + sz


def records(raw):
    """(tag, header_rest, body, start, total_len) для кожного запису."""
    pos, n = 0, len(raw)
    while pos + 16 <= n:
        tag = raw[pos:pos + 4]
        size = struct.unpack('<I', raw[pos + 4:pos + 8])[0]
        yield tag, raw[pos + 8:pos + 16], raw[pos + 16:pos + 16 + size]
        pos += 16 + size


def text_of(body, tag=b'NAME'):
    for st, sd in subrecs(body):
        if st == tag:
            return sd.split(b'\0')[0].decode('cp1251', 'replace')
    return None


def build(uk_topics_lower):
    return alternation(uk_topics_lower)


stats = {'added': 0, 'infos': 0, 'files': 0, 'warn': 0}
touched = []

BASE_ESM = os.path.join(paths.TOOLS, 'base.esm')


def our_file(c):
    local = os.path.join(MODROOT, c)
    if os.path.isfile(local):
        return local
    if c.lower() == 'morrowind.esm' and os.path.isfile(BASE_ESM):
        return BASE_ESM
    return resolved.get(c.lower())


# Усі теми гри разом: плагіни вантажаться в один світ, тож посилатися з репліки
# мода на тему з Morrowind.esm цілком законно.
GLOBAL_UK_TOPICS = set()
for c in contents:
    p = our_file(c)
    if not p or not os.path.isfile(p):
        continue
    raw = open(p, 'rb').read()
    if b'DIAL' not in raw:
        continue
    for tag, _hr, body in records(raw):
        if tag != b'DIAL':
            continue
        nm, typ = None, None
        for st, sd in subrecs(body):
            if st == b'NAME':
                nm = sd.split(b'\0')[0].decode('cp1251', 'replace')
            elif st == b'DATA' and sd:
                typ = sd[0]
        if typ == 0 and nm:
            GLOBAL_UK_TOPICS.add(nm)
UK_RE_GLOBAL = alternation(GLOBAL_UK_TOPICS)
print('усього тем у грі: %d' % len(GLOBAL_UK_TOPICS))

for c in contents:
    orig_path = resolved.get(c.lower())
    # Наш Morrowind.esm зібрано з tools/base.esm, а не з ванільного файлу Steam:
    # у них різна кількість записів, тож звірятися треба саме з тим, з чого збирали.
    if c.lower() == 'morrowind.esm' and os.path.isfile(BASE_ESM):
        orig_path = BASE_ESM
    if not orig_path or not os.path.isfile(orig_path):
        continue
    local = os.path.join(MODROOT, c)
    our_path = local if os.path.isfile(local) else orig_path
    orig_raw = open(orig_path, 'rb').read()
    our_raw = open(our_path, 'rb').read()
    if b'INFO' not in our_raw:
        continue

    orig_recs = list(records(orig_raw))
    our_recs = list(records(our_raw))
    if len(orig_recs) != len(our_recs):
        print('  ! %s: різна кількість записів (%d проти %d) - пропускаю'
              % (c, len(orig_recs), len(our_recs)))
        stats['warn'] += 1
        continue

    uk_topics = GLOBAL_UK_TOPICS
    out = bytearray()
    file_added = 0
    cur_uk_topic = None
    UK_RE = UK_RE_GLOBAL

    for idx, (tag, hr, body) in enumerate(our_recs):
        if tag == b'DIAL':
            nm, typ = None, None
            for st, sd in subrecs(body):
                if st == b'NAME':
                    nm = sd.split(b'\0')[0].decode('cp1251', 'replace')
                elif st == b'DATA' and sd:
                    typ = sd[0]
            cur_uk_topic = nm if typ == 0 else None
        elif tag == b'INFO' and EN_RE is not None:
            en_text = text_of(orig_recs[idx][2]) or ''
            uk_text = text_of(body) or ''
            if en_text:
                want = {en2uk[m.group(1).lower()] for m in EN_RE.finditer(en_text)
                        if m.group(1).lower() in en2uk}
                if want:
                    have = set()
                    if UK_RE is not None and uk_text:
                        have = {m.group(1) for m in UK_RE.finditer(uk_text)}
                    # тема сама на себе не посилається
                    missing = [t for t in sorted(want - have)
                               if t != cur_uk_topic and t in uk_topics]
                    if missing:
                        missing = missing[:MAX_PER_INFO]
                        subs = list(subrecs(body))
                        script = ''
                        for i, (st, sd) in enumerate(subs):
                            if st == b'BNAM':
                                script = sd.split(b'\0')[0].decode('cp1251', 'replace')
                                break
                        add = '\r\n'.join('AddTopic "%s"' % t for t in missing)
                        new_script = (script.rstrip('\r\n') + '\r\n' + add) if script.strip() else add
                        try:
                            enc = new_script.encode('cp1251')
                        except UnicodeEncodeError:
                            stats['warn'] += 1
                            enc = new_script.encode('cp1251', 'replace')
                        placed = False
                        for i, (st, sd) in enumerate(subs):
                            if st == b'BNAM':
                                subs[i] = (st, enc + b'\0')
                                placed = True
                                break
                        if not placed:
                            subs.append((b'BNAM', enc + b'\0'))
                        body = b''.join(s + struct.pack('<I', len(d)) + d for s, d in subs)
                        stats['added'] += len(missing)
                        stats['infos'] += 1
                        file_added += len(missing)
        out += tag + struct.pack('<I', len(body)) + hr + body

    if file_added:
        touched.append((file_added, c))
        stats['files'] += 1
        if APPLY:
            with open(os.path.join(MODROOT, os.path.basename(our_path)), 'wb') as f:
                f.write(bytes(out))

touched.sort(reverse=True)
for cnt, c in touched[:15]:
    print('%-52s %6d' % (c[:52], cnt))
if len(touched) > 15:
    print('... ще %d плагінів' % (len(touched) - 15))
print()
print('плагінів змінено      : %d' % stats['files'])
print('реплік доповнено      : %d' % stats['infos'])
print('тем повернуто (AddTopic): %d' % stats['added'])
print('попереджень           : %d' % stats['warn'])
print('режим                 : %s' % ('APPLIED' if APPLY else 'DRY RUN (--apply)'))
