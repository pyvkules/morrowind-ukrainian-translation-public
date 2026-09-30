# -*- coding: utf-8 -*-
"""Поставити модліст автора й відтворити його профіль.

Як це працює
------------
«Мій модліст» — не офіційний список: профіль зібраний із чотирьох одразу
(`total-overhaul`, `expanded-vanilla`, `just-good-morrowind`,
`i-heart-vanilla`) плюс власний порядок завантаження на 327 рядків. Тому:

1. самі моди тягне `umo` — рідний завантажувач Modding-OpenMW. Він уміє
   реєструватися обробником посилань `nxm://`, тож із преміумом на Nexus качає
   сам, а без нього відкриває сторінки по черзі;
2. профіль складаємо з рецепта (`recipe/profile.cfg`), підставивши шляхи цієї
   машини замість міток `{МОДИ}` і `{ГРА}`.

Чого ми НЕ робимо
-----------------
Не качаємо самі моди й не возимо їх: це чужі файли з Nexus, і роздавати їх не
можна. Не качаємо й самі інструменти MOMW — сталої адреси в них немає, а
вгадана адреса тихо зламається. Якщо інструментів немає, кажемо, звідки взяти.
"""
import io
import os
import re
import subprocess
import threading
import time

TOOLS = ('umo.exe', 'momw-configurator.exe')
SITE = 'https://modding-openmw.com/tools/'
HERE = os.path.dirname(os.path.abspath(__file__))


def recipe_dir(payload_root):
    return os.path.join(payload_root, 'recipe')


def wanted_lists(payload_root):
    p = os.path.join(recipe_dir(payload_root), 'lists.txt')
    if not os.path.isfile(p):
        return []
    return [l.strip() for l in io.open(p, encoding='utf-8') if l.strip()]


def find_tools():
    """Де лежить momw-tools-pack. Повертає теку або None."""
    seen = []
    for base in (os.path.dirname(HERE), os.getcwd(),
                 os.path.expanduser('~'), r'C:\games', r'E:\Morrowind'):
        seen.append(base)
        for sub in ('', 'momw-tools-pack-windows', 'momw-tools-pack',
                    'tools', 'Downloads'):
            d = os.path.join(base, sub) if sub else base
            if all(os.path.isfile(os.path.join(d, t)) for t in TOOLS):
                return d
    for drive in 'CDEFGH':
        d = r'%s:\momw-tools-pack-windows' % drive
        if all(os.path.isfile(os.path.join(d, t)) for t in TOOLS):
            return d
    return None


def umo_dirs(tools):
    """Куди umo складає моди — питаємо його самого, а не вгадуємо."""
    try:
        r = subprocess.run([os.path.join(tools, 'umo.exe'), 'info'],
                           capture_output=True, text=True, timeout=180,
                           encoding='utf-8', errors='replace')
    except (OSError, subprocess.SubprocessError):
        return None
    # `umo info` друкує рядок «basepath dir: <шлях>» — саме туди він і
    # складає моди. У різних людей тека різна, тож питаємо, а не гадаємо.
    for line in (r.stdout or '').splitlines():
        if 'basepath' in line.lower() and ':' in line:
            path = line.split(':', 1)[1].strip()
            if len(path) > 2 and path[1] == ':':
                return path
    return None


# Рамки й кольори rich: у журналі з них користі немає.
ANSI = re.compile(r'\x1b\[[0-9;?]*[ -/]*[@-~]')
FRAME = re.compile('[\u2500-\u257f]+')
ESCAPED = re.compile(r'\\u([0-9a-fA-F]{4})')
NO_WINDOW = 0x08000000        # CREATE_NO_WINDOW: чорне вікно консолі не треба


def unescape(s):
    """Повернути на місце символи, які rich віддав шістьма літерами.

    Коли вивід перенаправлено, rich на Windows пише непередавані символи
    звичайним текстом. Без цього рамки лишилися б у журналі як мотлох.
    """
    return ESCAPED.sub(lambda m: chr(int(m.group(1), 16)), s)


def tidy(raw):
    """Один рядок від umo у вигляді, придатному для журналу."""
    s = ' '.join(FRAME.sub(' ', unescape(ANSI.sub('', raw))).split())
    if not s:
        return ''
    return s if len(s) <= 150 else s[:147] + '...'


def expected_dirs(payload_root, mods_dir):
    """Теки модів, які мають з'явитися. Саме по них рахуємо поступ."""
    src = os.path.join(recipe_dir(payload_root), 'profile.cfg')
    if not os.path.isfile(src):
        return []
    base = mods_dir.rstrip('\\')
    found = []
    for line in io.open(src, encoding='utf-8'):
        s = line.strip()
        if s.startswith('data=') and '{МОДИ}' in s:
            found.append(s[5:].strip().strip('"').replace('{МОДИ}', base))
    return found


