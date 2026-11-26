# -*- coding: utf-8 -*-
"""Кнопка «Запустити»: чи ми справді знаходимо рушій.

Друге звернення гравця: «все встановив, натиснув запустити, і нічого не
відбувається». Причина - `openmw_exes()` лише вгадує теки (Program Files,
корені диска, `X:\\Games`), а хто тримає OpenMW у Steam-бібліотеці або в
себе, повз ті здогади проходить. Тоді exe не знаходився, вікно все одно
закривалося, і кнопка виглядала мертвою.

`engine_exes()` питає ті джерела, які вже знають правду: журнал останнього
запуску і рядок `resources=` в ланцюжку cfg. Перевірка ганяє його на
тимчасових теках - без гри, без рушія і без мережі.

    py installer/test_launch.py

Вихід 1, якщо хоч одна перевірка впала.
"""
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import install

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                              errors='replace', write_through=True)

FAIL = []


def check(name, ok, note=''):
    print('%-4s %s%s' % ('ОК' if ok else 'ПАДЕ', name,
                         '' if ok else '  <- ' + note))
    if not ok:
        FAIL.append(name)


def make_engine(root, name):
    """Тека рушія: exe і `resources/vfs/fonts`, як у справжнього OpenMW."""
    eng = os.path.join(root, name)
    os.makedirs(os.path.join(eng, 'resources', 'vfs', 'fonts'))
    exe = os.path.join(eng, 'openmw.exe')
    io.open(exe, 'w').close()
    return eng, exe


def write(path, text):
    io.open(path, 'w', encoding='utf-8', newline='').write(text)


def test_log_wins():
    """Журнал пише теку ресурсів останнього запуску - це найточніше джерело."""
    root = tempfile.mkdtemp(prefix='ukr-launch-')
    try:
        eng, exe = make_engine(root, 'OpenMW-своя-тека')
        cfgdir = os.path.join(root, 'My Games', 'OpenMW')
        os.makedirs(cfgdir)
        cfg = os.path.join(cfgdir, 'openmw.cfg')
        write(cfg, 'data="%s"\n' % root)
        write(os.path.join(cfgdir, 'openmw.log'),
              '[10:42:40.752 I] Adding data directory %s\n'
              % os.path.join(eng, 'resources', 'vfs'))
        got = install.engine_exes(cfg)
        check('exe з журналу знайдено', exe in got,
              'знайшли %r' % (got,))
        check('саме він і перший', got and got[0] == exe,
              'перший %r' % (got[0] if got else None,))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_resources_line():
    """Без журналу лишається `resources=` - рядок, якого з теки гравця не видно."""
    root = tempfile.mkdtemp(prefix='ukr-launch-')
    try:
        eng, exe = make_engine(root, 'OpenMW 0.51.0')
        cfgdir = os.path.join(root, 'My Games', 'OpenMW')
        os.makedirs(cfgdir)
        cfg = os.path.join(cfgdir, 'openmw.cfg')
        write(cfg, 'resources="%s"\n' % os.path.join(eng, 'resources'))
        got = install.engine_exes(cfg)
        check('exe з рядка resources знайдено', exe in got,
              'знайшли %r' % (got,))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_relative_resources():
    """`resources=./resources` рахується від теки свого ж cfg, а не від нашої."""
    root = tempfile.mkdtemp(prefix='ukr-launch-')
    try:
        eng, exe = make_engine(root, 'OpenMW')
        cfg = os.path.join(eng, 'openmw.cfg')
        write(cfg, 'resources=./resources\n')
        got = install.engine_exes(cfg)
        check('відносний resources розгортається правильно', exe in got,
              'знайшли %r' % (got,))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_no_cfg_no_crash():
    """Без cfg функція мусить просто віддати здогади, а не впасти."""
    try:
        got = install.engine_exes(None)
        ok = isinstance(got, list)
        note = ''
    except Exception as e:                       # noqa: BLE001
        ok, got, note = False, None, '%s: %s' % (type(e).__name__, e)
    check('без cfg не падає', ok, note)
    try:
        install.engine_exes(os.path.join(tempfile.gettempdir(), 'немає.cfg'))
        ok, note = True, ''
    except Exception as e:                       # noqa: BLE001
        ok, note = False, '%s: %s' % (type(e).__name__, e)
    check('на неіснуючий cfg не падає', ok, note)


def test_no_phantom_paths():
    """Нічого з того, чого немає на диску, у списку бути не може."""
    root = tempfile.mkdtemp(prefix='ukr-launch-')
    try:
        cfgdir = os.path.join(root, 'My Games', 'OpenMW')
        os.makedirs(cfgdir)
        cfg = os.path.join(cfgdir, 'openmw.cfg')
        write(cfg, 'resources="%s"\n' % os.path.join(root, 'нема', 'resources'))
        write(os.path.join(cfgdir, 'openmw.log'),
              '[10:42:40.752 I] Adding data directory %s\n'
              % os.path.join(root, 'теж-нема', 'resources', 'vfs'))
        got = install.engine_exes(cfg)
        bad = [p for p in got if not os.path.isfile(p)]
        check('неіснуючих шляхів у списку немає', not bad, '%r' % (bad,))
        mine = [p for p in got if os.path.normcase(root) in os.path.normcase(p)]
        check('із цих двох джерел нічого не взялося', not mine, '%r' % (mine,))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_start_engine_runs_from_its_own_dir():
    """Рушій запускаємо з його ж теки, інакше відносний resources не знайдеться.

    Самого рушія тут немає, тож підміняємо `subprocess.Popen` і дивимося, з
    чим його покликали. Запускати щось справжнє перевірці не можна.
    """
    import subprocess
    said = {}
    real = subprocess.Popen

    class Fake(object):
        def __init__(self, cmd, **kw):
            said['cmd'] = cmd
            said['cwd'] = kw.get('cwd')

    subprocess.Popen = Fake
    try:
        exe = os.path.join(tempfile.gettempdir(), 'OpenMW', 'openmw.exe')
        install.start_engine(exe)
    finally:
        subprocess.Popen = real

    check('запускаємо саме той exe', said.get('cmd') == [exe],
          'покликали %r' % (said.get('cmd'),))
    check('робоча тека - тека рушія',
          said.get('cwd') == os.path.dirname(exe),
          'вийшла %r' % (said.get('cwd'),))


test_log_wins()
test_resources_line()
test_relative_resources()
test_no_cfg_no_crash()
test_no_phantom_paths()
test_start_engine_runs_from_its_own_dir()
print()
print('перевірок упало: %d' % len(FAIL))
sys.exit(1 if FAIL else 0)
