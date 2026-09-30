# -*- coding: utf-8 -*-
"""Поставити моди з профілю автора й відтворити сам профіль.

Як це працює
------------
Профіль `just-good-morrowind-plus` зібраний із чотирьох офіційних наборів
Modding-OpenMW плюс власний порядок завантаження на 327 рядків. Разом ті
чотири набори містять понад тисячу модів, а профіль бере чотириста, тож
решту качати немає навіщо: у гру вона однаково не потрапить.

1. `umo sync` бере опис набору з modding-openmw.com;
2. `umo install --subset` качає з нього саме ті моди, що стоять у профілі.
   Перелік беремо з самого рецепта: кожен рядок `data=` називає свій мод;
3. профіль складаємо з рецепта (`recipe/profile.cfg`), підставивши шляхи
   цієї машини замість міток `{МОДИ}` і `{ГРА}`.

Чого ми НЕ робимо
-----------------
Не качаємо самі моди й не возимо їх: це чужі файли з Nexus, і роздавати їх
не можна. А от самі інструменти MOMW качаємо: GitLab віддає їхню збірку за
сталою адресою свого API, тож людині нічого шукати руками.
"""
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.request
import zipfile

TOOLS = ('umo.exe', 'momw-configurator.exe')
SITE = 'https://modding-openmw.com/tools/'
HERE = os.path.dirname(os.path.abspath(__file__))
MODS = '{МОДИ}'

# Збірку інструментів складає CI GitLab, і лежить вона артефактом завдання.
# Адреса стала: це API, а не сторінка, яку перемалюють.
PACK_API = ('https://gitlab.com/api/v4/projects/'
            'modding-openmw%2Fmomw-tools-pack')
PACK_JOB = '/jobs/artifacts/%s/raw/momw-tools-pack-windows.zip?job=make'
PACK_HOME = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')),
                         'Programs', 'momw-tools-pack-windows')


def recipe_dir(payload_root):
    return os.path.join(payload_root, 'recipe')


def profile_mods(payload_root):
    """Які моди бере профіль: набір -> теки модів.

    Шлях у рецепті має вигляд {МОДИ}\\<набір>\\<категорія>\\<мод>, іноді з
    підтекою. Перші три частини й кажуть, що саме качати.
    """
    src = os.path.join(recipe_dir(payload_root), 'profile.cfg')
    need = {}
    if not os.path.isfile(src):
        return need
    for line in io.open(src, encoding='utf-8'):
        s = line.strip()
        if not (s.startswith('data=') and MODS in s):
            continue
        parts = [p for p in s.split(MODS, 1)[1].strip('"').split('\\') if p]
        # MOMWToolsPack на Nexus немає: цю теку наповнюють інструменти,
        # і просити її в umo означало б шукати те, чого не існує.
        if len(parts) >= 3 and parts[2] != 'MOMWToolsPack':
            need.setdefault(parts[0], set()).add((parts[1], parts[2]))
    return need


def skip_mods(payload_root):
    """Моди, які причепилися б за збігом назв. Їх складає make_recipe.py."""
    p = os.path.join(recipe_dir(payload_root), 'skip.txt')
    out = {}
    if not os.path.isfile(p):
        return out
    for line in io.open(p, encoding='utf-8'):
        if '\t' in line:
            name, mod = line.rstrip('\n').split('\t', 1)
            out.setdefault(name, []).append(mod)
    return out


def expected_dirs(need, mods_dir):
    """Теки модів, які мають з'явитися. Саме по них рахуємо поступ."""
    base = mods_dir.rstrip('\\')
    return [os.path.join(base, name, cat, mod)
            for name in sorted(need)
            for cat, mod in sorted(need[name])]


def find_tools():
    """Де лежить momw-tools-pack. Повертає теку або None."""
    if all(os.path.isfile(os.path.join(PACK_HOME, t)) for t in TOOLS):
        return PACK_HOME
    for base in (os.path.dirname(HERE), os.getcwd(),
                 os.path.expanduser('~'), r'C:\games', r'E:\Morrowind'):
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