class Counter(object):
    """Скільки тек модів уже на місці.

    umo друкує назви й відсотки, але скільки лишилося, з того не видно.
    Зате видно з самого диска: у рецепті перелічені всі теки профілю, і ми
    просто дивимося, скільки їх уже є. Раз на кілька секунд, окремою ниткою.
    """

    def __init__(self, dirs, on_count, every=4.0):
        self.dirs = list(dirs)
        self.on_count = on_count
        self.every = every
        self.stop = threading.Event()
        self.thread = None
        self.have = 0

    def count(self):
        return sum(1 for d in self.dirs if os.path.isdir(d))

    def tell(self):
        self.have = self.count()
        self.on_count(self.have, len(self.dirs))

    def run(self):
        while not self.stop.wait(self.every):
            was = self.have
            self.have = self.count()
            if self.have != was:
                self.on_count(self.have, len(self.dirs))

    def __enter__(self):
        if self.dirs:
            self.tell()
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=self.every + 1)
        if self.dirs and self.count() != self.have:
            self.tell()
        return False


def run_umo(cmd, on_line):
    """Пустити umo й переказувати кожен його рядок у журнал.

    Читаємо сирі байти, бо поступ завантаження приходить із поверненням
    каретки, а не з новим рядком: чекати на переведення рядка означало б
    мовчати хвилинами. Ділимо по обох, а однакові рядки поспіль відкидаємо.
    """
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         bufsize=0, creationflags=NO_WINDOW)
    buf = b''
    last = ''
    try:
        while True:
            chunk = p.stdout.read(4096)
            if not chunk:
                break
            buf += chunk
            parts = re.split(b'[\r\n]', buf)
            buf = parts.pop()
            for part in parts:
                line = tidy(part.decode('utf-8', 'replace'))
                if line and line != last:
                    last = line
                    on_line('  ' + line)
    finally:
        p.stdout.close()
        p.wait()
    line = tidy(buf.decode('utf-8', 'replace'))
    if line and line != last:
        on_line('  ' + line)
    return p.returncode


def hhmm(seconds):
    m = int(seconds) // 60
    return '%d хв' % m if m < 60 else '%d год %d хв' % (m // 60, m % 60)


def install_lists(tools, lists, on_line, expected=(), on_count=None):
    """Провести `umo install` по кожному списку. Це найдовша частина.

    Моди важать десятки гігабайтів, тож людина сидить перед вікном довго.
    Тому показуємо і те, що каже umo, і те, скільки тек уже на місці.
    """
    umo = os.path.join(tools, 'umo.exe')
    began = time.time()

    said = [-1]

    def report(have, total):
        if on_count:
            on_count(have, total)
        if have < said[0] + max(5, total // 40) and have != total:
            return
        said[0] = have
        share = 100.0 * have / total if total else 0
        on_line('Готово %d тек із %d (%d%%), минуло %s'
                % (have, total, share, hhmm(time.time() - began)))

    with Counter(expected, report):
        for n, name in enumerate(lists, 1):
            on_line('')
            on_line('Список %d з %d: %s' % (n, len(lists), name))
            code = run_umo([umo, 'install', name], on_line)
            if code != 0:
                on_line('umo повернув %d на списку «%s»' % (code, name))
                return False
    on_line('Усі списки завантажено за %s.' % hhmm(time.time() - began))
    return True


def write_profile(payload_root, cfg_path, mods_dir, game_dir, on_line):
    """Скласти openmw.cfg із рецепта, підставивши шляхи цієї машини."""
    src = os.path.join(recipe_dir(payload_root), 'profile.cfg')
    if not os.path.isfile(src):
        on_line('Рецепта профілю немає — нічого відтворювати.')
        return False
    text = io.open(src, encoding='utf-8').read()
    text = text.replace('{МОДИ}', mods_dir.rstrip('\\')) \
               .replace('{ГРА}', game_dir.rstrip('\\'))

    missing = 0
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('data='):
            d = s[5:].strip().strip('"')
            if not os.path.isdir(d):
                missing += 1
    if missing:
        on_line('Увага: %d тек із профілю ще немає — якісь моди не '
                'завантажилися.' % missing)

    if os.path.isfile(cfg_path):
        backup = cfg_path + '.before-modlist'
        if not os.path.exists(backup):
            io.open(backup, 'w', encoding='utf-8').write(
                io.open(cfg_path, encoding='utf-8', errors='replace').read())
            on_line('стару конфігурацію збережено як %s'
                    % os.path.basename(backup))
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
    io.open(cfg_path, 'w', encoding='utf-8', newline='\n').write(text)
    on_line('профіль записано: %s' % cfg_path)
    return True
