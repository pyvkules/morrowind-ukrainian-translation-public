# -*- coding: utf-8 -*-
"""Резервна копія цього модпаку - і відновлення з неї в один крок.

Nexus без преміуму змушує чекати перед кожним завантаженням, а модів чотири сотні.
Найнадійніший спосіб більше ніколи цього не проходити - зберегти те, що вже
встановлено. Це власні файли на власному диску: копія робиться для себе.

Копіюються НЕ цілі колекції, а лише ті каталоги, які модпак справді вантажить -
їх перелічує modpack/modlist.json. Різниця істотна: колекції важать близько 186 ГБ,
а сам модпак - 47 ГБ, бо в колекціях лежить купа взаємовиключних варіантів, з яких
цей набір бере один.

Копіювання робить robocopy: воно інкрементне (друга копія переносить лише
різницю), відновлюване після обриву й багатопотокове.

Разом із копією пишеться manifest.json, щоб відновлення можна було перевірити.

    py backup.py --to D:\\morrowind-modpack             # зберегти
    py backup.py --to D:\\morrowind-modpack --verify     # перевірити копію
    py backup.py --from D:\\morrowind-modpack --restore  # відновити
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))
MANIFEST = 'manifest.json'
MODS_TOKEN = '{mods}'


def arg(flag):
    for i, a in enumerate(sys.argv):
        if a == flag and i + 1 < len(sys.argv):
            return os.path.abspath(sys.argv[i + 1])
    return None


def recipe():
    with open(os.path.join(REPO, 'modpack', 'modlist.json'), encoding='utf-8') as f:
        return json.load(f)


def mod_dirs():
    """Відносні шляхи всіх каталогів модів, які вантажить модпак."""
    return [e['v'][len(MODS_TOKEN) + 1:] for e in recipe()['entries']
            if e['k'] == 'data' and e['v'].startswith(MODS_TOKEN + '/')]


def mods_root():
    """Каталог, у якому лежать колекції модів."""
    names = recipe()['based_on']
    guess = os.path.abspath(os.path.join(REPO, '..', '..', '..'))
    for c in [guess, os.path.dirname(guess)] + [r'%s:\Morrowind' % d for d in 'CDEFGH']:
        if c and os.path.isdir(c) and all(os.path.isdir(os.path.join(c, n)) for n in names):
            return os.path.normpath(c)
    return None


def measure(path):
    files = total = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for name in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
                files += 1
            except OSError:
                pass
    return files, total


def gb(n):
    return n / (1024.0 ** 3)


def mirror(src, dst):
    """robocopy /MIR: dst стає точною копією src, переносячи лише різницю."""
    os.makedirs(dst, exist_ok=True)
    p = subprocess.run(['robocopy', src, dst, '/MIR', '/MT:16', '/R:1', '/W:1',
                        '/NFL', '/NDL', '/NP', '/NJH', '/NJS'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    return p.returncode < 8          # robocopy: 0-7 успіх, 8+ справжня помилка


def each(rels, src_root, dst_root, log, verb):
    done, failed = 0, []
    for i, rel in enumerate(rels, 1):
        src = os.path.join(src_root, rel.replace('/', os.sep))
        dst = os.path.join(dst_root, rel.replace('/', os.sep))
        if not os.path.isdir(src):
            failed.append(rel)
            continue
        if not mirror(src, dst):
            failed.append(rel)
        done += 1
        if i % 25 == 0 or i == len(rels):
            log('  %s %d/%d' % (verb, i, len(rels)))
    return done, failed


def do_backup(dest, log=print):
    root = mods_root()
    if not root:
        log('! не знайдено каталог з колекціями модів')
        return False
    rels = mod_dirs()
    log('джерело : %s' % root)
    log('призначення: %s' % dest)
    log('каталогів модів: %d' % len(rels))
    log('')
    os.makedirs(dest, exist_ok=True)

    done, failed = each(rels, root, dest, log, 'скопійовано')
    files, total = measure(dest)
    manifest = {'source': root, 'created': time.strftime('%Y-%m-%d %H:%M'),
                'dirs': rels, 'files': files, 'bytes': total,
                'modpack_version': json.load(
                    open(os.path.join(REPO, 'version.json'), encoding='utf-8'))['version']}
    with open(os.path.join(dest, MANIFEST), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    log('')
    log('збережено: %s файлів, %.1f ГБ' % ('{:,}'.format(files), gb(total)))
    if failed:
        log('! не скопійовано каталогів: %d' % len(failed))
        for r in failed[:10]:
            log('   %s' % r)
        return False
    return True


def load_manifest(src, log):
    path = os.path.join(src, MANIFEST)
    if not os.path.isfile(path):
        log('! у %s немає %s - це не копія модпаку' % (src, MANIFEST))
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def do_verify(src, log=print):
    m = load_manifest(src, log)
    if not m:
        return False
    missing = [r for r in m['dirs']
               if not os.path.isdir(os.path.join(src, r.replace('/', os.sep)))]
    files, total = measure(src)
    log('каталогів у копії : %d з %d' % (len(m['dirs']) - len(missing), len(m['dirs'])))
    log('файлів            : %s (у маніфесті %s)'
        % ('{:,}'.format(files), '{:,}'.format(m['files'])))
    log('розмір            : %.1f ГБ (у маніфесті %.1f ГБ)' % (gb(total), gb(m['bytes'])))
    for r in missing[:10]:
        log('   бракує: %s' % r)
    ok = not missing and files == m['files'] and total == m['bytes']
    log('копія %s' % ('ціла' if ok else 'НЕПОВНА'))
    return ok


def do_restore(src, dest=None, log=print):
    m = load_manifest(src, log)
    if not m:
        return False
    dest = dest or mods_root() or m['source']
    log('відновлення у %s' % dest)
    log('каталогів: %d' % len(m['dirs']))
    log('')
    done, failed = each(m['dirs'], src, dest, log, 'відновлено')
    if failed:
        log('! не відновлено каталогів: %d' % len(failed))
        for r in failed[:10]:
            log('   %s' % r)
        return False
    log('')
    log('моди відновлено - далі інсталятор збере переклад і профіль')
    return True


if __name__ == '__main__':
    to, frm = arg('--to'), arg('--from')
    if '--restore' in sys.argv:
        raise SystemExit(0 if do_restore(frm or to, arg('--dest')) else 1)
    if '--verify' in sys.argv:
        raise SystemExit(0 if do_verify(frm or to) else 1)
    if to:
        raise SystemExit(0 if do_backup(to) else 1)
    print(__doc__)
