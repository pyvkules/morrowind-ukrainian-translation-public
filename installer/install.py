# -*- coding: utf-8 -*-
"""Інсталятор українізатора: знайти гру, розпакувати переклад, зібрати, прописати.

Чому саме так, а не «розпакувати готові файли»
----------------------------------------------
Зібраний `Morrowind.esm` — це 80 МБ даних Bethesda з підміненим текстом. Носити
його в інсталяторі означало б роздавати гру. Тому в пакунку лежить **лише наш
переклад і патчер**, а латаємо ми файли, які вже є на машині гравця. Заразом це
знімає питання «а яка в нього версія»: беремо ту, що знайшли.

Що робимо
---------
1. шукаємо `openmw.cfg` — це і є опис того, яка гра і які моди стоять;
2. розпаковуємо переклад у теку модів поруч із ним;
3. запускаємо звичайну збірку (`build.py`) — вона читає **чисті** плагіни
   гравця й пише поруч наші копії з українським текстом;
4. дописуємо в `openmw.cfg` рядок `data=` **останнім** (виграє останній) і
   `encoding=win1251`, без якого рушій прочитає кирилицю як мотлох.

Оригінальний Morrowind.exe
--------------------------
Не підтримуємо, і мовчки вдавати, що працює, не будемо. Рушій 2002 року вантажить
растрові `.fnt`, а наш шрифт — TrueType із дорисованими Є І Ї Ґ. Гравець побачив
би порожні квадратики замість кожної української літери. Якщо знайдено лише його,
інсталятор так і каже.

    ukrainizer-setup.exe                  # знайти все саме
    ukrainizer-setup.exe --cfg <шлях>     # вказати openmw.cfg вручну
    ukrainizer-setup.exe --uninstall      # прибрати за собою
    ukrainizer-setup.exe --dry-run        # лише показати, що зробить
"""
import io
import json
import os
import runpy
import shutil
import sys
import time

def setup_console():
    """Консоль Windows за замовчуванням не в UTF-8, і українська стає мотлохом.

    Перемикаємо кодову сторінку виводу і перезагортаємо потоки. Якщо щось із
    цього недоступне (перенаправлений вивід, інша ОС) — просто працюємо далі.
    """
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:                      # noqa: BLE001 - не Windows або нема консолі
        pass
    for stream in ('stdout', 'stderr'):
        f = getattr(sys, stream, None)
        try:
            f.reconfigure(encoding='utf-8', errors='replace')
        except Exception:                  # noqa: BLE001 - старий Python або не файл
            if f is not None and hasattr(f, 'buffer'):
                setattr(sys, stream, io.TextIOWrapper(
                    f.buffer, encoding='utf-8', errors='replace',
                    line_buffering=True))


setup_console()

APP = 'Українізатор Morrowind'
MOD_DIR_NAME = 'morrowind-ukrainian-translation'
# Мітка «цю теку зробили ми». Без неї не можна безпечно чистити перед
# перевстановленням: користувач міг вказати теку, де лежить щось своє.
MARKER = '.ukrainizer'
ENCODING_LINE = 'encoding=win1251'

# Кроки збірки. Той самий список і порядок, що в build.py: patch_plugins читає
# чисті плагіни, а решта — вже наші копії, тож переставляти не можна.
#
# Шрифти йдуть двома кроками, бо різні збірки малюють інтерфейс різними: чиста
# OpenMW — своїм MysticCards, модпаки — Pelagiad. Патчимо той, що знайдено;
# код 3 означає «такого тут немає», і це не помилка.
SKIP_HAVE, SKIP_CANT, SKIP_NONE = 3, 4, 5   # уже є / нема з чого / нема файлу
SKIPS = (SKIP_HAVE, SKIP_CANT, SKIP_NONE)
# Даедричний шрифт лишається латиницею навмисно: у грі це руни, і кирилиці
# в них нема чого робити.
FONT_SKIP = ('demonicletters', 'daedric')
STEPS = [
    ('ядро',    'tools/rebuild_esm.py',           []),
    ('плагіни', 'tools/patch_plugins.py',         ['--apply']),
    ('назви',   'tools/patch_names.py',           ['--apply']),
    ('теми',    'tools/topics/rename_topics.py',  ['--apply']),
    ('інтерфейс', 'tools/gmst/patch_gmst.py',     ['--apply']),
    ('посилання', 'tools/topics/mark_topics.py',  ['--apply']),
]


