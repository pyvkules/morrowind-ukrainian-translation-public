import json, glob, os, io, sys, collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = os.path.dirname(os.path.abspath(__file__))

def load_json(path):
    raw = open(path, 'rb').read()
    for enc in ('utf-8-sig', 'utf-16', 'cp1251'):
        try:
            return json.loads(raw.decode(enc))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise ValueError('cannot decode ' + path)

corpus = load_json(os.path.join(BASE, 'corpus.json'))

covered = set()
for f in glob.glob(os.path.join(BASE, 'src', '*.json')):
    covered.update(load_json(f))
print('already sliced uniques:', len(covered))

by_type = collections.defaultdict(list)
seen = set(covered)
for e in corpus:
    t = e['text']
    if t in seen:
        continue
    seen.add(t)
    by_type[e['type']].append(t)

for typ, texts in sorted(by_type.items()):
    print(typ, len(texts), sum(len(t) for t in texts), 'chars')

# journal: one slice, sorted by quest (dial) so related entries stay adjacent
if 'journal' in by_type:
    jset = set(by_type['journal'])
    ordered, emitted = [], set()
    for e in corpus:
        if e['type'] == 'journal' and e['text'] in jset and e['text'] not in emitted:
            ordered.append(e['text'])
            emitted.add(e['text'])
    out = os.path.join(BASE, 'src', 'journal.json')
    json.dump(ordered, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('wrote', out, len(ordered))

# topics: split into ~10 slices grouped by dial topic name
if 'topic' in by_type:
    tset = set(by_type['topic'])
    ordered, emitted = [], set()
    for e in corpus:
        if e['type'] == 'topic' and e['text'] in tset and e['text'] not in emitted:
            ordered.append(e['text'])
            emitted.add(e['text'])
    n = len(ordered)
    per = (n + 9) // 10
    for i in range(0, n, per):
        idx = i // per + 1
        out = os.path.join(BASE, 'src', 'topics%02d.json' % idx)
        json.dump(ordered[i:i+per], open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        print('wrote', out, len(ordered[i:i+per]))
