# -*- coding: utf-8 -*-
"""Успадкувати переклад ванільної репліки, яку мод перевизначив із опискою.

Навіщо
------
«Patch for Purists» та інші моди перевизначають ванільні репліки **за тим
самим id запису**, виправляючи в них описку: `Khajiti` -> `Khajiiti`,
`give my` -> `give me`, пробіл на дефіс. Ключ нашої пам'яті - текст, тож
найменша така правка робить наш переклад недосяжним: у грі виграє пізніший
плагін, і гравець бачить англійську там, де ваніль давно перекладено. Саме
так «англійськими» стають репліки, яких у жодному незакритому зрізі нема.

Виміряно: 924 записи, з них 905 у «Patch for Purists».

Що вважаємо безпечним
---------------------
Тексти розкладаємо на слова. Успадковуємо лише тоді, коли кожна відмінність -
це **заміна одного слова на одне** й ті слова різняться щонайбільше двома
літерами (`Khajiti`/`Khajiiti`, `my`/`me`). Якщо мод слово **додав** або
**викинув** - це вже зміна змісту, а не описка: такі випадки скрипт показує
окремо, і їх вирішує людина.

    py tools\\dialogue\\inherit.py            # показати, що успадкується
    py tools\\dialogue\\inherit.py --apply    # записати в uk/
    py tools\\dialogue\\inherit.py --unsafe   # показати те, що людині
"""
import glob
import io
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import paths

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                              errors='replace', write_through=True)

APPLY = '--apply' in sys.argv
UNSAFE = '--unsafe' in sys.argv
CYR = re.compile(u'[Ѐ-ӿ]')
LAT = re.compile(r'[A-Za-z]{3}')
# Апостроф - частина слова, а не межа: інакше `You're` розпадається на два
# токени, і правка `You're`->`Your` виглядає зміною змісту, хоч це описка.
WORD = re.compile(r"[\w']+", re.UNICODE)
# %PCName, %PCRank... - рушій підставляє в них ім'я й звання гравця. Якщо мод
# додав підстановку, якої у ванілі не було, старий переклад її не має, і в грі
# лишиться дірка. `check_sources` це ловить, але краще не створювати.
TOKEN = re.compile(r'%[A-Za-z]+')
MAX_EDITS = 2


def dec(b):
    return b.rstrip(b'\0').decode('cp1251', 'replace')


def infos(data):
    """id запису -> текст, у порядку файлу."""
    i, L = 0, len(data)
    while i + 16 <= L:
        rt = data[i:i + 4]
        sz = struct.unpack_from('<I', data, i + 4)[0]
        if sz > L:
            break
        if rt == b'INFO':
            body = data[i + 16:i + 16 + sz]
            j, subs = 0, {}
            while j + 8 <= len(body):
                st = body[j:j + 4]
                ss = struct.unpack_from('<I', body, j + 4)[0]
                subs.setdefault(st, body[j + 8:j + 8 + ss])
                j += 8 + ss
            if b'INAM' in subs:
                yield dec(subs[b'INAM']).strip(), dec(subs.get(b'NAME', b'')).strip()
        i += 16 + sz


def load(p):
    with open(p, 'rb') as f:
        raw = f.read()
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return json.loads(raw.decode('utf-16'))
    return json.loads(raw.decode('utf-8-sig'))


def edits(a, b):
    """Відстань Левенштейна, але рахуємо лише до MAX_EDITS + 1."""
    if abs(len(a) - len(b)) > MAX_EDITS:
        return MAX_EDITS + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
        if min(prev) > MAX_EDITS:
            return MAX_EDITS + 1
    return prev[-1]


# Службові слова англійської, які в українську не переносяться зовсім:
# артиклі, прийменники, сполучники. «Patch for Purists» тим і зайнятий,
# що лагодить граматику оригіналу, а переклад від цього не змінюється.
# Займенників і дієслів тут свідомо нема: `his`->`her` чи `We`->`They`
# змінюють зміст, і такі випадки мусить бачити людина.
ARTICLE = re.compile(
    r'\b(?:a|an|the|to|of|in|on|at|and|or|that|s)\b', re.IGNORECASE)


def letters(text):
    """Самі літери, без артиклів, пробілів і розділових знаків.

    Англійська граматика на українську не переноситься: вставлений артикль,
    `soulgems` -> `soul gems`, `alot` -> `a lot` - усе це той самий текст для
    перекладача. Звівши обидва до суцільного ряду літер, ми саме ці правки й
    робимо невидимими.
    """
    return re.sub(r'[^a-z]', '', ARTICLE.sub(' ', text).lower())


