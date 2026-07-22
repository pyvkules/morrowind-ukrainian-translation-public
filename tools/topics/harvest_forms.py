# -*- coding: utf-8 -*-
"""Harvest real inflected forms of every topic name from our own translated corpus.

OpenMW only makes a word clickable when the dialogue text literally contains a known
topic phrase, matched on whole-word boundaries. Ukrainian inflects, so the nominative
topic name ("Балмора") never matches "у Балморі". Rather than guess morphology, this
harvests the forms that ACTUALLY occur in the ~23.5k lines we already translated.

Naive stemming over-matches badly ("імперці" -> "імператор", "Неревар" -> "Нереварін",
"потреба" -> "потребувала"), so three guards are applied:

  1. SUFFIX CAP    - at most MAX_SUF extra letters may follow the stem, which kills
                     derivations like -атор / -увала while keeping real case endings.
  2. STEM FLOOR    - the stem keeps at least STEM_KEEP of the word, so short topics
                     cannot swallow longer unrelated words.
  3. OWNERSHIP     - every harvested form belongs to exactly ONE topic: the one whose
                     stem matches it most specifically. A form that is another topic's
                     canonical name is never stolen.

Output: tools/topics/harvested_forms.json  { "<UK topic name>": ["form", ...] }
Usage: py harvest_forms.py
"""
import json
import glob
import os
import re
import sys
import io
import math
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', write_through=True)

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)

MAX_SUF = 3        # letters allowed after the stem
STEM_KEEP = 0.72   # fraction of a word that must survive stemming
MIN_STEM = 4

CYR = 'а-щьюяєіїґА-ЩЬЮЯЄІЇҐ'
WORD = re.compile('[' + CYR + ']+')

# derivational tails that the suffix cap alone cannot stop: verbs built off a noun
# stem ("потреба" -> "потребує") and relative adjectives ("щур" -> "щуряча").
# Real case endings never start this way, so rejecting them costs nothing.
BAD_SUF = re.compile('^(у[юєяії]|ув|яч|ськ|цьк)')

src = json.load(open(os.path.join(HERE, 'dial_topics.json'), encoding='utf-8'))
uk = {}
for p in sorted(glob.glob(os.path.join(HERE, 'uk_dial_topics*.json'))):
    for k, v in json.load(open(p, encoding='utf-8')).items():
        uk[int(k)] = v
print('topics translated so far: %d / %d' % (len(uk), len(src)))

chunks = []
for p in glob.glob(os.path.join(TOOLS, 'uk', '*.json')):
    try:
        data = json.load(open(p, encoding='utf-8'))
    except Exception:
        continue
    chunks.extend(str(v) for v in data.values())
corpus = '\n'.join(chunks)
print('corpus: %d lines, %d chars' % (len(chunks), len(corpus)))

canonical = {v.lower() for v in uk.values()}


def stem(word):
    if len(word) <= MIN_STEM:
        return word
    keep = max(MIN_STEM, int(math.ceil(len(word) * STEM_KEEP)), len(word) - 2)
    return word[:keep]


def pattern_for(name):
    parts, last, stems = [], 0, []
    for m in WORD.finditer(name):
        parts.append(re.escape(name[last:m.start()]))
        s = stem(m.group(0))
        stems.append(s)
        parts.append(re.escape(s) + '[' + CYR + ']{0,%d}' % MAX_SUF)
        last = m.end()
    parts.append(re.escape(name[last:]))
    body = ''.join(parts)
    if not body.strip():
        return None, 0, []
    return (re.compile(r'(?<![' + CYR + r'])(' + body + r')(?![' + CYR + r'])'),
            sum(len(s) for s in stems), stems)


def suffix_ok(form, stems):
    """Reject a candidate whose extra letters are a derivational, not inflectional, tail."""
    words = WORD.findall(form)
    if len(words) != len(stems):
        return False
    for w, s in zip(words, stems):
        if BAD_SUF.match(w[len(s):].lower()):
            return False
    return True


# collect candidates together with how specific the owning topic's stem is
claims = defaultdict(list)          # form -> [(specificity, topic)]
no_hits = []
for i, name in uk.items():
    if not WORD.search(name):
        continue
    rx, spec, stems = pattern_for(name)
    if rx is None:
        continue
    forms = {m.group(1) for m in rx.finditer(corpus)}
    forms = {f for f in forms if abs(len(f) - len(name)) <= 3}
    forms.discard(name)
    forms = {f for f in forms if f.lower() not in canonical}   # never steal another topic
    forms = {f for f in forms if suffix_ok(f, stems)}
    if forms:
        for f in forms:
            claims[f].append((spec, name))
    else:
        no_hits.append(name)

harvest = defaultdict(set)
for form, owners in claims.items():
    owners.sort(reverse=True)       # most specific stem wins
    harvest[owners[0][1]].add(form)

out = {k: sorted(v) for k, v in sorted(harvest.items())}
json.dump(out, open(os.path.join(HERE, 'harvested_forms.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

print()
print('topics with extra forms : %d' % len(out))
print('topics with none        : %d' % len(no_hits))
print('extra .top lines        : %d' % sum(len(v) for v in out.values()))
print('contested forms resolved: %d' % sum(1 for v in claims.values() if len(v) > 1))
print()
print('examples:')
for k in ['щур', 'імперці', 'Неревар', 'Храм', 'Балмора', 'Гільдія магів', 'потреба']:
    if k in out:
        print('  %-18s -> %s' % (k, ', '.join(out[k][:8])))