def pack_url():
    """Адреса свіжої збірки інструментів.

    Беремо останній випуск, а як його артефакти вже прибрали, то збірку з
    master. Обидві адреси однаково сталі.
    """
    tag = None
    try:
        req = urllib.request.Request(PACK_API + '/releases?per_page=1')
        data = json.load(urllib.request.urlopen(req, timeout=30))
        tag = data[0]['tag_name'] if data else None
    except Exception:                          # noqa: BLE001 - мережа
        tag = None

    for ref in (tag, 'master'):
        if not ref:
            continue
        url = PACK_API + PACK_JOB % ref
        try:
            head = urllib.request.Request(url, method='HEAD')
            r = urllib.request.urlopen(head, timeout=30)
            return url, ref, int(r.headers.get('Content-Length') or 0)
        except Exception:                      # noqa: BLE001 - мережа
            continue
    raise RuntimeError('GitLab не віддав збірку інструментів')


def fetch_tools(on_line):
    """Завантажити momw-tools-pack і розпакувати. Повертає теку або None."""
    have = find_tools()
    if have:
        return have

    on_line('Інструментів Modding-OpenMW немає, качаю.')
    try:
        url, ref, size = pack_url()
    except Exception as e:                     # noqa: BLE001 - мережа
        on_line('Не вдалося спитати GitLab: %s' % e)
        return None

    on_line('Версія %s, %.0f МБ' % (ref, size / 1048576.0))
    tmp = os.path.join(os.environ.get('TEMP', '.'),
                       'momw-tools-pack-windows.zip')
    try:
        engine_download(url, tmp, size,
                        lambda p: on_line('  %d%%' % p) if p % 20 == 0 else None)
    except Exception as e:                     # noqa: BLE001 - мережа
        on_line('Завантаження не вдалося: %s' % e)
        return None

    on_line('Розпаковую у %s' % PACK_HOME)
    try:
        os.makedirs(PACK_HOME, exist_ok=True)
        with zipfile.ZipFile(tmp) as z:
            z.extractall(PACK_HOME)
    except (OSError, zipfile.BadZipFile) as e:
        on_line('Розпакувати не вдалося: %s' % e)
        return None
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass

    have = find_tools()
    if not have:
        on_line('У збірці немає umo.exe. Візьми її руками: ' + SITE)
    return have


def engine_download(url, dest, size, on_progress):
    """Те саме завантаження, що й для OpenMW. Тримаємо його в одному місці."""
    import engine
    return engine.download(url, dest, size, on_progress)


def umo_dirs(tools):
    """Куди umo складає моди: питаємо його самого, а не вгадуємо."""
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


NEW_CONSOLE = 0x00000010      # CREATE_NEW_CONSOLE: umo потрібне своє вікно


def suggest_mods_dir():
    """Куди радити складати моди: диск, де найбільше вільного місця.

    Повертає (шлях, вільно байтів). Профіль важить близько 80 ГБ, і людині
    легше вибрати теку, коли перед очима є готовий варіант.
    """
    best, free = None, 0
    for letter in 'CDEFGHIJ':
        root = letter + ':' + os.sep
        if not os.path.isdir(root):
            continue
        try:
            avail = shutil.disk_usage(root).free
        except OSError:
            continue
        if avail > free:
            best, free = root, avail
    return (os.path.join(best, 'Morrowind'), free) if best else (None, 0)


def setup_umo(tools):
    """Перше налаштування umo: вхід у Nexus і тека для модів.

    Відповісти на це може тільки людина, а з нашого вікна показати ті
    питання нема як. Тож даємо umo власне вікно консолі й чекаємо, поки
    вона закриється. Теку з tes3cmd він знайде сам, бо той лежить поруч.
    """
    p = subprocess.Popen([os.path.join(tools, 'umo.exe'), 'setup'],
                         cwd=tools, creationflags=NEW_CONSOLE)
    return p.wait()


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


class Counter(object):
    """Скільки модів уже на місці.

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


def install_lists(tools, need, skips, on_line, expected=(), on_count=None):
    """Завантажити моди профілю. Це найдовша частина.

    Спершу `umo sync`: він бере з modding-openmw.com опис усього набору.
    Тоді `umo install --subset`, де перелічені саме потрібні моди. umo звіряє
    елемент із рядком «категорія-тека» як підрядок, тож коротша назва тягне
    за собою довшу; такі збіги перелічені в рецепті й ідуть у `--skip`.
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
        on_line('Готово %d модів із %d (%d%%), минуло %s'
                % (have, total, share, hhmm(time.time() - began)))

    with Counter(expected, report):
        for name in sorted(need):
            subset = ','.join(sorted({mod for _cat, mod in need[name]}))
            cmd = [umo, 'install', '--subset', subset]
            skip = skips.get(name)
            if skip:
                cmd += ['--skip', ','.join(skip)]

            on_line('')
            if run_umo([umo, 'sync', name], on_line) != 0:
                on_line('Не вдалося взяти опис модів.')
                return False
            if run_umo(cmd + [name], on_line) != 0:
                on_line('Моди завантажилися не всі.')
                return False

    on_line('Усі моди завантажено за %s.' % hhmm(time.time() - began))
    return True


