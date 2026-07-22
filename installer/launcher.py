# -*- coding: utf-8 -*-
"""Те, що насправді запускає Steam.

Перевіряє, чи вийшла новіша версія модпаку, пропонує оновитися - і запускає OpenMW.
Якщо мережі немає, перевірка тихо пропускається: гра ніколи не мусить чекати на
інтернет.

Шляхи бере з launcher.json, який пише інсталятор, тож користувач нічого не налаштовує.

    py launcher.py            # перевірити оновлення й запустити гру
    py launcher.py --no-update
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE)

import updater  # noqa: E402

CONF = os.path.join(REPO, 'launcher.json')


def config():
    try:
        with open(CONF, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def launch(cfg, extra_args):
    openmw = cfg.get('openmw')
    profile = cfg.get('profile')
    if not openmw or not os.path.isfile(os.path.join(openmw, 'openmw.exe')):
        raise SystemExit('launcher.json не вказує на OpenMW - перевстановіть модпак.')
    cmd = [os.path.join(openmw, 'openmw.exe'), '--replace=config',
           '--config=' + profile, '--user-data=' + profile] + list(extra_args)
    return subprocess.Popen(cmd, cwd=openmw).wait()


def rebuild(log):
    """Оновлення везе тексти, а не зібрані файли - після нього треба перезібрати.

    Крок пошуку відмінкових форм пропускається автоматично, якщо корпус не змінився,
    тож типове оновлення займає секунди, а не хвилини.
    """
    r = subprocess.run([sys.executable, os.path.join(REPO, 'build.py')],
                       cwd=REPO, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    for line in (r.stdout or '').splitlines():
        log(line)
    return r.returncode == 0


def ask_and_update(rel):
    """Маленьке вікно: оновити чи пропустити. Повертає True, якщо оновили."""
    try:
        import tkinter as tk
        from tkinter import scrolledtext
    except ImportError:
        return False

    state = {'done': False}
    win = tk.Tk()
    win.title('Оновлення модпаку')
    win.geometry('560x420')

    tk.Label(win, text='Доступна нова версія: %s' % rel['version'],
             font=('Segoe UI', 12, 'bold')).pack(pady=(14, 4))
    size = ('%.1f МБ' % (rel['size'] / 1048576.0)) if rel.get('size') else ''
    tk.Label(win, text='Встановлена: %s   %s'
             % (updater.local().get('version'), size)).pack()

    box = scrolledtext.ScrolledText(win, height=12, font=('Consolas', 9))
    box.pack(fill='both', expand=True, padx=14, pady=10)
    box.insert('end', rel.get('notes') or 'Опису змін немає.')

    def log(s):
        box.insert('end', '\n' + s)
        box.see('end')
        box.update_idletasks()

    row = tk.Frame(win)
    row.pack(pady=(0, 14))

    def do_update():
        up.config(state='disabled')
        skip.config(state='disabled')
        box.delete('1.0', 'end')
        try:
            log('завантаження...')
            tmp = os.path.join(tempfile.gettempdir(), 'mwuk-update.zip')
            updater.download(rel['url'], tmp,
                             lambda d, t: log('  %d%%' % (100 * d // t)) if t and
                             d % (1 << 20) < 65536 else None)
            log('застосування...')
            updater.apply(tmp, log)
            log('перезбірка...')
            if rebuild(log):
                state['done'] = True
                log('готово, запускаємо гру')
                win.after(700, win.destroy)
            else:
                log('! перезбірка не вдалася - гра запуститься на старій версії')
                up.config(state='normal', text='Запустити гру', command=win.destroy)
        except Exception as e:                          # noqa: BLE001
            log('! %s' % e)
            up.config(state='normal', text='Запустити гру', command=win.destroy)

    up = tk.Button(row, text='Оновити й грати', width=18, height=2,
                   font=('Segoe UI', 10, 'bold'), command=do_update)
    up.pack(side='left', padx=6)
    skip = tk.Button(row, text='Цього разу пропустити', width=22, height=2,
                     command=win.destroy)
    skip.pack(side='left', padx=6)

    win.mainloop()
    return state['done']


def main():
    args = [a for a in sys.argv[1:] if a != '--no-update']
    if '--no-update' not in sys.argv:
        rel = updater.check()          # None, якщо мережі нема або версія свіжа
        if rel and rel.get('url'):
            ask_and_update(rel)
    return launch(config(), args)


if __name__ == '__main__':
    raise SystemExit(main())
