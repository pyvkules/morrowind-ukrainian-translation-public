# -*- coding: utf-8 -*-
"""Зробити відмінкові згадки тем клікабельними — рідним механізмом OpenMW.

OpenMW уже вміє все потрібне; ми лише не давали йому даних:
  * при старті вантажить `Morrowind.top` — мапу «фраза -> тема»;
  * розмітку `@фраза#` у тексті перетворює на посилання: показує фразу, а веде на
    тему, яку `Morrowind.top` дає для цієї фрази (`topicStandardForm`).
Це працює на стоковому OpenMW — без патчу рушія (так робили рос./пол. локалізації).

Українська відмінює, тож «про Балмор**у**» не збігається з темою «Балмора», і
автопідсвітка (лише префікс) її не бачить. Тут ми обгортаємо згадку в `@форма#`.

КЛЮЧОВЕ проти хибних посилань: обгортаємо форму лише там, де **англійський
оригінал цієї ж репліки** посилався на цю тему. Інакше спільні слова («знак»,
«допомогти») ставали б хибними посиланнями всюди. Тобто лінкуємо рівно те, що
лінкувала б ваніль.

Якщо згадку в перекладі знайти не вдалося (переклад перефразував), тему все одно
додаємо в скрипт через `AddTopic`, щоб вона лишалася доступною.

Рядки з наявною розміткою `@…#` (давній переклад) не чіпаємо.

    py mark_topics.py            # діагностика
    py mark_topics.py --apply
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
BASE_ESM = os.path.join(paths.TOOLS, 'base.esm')
CYR = 'а-щьюяєіїґА-ЩЬЮЯЄІЇҐ'

# --- англійська назва теми -> українська; українська -> її форми ---
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

harvested = json.load(open(os.path.join(HERE, 'harvested_forms.json'), encoding='utf-8'))
uk2forms = {}
for topic in set(en2uk.values()):
    forms = list(harvested.get(topic, [])) + [topic]        # відмінкові форми + називний
    # довші форми раніше, щоб «Гільдії магів» виграло в «магів»
    uk2forms[topic] = sorted(set(forms), key=len, reverse=True)


def alt(words):
    ws = sorted({w for w in words if len(w) >= 3}, key=len, reverse=True)
    return re.compile(r'(?<!\w)(' + '|'.join(re.escape(w) for w in ws) + r')(?!\w)',
                      re.IGNORECASE) if ws else None


EN_RE = alt(en2uk.keys())

dirs, contents = paths.read_modlist()
resolved = paths.resolve_plugins(dirs)


def our_file(c):
    local = os.path.join(MODROOT, c)
    if os.path.isfile(local):
        return local
    if c.lower() == 'morrowind.esm' and os.path.isfile(BASE_ESM):
        return BASE_ESM
    return resolved.get(c.lower())


def orig_file(c):
    if c.lower() == 'morrowind.esm' and os.path.isfile(BASE_ESM):
        return BASE_ESM
    return resolved.get(c.lower())


def subrecs(body):
    sp = 0
    while sp + 8 <= len(body):
        st = body[sp:sp + 4]
        ss = struct.unpack('<I', body[sp + 4:sp + 8])[0]
        yield st, body[sp + 8:sp + 8 + ss]
        sp += 8 + ss


def records(raw):
    pos, n = 0, len(raw)
    while pos + 16 <= n:
        tag = raw[pos:pos + 4]
        size = struct.unpack('<I', raw[pos + 4:pos + 8])[0]
        yield tag, raw[pos + 8:pos + 16], raw[pos + 16:pos + 16 + size]
        pos += 16 + size


def find_form(text, topic):
    """(start, end, surface) першої згадки будь-якої форми теми в тексті, або None."""
    for form in uk2forms.get(topic, ()):
        m = re.search(r'(?<![' + CYR + r'])(' + re.escape(form) + r')(?![' + CYR + r'])', text)
        if m:
            return m.start(), m.end(), m.group(1)
    return None


stats = {'wrapped': 0, 'added': 0, 'infos': 0, 'files': 0, 'warn': 0}
top_used = {}
touched = []

for c in contents:
    op, wp = orig_file(c), os.path.join(MODROOT, c)
    wp = wp if os.path.isfile(wp) else our_file(c)
    if not op or not wp or not os.path.isfile(op) or not os.path.isfile(wp):
        continue
    orig = list(records(open(op, 'rb').read()))
    ours = list(records(open(wp, 'rb').read()))
    if len(orig) != len(ours):        # різна структура — звіряти нема з чим
        continue

    out = bytearray()
    file_wrapped = file_added = 0
    cur_topic = None
    for idx, (tag, hr, body) in enumerate(ours):
        if tag == b'DIAL':
            nm = typ = None
            for st, sd in subrecs(body):
                if st == b'NAME':
                    nm = sd.split(b'\0')[0].decode('cp1251', 'replace')
                elif st == b'DATA' and sd:
                    typ = sd[0]
            cur_topic = nm if typ == 0 else None
        elif tag == b'INFO' and EN_RE is not None:
            en_text = ''
            for st, sd in subrecs(orig[idx][2]):
                if st == b'NAME':
                    en_text = sd.split(b'\0')[0].decode('cp1251', 'replace')
                    break
            if en_text:
                referenced = {en2uk[m.group(1).lower()] for m in EN_RE.finditer(en_text)
                              if m.group(1).lower() in en2uk}
                referenced.discard(cur_topic)
                if referenced:
                    subs = list(subrecs(body))
                    # --- обгортання в тексті NAME ---
                    name_i = next((i for i, (st, _sd) in enumerate(subs) if st == b'NAME'), None)
                    linked = set()
                    if name_i is not None:
                        z = subs[name_i][1].endswith(b'\0')
                        text = (subs[name_i][1][:-1] if z else subs[name_i][1]).decode('cp1251', 'replace')
                        if '@' not in text:
                            spans = []
                            for topic in referenced:
                                hit = find_form(text, topic)
                                if hit:
                                    spans.append((hit[0], hit[1], hit[2], topic))
                            spans.sort()
                            # прибрати перекриття (лишаємо перше/довше)
                            clean, lastend = [], -1
                            for s, e, surf, topic in spans:
                                if s >= lastend:
                                    clean.append((s, e, surf, topic))
                                    lastend = e
                            if clean:
                                nt, last = [], 0
                                for s, e, surf, topic in clean:
                                    nt.append(text[last:s]); nt.append('@' + surf + '#')
                                    top_used[surf] = topic
                                    linked.add(topic)
                                    last = e
                                nt.append(text[last:])
                                nb = ''.join(nt)
                                try:
                                    enc = nb.encode('cp1251')
                                except UnicodeEncodeError:
                                    stats['warn'] += 1
                                    enc = nb.encode('cp1251', 'replace')
                                subs[name_i] = (b'NAME', enc + b'\0' if z else enc)
                                file_wrapped += len(clean)
                                stats['wrapped'] += len(clean)
                                stats['infos'] += 1
                    # --- запасний AddTopic для тем, які не вдалося обгорнути ---
                    missing = sorted(t for t in referenced if t not in linked)
                    if missing:
                        bnam_i = next((i for i, (st, _sd) in enumerate(subs) if st == b'BNAM'), None)
                        script = ''
                        if bnam_i is not None:
                            z2 = subs[bnam_i][1].endswith(b'\0')
                            script = (subs[bnam_i][1][:-1] if z2 else subs[bnam_i][1]).decode('cp1251', 'replace')
                        add = '\r\n'.join('AddTopic "%s"' % t for t in missing)
                        ns = (script.rstrip('\r\n') + '\r\n' + add) if script.strip() else add
                        try:
                            enc = ns.encode('cp1251')
                        except UnicodeEncodeError:
                            stats['warn'] += 1
                            enc = ns.encode('cp1251', 'replace')
                        if bnam_i is not None:
                            subs[bnam_i] = (b'BNAM', enc + b'\0')
                        else:
                            subs.append((b'BNAM', enc + b'\0'))
                        file_added += len(missing)
                        stats['added'] += len(missing)
                    body = b''.join(s + struct.pack('<I', len(d)) + d for s, d in subs)
        out += tag + struct.pack('<I', len(body)) + hr + body

    if file_wrapped or file_added:
        touched.append((file_wrapped, file_added, c))
        stats['files'] += 1
        if APPLY:
            with open(os.path.join(MODROOT, os.path.basename(wp)), 'wb') as f:
                f.write(bytes(out))

# --- Morrowind.top: ужиті форми + фрази давнього перекладу ---
glossary = {}
gpath = os.path.join(HERE, '..', 'topics_glossary.json')
if os.path.isfile(gpath):
    glossary = json.load(open(gpath, encoding='utf-8'))
    glossary.pop('_comment', None)
top_entries = dict(top_used)
for phrase, topic in glossary.items():
    top_entries.setdefault(phrase, topic)

if APPLY:
    buf = bytearray()
    for phrase in sorted(top_entries):
        try:
            buf += phrase.encode('cp1251') + b'\t' + top_entries[phrase].encode('cp1251') + b'\r\n'
        except UnicodeEncodeError:
            stats['warn'] += 1
    with open(os.path.join(MODROOT, 'Morrowind.top'), 'wb') as f:
        f.write(bytes(buf))

touched.sort(reverse=True)
print('%-46s %8s %9s' % ('PLUGIN', 'wrapped', 'AddTopic'))
for w, a, c in touched[:15]:
    print('%-46s %8d %9d' % (c[:46], w, a))
if len(touched) > 15:
    print('... ще %d плагінів' % (len(touched) - 15))
print()
print('плагінів змінено      : %d' % stats['files'])
print('згадок обгорнуто @…#  : %d' % stats['wrapped'])
print('запасних AddTopic     : %d' % stats['added'])
print('рядків у Morrowind.top: %d' % len(top_entries))
print('попереджень           : %d' % stats['warn'])
print('режим                 : %s' % ('APPLIED' if APPLY else 'DRY RUN (--apply)'))