# Плагіни, яких немає на Nexus: їх складають із самого порядку завантаження.
# Порядок тут той, у якому їх треба робити, і він не випадковий: злиття має
# пройти до трави, бо інакше вони посилалися б одне на одне по колу.
DELTA = 'delta-merged.omwaddon'
GROUND = 'groundcover.omwaddon'
NO_GROUND = 'deleted_groundcover.omwaddon'
LIGHTS = 'S3LightFixes.omwaddon'
MADE = (DELTA, GROUND, NO_GROUND, LIGHTS)

# Файли профілю поза openmw.cfg. Без них моди стоять, але гра має інший
# вигляд: без тіней, без післяобробки, з коротким видноколом.
EXTRAS = ('settings.cfg', 'shaders.yaml', 'lightconfig.toml')


def made_name(line):
    """Яку саме згенеровану річ називає цей рядок. Порожньо, якщо жодну."""
    s = line.strip()
    for tag in ('content=', 'groundcover='):
        if s.startswith(tag):
            name = s[len(tag):].strip()
            if name in MADE:
                return name
    return ''


def cfg_without(text, names):
    """Той самий профіль, але без рядків про ці згенеровані файли."""
    return '\n'.join(l for l in text.splitlines()
                      if made_name(l) not in names) + '\n'


def tools_out(text):
    """Куди профіль чекає згенеровані плагіни."""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('data=') and s.rstrip('"').endswith('MOMWToolsPack'):
            return s[5:].strip().strip('"')
    return None


def run_tool(cmd, cwd, on_line):
    """Один інструмент. Довгий, тож переказуємо його рядки в журнал.

    Робоча тека важить: groundcoverify кладе свій доробок саме туди.
    """
    try:
        return _run_in(cmd, cwd, on_line)
    except OSError as e:
        on_line('  не запустився: %s' % e)
        return 1


def _run_in(cmd, cwd, on_line):
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE,
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
    return p.returncode


STAMP = '.made'          # чим саме зроблено те, що лежить у теці


def load_stamp(out_dir):
    p = os.path.join(out_dir, STAMP)
    try:
        return io.open(p, encoding='utf-8').read().strip()
    except OSError:
        return ''


def all_made(out_dir):
    return all(os.path.isfile(os.path.join(out_dir, n)) for n in MADE)


def make_plugins(tools, cfg_path, text, out_dir, on_line):
    """Зробити злитий плагін, траву і світло.

    Кожен інструмент читає openmw.cfg, тож перед його запуском у файлі не
    має бути того, що він аж тепер зробить. Тому профіль переписуємо тричі,
    щоразу додаючи вже готове.

    Робота ця залежить тільки від порядку завантаження, тож поруч лишаємо
    його відбиток. Коли порядок не змінився, переробляти нічого: людина,
    що оновлює переклад, не чекатиме зайвої хвилини.
    """
    os.makedirs(out_dir, exist_ok=True)
    base = cfg_without(text, set(MADE))
    mark = hashlib.sha256(base.encode('utf-8')).hexdigest()[:16]
    if all_made(out_dir) and load_stamp(out_dir) == mark:
        on_line('Порядок завантаження той самий, плагіни лишаються.')
        return set()

    left = set(MADE)

    def stage():
        io.open(cfg_path, 'w', encoding='utf-8',
                newline='\n').write(cfg_without(text, left))

    on_line('Зливаю плагіни в один. Це кілька хвилин.')
    stage()
    run_tool([os.path.join(tools, 'delta_plugin.exe'), '-q',
              '-c', cfg_path, 'merge', '--ignore', NO_GROUND,
              os.path.join(out_dir, DELTA)], out_dir, on_line)
    left.discard(DELTA)

    on_line('Роблю траву.')
    stage()
    run_tool([os.path.join(tools, 'groundcoverify.exe'),
              '--openmw-config', cfg_path,
              '--delta-plugin-exe', os.path.join(tools, 'delta_plugin.exe')],
             out_dir, on_line)
    left.discard(GROUND)
    left.discard(NO_GROUND)

    on_line('Правлю світло.')
    stage()
    run_tool([os.path.join(tools, 's3lightfixes.exe'), '-n',
              '-c', cfg_path, '-o', out_dir], out_dir, on_line)
    left.discard(LIGHTS)

    have = [n for n in MADE if os.path.isfile(os.path.join(out_dir, n))]
    for name in MADE:
        if name not in have:
            on_line('Не вийшло зробити %s, рядок про нього прибрано.' % name)
    if len(have) == len(MADE):
        io.open(os.path.join(out_dir, STAMP), 'w',
                encoding='utf-8').write(mark + '\n')
    return set(MADE) - set(have)


