# -*- coding: utf-8 -*-
"""Інсталятор українського модпаку Morrowind.

Одне вікно, одна кнопка. Знаходить гру й рушій, збирає переклад, створює профіль
OpenMW і прописує параметри запуску в Steam, щоб працював звичайний ярлик Steam.

Оригінальну гру не змінює: OpenMW ставиться поруч і читає її як дані, а наш каталог
стоїть останнім у списку, тому лише перекриває файли, не переписуючи їх.

    py installer/install.py           # вікно
    py installer/install.py --cli     # те саме в консолі

Чого цей інсталятор НЕ робить: не завантажує самі моди. Колекції
(total-overhaul, expanded-vanilla, just-good-morrowind, i-heart-vanilla)
ставляться через momw-configurator з modding-openmw.com - частина модів лежить на
Nexus, а Nexus не дозволяє автоматичне завантаження без преміум-акаунта. Якщо
колекцій немає, інсталятор скаже про це прямо, а не впаде посеред збірки.
"""
import json
import os
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, 'tools'))

import steam  # noqa: E402


def recipe():
    with open(os.path.join(REPO, 'modpack', 'modlist.json'), encoding='utf-8') as f:
        return json.load(f)


def find_openmw():
    guess = os.path.abspath(os.path.join(REPO, '..', '..'))
    if os.path.isfile(os.path.join(guess, 'openmw.exe')):
        return guess
    for drive in 'CDEFGH':
        for p in (r'%s:\Program Files\OpenMW', r'%s:\Morrowind\OpenMW', r'%s:\OpenMW'):
            d = p % drive
            if os.path.isfile(os.path.join(d, 'openmw.exe')):
                return d
    return None


def find_mods(collections):
    guess = os.path.abspath(os.path.join(REPO, '..', '..', '..'))
    for c in [guess, os.path.dirname(guess)] + [r'%s:\Morrowind' % d for d in 'CDEFGH']:
        if c and os.path.isdir(c) and all(os.path.isdir(os.path.join(c, n))
                                          for n in collections):
            return os.path.normpath(c)
    return None


class Plan(object):
    def __init__(self):
        r = recipe()
        self.collections = r['based_on']
        self.morrowind = steam.morrowind_data_files()
        self.openmw = find_openmw()
        self.mods = find_mods(self.collections)
        self.profile = (os.path.join(self.openmw, 'ukrainian-modpack')
                        if self.openmw else None)

    def blockers(self):
        out = []
        if not self.morrowind:
            out.append('Не знайдено Morrowind. Установіть його у Steam і запустіть '
                       'хоча б раз.')
        if not self.openmw:
            out.append('Не знайдено OpenMW. Завантажте його з openmw.org і встановіть.')
        if not self.mods:
            out.append('Не знайдено колекції модів (%s). Установіть їх через '
                       'momw-configurator з modding-openmw.com.'
                       % ', '.join(self.collections))
        if not os.path.isfile(os.path.join(REPO, 'tools', 'base.esm')):
            out.append('Немає tools/base.esm - без нього переклад не збереться. '
                       'Див. README.')
        return out


def run(cmd, log):
    log('$ ' + ' '.join(os.path.basename(c) if i == 1 else c
                        for i, c in enumerate(cmd)))
    p = subprocess.Popen(cmd, cwd=REPO, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True,
                         encoding='utf-8', errors='replace')
    for line in p.stdout:
        log('  ' + line.rstrip())
    return p.wait()


