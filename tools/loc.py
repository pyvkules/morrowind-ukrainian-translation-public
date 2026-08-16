# -*- coding: utf-8 -*-
"""Єдина точка входу для локалізації — щоб дозвіл давати ОДИН раз.

Усе (перевірка cp1251, композитори, build.py, перевірка esmtool, git) виконується
всередині ЦЬОГО процесу, тож назовні видно лише незмінні команди:

    py tools\loc.py            # валідація overrides + компоузери + build + esmcheck
    py tools\loc.py save       # git add/commit/push (повідомлення з tools\_msg.txt)
    py tools\loc.py all        # rebuild, а тоді save

Оскільки git та esmtool стартують як підпроцеси ЗСЕРЕДИНИ python, окремих запитів
дозволу на них немає — досить дозволити `py ...loc.py` (і `py ...loc.py save`) раз.
"""
import io
import json
import os
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import glyphs
REPO = os.path.dirname(HERE)
ITEMS = os.path.join(HERE, 'items')
ESMTOOL = r'E:\Morrowind\OpenMW\esmtool.exe'
PY = sys.executable


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd or REPO, capture_output=True, text=True,
                          encoding='utf-8', errors='replace')


CYR = set('абвгдежзийклмнопрстуфхцчшщъыьэюяєіїґ')
LAT = set('abcdefghijklmnopqrstuvwxyz')


def mixed(word):
    """Слово з літерами обох абеток - майже завжди описка.

    Латинські a c e i o p x y виглядають точнісінько як кириличні, тож
    'Нiвалiс' з латинським i мовчки проходить cp1251 і псує рядок уже в грі.
    Мітки варіантів моделей ('Чорна01-1S', 'Руда02-2S') змішують абетки навмисно
    і завжди містять цифру - саме за цифрою їх і відрізняємо від описки.
    """
    low = word.lower()
    if any(c.isdigit() for c in low):
        return False
    return bool(set(low) & CYR) and bool(set(low) & LAT)


def normalize_punctuation():
    """Полагодити розділові знаки, які не доїдуть до екрана.

    Дві різні біди, обидві мовчазні:
      * U+02BC і U+2019 у cp1251 не існують - рядок зникне цілком;
      * «, », „ у cp1251 є, але в шрифтах мода нема гліфа - буде порожнеча.
    В обох випадках заміна однозначна (див. glyphs.SUBST), тож не сваримося,
    а чинимо самі й лише кажемо, скільки разів довелося.
    """
    fixed = 0
    for fn in sorted(os.listdir(ITEMS)):
        if not fn.endswith('_overrides.json'):
            continue
        p = os.path.join(ITEMS, fn)
        d = json.load(open(p, encoding='utf-8'))
        hit = False
        for k, v in list(d.items()):
            if not isinstance(v, str):
                continue
            new = glyphs.fix(v)
            if new != v:
                d[k] = new
                hit, fixed = True, fixed + 1
        if hit:
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=1, sort_keys=True)
    if fixed:
        print('розділові знаки: виправлено %d (нема в cp1251 або в шрифті)' % fixed)


def validate_cp1251():
    """Значення в *_overrides.json: cp1251, гліфи в шрифті, одна абетка."""
    normalize_punctuation()
    bad = 0
    for fn in sorted(os.listdir(ITEMS)):
        if not fn.endswith('_overrides.json'):
            continue
        d = json.load(open(os.path.join(ITEMS, fn), encoding='utf-8'))
        d.pop('_comment', None)
        for k, v in d.items():
            if not isinstance(v, str):
                continue
            try:
                v.encode('cp1251')
            except UnicodeEncodeError:
                bad += 1
                print('  CP1251 FAIL %s: %r -> %r' % (fn, k, v))
            gone = glyphs.missing(v)
            if gone:
                bad += 1
                print('  НЕМА ГЛІФА %s: %r -> %r (%s)'
                      % (fn, k, v, ' '.join('U+%04X' % ord(c) for c in sorted(gone))))
            for w in v.split():
                if mixed(w):
                    bad += 1
                    print('  ЗМІШАНІ АБЕТКИ %s: %r -> %r (слово %r)' % (fn, k, v, w))
    print('cp1251: %s' % ('OK' if bad == 0 else '%d ПОМИЛОК' % bad))
    return bad == 0