# Куди йде вивід. У консолі - у stdout; у віконному режимі gui.py підмінює
# цей приймач на запис у поле журналу, і логіка встановлення про це не знає.
_sink = None


def out(msg=''):
    if _sink is not None:
        _sink(msg)
        return
    sys.stdout.write(msg + '\n')
    sys.stdout.flush()


def set_sink(fn):
    global _sink
    _sink = fn


# Сигнал про поступ: (ключ кроку, стан). Стан - 'run', 'ok', 'skip', 'fail'.
# Вікно малює з цього людські назви; консоль на це не зважає.
_progress = None


def set_progress(fn):
    global _progress
    _progress = fn


def step(key, state, note=None):
    """`note` — коротке число праворуч у рядку кроку; може бути None."""
    if _progress is not None:
        _progress(key, state, note)


def payload_root():
    """Тека з розпакованим вмістом: поруч із exe або сам каталог репозиторію."""
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, 'payload')
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def measure(root):
    """Порахувати переклад просто зараз — тим самим кодом, що й у релізі."""
    sys.path.insert(0, os.path.join(root, 'tools'))
    try:
        import stats
    except ImportError:
        return {}
    vd, vt, md, mt = stats.count()
    td, tt = stats.topics()
    return {'vanilla': [vd, vt], 'topics': [td, tt],
            'names': stats.names(), 'mods': [md, mt]}


_BUILD = None


def build_info():
    """Версія збірки й стан перекладу.

    `make.py` кладе це у `payload/build.json` під час збірки, бо перерахунок
    усіх зрізів — секунди, і платити їх щоразу при відкритті вікна нема за що.
    Коли запускаємося з репозиторію, файлу немає: рахуємо на місці, там пауза
    не заважає. Так число в шапці не може розійтися з тим, що всередині.
    """
    global _BUILD
    if _BUILD is None:
        try:
            with io.open(os.path.join(payload_root(), 'build.json'),
                         encoding='utf-8') as f:
                _BUILD = json.load(f)
        except (OSError, ValueError):
            _BUILD = measure(payload_root())
    return _BUILD


