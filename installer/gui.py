# -*- coding: utf-8 -*-
"""Вікно інсталятора: провести людину за руку й зробити все самому.

Уся робота — в `install.py`; тут лише те, що видно. Два правила:

* людина не мусить розуміти слів «плагін», «зріз» чи «модліст». Кроки звуться
  по-людськи, а технічний журнал захований під «Подробиці»;
* кнопка одна й очевидна. Небезпечне («Вилучити переклад») стоїть окремо,
  зветься повністю і вмикається лише тоді, коли є що вилучати.

Консольний режим лишається: exe з будь-яким аргументом вікна не відкриває.
"""
import os
import queue
import sys
import threading
import traceback

import tkinter as tk
from tkinter import filedialog, font as tkfont, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import install                                  # noqa: E402

BG = '#1b1917'
PANEL = '#232020'
FG = '#e9e2d2'
DIM = '#968f7e'
GOLD = '#cba85f'
GOOD = '#8fbf6b'
BAD = '#d98b6a'

# Внутрішня назва кроку -> те, що бачить людина. Імена скриптів їй ні про що
# не кажуть, а «Перекладаю меню» каже все.
STEP_NAMES = [
    ('шрифт',     'Додаю українські літери до шрифту'),
    ('ядро',      'Перекладаю основну гру'),
    ('плагіни',   'Перекладаю доповнення й моди'),
    ('назви',     'Перекладаю назви предметів і людей'),
    ('теми',      'Перекладаю теми розмов'),
    ('інтерфейс', 'Перекладаю меню гри'),
    ('посилання', 'Зв’язую згадки в розмовах'),
]


