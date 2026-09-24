# -*- coding: utf-8 -*-
"""Поставити OpenMW самому, щоб людина цього не робила.

Навіщо
------
Найчастіший випадок — у людини є гра в Steam і більше нічого. Просити її піти
на сайт, вибрати правильний файл, пройти майстер і показати йому гру — це вже
три місця, де вона зупиниться. OpenMW вільний і лежить на GitHub, тож качаємо
й ставимо самі.

Що робимо
---------
1. питаємо GitHub, який зараз реліз, і беремо з нього файл для Windows;
2. запускаємо його тихо (`/S` — це NSIS, він так уміє);
3. знаходимо, куди він став, і готуємо налаштування під знайдену гру:
   переносимо `Morrowind.ini` рідним `openmw-iniimporter`, а тоді дописуємо
   саму гру й доповнення.

Чого не робимо
--------------
Не чіпаємо наявний OpenMW. Якщо він уже є, цей крок просто не потрібен.
"""
import io
import json
import os
import re
import subprocess
import urllib.request

RELEASES = 'https://api.github.com/repos/OpenMW/openmw/releases/latest'
ASSET = re.compile(r'^OpenMW-[\d.]+-Windows-x64\.exe$', re.IGNORECASE)
MASTERS = ('Morrowind.esm', 'Tribunal.esm', 'Bloodmoon.esm')


def latest_windows_build():
    """(назва, адреса, розмір) найсвіжішої збірки для Windows."""
    req = urllib.request.Request(RELEASES, headers={'Accept': 'application/vnd.github+json'})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    for a in data.get('assets', []):
        if ASSET.match(a['name']):
            return a['name'], a['browser_download_url'], a['size'], data['tag_name']
    raise RuntimeError('у релізі OpenMW немає файлу для Windows')


def download(url, dest, size=0, on_progress=None):
    """Завантажити, повідомляючи про поступ у відсотках."""
    with urllib.request.urlopen(url, timeout=60) as r, io.open(dest, 'wb') as f:
        total = size or int(r.headers.get('Content-Length') or 0)
        got = 0
        last = -1
        while True:
            chunk = r.read(262144)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if on_progress and total:
                pct = int(got * 100 / total)
                if pct != last and pct % 5 == 0:
                    last = pct
                    on_progress(pct)
    return dest


def silent_install(installer_exe, target, timeout=900):
    """Тихе встановлення OpenMW.

    Дві примхи NSIS: `/D=` мусить бути **останнім** параметром і **без лапок**.
    Якби ми передали список аргументів, Python сам узяв би шлях у лапки
    (типовий шлях містить «Program Files»), і NSIS зробив би теку з лапками в
    назві. Тому рядок команди складаємо самі.

    Третя, і головна: інсталятор OpenMW **вимагає прав адміністратора** —
    звичайний запуск падає з WinError 740. Тому піднімаємо права через
    ShellExecute з дієсловом `runas`; Windows покаже звичне вікно згоди, і
    людина натисне «Так» один раз. Обійти це не можна: так підписаний сам
    інсталятор OpenMW.
    """
    import ctypes
    from ctypes import wintypes

    os.makedirs(target, exist_ok=True)
    params = '/S /D=%s' % target          # саме без лапок, див. вище

    class SHELLEXECUTEINFO(ctypes.Structure):
        _fields_ = [('cbSize', wintypes.DWORD), ('fMask', ctypes.c_ulong),
                    ('hwnd', wintypes.HWND), ('lpVerb', wintypes.LPCWSTR),
                    ('lpFile', wintypes.LPCWSTR), ('lpParameters', wintypes.LPCWSTR),
                    ('lpDirectory', wintypes.LPCWSTR), ('nShow', ctypes.c_int),
                    ('hInstApp', wintypes.HINSTANCE), ('lpIDList', ctypes.c_void_p),
                    ('lpClass', wintypes.LPCWSTR), ('hkeyClass', wintypes.HKEY),
                    ('dwHotKey', wintypes.DWORD), ('hIcon', wintypes.HANDLE),
                    ('hProcess', wintypes.HANDLE)]

    SEE_MASK_NOCLOSEPROCESS = 0x00000040
    info = SHELLEXECUTEINFO()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = 'runas'
    info.lpFile = installer_exe
    info.lpParameters = params
    info.nShow = 0                        # SW_HIDE - вікна інсталятора не треба

    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
        err = ctypes.GetLastError()
        # 1223 = людина натиснула «Ні» у вікні згоди
        raise PermissionError('відмовлено в правах' if err == 1223
                              else 'не вдалося запустити (код %d)' % err)

    ctypes.windll.kernel32.WaitForSingleObject(info.hProcess, timeout * 1000)
    code = wintypes.DWORD()
    ctypes.windll.kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
    ctypes.windll.kernel32.CloseHandle(info.hProcess)
    return code.value


def find_engine(target):
    for root, dirs, files in os.walk(target):
        for f in files:
            if f.lower() == 'openmw.exe':
                return os.path.join(root, f)
    return None


def morrowind_ini(data_files):
    """`Morrowind.ini` лежить над текою Data Files."""
    p = os.path.join(os.path.dirname(data_files), 'Morrowind.ini')
    return p if os.path.isfile(p) else None


def bootstrap_config(engine_exe, data_files, cfg_path, on_line=None):
    """Зробити робочі налаштування для знайденої гри.

    Спершу пускаємо рідний `openmw-iniimporter`: він переносить із
    `Morrowind.ini` сотні `fallback=` (кольори мапи, вода, освітлення). Без них
    гра запуститься, але виглядатиме не так, як має.
    """
    def say(m):
        if on_line:
            on_line(m)

    engine_dir = os.path.dirname(engine_exe)
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
    if not os.path.isfile(cfg_path):
        io.open(cfg_path, 'w', encoding='utf-8').write('')

    ini = morrowind_ini(data_files)
    importer = os.path.join(engine_dir, 'openmw-iniimporter.exe')
    if ini and os.path.isfile(importer):
        r = subprocess.run([importer, '-i', ini, '-c', cfg_path, '--game-files'],
                           capture_output=True)
        say('перенесено налаштування з Morrowind.ini'
            if r.returncode == 0 else 'Morrowind.ini перенести не вдалося')

    lines = io.open(cfg_path, encoding='utf-8', errors='replace').read().splitlines()
    have_data = any(l.strip().startswith('data=') for l in lines)
    have_content = {l.strip().lower() for l in lines if l.strip().startswith('content=')}

    add = []
    if not have_data:
        add.append('data="%s"' % data_files)
    for m in MASTERS:
        if os.path.isfile(os.path.join(data_files, m)) \
                and ('content=' + m).lower() not in have_content:
            add.append('content=' + m)
    for m in ('Morrowind.bsa', 'Tribunal.bsa', 'Bloodmoon.bsa'):
        if os.path.isfile(os.path.join(data_files, m)) \
                and not any(('fallback-archive=' + m).lower() == l.strip().lower()
                            for l in lines):
            add.append('fallback-archive=' + m)

    if add:
        with io.open(cfg_path, 'a', encoding='utf-8') as f:
            f.write('\n'.join(add) + '\n')
        say('додано гру й доповнення (%d рядків)' % len(add))
    return cfg_path