def compose():
    """Запустити всі композитори з --apply."""
    # translit.py теж композитор, просто названий інакше: він зводить npc.json з
    # npc_overrides.json у uk_npc.json. Поки його тут бракувало, правки імен NPC
    # лишалися в overrides і до збірки не доїжджали.
    scripts = [
        os.path.join(ITEMS, 'compose_names.py'),
        os.path.join(ITEMS, 'compose_creatures.py'),
        os.path.join(ITEMS, 'compose_potions.py'),
        os.path.join(ITEMS, 'compose_spells.py'),
        os.path.join(ITEMS, 'compose_overrides.py'),
        os.path.join(ITEMS, 'translit.py'),
    ]
    for s in scripts:
        if not os.path.isfile(s):
            continue
        r = run([PY, s, '--apply'])
        for line in (r.stdout or '').splitlines():
            if any(w in line for w in ('складено', 'РАЗОМ', 'ЗАПИСАНО')):
                print('  %s' % line)
            elif '/' in line and '%' in line and '->' not in line:
                print('  %s' % line.rstrip())
        if r.returncode != 0:
            print('  ПОМИЛКА у %s:\n%s' % (os.path.basename(s), r.stderr))
            return False
    return True


def build():
    r = run([PY, os.path.join(REPO, 'build.py')])
    tail = (r.stdout or '').strip().splitlines()
    for line in tail:
        if any(w in line for w in ('complete', 'FAIL', 'ПОМИЛКА', 'Error')):
            print('  %s' % line)
    if r.returncode != 0:
        print('  BUILD stderr:\n%s' % r.stderr)
    return r.returncode == 0


def esmcheck():
    bad = 0
    n = 0
    for fn in sorted(os.listdir(REPO)):
        ext = os.path.splitext(fn)[1].lower()
        if ext not in ('.esm', '.esp', '.omwaddon'):
            continue
        n += 1
        r = run([ESMTOOL, '-q', '-e', 'win1251', 'dump', os.path.join(REPO, fn)])
        out = (r.stdout or '') + (r.stderr or '')
        errs = [ln for ln in out.splitlines()
                if any(w in ln for w in ('rror', 'xception', 'nvalid', 'ailed',
                                         'nknown record', 'runcated'))]
        if r.returncode != 0 or errs:
            bad += 1
            print('  FAIL %s (exit %d)' % (fn, r.returncode))
            for e in errs[:4]:
                print('       %s' % e)
    print('esmcheck: %d файлів, %d з проблемами' % (n, bad))
    return bad == 0


def rebuild():
    print('== rebuild ==')
    ok = validate_cp1251()
    ok = compose() and ok            # також пише tools/_remaining_<cat>.txt
    ok = build() and ok
    ok = esmcheck() and ok
    print('== %s ==' % ('ГОТОВО' if ok else 'Є ПРОБЛЕМИ'))
    return ok


def save():
    print('== save ==')
    msgfile = os.path.join(HERE, '_msg.txt')
    if not os.path.isfile(msgfile):
        print('  немає tools\\_msg.txt — нема чого комітити')
        return False
    msg = open(msgfile, encoding='utf-8').read().strip()
    if not msg:
        print('  _msg.txt порожній')
        return False
    run(['git', 'add', '-A'])
    r = run(['git', 'commit', '-F', msgfile])
    print('  ' + (r.stdout or r.stderr or '').strip().splitlines()[0] if (r.stdout or r.stderr).strip() else '  (нічого комітити)')
    p = run(['git', 'push', 'origin', 'main'])
    print('  push: %s' % ('OK' if p.returncode == 0 else (p.stderr or '').strip().splitlines()[-1:] or 'FAIL'))
    return True


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else 'build'
    if arg == 'save':
        save()
    elif arg == 'all':
        if rebuild():
            save()
    else:
        rebuild()


if __name__ == '__main__':
    main()