def only_typos(new, old):
    """Чи відмінність між текстами - самі лише описки в окремих словах."""
    if sorted(TOKEN.findall(new)) != sorted(TOKEN.findall(old)):
        return False                      # набір підстановок різний
    if letters(new) == letters(old):
        return True                       # різниця суто англограматична
    a, b = WORD.findall(new), WORD.findall(old)
    if len(a) != len(b):
        return False                      # слово додано або викинуто
    changed = 0
    for x, y in zip(a, b):
        if x == y:
            continue
        changed += 1
        if changed > 3 or edits(x.lower(), y.lower()) > MAX_EDITS:
            return False
    return True


def memory():
    """Англійський текст -> наш переклад, з усіх зрізів."""
    out = {}
    for path in sorted(glob.glob(os.path.join(TOOLS, 'src', '*.json'))):
        name = os.path.basename(path)[:-5]
        src = load(path)
        if not isinstance(src, list):
            continue
        uk = {}
        for q in sorted(glob.glob(os.path.join(TOOLS, 'uk', name + '.json'))
                        + glob.glob(os.path.join(TOOLS, 'uk', name + '_p*.json'))):
            uk.update(load(q))
        for i, en in enumerate(src):
            if isinstance(en, str) and uk.get(str(i)):
                out.setdefault(en, uk[str(i)])
    return out


def slices():
    """Англійський текст -> (зріз, номер), лише для неперекладених."""
    out = {}
    for path in sorted(glob.glob(os.path.join(TOOLS, 'src', '*.json'))):
        name = os.path.basename(path)[:-5]
        src = load(path)
        if not isinstance(src, list):
            continue
        uk = {}
        for q in sorted(glob.glob(os.path.join(TOOLS, 'uk', name + '.json'))
                        + glob.glob(os.path.join(TOOLS, 'uk', name + '_p*.json'))):
            uk.update(load(q))
        for i, en in enumerate(src):
            if isinstance(en, str) and not uk.get(str(i)):
                out.setdefault(en, (name, i))
    return out


def main():
    dirs, contents = paths.read_modlist()
    res = paths.resolve_plugins(dirs)
    if 'morrowind.esm' not in res:
        print('не знайдено Morrowind.esm у модлисті')
        return 1
    van = {k: t for k, t in infos(open(res['morrowind.esm'], 'rb').read()) if t}
    mem = memory()
    where = slices()

    safe, unsafe = {}, []
    for c in contents:
        p = res.get(c.lower())
        if not p or not os.path.isfile(p) or c.lower() == 'morrowind.esm':
            continue
        for k, t in infos(open(p, 'rb').read()):
            if not t or CYR.search(t) or not LAT.search(t):
                continue
            if t in mem or t not in where:
                continue                  # уже перекладено або поза зрізами
            vt = van.get(k)
            if not vt or vt == t or vt not in mem:
                continue
            if only_typos(t, vt):
                safe.setdefault(t, (where[t], mem[vt], c))
            else:
                unsafe.append((c, where[t], vt, t))

    print('можна успадкувати (самі описки): %d реплік' % len(safe))
    print('потребують людини (змінено слова): %d' % len(unsafe))
    if UNSAFE:
        print()
        for c, (name, i), vt, t in unsafe[:40]:
            print('%s:%d  [%s]' % (name, i, c[:28]))
            print('   ВАНІЛЬ %s' % vt[:110])
            print('   МОД    %s' % t[:110])
        return 0

    if not APPLY:
        for t, ((name, i), uk, c) in list(safe.items())[:8]:
            print('  %s:%d  %s' % (name, i, uk[:80]))
        print('(без --apply нічого не записано)')
        return 0

    by_slice = {}
    for t, ((name, i), uk, c) in safe.items():
        by_slice.setdefault(name, {})[i] = uk
    total = 0
    for name, items in sorted(by_slice.items()):
        found = sorted(glob.glob(os.path.join(TOOLS, 'uk', name + '.json'))
                       + glob.glob(os.path.join(TOOLS, 'uk', name + '_p*.json')))
        out = found[-1] if found else os.path.join(TOOLS, 'uk', name + '.json')
        d = load(out) if os.path.isfile(out) else {}
        for i, uk in items.items():
            d[str(i)] = uk
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write('\n')
        print('  %-34s +%d -> %s' % (name, len(items), os.path.basename(out)))
        total += len(items)
    print('успадковано: %d' % total)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
