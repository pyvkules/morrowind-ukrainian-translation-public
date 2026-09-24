# -*- coding: utf-8 -*-
"""Вікно інсталятора: людина обирає одне з трьох і тисне одну кнопку.

Правила, за якими це зроблено:

* у вікні лише те, що людині треба вирішити. Шлях до `openmw.cfg` — не
  рішення, а подробиця, тож його видно лише тоді, коли є з чого вибирати;
* кроки звуться так, як їх розуміє гравець, а не як звуться наші скрипти;
* показуємо тільки ті кроки, які справді виконуватимуться за обраним шляхом;
* небезпечне («Вилучити переклад») стоїть окремо й вмикається лише тоді, коли
  є що вилучати.

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
OFF = '#5d574c'
GOLD = '#cba85f'
GOOD = '#8fbf6b'
BAD = '#d98b6a'

TR, ENGINE, MODS = 'tr', 'engine', 'mods'

PLANS = [
    (TR, 'Тільки українська мова',
     'Перекласти гру, яка вже стоїть.'),
    (ENGINE, 'Українська мова + OpenMW',
     'Поставити OpenMW — програму, через яку працює гра, — і перекласти.'),
    (MODS, 'Українська мова + OpenMW + моди',
     'Ще й зібрати той самий набір модів, що в автора перекладу: '
     'десятки гігабайтів і кілька годин. Потрібен обліковий запис Nexus Mods.'),
]

# ключ кроку -> (людська назва, у яких шляхах він потрібен)
STEPS = [
    ('рушій',     'Ставлю OpenMW',                      {ENGINE, MODS}),
    ('моди',      'Завантажую моди',                    {MODS}),
    ('шрифт',     'Додаю українські літери до шрифту',  {TR, ENGINE, MODS}),
    ('ядро',      'Перекладаю основну гру',             {TR, ENGINE, MODS}),
    ('плагіни',   'Перекладаю доповнення й моди',       {TR, ENGINE, MODS}),
    ('назви',     'Перекладаю назви предметів і людей', {TR, ENGINE, MODS}),
    ('теми',      'Перекладаю теми розмов',             {TR, ENGINE, MODS}),
    ('інтерфейс', 'Перекладаю меню гри',                {TR, ENGINE, MODS}),
    ('посилання', 'Зв’язую згадки в розмовах',          {TR, ENGINE, MODS}),
]
HINTS = {k: n for k, _, n in PLANS}


class App:
    def __init__(self, root):
        self.root = root
        self.queue = queue.Queue()
        self.busy = False
        self.cfgs = install.cfg_candidates()
        self.rows = {}
        self.state = {}
        self.details_open = False
        self.plan = tk.StringVar(value=TR if self.cfgs else ENGINE)

        root.title('Українізатор Morrowind')
        root.configure(bg=BG)
        root.geometry('760x660')
        root.minsize(760, 660)
        try:
            root.tk.call('tk', 'scaling', 1.3)
        except tk.TclError:
            pass

        base = tkfont.nametofont('TkDefaultFont')
        self.f_head = base.copy(); self.f_head.configure(size=16, weight='bold')
        self.f_body = base.copy(); self.f_body.configure(size=10)
        self.f_small = base.copy(); self.f_small.configure(size=9)
        self.f_btn = base.copy(); self.f_btn.configure(size=10, weight='bold')
        self.f_mono = tkfont.nametofont('TkFixedFont').copy()
        self.f_mono.configure(size=8)

        tk.Label(root, text='Українська мова для Morrowind', bg=BG, fg=GOLD,
                 font=self.f_head).pack(anchor='w', padx=24, pady=(20, 2))
        self.sub = tk.Label(root, bg=BG, fg=DIM, font=self.f_body,
                            justify='left', anchor='w', wraplength=700)
        self.sub.pack(anchor='w', padx=24, pady=(0, 14), fill='x')

        # --- що саме робимо ---------------------------------------------------
        self.opts = {}
        for key, title, note in PLANS:
            block = tk.Frame(root, bg=BG)
            block.pack(fill='x', padx=24, pady=(0, 4))
            rb = tk.Radiobutton(
                block, text=title, value=key, variable=self.plan,
                command=self.refresh, bg=BG, fg=FG, selectcolor=PANEL,
                activebackground=BG, activeforeground=GOLD, font=self.f_body,
                anchor='w', highlightthickness=0, bd=0, cursor='hand2')
            rb.pack(anchor='w')
            hint = tk.Label(block, text=note, bg=BG, fg=DIM, font=self.f_small,
                            justify='left', anchor='w', wraplength=650)
            hint.pack(anchor='w', padx=(26, 0))
            self.opts[key] = (rb, hint)

        # --- куди ставимо: подробиця, а не рішення ----------------------------
        self.wrapcfg = tk.Frame(root, bg=BG)
        self.choice = ttk.Combobox(self.wrapcfg, state='readonly',
                                   values=self.cfgs, font=self.f_mono)
        self.choice.pack(side='left', fill='x', expand=True, ipady=2)
        if self.cfgs:
            self.choice.current(0)
        self.choice.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        self.mk_button(self.wrapcfg, 'Інша гра', self.browse,
                       small=True).pack(side='left', padx=(8, 0))

        # --- кроки ------------------------------------------------------------
        self.panel = tk.Frame(root, bg=PANEL)
        self.panel.pack(fill='x', padx=24, pady=(14, 12))
        for key, title, plans in STEPS:
            line = tk.Frame(self.panel, bg=PANEL)
            mark = tk.Label(line, text='·', bg=PANEL, fg=DIM, width=2,
                            font=self.f_body)
            mark.pack(side='left')
            name = tk.Label(line, text=title, bg=PANEL, fg=DIM,
                            font=self.f_body, anchor='w')
            name.pack(side='left', fill='x', expand=True)
            self.rows[key] = (mark, name, line, plans)

        # --- дії ---------------------------------------------------------------
        act = tk.Frame(root, bg=BG)
        act.pack(fill='x', padx=24)
        self.go = self.mk_button(act, 'Встановити', self.start, primary=True)
        self.go.pack(side='left')
        self.details_btn = self.mk_button(act, 'Подробиці', self.toggle)
        self.details_btn.pack(side='left', padx=(10, 0))
        self.rm = self.mk_button(act, 'Вилучити переклад', self.remove)
        self.rm.pack(side='right')

        self.bar = ttk.Progressbar(root, mode='indeterminate')
        self.result = tk.Label(root, bg=BG, fg=GOOD, font=self.f_body,
                               justify='left', anchor='w', wraplength=700)

        self.logwrap = tk.Frame(root, bg=BG)
        self.log = tk.Text(self.logwrap, bg='#131211', fg=DIM, relief='flat',
                           wrap='word', font=self.f_mono, height=9,
                           state='disabled', padx=10, pady=8)
        self.log.pack(side='left', fill='both', expand=True)
        sb = ttk.Scrollbar(self.logwrap, command=self.log.yview)
        sb.pack(side='right', fill='y')
        self.log.configure(yscrollcommand=sb.set)

        install.set_sink(lambda m: self.queue.put(('log', m)))
        install.set_progress(lambda k, s: self.queue.put(('step', (k, s))))
        self.refresh()
        self.root.after(80, self.drain)

    # --- дрібниці --------------------------------------------------------------

    def mk_button(self, parent, text, cmd, primary=False, small=False):
        """Усі кнопки одного розміру; головна відрізняється лише кольором."""
        return tk.Button(
            parent, text=text, command=cmd,
            font=self.f_small if small else self.f_btn,
            bg=GOLD if primary else PANEL, fg='#1b1917' if primary else FG,
            activebackground=GOLD if primary else PANEL,
            activeforeground='#1b1917' if primary else GOLD,
            relief='flat', bd=0, padx=14 if small else 18,
            pady=5 if small else 9, width=11 if small else 17, cursor='hand2')

    def cfg(self):
        return self.choice.get().strip()

    def installed(self, cfg):
        if not cfg or not os.path.isfile(cfg):
            return False
        _, _, _, mod_dir = install.describe(cfg)
        return os.path.isfile(os.path.join(mod_dir, install.MARKER))

    def set_enabled(self, key, ok, why):
        rb, hint = self.opts[key]
        rb.configure(state='normal' if ok else 'disabled',
                     fg=FG if ok else OFF)
        hint.configure(text=HINTS[key] if ok else why, fg=DIM if ok else OFF)

    # --- стан -------------------------------------------------------------------

    def refresh(self):
        game = install.game_data_dir()
        have = bool(self.cfgs)

        self.set_enabled(TR, have, 'спершу потрібен OpenMW')
        self.set_enabled(ENGINE, bool(game) and not have,
                         'OpenMW уже стоїть' if have else 'не знайдено гри')
        self.set_enabled(MODS, bool(game), 'не знайдено гри')
        plan = self.plan.get()
        if self.opts[plan][0].cget('state') == 'disabled':
            plan = TR if have else (MODS if game else TR)
            self.plan.set(plan)

        for key, title, plans in STEPS:
            line = self.rows[key][2]
            if plan in plans and not (key == 'рушій' and have):
                line.pack(fill='x', padx=14, pady=3)
            else:
                line.pack_forget()

        if have and len(self.cfgs) > 1:
            self.wrapcfg.pack(fill='x', padx=24, pady=(10, 0), before=self.panel)
        else:
            self.wrapcfg.pack_forget()

        if not game and not have:
            self.sub.configure(text=install.why_no_openmw().splitlines()[0],
                               fg=BAD)
            self.go.configure(state='disabled')
            self.rm.configure(state='disabled')
            return

        has_tr = have and self.installed(self.cfg())
        self.sub.configure(fg=DIM, text={
            TR: ('Переклад уже стоїть — можна оновити до свіжого.' if has_tr
                 else 'Гру знайдено. Це займе близько хвилини.'),
            ENGINE: 'OpenMW ще немає — поставлю сам. Windows один раз запитає '
                    'дозвіл: це звичайне встановлення програми.',
            MODS: 'Найдовший шлях. Спершу моди, тоді переклад — інакше моди '
                  'перекрили б його.',
        }[plan])
        self.go.configure(
            state='normal',
            text='Оновити' if (plan == TR and has_tr) else 'Встановити')
        self.rm.configure(state='normal' if has_tr else 'disabled')

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
            self.logwrap.pack(fill='both', expand=True, padx=24, pady=(10, 16))
            self.details_btn.configure(text='Сховати')
        else:
            self.logwrap.pack_forget()
            self.details_btn.configure(text='Подробиці')

    # --- журнал і кроки -----------------------------------------------------------

    def write(self, msg):
        self.log.configure(state='normal')
        self.log.insert('end', msg + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def mark_step(self, key, state):
        if key not in self.rows:
            return
        # успіх не затирається пропуском: крок шрифту виконується кілька разів,
        # і якщо котрогось шрифту в системі немає, рядок має лишитися зробленим
        if self.state.get(key) == 'ok' and state == 'skip':
            return
        self.state[key] = state
        mark, name = self.rows[key][0], self.rows[key][1]
        look = {'run': ('▸', GOLD), 'ok': ('✓', GOOD),
                'skip': ('–', DIM), 'fail': ('✕', BAD)}[state]
        mark.configure(text=look[0], fg=look[1])
        name.configure(fg=FG if state in ('run', 'ok') else DIM)

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

    # --- робота --------------------------------------------------------------------

    def start(self):
        plan = self.plan.get()
        done = {
            TR: 'Готово. Запускай гру як завжди — вона буде українською.',
            ENGINE: 'Готово. У меню «Пуск» з’явився OpenMW — запускай його.',
            MODS: 'Готово. Запускай OpenMW: це та сама збірка, що в автора '
                  'перекладу, українською.',
        }[plan]
        self.run(lambda cfg: self.chain(plan, cfg), ok=done)

    def chain(self, plan, cfg):
        """Порядок кроків тут не випадковий.

        Рушій перший: без його налаштувань нема куди ставити. Моди другі: вони
        переписують профіль цілком. Переклад останній, бо його тека мусить
        лишитися в списку найостаннішою — інакше моди її перекриють.
        """
        if plan in (ENGINE, MODS) and not self.cfgs:
            cfg = install.install_engine()
            if not cfg:
                return 1
            self.cfgs = install.cfg_candidates() or [cfg]
            self.root.after(0, lambda: self.choice.configure(values=self.cfgs))
            self.root.after(0, lambda: self.choice.set(cfg))
        if plan == MODS and install.install_modlist(cfg):
            return 1
        return install.install_to(cfg)

    def remove(self):
        self.run(install.uninstall_from,
                 ok='Переклад вилучено. Гра знову англійською.')

    def run(self, fn, ok):
        if self.busy:
            return
        cfg = self.cfg()
        self.busy = True
        self.state.clear()
        for key in self.rows:
            self.rows[key][0].configure(text='·', fg=DIM)
            self.rows[key][1].configure(fg=DIM)
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
        self.result.pack(anchor='w', fill='x', padx=24, pady=(4, 8))
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
