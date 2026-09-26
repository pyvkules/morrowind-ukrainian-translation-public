# -*- coding: utf-8 -*-
"""Взірці, за якими згадку теми впізнають у тексті.

Спільне для `mark_topics.py` і `unlinked.py`: доти те саме лежало в обох
файлах двома копіями й уже почало розходитися.

Як упізнається згадка
---------------------
Від назви теми беремо основу й дозволяємо після неї кілька літер закінчення.
Так «Балмора» ловить «Балморі» й «Балморою». Два правила понад це:

* **чергування** голосної в основі: «Дім» -> «Дому», «ніч» -> «ночі»;
* **випадний голосний**: «чужинець» -> «чужинця», «будинок» -> «будинку».

Чого основа не ловить
---------------------
Англійська тема часто складається з одного побутового слова, а українською те
саме поняття в реченні звучить іншим коренем: тема «розмова», а в тексті
«поговорити». Такі відповідники живуть у `topic_forms.json` і додаються до
теми як окремі взірці. Посилання від цього не бреше: обгортаємо лише там, де
англійський оригінал тієї самої репліки справді посилався на цю тему.
"""
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
CYR = 'а-щьюяєіїґА-ЩЬЮЯЄІЇҐ'
WORD = re.compile('[' + CYR + ']+')
MAX_SUF = 3
MAX_SUF_RAW = 6      # готовому кореню треба дотягтися до «працюватиме»
VOWELS = 'аеєиіїоуюя'
VOWEL_END = set('аяоеєуюіи')
BAD_SUF = re.compile('^(у[юєяії]|ув|яч|ськ|цьк)')
# Закритий склад дає і, відкритий о або е: Дім -> Дому, ніч -> ночі.
ALT = {'і': 'іо', 'о': 'оі', 'е': 'еі'}


def stem(word):
    """Відкинути лише власне закінчення, а не частину основи."""
    low, n = word.lower(), len(word)
    if n >= 6 and low[-2:] in ('ий', 'ій'):
        return word[:-2]
    if n >= 5 and (low[-1] in VOWEL_END or low[-1] == 'ь'):
        return word[:-1]
    return word


def flex(part):
    """Основа як взірець: остання голосна чергується або випадає."""
    for i in range(len(part) - 1, -1, -1):
        alt = ALT.get(part[i].lower())
        if not alt:
            continue
        if i == len(part) - 1:
            break
        head, rest = re.escape(part[:i]), part[i + 1:]
        drops = (0 < len(rest) <= 2
                 and not any(ch.lower() in VOWELS for ch in rest))
        pick = alt.upper() + alt if part[i].isupper() else alt
        return head + '[' + pick + ']' + ('?' if drops else '') + re.escape(rest)
    return re.escape(part)


def pattern(name, raw=False):
    """(взірець, основи) для назви теми або для готового кореня.

    Збіг шукаємо без огляду на регістр: «Поговори» на початку речення це та
    сама згадка, що й «поговорити» всередині. Рідне впізнавання тем у грі теж
    регістру не розрізняє.

    Готовому кореню з `topic_forms.json` даємо більше місця на закінчення:
    «працю» мусить дотягтися до «працюватиме».
    """
    tail = MAX_SUF_RAW if raw else MAX_SUF
    parts, last, stems = [], 0, []
    for m in WORD.finditer(name):
        parts.append(re.escape(name[last:m.start()]))
        s = m.group(0) if raw else stem(m.group(0))
        stems.append(s)
        parts.append(flex(s) + '[' + CYR + ']{0,%d}' % tail)
        last = m.end()
    parts.append(re.escape(name[last:]))
    body = ''.join(parts)
    if not body.strip():
        return None, []
    return re.compile(r'(?<![' + CYR + r'])(' + body + r')(?![' + CYR + r'])',
                      re.IGNORECASE), stems


def suffix_ok(surface, stems, lenient=False):
    words = WORD.findall(surface)
    if len(words) != len(stems):
        return False
    if lenient:
        return True
    return not any(BAD_SUF.match(w[len(s):].lower()) for w, s in zip(words, stems))


def extra_forms():
    path = os.path.join(HERE, 'topic_forms.json')
    if not os.path.isfile(path):
        return {}
    with io.open(path, encoding='utf-8') as f:
        data = json.load(f)
    data.pop('_comment', None)
    return data


def build(topics):
    """тема -> список взірців. Перший з назви теми, решта з topic_forms."""
    extra = extra_forms()
    out = {}
    for topic in topics:
        rx, stems = pattern(topic)
        variants = []
        if rx is not None:
            variants.append((rx, stems, False))
        for root in extra.get(topic, ()):
            rx2, stems2 = pattern(root, raw=True)
            if rx2 is not None:
                variants.append((rx2, stems2, True))
        if variants:
            out[topic] = variants
    return out


def find(text, topic, patterns, taken=(), limit=4):
    """(start, end, surface) першої згадки теми, або None.

    `taken` - ділянки під наявними посиланнями: усередину них не лізем.
    """
    for rx, stems, lenient in patterns.get(topic, ()):
        for m in rx.finditer(text):
            surface = m.group(1)
            if not lenient and abs(len(surface) - len(topic)) > limit:
                continue
            if not suffix_ok(surface, stems, lenient):
                continue
            if any(m.start() < b and a < m.end() for a, b in taken):
                continue
            return m.start(), m.end(), surface
    return None


def known(surface, topic, patterns):
    """Чи веде вже наявна розмітка `@surface#` саме на цю тему."""
    for rx, stems, lenient in patterns.get(topic, ()):
        if rx.fullmatch(surface) and suffix_ok(surface, stems, lenient):
            return True
    return False