def version_line():
    """Рядок для шапки вікна й для звіту про помилку.

    Два числа, а не одне: базова гра перекладена повністю, моди — ні, і
    самотнє «100%» читалося б як «усе готово».
    """
    b = build_info()
    ver = b.get('version') or 'з репозиторію'
    parts = [ver]
    for label, key in (('гра', 'vanilla'), ('моди', 'mods')):
        done, total = (b.get(key) or [0, 0])[:2]
        if total:
            parts.append('%s %d%%' % (label, 100 * done // total))
    return ' \u00b7 '.join(parts)


def arg(flag, default=None):
    for i, a in enumerate(sys.argv):
        if a == flag and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


# --- пошук гри ---------------------------------------------------------------

def cfg_candidates():
    """Де зазвичай лежить openmw.cfg, від найімовірнішого."""
    seen, found = set(), []
    home = os.path.expanduser('~')
    roots = [
        os.path.join(home, 'Documents', 'My Games', 'OpenMW'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'openmw'),
        os.path.join(os.environ.get('APPDATA', ''), 'openmw'),
    ]
    for root in roots:
        p = os.path.join(root, 'openmw.cfg')
        if os.path.isfile(p) and p.lower() not in seen:
            seen.add(p.lower())
            found.append(p)
    # momw-configurator тримає по теці на модліст поруч із рушієм; там і профілі
    for exe in openmw_exes():
        base = os.path.dirname(exe)
        for sub in [base] + [os.path.join(base, d) for d in safe_listdir(base)]:
            p = os.path.join(sub, 'openmw.cfg')
            if os.path.isfile(p) and p.lower() not in seen:
                seen.add(p.lower())
                found.append(p)
    return found


def safe_listdir(path):
    try:
        return [d for d in os.listdir(path)
                if os.path.isdir(os.path.join(path, d))]
    except OSError:
        return []


def openmw_exes():
    """Де може стояти сам рушій."""
    out_ = []
    roots = []
    for var in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA'):
        v = os.environ.get(var)
        if v:
            roots += [os.path.join(v, 'OpenMW'), os.path.join(v, 'openmw')]
    for drive in 'CDEFGH':
        roots += [r'%s:\Morrowind\OpenMW' % drive, r'%s:\OpenMW' % drive,
                  r'%s:\Games\OpenMW' % drive]
    for r in roots:
        p = os.path.join(r, 'openmw.exe')
        if os.path.isfile(p):
            out_.append(p)
    return out_


def morrowind_exes():
    """Оригінальний рушій — шукаємо, щоб пояснити, чому не підтримуємо."""
    out_ = []
    for drive in 'CDEFGH':
        for p in (r'%s:\SteamLibrary\steamapps\common\Morrowind\Morrowind.exe' % drive,
                  r'%s:\Program Files (x86)\Steam\steamapps\common\Morrowind\Morrowind.exe' % drive,
                  r'%s:\Games\Morrowind\Morrowind.exe' % drive,
                  r'%s:\Morrowind\Morrowind.exe' % drive):
            if os.path.isfile(p):
                out_.append(p)
    return out_


def engine_font_dirs(cfg_path, lines):
    """Де лежать шрифти самого рушія.

    Іти вгору від конфігурації не можна: типово вона в «Documents\My Games»,
    а рушій — у Program Files. Тому беремо `resources=` з конфігурації, а як
    його немає — теки, де знайшовся openmw.exe.
    """
    dirs = []
    for ln in lines:
        t = ln.strip()
        if t.startswith('resources='):
            d = t[len('resources='):].strip().strip('"')
            if not os.path.isabs(d):
                d = os.path.join(os.path.dirname(cfg_path), d)
            dirs.append(os.path.join(d, 'vfs', 'fonts'))
    for exe in openmw_exes():
        dirs.append(os.path.join(os.path.dirname(exe), 'resources', 'vfs', 'fonts'))
    return [d for d in dirs if os.path.isdir(d)]


def font_steps(cfg_path, lines):
    """По кроку на кожен шрифт, який гра може малювати.

    Двох імен не досить: модпаки вживають і Pelagiad, і OMWAyembedt, а чиста
    OpenMW — свій MysticCards. Якщо пропустити той, що гра насправді вантажить,
    гравець побачить порожні квадратики замість кожної української літери. Тому
    беремо **всі** .ttf з тек модліста й ресурсів рушія; ті, що вже мають
    кирилицю, patch_font пропустить сам.

    Порядок той самий, що у VFS: пізніша тека перекриває ранішу, тож для
    однойменних шрифтів лишаємо останній.
    """
    dirs = engine_font_dirs(cfg_path, lines)
    for d in data_dirs(lines, cfg_path):
        cand = os.path.join(d, 'fonts')
        if os.path.isdir(cand):
            dirs.append(cand)

    found = {}
    for d in dirs:
        try:
            entries = os.listdir(d)
        except OSError:
            continue
        for e in entries:
            if not e.lower().endswith('.ttf'):
                continue
            name = e[:-4]
            if name.lower() in FONT_SKIP:
                continue
            found[name.lower()] = (name, os.path.join(d, e))

    return [('шрифт', 'tools/patch_font.py', ['--font', name, '--src', path])
            for name, path in sorted(found.values())]


def read_cfg(path):
    with io.open(path, encoding='utf-8', errors='replace') as f:
        return f.read().splitlines()


def data_dirs(lines, cfg_path):
    dirs = []
    for ln in lines:
        s = ln.strip()
        if s.startswith('data='):
            d = s[5:].strip().strip('"')
            if not os.path.isabs(d):
                d = os.path.join(os.path.dirname(cfg_path), d)
            dirs.append(d)
    return dirs


def find_master(dirs):
    for d in dirs:
        p = os.path.join(d, 'Morrowind.esm')
        if os.path.isfile(p):
            return p
    return None


# --- правка openmw.cfg -------------------------------------------------------

def rewrite_cfg(cfg_path, mod_dir, remove=False):
    """Прописати (або прибрати) нашу теку і кодування. Повертає, що змінилось."""
    lines = read_cfg(cfg_path)
    target = os.path.normcase(os.path.abspath(mod_dir))
    kept, changed = [], []
    for ln in lines:
        s = ln.strip()
        if s.startswith('data='):
            d = s[5:].strip().strip('"')
            if not os.path.isabs(d):
                d = os.path.join(os.path.dirname(cfg_path), d)
            if os.path.normcase(os.path.abspath(d)) == target:
                changed.append('прибрано старий запис data=')
                continue          # приберемо, щоб потім дописати останнім
        kept.append(ln)

    if not remove:
        if not any(l.strip().startswith('encoding=') for l in kept):
            # без цього рушій читає cp1251 як win1252 і кирилиця стає мотлохом
            kept.insert(0, ENCODING_LINE)
            changed.append('додано ' + ENCODING_LINE)
        else:
            for i, l in enumerate(kept):
                if l.strip().startswith('encoding=') and l.strip() != ENCODING_LINE:
                    kept[i] = ENCODING_LINE
                    changed.append('виправлено encoding на win1251')
        # У лапках завжди: типовий шлях містить «My Games», а без лапок
        # OpenMW обріже його по пробілу.
        kept.append('data="%s"' % mod_dir)     # останній виграє
        changed.append('дописано data= останнім рядком')

    backup = cfg_path + '.ukr-backup'
    if not os.path.exists(backup):
        shutil.copy2(cfg_path, backup)
        changed.append('збережено копію ' + os.path.basename(backup))
    with io.open(cfg_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(kept) + '\n')
    return changed


# --- збірка ------------------------------------------------------------------

class _KeepOpen(io.BytesIO):
    """Буфер, який не дає себе закрити.

    Кожен крок загортає наш потік у власний `TextIOWrapper`, а той, коли його
    збирає смітник, закриває буфер під собою. Нам той буфер ще потрібен —
    інакше читання виводу падає з «I/O operation on closed file».
    """

    def close(self):
        pass


class Capture(io.TextIOWrapper):
    """Перехопити вивід кроку, не ламаючи його власне загортання.

    Кожен наш скрипт першою дією робить `io.TextIOWrapper(sys.stdout.buffer)`,
    щоб писати українською. Тому підмінити stdout на StringIO не можна - у неї
    немає `.buffer`. Загортаємо BytesIO: `.buffer` у нього є.
    """

    def __init__(self):
        self._raw = _KeepOpen()
        super().__init__(self._raw, encoding='utf-8', errors='replace',
                         write_through=True)

    def text(self):
        try:
            self.flush()
        except ValueError:                 # крок міг закрити обгортку
            pass
        return self._raw.getvalue().decode('utf-8', 'replace')


def run_steps(mod_dir, steps):
    """Запустити кроки збірки в цьому ж процесі.

    Заморожений exe не є інтерпретатором Python, тож `subprocess` із
    `sys.executable`, як у build.py, тут не працює. Виконуємо скрипти
    через runpy, підмінивши argv.
    """
    ok = True
    results = {}
    saved_argv, saved_cwd, saved_stdout = sys.argv[:], os.getcwd(), sys.stdout
    os.chdir(mod_dir)
    if mod_dir not in sys.path:
        sys.path.insert(0, mod_dir)
    tools = os.path.join(mod_dir, 'tools')
    if tools not in sys.path:
        sys.path.insert(0, tools)
    for label, rel, extra in steps:
        script = os.path.join(mod_dir, rel.replace('/', os.sep))
        name = os.path.basename(rel)
        t0 = time.time()
        step(label, 'run')
        sys.argv = [script] + extra
        buf = Capture()
        try:
            sys.stdout = buf
            runpy.run_path(script, run_name='__main__')
            code = 0
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else (0 if not e.code else 1)
        except Exception as e:                       # noqa: BLE001 - показуємо гравцю
            code = 1
            buf.write('%s: %s\n' % (type(e).__name__, e))
        finally:
            sys.stdout = saved_stdout
        mark = {0: 'ок  ', SKIP_HAVE: 'вже ', SKIP_CANT: 'нема',
                SKIP_NONE: 'нема'}.get(code, 'ЗБІЙ')
        out('  %-11s %-26s %s  %4.1f с'
            % (label, name, mark, time.time() - t0))
        step(label, {0: 'ok'}.get(code, 'skip')
             if code in (0,) + SKIPS else 'fail')
        results[rel + ' '.join(extra)] = code
        if code not in (0,) + SKIPS:
            ok = False
            for ln in buf.text().splitlines()[-12:]:
                out('      ' + ln)
            break
    sys.argv = saved_argv
    os.chdir(saved_cwd)
    return ok, results


# --- головне -----------------------------------------------------------------

def pick_cfg():
    explicit = arg('--cfg')
    if explicit:
        if not os.path.isfile(explicit):
            out('Не бачу файлу: %s' % explicit)
            return None
        return explicit
    found = cfg_candidates()
    if not found:
        return None
    if len(found) == 1:
        return found[0]
    out('Знайдено кілька конфігурацій OpenMW:')
    for i, p in enumerate(found, 1):
        out('  %d) %s' % (i, p))
    while True:
        try:
            choice = input('Котру брати? [1] ').strip() or '1'
        except EOFError:
            return found[0]
        if choice.isdigit() and 1 <= int(choice) <= len(found):
            return found[int(choice) - 1]


# Що саме їде в пакунку. Явний список, а не «усе, крім»: у теці репозиторію
# поруч із джерелами лежать 76 зібраних плагінів модпака - це і 340 зайвих МБ,
# і роздача чужого вмісту разом із даними Bethesda.
PAYLOAD_DIRS = ('tools', 'l10n', 'Fonts', 'Textures', 'recipe')
PAYLOAD_FILES = ('build.py', 'README.md')
SKIP_NAMES = {'base.esm', '__pycache__', '.git', 'installer'}
# .ttf не возимо: Pelagiad має ліцензію SIL OFL із зарезервованою назвою, тож
# змінений файл роздавати не можна. Патчимо шрифт гравця на його ж машині.
SKIP_EXT = ('.pyc', '.bak', '.ttf')
# Ці два — англійські тексти самої гри (сира вигрузка реплік і проза книг).
# .gitignore тримає їх поза репозиторієм саме тому, що це чуже; жоден крок
# збірки їх не читає, тож і в пакунку їм робити нічого.
SKIP_REL = {os.path.join('tools', 'corpus.json'),
            os.path.join('tools', 'books', '_source.json')}


def copy_payload(src, dst, allow=None):
    """Скопіювати джерела перекладу. `allow` — набір дозволених шляхів.

    Під час пакування туди йде список git: саме він проводить межу між нашим
    і чужим. На машині гравця фільтрувати вже нічого — у пакунку лежить готове.
    """
    def ok(rel):
        return allow is None or os.path.normcase(os.path.normpath(rel)) in allow

    n = 0
    for name in PAYLOAD_FILES:
        p = os.path.join(src, name)
        if os.path.isfile(p) and ok(name):
            os.makedirs(dst, exist_ok=True)
            shutil.copy2(p, os.path.join(dst, name))
            n += 1
    for top in PAYLOAD_DIRS:
        root_src = os.path.join(src, top)
        if not os.path.isdir(root_src):
            continue
        for root, dirs, files in os.walk(root_src):
            dirs[:] = [d for d in dirs if d not in SKIP_NAMES]
            rel = os.path.relpath(root, src)
            target = os.path.join(dst, rel)
            os.makedirs(target, exist_ok=True)
            for f in files:
                if f in SKIP_NAMES or f.endswith(SKIP_EXT):
                    continue
                if os.path.join(rel, f) in SKIP_REL or not ok(os.path.join(rel, f)):
                    continue
                shutil.copy2(os.path.join(root, f), os.path.join(target, f))
                n += 1
    return n


def describe(cfg):
    """Що ми знайшли за цією конфігурацією: гру, теки, куди ставитимемо."""
    lines = read_cfg(cfg)
    dirs = data_dirs(lines, cfg)
    master = find_master(dirs)
    mod_dir = os.path.join(os.path.dirname(cfg), 'mods', MOD_DIR_NAME)
    return lines, dirs, master, mod_dir


def why_no_openmw():
    """Текст пояснення, коли OpenMW немає. Однаковий у консолі й у вікні."""
    mw = morrowind_exes()
    if mw:
        found = ['OpenMW не знайдено, зате знайдено оригінальний Morrowind:']
        found += ['    ' + p for p in mw]
        found += [
            '',
            'На рушії 2002 року переклад не запрацює: він малює інтерфейс',
            'растровими шрифтами .fnt, а українські літери ми дорисовуємо',
            'в TrueType. Замість тексту були б порожні квадратики.',
            '',
            'Постав OpenMW — він читає ту саму гру, нічого',
            'перевстановлювати не треба.',
        ]
        return chr(10).join(found)
    return chr(10).join([
        'OpenMW не знайдено, і гри теж не видно.',
        '',
        'Якщо OpenMW стоїть у незвичному місці, вкажи його openmw.cfg',
        'вручну.',
    ])

def game_data_dir():
    """Тека Data Files знайденої гри — те, що потрібно новому OpenMW."""
    for exe in morrowind_exes():
        d = os.path.join(os.path.dirname(exe), 'Data Files')
        if os.path.isfile(os.path.join(d, 'Morrowind.esm')):
            return d
    return None


def install_engine():
    """Завантажити й поставити OpenMW, тоді налаштувати його під знайдену гру.

    Повертає шлях до створеного openmw.cfg або None. Потрібне лише тоді, коли
    OpenMW у людини ще немає: наявний ми не чіпаємо.
    """
    import engine

    data = game_data_dir()
    if not data:
        out('Не знайшов саму гру — нема що налаштовувати.')
        out('Купи й постав Morrowind (Steam або GOG), тоді запусти ще раз.')
        return None

    out('Гра: %s' % data)
    step('рушій', 'run')
    try:
        name, url, size, tag = engine.latest_windows_build()
    except Exception as e:                     # noqa: BLE001 - мережа
        out('Не вдалося спитати GitHub про OpenMW: %s' % e)
        step('рушій', 'fail')
        return None

    out('Завантажую OpenMW %s (%.0f МБ)...' % (tag.replace('openmw-', ''),
                                               size / 1048576.0))
    tmp = os.path.join(os.environ.get('TEMP', '.'), name)
    try:
        engine.download(url, tmp, size,
                        lambda p: out('  %d%%' % p) if p % 20 == 0 else None)
    except Exception as e:                     # noqa: BLE001 - мережа
        out('Завантаження не вдалося: %s' % e)
        step('рушій', 'fail')
        return None

    target = os.path.join(os.environ.get('PROGRAMFILES', r'C:\Program Files'),
                          'OpenMW')
    out('Ставлю у %s' % target)
    out('Windows зараз запитає дозвіл — це звичайне встановлення програми.')
    try:
        code = engine.silent_install(tmp, target)
    except PermissionError as e:
        out('OpenMW не встановлено: %s' % e)
        step('рушій', 'fail')
        return None
    if code != 0:
        out('Встановлення повернуло код %s' % code)

    exe = engine.find_engine(target)
    if not exe:
        out('Не бачу openmw.exe після встановлення.')
        step('рушій', 'fail')
        return None
    out('Рушій: %s' % exe)

    cfg = os.path.join(os.path.expanduser('~'), 'Documents', 'My Games',
                       'OpenMW', 'openmw.cfg')
    engine.bootstrap_config(exe, data, cfg, on_line=lambda m: out('  ' + m))
    out('Налаштування: %s' % cfg)
    step('рушій', 'ok')
    return cfg


def install_modlist(cfg):
    """Поставити модліст автора й відтворити його профіль.

    Найдовший крок: моди важать десятки гігабайтів, і тягне їх `umo` — рідний
    завантажувач Modding-OpenMW. Ми лише кажемо йому, які списки потрібні, а
    тоді складаємо профіль із рецепта.
    """
    import mods as modlist

    step('моди', 'run')
    tools = modlist.find_tools()
    if not tools:
        out('Не знайшов інструментів Modding-OpenMW (umo, momw-configurator).')
        out('Візьми momw-tools-pack тут і поклади поруч із цим файлом:')
        out('  ' + modlist.SITE)
        step('моди', 'fail')
        return 1
    out('Інструменти: %s' % tools)

    lists = modlist.wanted_lists(payload_root())
    if not lists:
        out('У пакунку немає рецепта модліста.')
        step('моди', 'fail')
        return 1
    out('Списки: %s' % ', '.join(lists))

    mods_dir = modlist.umo_dirs(tools)
    if not mods_dir:
        out('umo не сказав, куди складає моди. Запусти `umo reconfig`.')
        step('моди', 'fail')
        return 1
    out('Моди підуть у %s' % mods_dir)

    if not modlist.install_lists(tools, lists, out):
        step('моди', 'fail')
        return 1

    _, _, master, _ = describe(cfg)
    game = os.path.dirname(master) if master else game_data_dir()
    if not game:
        out('Не знайшов теки гри.')
        step('моди', 'fail')
        return 1

    if not modlist.write_profile(payload_root(), cfg, mods_dir, game, out):
        step('моди', 'fail')
        return 1
    step('моди', 'ok')
    return 0


def uninstall_from(cfg):
    lines, dirs, master, mod_dir = describe(cfg)
    for note in rewrite_cfg(cfg, mod_dir, remove=True):
        out('  ' + note)
    if os.path.isfile(os.path.join(mod_dir, MARKER)):
        shutil.rmtree(mod_dir, ignore_errors=True)
        out('  вилучено теку перекладу')
    elif os.path.isdir(mod_dir):
        out('  теку лишено: немає нашої мітки, могло бути не наше')
    out()
    out('Готово. Гра знову англійською.')
    return 0


def install_to(cfg):
    lines, dirs, master, mod_dir = describe(cfg)
    if not master:
        out('У цій конфігурації немає Morrowind.esm — нема чого перекладати.')
        out('Спершу пройди майстер налаштування OpenMW і вкажи йому гру.')
        return 2

    # Прибираємо попередню версію: інакше файл-тінь, якого вже немає в новій
    # збірці, лишиться в теці й далі перекриватиме справжній плагін мода.
    if os.path.isfile(os.path.join(mod_dir, MARKER)):
        shutil.rmtree(mod_dir, ignore_errors=True)
        out('Прибрано попередню версію.')
    elif os.path.isdir(mod_dir) and os.listdir(mod_dir):
        out('У теці вже щось є, а мітки нашої немає — не чіпаю її.')
        out('  %s' % mod_dir)
        return 1

    out('Розпаковую переклад...')
    os.makedirs(mod_dir, exist_ok=True)
    io.open(os.path.join(mod_dir, MARKER), 'w', encoding='utf-8').write(APP)
    n = copy_payload(payload_root(), mod_dir)
    out('  файлів: %d' % n)

    # звідси наші скрипти знають, який модліст читати
    with io.open(os.path.join(mod_dir, 'config.json'), 'w', encoding='utf-8') as f:
        json.dump({'openmw_cfg': cfg}, f, ensure_ascii=False, indent=1)

    out()
    out('Збираю (це кілька хвилин — патчимо твої власні файли):')
    fonts = font_steps(cfg, lines)
    built, results = run_steps(mod_dir, fonts + STEPS)
    if not built:
        out()
        out('Збірка не вдалася. Гру не чіпали: рядок data= не дописано.')
        return 1

    # Який шрифт гра малює насправді, знає тільки вона. Тому кажемо прямо, що
    # вдалося, а що ні: якщо непропатченим лишився саме той, гравець побачить
    # порожні квадратики, і краще, щоб він знав, про що писати.
    fdir = os.path.join(mod_dir, 'Fonts')
    done = {f[:-4].lower() for f in (os.listdir(fdir) if os.path.isdir(fdir) else [])
            if f.lower().endswith('.ttf')}
    asked = [step[2][1] for step in fonts]
    codes = {step[2][1]: results.get(step[1] + ' '.join(step[2]))
             for step in fonts}
    left = [x for x in asked
            if x.lower() not in done and codes.get(x) != SKIP_HAVE]
    if done:
        out()
        out('Шрифти з українськими літерами: %s'
            % ', '.join(sorted(x for x in asked if x.lower() in done)))
    if left:
        out('Без кирилиці, використати не вийде: %s' % ', '.join(left))
    if not done:
        out()
        out('! УВАГА: не вдалося пропатчити жодного шрифту.')
        out('! Гра буде українською, але замість літер будуть порожні місця.')
        out('! Напиши про це автору перекладу разом із цим виводом.')

    out()
    out('Прописую в openmw.cfg:')
    for note in rewrite_cfg(cfg, mod_dir):
        out('  ' + note)
    return 0


def main():
    out('=' * 62)
    out(' %s' % APP)
    out(' %s' % version_line())
    out('=' * 62)
    out()

    dry = '--dry-run' in sys.argv
    cfg = pick_cfg()
    if not cfg:
        out(why_no_openmw())
        return 2

    lines, dirs, master, mod_dir = describe(cfg)
    out('Конфігурація OpenMW : %s' % cfg)
    out('Гра                 : %s' % (master or 'не знайдено'))
    out('Тек із даними       : %d' % len(dirs))
    out('Ставимо у           : %s' % mod_dir)
    out()

    if '--uninstall' in sys.argv:
        if dry:
            out('(пробний запуск) прибрав би теку і рядок data=')
            return 0
        return uninstall_from(cfg)

    if dry:
        out('(пробний запуск) розпакував би переклад, зібрав і прописав data=')
        return 0

    code = install_to(cfg)
    if code:
        return code

    out()
    out('=' * 62)
    out(' Готово. Запускай OpenMW як звичайно.')
    out('=' * 62)
    out()
    out('Переклад працює тим, що його тека стоїть **останньою** в списку —')
    out('виграє останній. Якщо відкриєш лаунчер OpenMW і переставиш теки на')
    out('вкладці Data Files, гра знову стане англійською. Тоді просто запусти')
    out('цей файл ще раз.')
    out()
    out('Щоб відкотити: ukrainizer-setup.exe --uninstall')
    return 0


# Аргументи, що означають «працюємо в консолі». Без жодного з них людина,
# найпевніше, просто двічі клацнула файл — тоді відкриваємо вікно.
CLI_FLAGS = ('--cfg', '--uninstall', '--dry-run', '--no-pause', '--console')


if __name__ == '__main__':
    if not any(a in CLI_FLAGS or a.startswith('--cfg=') for a in sys.argv[1:]):
        import gui
        sys.exit(gui.run())
    try:
        code = main()
    except KeyboardInterrupt:
        out('\nПерервано.')
        code = 130
    if sys.stdout.isatty() and '--no-pause' not in sys.argv:
        try:
            input('\nНатисни Enter, щоб закрити...')
        except EOFError:
            pass
    sys.exit(code)
