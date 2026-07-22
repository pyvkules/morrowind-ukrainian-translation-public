# -*- coding: utf-8 -*-
"""Regenerate ../morrowind.top - the phrase -> topic id keyword table.

OpenMW only hyperlinks a topic when the dialogue text contains the topic id itself,
matched on whole-word boundaries. Ukrainian inflects, so the table supplies the forms
the nominative id can never match. Three sources feed it:

  1. topics_glossary.json    - hand-written phrases for the topics that were already
                               Ukrainian before this project started.
  2. topics/harvested_forms.json - inflected forms mined from our own translated
                               corpus by topics/harvest_forms.py.
  3. topics/dial_topics.json - the ENGLISH name of every renamed topic, so that mod
                               dialogue we have not translated yet still hyperlinks.

Regenerates the whole file, so it is safe to re-run after any of the three change.
Format: 'phrase<TAB>topic id', cp1251, CRLF, one trailing newline.

Usage: py build_top.py
"""
import json
import glob
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TOOLS = os.path.dirname(os.path.abspath(__file__))
TOPICS = os.path.join(TOOLS, 'topics')
TOP = os.path.abspath(os.path.join(TOOLS, '..', 'morrowind.top'))

src = json.load(open(os.path.join(TOPICS, 'dial_topics.json'), encoding='utf-8'))
uk = {}
for p in sorted(glob.glob(os.path.join(TOPICS, 'uk_dial_topics*.json'))):
    for k, v in json.load(open(p, encoding='utf-8')).items():
        uk[int(k)] = v

# final topic id for every entry, and the set of ids we must never shadow
final = {i: (uk.get(i) or src[i]) for i in range(len(src))}
canonical = {v.lower() for v in final.values()}

entries = {}      # phrase.lower() -> (phrase, topic id); first writer wins
counts = {'glossary': 0, 'harvested': 0, 'english': 0, 'skipped': 0}


def add(phrase, topic, kind):
    phrase = phrase.strip()
    # a phrase pointing at an id no longer in the game is dead weight in the table
    if not phrase or not topic or topic.lower() not in canonical:
        counts['skipped'] += 1
        return
    key = phrase.lower()
    if key == topic.lower() or key in entries:
        counts['skipped'] += 1
        return
    entries[key] = (phrase, topic)
    counts[kind] += 1


# the glossary predates the rename, so its targets are still English ids
en_to_uk = {src[i].lower(): final[i] for i in range(len(src)) if final[i] != src[i]}
glossary = json.load(open(os.path.join(TOOLS, 'topics_glossary.json'), encoding='utf-8'))
glossary.pop('_comment', None)
for phrase, topic in glossary.items():
    add(phrase, en_to_uk.get(topic.lower(), topic), 'glossary')

harvested = json.load(open(os.path.join(TOPICS, 'harvested_forms.json'), encoding='utf-8'))
for topic, forms in harvested.items():
    for f in forms:
        add(f, topic, 'harvested')

for i, en in enumerate(src):
    if final[i] != en and en.lower() not in canonical:
        add(en, final[i], 'english')

for en, uid in json.load(open(os.path.join(TOPICS, 'legacy_en_ids.json'),
                              encoding='utf-8')).items():
    add(en, uid, 'english')

out = bytearray()
warn = 0
for key in sorted(entries):
    phrase, topic = entries[key]
    try:
        out += phrase.encode('cp1251') + b'\t' + topic.encode('cp1251') + b'\r\n'
    except UnicodeEncodeError as e:
        warn += 1
        print('  WARN cp1251:', repr(phrase), repr(topic), e)

with open(TOP, 'wb') as f:
    f.write(bytes(out))

print('morrowind.top rebuilt: %d entries' % len(entries))
print('  from glossary  : %d' % counts['glossary'])
print('  harvested forms: %d' % counts['harvested'])
print('  english names  : %d' % counts['english'])
print('  skipped (dupe / same as id): %d' % counts['skipped'])
print('  encode warnings: %d' % warn)
