# -*- coding: utf-8 -*-
"""Окрема збірка Morrowind для випробувань встановлювача.

Навіщо
------
Усі три звернення від людей, які спробували встановлювач, були про шляхи:
«Program Files» без прав адміністратора, тека інструментів у «Downloads»,
непроханий запуск налаштування umo. На машині автора нічого з цього немає,
бо там усе вже стоїть і все вже налаштоване. Побачити ті поламки можна
тільки з чистої системи.

Повноцінна чиста система це або друга Windows, або віртуалка. Та всі три
поламки були в тому, **звідки програма бере шляхи**, а шляхи вона бере з
оточення: `USERPROFILE`, `LOCALAPPDATA`, `APPDATA`, `TEMP`, `PROGRAMFILES`.
Підміняємо ці змінні, і та сама програма, нічим не змінена, бачить машину,
на якій немає нічого.

Чого ця пісочниця не ловить
---------------------------
Реєстр, права адміністратора й справжній «Program Files» лишаються
спільні. Тобто вона показує поламки шляхів і порядку кроків, а не поламки
прав. Для прав потрібна віртуалка.

Як користуватися
----------------
    py installer/sandbox.py probe            # швидка перевірка кроків
    py installer/sandbox.py run              # пустити встановлювач у вікні
    py installer/sandbox.py run --exe        # те саме, але зібраний .exe
    py installer/sandbox.py reset            # стерти й почати з чистого
    py installer/sandbox.py seed --mods      # дати пісочниці готові моди
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.environ.get('UKR_SANDBOX') or r'E:\Morrowind\test-home'

# Теки, які Windows створює в кожному профілі. Без них програми, що пишуть
# у «Documents», падають ще до того, як ми щось перевіримо.
DIRS = ('Documents', 'Downloads', 'Temp',
        os.path.join('AppData', 'Local'),
        os.path.join('AppData', 'Roaming'),
        os.path.join('AppData', 'Local', 'Programs'),
        'Program Files')

UMO_CFG = os.path.join('AppData', 'Local', 'umomwd', 'umomwd', 'config.json')


def paths(home):
    """Оточення підміненого профілю."""
    drive, tail = os.path.splitdrive(home)
    return {
        'USERPROFILE': home,
        'HOMEDRIVE': drive,
        'HOMEPATH': tail,
        'LOCALAPPDATA': os.path.join(home, 'AppData', 'Local'),
        'APPDATA': os.path.join(home, 'AppData', 'Roaming'),
        'TEMP': os.path.join(home, 'Temp'),
        'TMP': os.path.join(home, 'Temp'),
        # PROGRAMFILES підмінити не можна: Windows виставляє його кожному
        # процесові наново з реєстру, хоч що передай. Тому встановлювач
        # дивиться ще й на власну UKR_PROGRAMFILES.
        'UKR_PROGRAMFILES': os.path.join(home, 'Program Files'),
    }


def make(home):
    for d in DIRS:
        os.makedirs(os.path.join(home, d), exist_ok=True)
    return home


def env(home):
    e = dict(os.environ)
    e.update(paths(home))
    # Щоб запущена програма могла сказати, що вона в пісочниці.
    e['UKR_SANDBOX'] = home
    return e


def guard(home):
    """Не дати стерти щось, що не є пісочницею."""
    home = os.path.abspath(home)
    if len(home) < 8 or os.path.splitdrive(home)[1].strip('\\/') == '':
        raise SystemExit('Небезпечний шлях пісочниці: %s' % home)
    real = os.path.abspath(os.path.expanduser('~'))
    if os.path.normcase(home) == os.path.normcase(real):
        raise SystemExit('Це справжній профіль, а не пісочниця.')
    return home


def cmd_reset(args):
    home = guard(args.home)
    if os.path.isdir(home):
        shutil.rmtree(home, ignore_errors=True)
        print('Стерто %s' % home)
    make(home)
    print('Пісочниця чиста: %s' % home)
    return 0


def cmd_seed(args):
    """Покласти в пісочницю те, що на машині випробувача вже є.

    Без цього кожен запуск качав би ті самі вісімдесят гігабайтів. Ключ
    Nexus із власного config.json переносимо як є: він лишається на цій
    самій машині й нікуди не їде.
    """
    home = make(guard(args.home))
    src = os.path.join(os.environ.get('LOCALAPPDATA', ''),
                       'umomwd', 'umomwd', 'config.json')
    if not os.path.isfile(src):
        print('Свого config.json umo немає, засівати нема чим.')
        return 1
    with io.open(src, encoding='utf-8') as f:
        cfg = json.load(f)
    if not args.mods:
        # Моди в пісочницю окремо: інакше umo писатиме в теку автора.
        cfg['BASEPATH'] = os.path.join(home, 'Morrowind')
        cfg['CACHE_DIR'] = os.path.join(home, 'Morrowind', 'cache')
        os.makedirs(cfg['BASEPATH'], exist_ok=True)
    dst = os.path.join(home, UMO_CFG)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with io.open(dst, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print('umo в пісочниці налаштований, моди в %s' % cfg['BASEPATH'])
    return 0


PROBE = r'''# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, HERE_PATH)
import mods, install

print('USERPROFILE   %s' % os.path.expanduser('~'))
print('LOCALAPPDATA  %s' % os.environ.get('LOCALAPPDATA'))
print('куди рушій   %s' % os.environ.get('UKR_PROGRAMFILES'))
print()
print('інструменти   %s' % (mods.find_tools() or 'немає'))
print('config umo    %s' % mods.umo_config())
print('тека модів    %s' % (mods.umo_dirs() or 'НЕ НАЛАШТОВАНО'))
where, free = mods.suggest_mods_dir()
print('радимо        %s (%.0f ГБ вільно)' % (where, free / 1073741824.0))
print()
cfg = os.path.join(os.path.expanduser('~'), 'Documents', 'My Games',
                   'OpenMW', 'openmw.cfg')
print('openmw.cfg    %s' % ('є' if os.path.isfile(cfg) else 'немає'))
print('гра           %s' % (install.game_data_dir() or 'не знайдено'))
'''


def cmd_probe(args):
    """Пройти кроки, які не чіпають диска, і показати, що бачить програма.

    Саме цей вивід відповідає на питання «а чому в людини інакше»: видно
    всі шляхи, з яких починається кожен крок.
    """
    home = make(guard(args.home))
    script = os.path.join(home, 'Temp', 'probe.py')
    with io.open(script, 'w', encoding='utf-8') as f:
        # Підставляємо міткою, бо в самому тексті повно %s.
        f.write(PROBE.replace('HERE_PATH', repr(HERE)))
    r = subprocess.run([sys.executable, script], env=env(home),
                       cwd=home, encoding='utf-8', errors='replace')
    return r.returncode


def cmd_run(args):
    home = make(guard(args.home))
    if args.exe:
        target = os.path.join(HERE, 'dist', 'ukrainizer-setup.exe')
        if not os.path.isfile(target):
            print('Спершу збери: py installer/make.py')
            return 1
        cmd = [target]
    else:
        cmd = [sys.executable, os.path.join(HERE, 'install.py')]
    cmd += args.rest
    print('Пісочниця: %s' % home)
    print('Запускаю: %s' % ' '.join(cmd))
    return subprocess.run(cmd, env=env(home), cwd=home).returncode


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--home', default=HOME, help='тека пісочниці')
    sub = p.add_subparsers(dest='what')

    sub.add_parser('reset', help='стерти й створити заново')
    sub.add_parser('probe', help='показати, що бачить програма')

    s = sub.add_parser('seed', help='покласти налаштування umo')
    s.add_argument('--mods', action='store_true',
                   help='лишити теку модів автора, щоб не качати заново')

    r = sub.add_parser('run', help='пустити встановлювач')
    r.add_argument('--exe', action='store_true', help='зібраний .exe')
    r.add_argument('rest', nargs=argparse.REMAINDER)

    args = p.parse_args(argv)
    doer = {'reset': cmd_reset, 'seed': cmd_seed,
            'probe': cmd_probe, 'run': cmd_run}.get(args.what)
    if not doer:
        p.print_help()
        return 2
    return doer(args)


if __name__ == '__main__':
    sys.exit(main())