def install(plan, set_steam, log):
    """Returns True on success."""
    blockers = plan.blockers()
    if blockers:
        for b in blockers:
            log('! ' + b)
        return False

    log('Гра     : %s' % plan.morrowind)
    log('OpenMW  : %s' % plan.openmw)
    log('Моди    : %s' % plan.mods)
    log('Профіль : %s' % plan.profile)
    log('')

    log('== Крок 1/3: збірка перекладу ==')
    if run([sys.executable, os.path.join(REPO, 'build.py')], log) != 0:
        log('! Збірка перекладу не вдалася.')
        return False

    log('')
    log('== Крок 2/3: профіль OpenMW ==')
    rc = run([sys.executable, os.path.join(REPO, 'tools', 'modpack', 'install_modpack.py'),
              '--apply', '--morrowind', plan.morrowind, '--openmw', plan.openmw,
              '--mods', plan.mods, '--profile', plan.profile], log)
    if rc != 0:
        log('! Профіль не створено.')
        return False

    log('')
    log('== Крок 3/3: ярлик Steam ==')
    opts = steam.launch_options(plan.openmw, plan.profile)
    if not set_steam:
        log('Пропущено. Параметри запуску, якщо схочете вписати вручну')
        log('(Steam -> Morrowind -> Властивості -> Параметри запуску):')
        log('  ' + opts)
    elif steam.is_running():
        log('! Steam запущено. Закрийте Steam і натисніть «Встановити» ще раз -')
        log('  Steam перезаписує свої налаштування з пам\'яті при виході.')
        log('  Або впишіть вручну:')
        log('  ' + opts)
    else:
        for path, status in steam.set_launch_options(opts, dry_run=False):
            log('  %-12s %s' % (status, path))
        log('Готово. Запускайте Morrowind звичайним ярликом Steam.')
    return True


# ------------------------------------------------------------------ interfaces
def cli():
    plan = Plan()
    ok = install(plan, '--steam' in sys.argv, lambda s: print(s))
    return 0 if ok else 1


def gui():
    import tkinter as tk
    from tkinter import scrolledtext

    plan = Plan()
    root = tk.Tk()
    root.title('Український модпак Morrowind')
    root.geometry('820x560')

    tk.Label(root, text='Український модпак Morrowind',
             font=('Segoe UI', 14, 'bold')).pack(pady=(12, 2))
    tk.Label(root, text='Оригінальну гру не змінює - OpenMW ставиться поруч.',
             font=('Segoe UI', 9)).pack()

    info = tk.Frame(root)
    info.pack(fill='x', padx=16, pady=10)
    for i, (label, value) in enumerate([
            ('Гра', plan.morrowind), ('OpenMW', plan.openmw),
            ('Моди', plan.mods), ('Профіль', plan.profile)]):
        tk.Label(info, text=label, width=9, anchor='w',
                 font=('Segoe UI', 9, 'bold')).grid(row=i, column=0, sticky='w')
        tk.Label(info, text=value or 'не знайдено', anchor='w',
                 fg=('#222' if value else '#b00')).grid(row=i, column=1, sticky='w')

    want_steam = tk.BooleanVar(value=True)
    tk.Checkbutton(root, text='Прописати параметри запуску в Steam '
                              '(Steam має бути закритий)',
                   variable=want_steam).pack(anchor='w', padx=16)

    log_box = scrolledtext.ScrolledText(root, height=18, font=('Consolas', 9))
    log_box.pack(fill='both', expand=True, padx=16, pady=10)

    def log(s):
        log_box.insert('end', s + '\n')
        log_box.see('end')
        log_box.update_idletasks()

    button = tk.Button(root, text='Встановити', font=('Segoe UI', 11, 'bold'),
                       height=2, width=20)
    button.pack(pady=(0, 14))

    def go():
        button.config(state='disabled', text='Встановлення...')
        log_box.delete('1.0', 'end')

        def work():
            try:
                ok = install(Plan(), want_steam.get(), log)
            except Exception as e:                      # noqa: BLE001
                log('! %s' % e)
                ok = False
            button.config(state='normal',
                          text='Готово' if ok else 'Спробувати ще раз')
        threading.Thread(target=work, daemon=True).start()

    button.config(command=go)
    for b in plan.blockers():
        log('! ' + b)
    root.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(cli() if '--cli' in sys.argv else gui())
