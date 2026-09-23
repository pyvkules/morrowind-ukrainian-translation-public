# -*- coding: utf-8 -*-
"""Вікно інсталятора. Уся логіка — в `install.py`, тут лише її обгортка.

Консольний режим лишається: якщо exe запустили з аргументами (`--cfg`,
`--uninstall`, `--dry-run`), вікна не буде. Це потрібно і нам для перевірок,
і CI, який саме так димово тестує збірку.
"""
import os
import sys
import threading
import traceback
import queue

import tkinter as tk
from tkinter import filedialog, font as tkfont, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import install                                  # noqa: E402

BG = '#1d1b17'          # під колір самої гри, щоб не різало око
FG = '#e8dfc8'
ACCENT = '#c8a45a'
DIM = '#8d8570'
BAD = '#d98b6a'


class App:
    def __init__(self, root):
        self.root = root
        self.queue = queue.Queue()
        self.busy = False
        self.cfgs = install.cfg_candidates()

        root.title(install.APP)
        root.configure(bg=BG)
        root.minsize(760, 520)
        try:
            root.tk.call('tk', 'scaling', 1.25)
        except tk.TclError:
            pass

        self.mono = tkfont.nametofont('TkFixedFont').copy()
        self.mono.configure(size=9)
        head = tkfont.nametofont('TkDefaultFont').copy()
        head.configure(size=15, weight='bold')

        tk.Label(root, text='Українізатор Morrowind', bg=BG, fg=ACCENT,
                 font=head).pack(anchor='w', padx=18, pady=(16, 2))
        self.sub = tk.Label(root, text='', bg=BG, fg=DIM, justify='left',
                            anchor='w')
        self.sub.pack(anchor='w', padx=18, pady=(0, 10), fill='x')

        box = tk.Frame(root, bg=BG)
        box.pack(fill='x', padx=18)
        tk.Label(box, text='Гра', bg=BG, fg=FG).pack(anchor='w')
        row = tk.Frame(box, bg=BG)
        row.pack(fill='x', pady=(2, 10))
        self.choice = ttk.Combobox(row, state='readonly', values=self.cfgs,
                                   font=self.mono)
        self.choice.pack(side='left', fill='x', expand=True)
        if self.cfgs:
            self.choice.current(0)
        self.choice.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        tk.Button(row, text='Вибрати…', command=self.browse, bg=BG, fg=FG,
                  activebackground=BG, activeforeground=ACCENT,
                  relief='groove', padx=10).pack(side='left', padx=(8, 0))

        self.info = tk.Label(box, text='', bg=BG, fg=DIM, justify='left',
                             anchor='w', font=self.mono)
        self.info.pack(anchor='w', fill='x')

        btns = tk.Frame(root, bg=BG)
        btns.pack(fill='x', padx=18, pady=12)
        self.go = tk.Button(btns, text='Встановити переклад', command=self.start,
                            bg=ACCENT, fg='#1d1b17', activebackground=ACCENT,
                            relief='flat', padx=18, pady=8,
                            font=(head.actual('family'), 11, 'bold'))
        self.go.pack(side='left')
        self.rm = tk.Button(btns, text='Прибрати', command=self.remove, bg=BG,
                            fg=DIM, activebackground=BG, activeforeground=FG,
                            relief='groove', padx=12, pady=6)
        self.rm.pack(side='left', padx=(10, 0))

        self.bar = ttk.Progressbar(root, mode='indeterminate')

        wrap = tk.Frame(root, bg=BG)
        wrap.pack(fill='both', expand=True, padx=18, pady=(0, 16))
        self.log = tk.Text(wrap, bg='#141310', fg=FG, insertbackground=FG,
                           relief='flat', wrap='word', font=self.mono,
                           height=14, state='disabled', padx=10, pady=8)
        self.log.pack(side='left', fill='both', expand=True)
        sb = ttk.Scrollbar(wrap, command=self.log.yview)
        sb.pack(side='right', fill='y')
        self.log.configure(yscrollcommand=sb.set)
        self.log.tag_configure('good', foreground='#9ec97f')
        self.log.tag_configure('bad', foreground=BAD)
        self.log.tag_configure('dim', foreground=DIM)

        install.set_sink(self.queue.put)
        self.refresh()
        self.root.after(80, self.drain)

    # --- стан ---------------------------------------------------------------

    def cfg(self):
        return self.choice.get().strip()

    def refresh(self):
        if not self.cfgs:
            self.sub.configure(text='OpenMW не знайдено', fg=BAD)
            self.info.configure(text=install.why_no_openmw(), fg=BAD)
            self.go.configure(state='disabled')
            self.rm.configure(state='disabled')
            return
        cfg = self.cfg()
        if not cfg or not os.path.isfile(cfg):
            return
        lines, dirs, master, mod_dir = install.describe(cfg)
        if master:
            self.sub.configure(
                text='Знайдено гру. Натисни кнопку — решту зробимо самі.',
                fg=DIM)
            self.info.configure(
                text='гра:   %s\nтеки:  %d\nставимо: %s' % (master, len(dirs), mod_dir),
                fg=DIM)
            self.go.configure(state='normal')
            self.rm.configure(state='normal')
        else:
            self.sub.configure(text='У цій конфігурації немає гри', fg=BAD)
            self.info.configure(
                text='Morrowind.esm не знайдено серед тек цієї конфігурації.\n'
                     'Спершу пройди майстер налаштування OpenMW.', fg=BAD)
            self.go.configure(state='disabled')

    def browse(self):
        p = filedialog.askopenfilename(
            title='Вкажи openmw.cfg', filetypes=[('openmw.cfg', 'openmw.cfg'),
                                                 ('Усі файли', '*.*')])
        if p:
            if p not in self.cfgs:
                self.cfgs.append(p)
                self.choice.configure(values=self.cfgs)
            self.choice.set(p)
            self.refresh()

    # --- журнал -------------------------------------------------------------

    def write(self, msg):
        self.log.configure(state='normal')
        tag = 'dim'
        if msg.startswith('!') or 'ЗБІЙ' in msg or 'не вдалася' in msg:
            tag = 'bad'
        elif 'Готово' in msg or msg.strip().endswith('ок'):
            tag = 'good'
        self.log.insert('end', msg + '\n', tag)
        self.log.see('end')
        self.log.configure(state='disabled')

    def drain(self):
        try:
            while True:
                self.write(self.queue.get_nowait())
        except queue.Empty:
            pass
        self.root.after(80, self.drain)

    # --- робота -------------------------------------------------------------

    def start(self):
        self.run(install.install_to, done='Готово. Запускай OpenMW як звичайно.')

    def remove(self):
        self.run(install.uninstall_from, done='Прибрано. Гра знову англійською.')

    def run(self, fn, done):
        if self.busy:
            return
        cfg = self.cfg()
        self.busy = True
        self.go.configure(state='disabled')
        self.rm.configure(state='disabled')
        self.bar.pack(fill='x', padx=18, pady=(0, 8))
        self.bar.start(12)

        def work():
            try:
                code = fn(cfg)
            except Exception:                   # noqa: BLE001 - показуємо гравцю
                self.queue.put('! Несподівана помилка:')
                for ln in traceback.format_exc().splitlines()[-6:]:
                    self.queue.put('  ' + ln)
                code = 1
            self.root.after(0, lambda: self.finish(code, done))

        threading.Thread(target=work, daemon=True).start()

    def finish(self, code, done):
        self.busy = False
        self.bar.stop()
        self.bar.pack_forget()
        self.go.configure(state='normal')
        self.rm.configure(state='normal')
        if code == 0:
            self.write('')
            self.write(done)
            self.write('')
            self.write('Переклад працює тим, що його тека стоїть останньою в '
                       'списку тек. Якщо відкриєш лаунчер OpenMW і переставиш '
                       'їх на вкладці Data Files, гра знову стане англійською '
                       '— тоді просто натисни «Встановити» ще раз.')
        else:
            self.write('')
            self.write('! Не вдалося. Гру не чіпали.')


def hide_console():
    """Сховати консоль, що блимнула під час запуску.

    Збираємо exe **не** віконним: інакше зник би консольний режим, яким
    користуємося ми й CI. Тому вікно консолі ховаємо самі.
    """
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:                           # noqa: BLE001 - не Windows
        pass


def run():
    hide_console()
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0