def write_extras(payload_root, cfg_path, on_line):
    """Покласти решту налаштувань профілю поруч із openmw.cfg."""
    here = os.path.dirname(cfg_path)
    for name in EXTRAS:
        src = os.path.join(recipe_dir(payload_root), name)
        if not os.path.isfile(src):
            continue
        dest = os.path.join(here, name)
        if os.path.isfile(dest):
            backup = dest + '.before-modlist'
            if not os.path.exists(backup):
                io.open(backup, 'wb').write(io.open(dest, 'rb').read())
        io.open(dest, 'wb').write(io.open(src, 'rb').read())
        on_line('покладено %s' % name)


def data_dirs(text):
    """Теки даних профілю, у порядку профілю."""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('data='):
            out.append(s[5:].strip().strip('"'))
    return out


def prune_missing(text, on_line):
    """Прибрати з порядку завантаження плагіни, яких немає на диску.

    OpenMW на такому профілі не стартує взагалі: «the content file does not
    exist». Набори Modding-OpenMW живуть своїм життям, моди з них зникають і
    перейменовуються, тож тримати рядок про те, чого немає, означало б
    віддати людині гру, яка не запускається. Краще без кількох модів.
    """
    dirs = data_dirs(text)
    known = {}
    for d in dirs:
        try:
            for f in os.listdir(d):
                known.setdefault(f.lower(), d)
        except OSError:
            continue

    kept, dropped = [], []
    for line in text.splitlines():
        s = line.strip()
        name = ''
        for tag in ('content=', 'groundcover='):
            if s.startswith(tag):
                name = s[len(tag):].strip()
        if name and name.lower() not in known:
            dropped.append(name)
            continue
        kept.append(line)

    if dropped:
        on_line('Немає %d плагінів, рядки про них прибрано.' % len(dropped))
        for name in dropped[:8]:
            on_line('  %s' % name)
        if len(dropped) > 8:
            on_line('  і ще %d' % (len(dropped) - 8))
    return '\n'.join(kept) + '\n', dropped


def write_profile(payload_root, cfg_path, mods_dir, game_dir, on_line,
                  tools=None):
    """Скласти профіль цієї машини: openmw.cfg, згенеровані плагіни, решта."""
    src = os.path.join(recipe_dir(payload_root), 'profile.cfg')
    if not os.path.isfile(src):
        on_line('Рецепта профілю немає.')
        return False
    text = io.open(src, encoding='utf-8').read()
    text = text.replace('{МОДИ}', mods_dir.rstrip('\\')) \
               .replace('{ГРА}', game_dir.rstrip('\\'))

    missing = 0
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('data='):
            d = s[5:].strip().strip('"')
            if not os.path.isdir(d) and not d.endswith('MOMWToolsPack'):
                missing += 1
    if missing:
        on_line('Увага: %d тек із профілю ще немає, якісь моди не '
                'завантажилися.' % missing)

    if os.path.isfile(cfg_path):
        backup = cfg_path + '.before-modlist'
        if not os.path.exists(backup):
            io.open(backup, 'w', encoding='utf-8').write(
                io.open(cfg_path, encoding='utf-8', errors='replace').read())
            on_line('стару конфігурацію збережено як %s'
                    % os.path.basename(backup))
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)

    write_extras(payload_root, cfg_path, on_line)

    out_dir = tools_out(text)
    failed = set(MADE)
    if tools and out_dir:
        failed = make_plugins(tools, cfg_path, text, out_dir, on_line)
    elif out_dir:
        on_line('Інструментів немає, згенерованих плагінів не буде.')
    final, _dropped = prune_missing(cfg_without(text, failed), on_line)
    io.open(cfg_path, 'w', encoding='utf-8', newline='\n').write(final)
    on_line('профіль записано: %s' % cfg_path)
    return True