class App:
    def __init__(self, root):
        self.root = root
        self.queue = queue.Queue()
        self.busy = False
        self.cfgs = install.cfg_candidates()
        self.rows = {}
        self.state = {}
        self.details_open = False

        root.title('Українізатор Morrowind')
        root.configure(bg=BG)
        root.geometry('720x560')
        root.minsize(720, 560)
        try:
            root.tk.call('tk', 'scaling', 1.3)
        except tk.TclError:
            pass

        base = tkfont.nametofont('TkDefaultFont')
        self.f_head = base.copy(); self.f_head.configure(size=16, weight='bold')
        self.f_body = base.copy(); self.f_body.configure(size=10)
        self.f_btn = base.copy(); self.f_btn.configure(size=10, weight='bold')
        self.f_mono = tkfont.nametofont('TkFixedFont').copy()
        self.f_mono.configure(size=8)

        tk.Label(root, text='Українська мова для Morrowind', bg=BG, fg=GOLD,
                 font=self.f_head).pack(anchor='w', padx=24, pady=(20, 4))
        self.sub = tk.Label(root, bg=BG, fg=DIM, font=self.f_body,
                            justify='left', anchor='w', wraplength=660)
        self.sub.pack(anchor='w', padx=24, pady=(0, 14), fill='x')

        # --- яку гру перекладаємо -------------------------------------------
        pick = tk.Frame(root, bg=BG)
        pick.pack(fill='x', padx=24)
        tk.Label(pick, text='Гра', bg=BG, fg=FG, font=self.f_body).pack(anchor='w')
        row = tk.Frame(pick, bg=BG)
        row.pack(fill='x', pady=(4, 6))
        self.choice = ttk.Combobox(row, state='readonly', values=self.cfgs,
                                   font=self.f_mono)
        self.choice.pack(side='left', fill='x', expand=True, ipady=3)
        if self.cfgs:
            self.choice.current(0)
        self.choice.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        self.mk_button(row, 'Вказати іншу', self.browse).pack(side='left',
                                                              padx=(8, 0))
        self.where = tk.Label(pick, bg=BG, fg=DIM, font=self.f_mono,
                              justify='left', anchor='w', wraplength=660)
        self.where.pack(anchor='w', fill='x', pady=(0, 12))

        # --- кроки ------------------------------------------------------------
        self.steps = tk.Frame(root, bg=PANEL)
        self.steps.pack(fill='x', padx=24, pady=(0, 12))
        for key, title in STEP_NAMES:
            line = tk.Frame(self.steps, bg=PANEL)
            line.pack(fill='x', padx=14, pady=3)
            mark = tk.Label(line, text='·', bg=PANEL, fg=DIM, width=2,
                            font=self.f_body)
            mark.pack(side='left')
            name = tk.Label(line, text=title, bg=PANEL, fg=DIM,
                            font=self.f_body, anchor='w')
            name.pack(side='left', fill='x', expand=True)
            self.rows[key] = (mark, name)

        # --- дії --------------------------------------------------------------
        act = tk.Frame(root, bg=BG)
        act.pack(fill='x', padx=24)
        self.go = self.mk_button(act, 'Встановити', self.start, primary=True)
        self.go.pack(side='left')
        self.details_btn = self.mk_button(act, 'Подробиці', self.toggle)
        self.details_btn.pack(side='left', padx=(10, 0))
        self.rm = self.mk_button(act, 'Вилучити переклад', self.remove)
        self.rm.pack(side='right')

        self.bar = ttk.Progressbar(root, mode='indeterminate')

        self.logwrap = tk.Frame(root, bg=BG)
        self.log = tk.Text(self.logwrap, bg='#131211', fg=DIM, relief='flat',
                           wrap='word', font=self.f_mono, height=10,
                           state='disabled', padx=10, pady=8,
                           insertbackground=FG)
        self.log.pack(side='left', fill='both', expand=True)
        sb = ttk.Scrollbar(self.logwrap, command=self.log.yview)
        sb.pack(side='right', fill='y')
        self.log.configure(yscrollcommand=sb.set)

        self.result = tk.Label(root, bg=BG, fg=GOOD, font=self.f_body,
                               justify='left', anchor='w', wraplength=660)

        install.set_sink(lambda m: self.queue.put(('log', m)))
        install.set_progress(lambda k, s: self.queue.put(('step', (k, s))))
        self.refresh()
        self.root.after(80, self.drain)

    # --- дрібниці ------------------------------------------------------------

    def mk_button(self, parent, text, cmd, primary=False):
        """Усі кнопки однакові на зріст; головна відрізняється лише кольором."""
        return tk.Button(
            parent, text=text, command=cmd, font=self.f_btn,
            bg=GOLD if primary else PANEL, fg='#1b1917' if primary else FG,
            activebackground=GOLD if primary else PANEL,
            activeforeground='#1b1917' if primary else GOLD,
            relief='flat', bd=0, padx=18, pady=9, width=17, cursor='hand2')

    def cfg(self):
        return self.choice.get().strip()

    def installed(self, cfg):
        if not cfg or not os.path.isfile(cfg):
            return False
        _, _, _, mod_dir = install.describe(cfg)
        return os.path.isfile(os.path.join(mod_dir, install.MARKER))

    # --- стан ----------------------------------------------------------------

    def refresh(self):
        if not self.cfgs:
            self.sub.configure(text='Не знайдено OpenMW', fg=BAD)
            self.where.configure(text=install.why_no_openmw(), fg=BAD)
            self.go.configure(state='disabled')
            self.rm.configure(state='disabled')
            return
        cfg = self.cfg()
        if not cfg or not os.path.isfile(cfg):
            return
        _, dirs, master, mod_dir = install.describe(cfg)
        if not master:
            self.sub.configure(text='Тут немає гри', fg=BAD)
            self.where.configure(
                text='У цих налаштуваннях OpenMW не вказано, де лежить '
                     'Morrowind. Спершу запусти OpenMW і покажи йому гру.',
                fg=BAD)
            self.go.configure(state='disabled')
            self.rm.configure(state='disabled')
            return

        has = self.installed(cfg)
        self.sub.configure(
            fg=DIM,
            text=('Переклад уже стоїть. Можна поставити наново — це оновить '
                  'його до свіжого.') if has else
                 ('Гру знайдено. Натисни «Встановити» — далі все зробиться '
                  'саме, це триває приблизно хвилину.'))
        self.where.configure(
            text='гра: %s\nдодатків і модів: %d' % (master, max(0, len(dirs) - 1)),
            fg=DIM)
        self.go.configure(state='normal',
                          text='Оновити' if has else 'Встановити')
        self.rm.configure(state='normal' if has else 'disabled')

    def browse(self):
        p = filedialog.askopenfilename(
            title='Знайди файл openmw.cfg',
            filetypes=[('Налаштування OpenMW', 'openmw.cfg'),
                       ('Усі файли', '*.*')])
        if p:
            if p not in self.cfgs:
                self.cfgs.append(p)
                self.choice.configure(values=self.cfgs)
            self.choice.set(p)
            self.refresh()

    def toggle(self):
        self.details_open = not self.details_open
        if self.details_open:
            self.logwrap.pack(fill='both', expand=True, padx=24, pady=(12, 16))
            self.details_btn.configure(text='Сховати')
        else:
            self.logwrap.pack_forget()
            self.details_btn.configure(text='Подробиці')

    # --- журнал і кроки -------------------------------------------------------

    def write(self, msg):
        self.log.configure(state='normal')
        self.log.insert('end', msg + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    # Успіх не затирається пропуском: крок «шрифт» виконується двічі (для
    # різних шрифтів), і якщо перший вдався, а другого шрифту просто немає,
    # рядок мусить лишитися позначеним як зроблений.
    RANK = {'run': 0, 'skip': 1, 'fail': 2, 'ok': 3}

    def mark_step(self, key, state):
        if key not in self.rows:
            return
        was = self.state.get(key)
        if was == 'ok' and state == 'skip':
            return
        self.state[key] = state
        mark, name = self.rows[key]
        look = {'run': ('▸', GOLD), 'ok': ('✓', GOOD),
                'skip': ('–', DIM), 'fail': ('✕', BAD)}[state]
        mark.configure(text=look[0], fg=look[1])
        name.configure(fg=FG if state in ('run', 'ok') else DIM)

    def reset_steps(self):
        self.state.clear()
        for mark, name in self.rows.values():
            mark.configure(text='·', fg=DIM)
            name.configure(fg=DIM)

    def drain(self):
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == 'log':
                    self.write(payload)
                else:
                    self.mark_step(*payload)
        except queue.Empty:
            pass
        self.root.after(80, self.drain)

    # --- робота ---------------------------------------------------------------

    def start(self):
        self.run(install.install_to, ok='Готово. Запускай гру як завжди — '
                                        'вона буде українською.')

    def remove(self):
        self.run(install.uninstall_from,
                 ok='Переклад вилучено. Гра знову англійською.')

    def run(self, fn, ok):
        if self.busy:
            return
        cfg = self.cfg()
        self.busy = True
        self.reset_steps()
        self.result.pack_forget()
        for b in (self.go, self.rm):
            b.configure(state='disabled')
        self.bar.pack(fill='x', padx=24, pady=(0, 10))
        self.bar.start(12)

        def work():
            try:
                code = fn(cfg)
            except Exception:                   # noqa: BLE001 - показуємо людині
                self.queue.put(('log', 'Несподівана помилка:'))
                for ln in traceback.format_exc().splitlines()[-8:]:
                    self.queue.put(('log', '  ' + ln))
                code = 1
            self.root.after(0, lambda: self.finish(code, ok))

        threading.Thread(target=work, daemon=True).start()

    def finish(self, code, ok):
        self.busy = False
        self.bar.stop()
        self.bar.pack_forget()
        if code == 0:
            self.result.configure(text=ok, fg=GOOD)
        else:
            self.result.configure(
                text='Не вийшло. Гру не змінено. Натисни «Подробиці» й надішли '
                     'цей текст автору перекладу.', fg=BAD)
            if not self.details_open:
                self.toggle()
        self.result.pack(anchor='w', fill='x', padx=24, pady=(4, 10))
        self.refresh()


def hide_console():
    """Сховати консоль, що блимає під час запуску.

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
