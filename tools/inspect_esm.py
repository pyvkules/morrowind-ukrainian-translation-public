# -*- coding: utf-8 -*-
"""Inspect TES3 ESM: header, record counts, cell names, dialogue topics, books."""
import struct
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def read_records(path):
    with open(path, 'rb') as f:
        data = f.read()
    pos = 0
    n = len(data)
    while pos + 16 <= n:
        rtype = data[pos:pos+4]
        size = struct.unpack('<I', data[pos+4:pos+8])[0]
        body = data[pos+16:pos+16+size]
        yield rtype.decode('ascii', 'replace'), body
        pos += 16 + size

def subrecords(body):
    pos = 0
    n = len(body)
    while pos + 8 <= n:
        stype = body[pos:pos+4]
        size = struct.unpack('<I', body[pos+4:pos+8])[0]
        yield stype.decode('ascii', 'replace'), body[pos+8:pos+8+size]
        pos += 8 + size

def zstr(b):
    return b.split(b'\0')[0].decode('cp1251', 'replace')

def inspect(path, label):
    print('=' * 20, label, '=' * 20)
    counts = {}
    interior_cells = []
    topics = []
    journals = 0
    books = []
    npcs = []
    gmsts = {}
    header_shown = False
    for rtype, body in read_records(path):
        counts[rtype] = counts.get(rtype, 0) + 1
        if rtype == 'TES3' and not header_shown:
            header_shown = True
            for st, sd in subrecords(body):
                if st == 'HEDR':
                    ver = struct.unpack('<f', sd[0:4])[0]
                    author = sd[8:40].split(b'\0')[0].decode('cp1251', 'replace')
                    desc = sd[40:296].split(b'\0')[0].decode('cp1251', 'replace')
                    nrec = struct.unpack('<I', sd[296:300])[0]
                    print(f'HEADER: ver={ver:.2f} author={author!r} records={nrec}')
                    print(f'DESC: {desc!r}')
        elif rtype == 'CELL' and len(interior_cells) < 400000:
            name = None
            flags = None
            for st, sd in subrecords(body):
                if st == 'NAME':
                    name = zstr(sd)
                elif st == 'DATA' and len(sd) >= 4:
                    flags = struct.unpack('<I', sd[0:4])[0]
                    break
            if flags is not None and flags & 1 and name:
                interior_cells.append(name)
        elif rtype == 'DIAL':
            dtype = None
            name = None
            for st, sd in subrecords(body):
                if st == 'NAME':
                    name = zstr(sd)
                elif st == 'DATA' and len(sd) >= 1:
                    dtype = sd[0]
            if dtype == 0 and name:
                topics.append(name)
            elif dtype == 4:
                journals += 1
        elif rtype == 'BOOK' and len(books) < 3:
            rec = {}
            for st, sd in subrecords(body):
                if st == 'NAME':
                    rec['id'] = zstr(sd)
                elif st == 'FNAM':
                    rec['name'] = zstr(sd)
                elif st == 'TEXT':
                    rec['text'] = sd.decode('cp1251', 'replace')[:150]
            if 'text' in rec:
                books.append(rec)
        elif rtype == 'NPC_' and len(npcs) < 5:
            rec = {}
            for st, sd in subrecords(body):
                if st == 'NAME':
                    rec['id'] = zstr(sd)
                elif st == 'FNAM':
                    rec['name'] = zstr(sd)
                    break
            npcs.append(rec)
        elif rtype == 'GMST' and len(gmsts) < 500:
            gid = None
            val = None
            for st, sd in subrecords(body):
                if st == 'NAME':
                    gid = zstr(sd)
                elif st == 'STRV':
                    val = zstr(sd)
            if gid in ('sBarter', 'sTake', 'sSkillLongblade', 'sAttributeStrength', 'sRestIllegal') and val:
                gmsts[gid] = val
    print('RECORD COUNTS:', {k: v for k, v in sorted(counts.items(), key=lambda x: -x[1])[:14]})
    print('INFO count:', counts.get('INFO', 0), '| DIAL topics:', len(topics), '| journal DIALs:', journals)
    print('INTERIOR CELLS total:', len(interior_cells))
    print('SAMPLE CELLS:', interior_cells[:10])
    print('SAMPLE TOPICS:', topics[:12])
    print('SAMPLE NPCs:', npcs)
    print('SAMPLE GMST:', gmsts)
    for b in books:
        print('BOOK:', b.get('id'), '|', b.get('name'), '| TEXT:', repr(b.get('text', ''))[:160])
    return set(interior_cells), set(topics)

ua_cells, ua_topics = inspect(sys.argv[1], 'UKRAINIAN ESM')
en_cells, en_topics = inspect(sys.argv[2], 'ENGLISH ESM (Steam)')
print()
print('=' * 20, 'COMPARISON', '=' * 20)
print(f'Interior cells: UA={len(ua_cells)} EN={len(en_cells)} | identical names: {len(ua_cells & en_cells)}')
print(f'Topics: UA={len(ua_topics)} EN={len(en_topics)} | identical: {len(ua_topics & en_topics)}')
