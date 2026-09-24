# -*- coding: utf-8 -*-
"""Вікно інсталятора.

Правила, за якими це зроблено:

* у вікні лише те, що людині треба вирішити, і те, що вже сталося. Жодних
  пояснень, заспокоєнь і розповідей програми про саму себе;
* підписи — іменники, не речення: «Основна гра», а не «Перекладаю основну
  гру». Число праворуч каже решту;
* геометрія однакова в усіх станах. Картки не зникають під час роботи, а
  результат пишеться туди ж, де стояв заголовок кроків, — ніщо не стрибає
  під курсором;
* розмір сталий, тож усе розкладено в пікселях, а шрифти задано від'ємним
  розміром — це теж пікселі, і вигляд не залежить від масштабу в системі.

Панель кроків — полотно, а не набір віджетів: крізь неї проходить
вертикальна лінія поступу, а прозорого тла Tk не має.

Консольний режим лишається: exe з будь-яким аргументом вікна не відкриває.
"""
import os
import queue
import sys
import threading
import traceback

import tkinter as tk
from tkinter import filedialog, font as tkfont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import install                                  # noqa: E402

# --- фарби -------------------------------------------------------------------
# Холодне тло й тепла позолота: саме це поєднання дає впізнаваний Морровінд,
# а не коричневий колір сам собою.
BG, SURF, SEL, OFFBG = '#101216', '#181B21', '#23262E', '#14161A'
LINE, TICK, SOFT = '#2B2F38', '#3A3E48', '#21242B'
STRIP, FOOT, LOGBG, TRACK = '#14171C', '#0C0E11', '#0A0C0E', '#1A1D23'
GRAD_TOP, EMBBG = '#1A1E25', '#161A20'
TEXT, MUTED, LABEL = '#E3DAC2', '#9C947E', '#8A8371'
OFF, DEAD, GHOST = '#6F6A5C', '#5E5A4E', '#4A4740'
GOLD, GOLDTOP, GOLDDIM, GOLDINK = '#D3B26B', '#EBCE8E', '#6A5A32', '#14120C'
GOOD, GOODDIM, GOODBG = '#93C47D', '#4C7A3C', '#14201A'
BAD, BADDIM, BADBG = '#DE8C67', '#7A4A32', '#201410'
BUSYBG, BUSYTOP, DEADEDGE = '#3A3526', '#4A442F', '#1F2229'

PAD = 28                    # бічні поля
W = 760                     # ширина стала; змінюється тільки висота
H_PLAIN, H_LOG = 680, 900   # без подробиць і з ними

TR, ENGINE, MODS = 'tr', 'engine', 'mods'

# план -> (назва, підказка). Пояснення живе в підказці, а не у вікні: у списку
# видно самі назви, а подробиця приходить тоді, коли на неї дивляться.
PLANS = [
    (TR, 'Переклад',
     'Гра вже стоїть — лишається перекласти. Хвилина.'),
    (ENGINE, 'Переклад + OpenMW',
     'OpenMW стане поруч зі старою грою й читатиме ті самі файли. '
     'Кілька хвилин.'),
    (MODS, 'Переклад + OpenMW + моди автора',
     'Той самий набір модів, у який грає автор перекладу. Кілька годин, '
     'десятки гігабайтів, і потрібен обліковий запис на Nexus Mods.'),
]

# ключ кроку -> (підпис, у яких планах потрібен)
STEPS = [
    ('рушій',     'OpenMW',            {ENGINE, MODS}),
    ('моди',      'Моди',              {MODS}),
    ('шрифт',     'Шрифт',             {TR, ENGINE, MODS}),
    ('ядро',      'Основна гра',       {TR, ENGINE, MODS}),
    ('плагіни',   'Доповнення й моди', {TR, ENGINE, MODS}),
    ('назви',     'Назви',             {TR, ENGINE, MODS}),
    ('теми',      'Теми розмов',       {TR, ENGINE, MODS}),
    ('інтерфейс', 'Меню',              {TR, ENGINE, MODS}),
    ('посилання', 'Згадки в розмовах', {TR, ENGINE, MODS}),
]
TITLES = dict((k, t) for k, t, _ in STEPS)

# стан кроку -> (значок, колір значка, колір підпису, жирність)
MARK = {
    'todo': ('·', OFF, MUTED, 'normal'),
    'run': ('▸', GOLD, TEXT, 'bold'),
    'ok': ('✓', GOOD, TEXT, 'normal'),
    'skip': ('–', OFF, MUTED, 'normal'),
    'fail': ('✕', BAD, TEXT, 'bold'),
    'never': ('·', GHOST, OFF, 'normal'),
}

ROW = 22          # висота рядка кроку
FIRST = 23        # центр першого рядка від верху полотна
SPINE = 22        # по цій вертикалі стоять значки й іде лінія поступу


class App:
    def __init__(self, root):
        self.root = root
        self.queue = queue.Queue()
        self.busy = False
        self.cfgs = install.cfg_candidates()
        self.state = {}
        self.visible = []
        self.items = {}
        self.spine = None
        self.details = False
        self.plan = tk.StringVar(value=TR if self.cfgs else ENGINE)

        root.title('Українізатор Morrowind')
        root.configure(bg=BG)
        root.resizable(False, False)
        self.resize(H_PLAIN)
        self.make_fonts()

        self.build_header()
        self.build_rules()
        self.build_pathbar()
        self.build_footer()          # перед тілом: він тримається за низ
        self.build_body()

        install.set_sink(lambda m: self.queue.put(('log', m)))
        install.set_progress(
            lambda k, s, n=None: self.queue.put(('step', (k, s, n))))
        root.bind('<Return>', lambda e: self.start())
        root.bind('<Escape>', lambda e: root.destroy())
        root.bind('<Up>', lambda e: self.move(-1))
        root.bind('<Down>', lambda e: self.move(1))

        self.refresh()
        threading.Thread(target=self.read_stamp, daemon=True).start()
        root.after(80, self.drain)

    # --- каркас ----------------------------------------------------------------

    def resize(self, height):
        self.root.geometry('%dx%d' % (W, height))
        self.root.minsize(W, height)
        self.root.maxsize(W, height)

    def make_fonts(self):
        def f(family, px, weight='normal'):
            return tkfont.Font(family=family, size=-px, weight=weight)

        self.f_title = f('Georgia', 25)
        self.f_emblem = f('Georgia', 27)
        self.f_glyph = f('Segoe UI', 15)
        self.f_card = f('Segoe UI', 14, 'bold')
        self.f_step = f('Segoe UI', 13)
        self.f_step_b = f('Segoe UI', 13, 'bold')
        self.f_small = f('Segoe UI', 11)
        self.f_label = f('Georgia', 13)
        self.f_btn = f('Segoe UI', 13)
        self.f_go = f('Segoe UI', 13, 'bold')
        self.f_mono = f('Consolas', 11)

    def build_header(self):
        """Заголовок на градієнті. Квадрат із літерою — він же індикатор стану."""
        c = tk.Canvas(self.root, height=88, width=W, highlightthickness=0,
                      bd=0, bg=BG)
        c.pack(fill='x')
        self.head = c

        top, bot = self.root.winfo_rgb(GRAD_TOP), self.root.winfo_rgb(BG)
        for y in range(88):
            k = y / 87.0
            c.create_line(0, y, W, y, fill='#%02x%02x%02x' % tuple(
                int((top[i] * (1 - k) + bot[i] * k) / 257) for i in range(3)))

        self.emb_box = c.create_rectangle(PAD, 22, PAD + 46, 68,
                                          outline=GOLDDIM, fill=EMBBG)
        self.emb_txt = c.create_text(PAD + 23, 45, text='Є',
                                     font=self.f_emblem, fill=GOLD)
        c.create_text(PAD + 62, 45, anchor='w', text='Morrowind українською',
                      font=self.f_title, fill=GOLD)
        self.stamp = c.create_text(W - PAD, 45, anchor='e', text='',
                                   justify='right', font=self.f_small, fill=OFF)

    def build_rules(self):
        tk.Frame(self.root, height=1, bg=GOLDDIM).pack(fill='x')
        tk.Frame(self.root, height=1, bg=BG).pack(fill='x')
        track = tk.Frame(self.root, height=3, bg=TRACK)
        track.pack(fill='x')
        track.pack_propagate(False)
        self.fill = tk.Frame(track, bg=GOLD)
        self.fill.place(x=0, y=0, relheight=1, relwidth=0)

    def build_pathbar(self):
        wrap = tk.Frame(self.root, bg=STRIP)
        wrap.pack(fill='x')
        row = tk.Frame(wrap, bg=STRIP)
        row.pack(fill='x', padx=PAD, pady=9)
        self.path = tk.Label(row, bg=STRIP, fg=MUTED, font=self.f_mono,
                             anchor='w')
        self.path.pack(side='left', fill='x', expand=True)
        self.change = tk.Label(row, text='Змінити', bg=STRIP, fg=GOLD,
                               font=self.f_small, cursor='hand2')
        self.change.pack(side='left', padx=(12, 0))
        self.change.bind('<Button-1>', lambda e: self.browse())
        tk.Frame(wrap, height=1, bg=SOFT).pack(fill='x')

    def build_body(self):
        box = tk.Frame(self.root, bg=BG)
        box.pack(fill='x', padx=PAD, pady=(20, 0))

        self.cards = {}
        for i, (key, title, tip) in enumerate(PLANS):
            card = Card(box, key, title, tip, self)
            card.pack(fill='x', pady=(0 if not i else 8, 0))
            self.cards[key] = card

        self.label = tk.Label(box, text='Кроки', bg=BG, fg=LABEL,
                              font=self.f_label, anchor='w')
        self.label.pack(fill='x', pady=(20, 10))

        self.panel = tk.Canvas(box, width=W - 2 * PAD, highlightthickness=0,
                               bd=0, bg=SURF)
        self.panel.pack(fill='x')

        # Рядок для Steam. З'являється тільки після успіху — доти показувати
        # нема чого.
        self.steam = tk.Frame(box, bg=BG)
        tk.Label(self.steam, text='Ярлик для Steam', bg=BG, fg=LABEL,
                 font=self.f_label).pack(side='left')
        self.steam_copy = tk.Label(self.steam, text='Копіювати', bg=BG,
                                   fg=GOLD, font=self.f_small, cursor='hand2')
        self.steam_copy.pack(side='right')
        self.steam_path = tk.Label(self.steam, text='', bg=BG, fg=MUTED,
                                   font=self.f_mono, anchor='w')
        self.steam_path.pack(side='left', fill='x', expand=True, padx=(12, 12))
        self.steam_copy.bind('<Button-1>', lambda e: self.copy_path())
        Tip([self.steam, self.steam_path, self.steam_copy],
            'Steam → Ігри → Додати гру не зі Steam → Огляд. Вкажи цей файл і '
            'назви його Morrowind. Далі Steam рахуватиме години сам.', self)

        self.logwrap = tk.Frame(box, bg=BG)
        self.log = tk.Text(self.logwrap, bg=LOGBG, fg='#8E8674', relief='flat',
                           wrap='word', font=self.f_mono, height=11,
                           state='disabled', padx=12, pady=10,
                           highlightthickness=1, highlightbackground=SOFT)
        self.log.pack(fill='both', expand=True)

    def build_footer(self):
        bar = tk.Frame(self.root, bg=FOOT)
        bar.pack(side='bottom', fill='x')
        tk.Frame(bar, height=1, bg=LINE).pack(fill='x')
        row = tk.Frame(bar, bg=FOOT)
        row.pack(fill='x', padx=PAD, pady=15)
        self.rm = Button(row, 'Вилучити', self.remove, self)
        self.rm.pack(side='left')
        self.more = Button(row, 'Подробиці', self.toggle, self)
        self.more.pack(side='left', padx=(10, 0))
        self.go = Button(row, 'Встановити', self.start, self, primary=True)
        self.go.pack(side='right')

    # --- шапка й поступ ---------------------------------------------------------

    def emblem(self, kind):
        fg, edge, fill, glyph, font = {
            'brand': (GOLD, GOLDDIM, EMBBG, 'Є', self.f_emblem),
            'ok': (GOOD, GOODDIM, GOODBG, '✓', self.f_title),
            'fail': (BAD, BADDIM, BADBG, '✕', self.f_title)}[kind]
        self.head.itemconfigure(self.emb_box, outline=edge, fill=fill)
        self.head.itemconfigure(self.emb_txt, text=glyph, fill=fg, font=font)

    def read_stamp(self):
        """Версія й повнота перекладу.

        У зібраному exe це читання `build.json`, а з репозиторію — підрахунок
        усіх зрізів, тобто секунди. Тому окремим потоком.
        """
        try:
            line = install.version_line()
        except Exception:                       # noqa: BLE001 - лише підпис
            return
        head, _, tail = line.partition(' · ')
        self.queue.put(('stamp', head + ('\n' + tail if tail else '')))

    def progress(self, frac, color=GOLD):
        self.fill.configure(bg=color)
        self.fill.place_configure(relwidth=max(0.0, min(1.0, frac)))

    # --- панель кроків ----------------------------------------------------------

    def draw_panel(self):
        c = self.panel
        c.delete('all')
        self.items, self.spine = {}, None
        n = len(self.visible)
        h, w = 12 + ROW * n + 13, W - 2 * PAD
        c.configure(height=h)

        for x, dx in ((0, 7), (w - 1, -7)):             # кутові засічки
            for y, dy in ((0, 7), (h - 1, -7)):
                c.create_line(x, y, x + dx, y, fill=TICK)
                c.create_line(x, y, x, y + dy, fill=TICK)

        if n > 1:
            c.create_line(SPINE, FIRST, SPINE, FIRST + ROW * (n - 1), fill=LINE)
        for i, key in enumerate(self.visible):
            y = FIRST + ROW * i
            glyph, gc, nc, _ = MARK['todo']
            self.items[key] = (
                c.create_text(SPINE, y, text=glyph, fill=gc, font=self.f_glyph),
                c.create_text(40, y, anchor='w', text=TITLES[key], fill=nc,
                              font=self.f_step),
                c.create_text(w - 16, y, anchor='e', text='', fill=LABEL,
                              font=self.f_small))

    def mark_step(self, key, state, note=None):
        # успіх не затирається пропуском: крок шрифту виконується кілька разів,
        # і якщо котрогось шрифту в системі немає, рядок має лишитися зробленим
        if self.state.get(key) == 'ok' and state == 'skip':
            return
        self.state[key] = state
        if key in self.items:
            glyph, gc, nc, weight = MARK[state]
            gid, nid, note_id = self.items[key]
            self.panel.itemconfigure(gid, text=glyph, fill=gc)
            self.panel.itemconfigure(
                nid, fill=nc,
                font=self.f_step_b if weight == 'bold' else self.f_step)
            if note:
                self.panel.itemconfigure(
                    note_id, text=note,
                    fill={'run': GOLD, 'fail': BAD}.get(state, LABEL))

        total = max(1, len(self.visible))
        done = sum(1 for k in self.visible
                   if self.state.get(k) in ('ok', 'skip'))
        self.progress(float(done) / total)
        self.label.configure(text='%d з %d' % (done, len(self.visible)))
        self.paint_spine()

    def paint_spine(self):
        """Пройдена частина вертикалі — це шкала поступу збоку від списку."""
        if self.spine:
            self.panel.delete(self.spine)
            self.spine = None
        last, color = -1, GOODDIM
        for i, key in enumerate(self.visible):
            st = self.state.get(key)
            if st == 'fail':
                last, color = i, BADDIM
                break
            if st in ('ok', 'skip', 'run'):
                last = i
        if last > 0:
            self.spine = self.panel.create_line(
                SPINE, FIRST, SPINE, FIRST + ROW * last, fill=color)
            self.panel.tag_lower(self.spine)

    # --- стан -------------------------------------------------------------------

    def cfg(self):
        return self.path.cget('text').strip() if self.cfgs else ''

    def installed(self, cfg):
        if not cfg or not os.path.isfile(cfg):
            return False
        _, _, _, mod_dir = install.describe(cfg)
        return os.path.isfile(os.path.join(mod_dir, install.MARKER))

    def move(self, delta):
        keys = [k for k, _, _ in PLANS if self.cards[k].enabled]
        if self.busy or not keys:
            return
        i = keys.index(self.plan.get()) if self.plan.get() in keys else 0
        self.plan.set(keys[(i + delta) % len(keys)])
        self.refresh()

    def refresh(self):
        game = install.game_data_dir()
        have = bool(self.cfgs)

        if have and not self.path.cget('text'):
            self.path.configure(text=self.cfgs[0])
        elif not have:
            exes = install.morrowind_exes()
            self.path.configure(text=(os.path.dirname(exes[0]) if exes
                                      else 'гру не знайдено'))
        self.change.configure(fg=GOLD if (have or game) else OFF)

        has_tr = have and self.installed(self.cfg())
        self.cards[TR].set(have, 'потрібен OpenMW')
        self.cards[ENGINE].set(bool(game) and not have, 'уже є')
        self.cards[MODS].set(bool(game), 'гру не знайдено')
        if has_tr:
            self.cards[TR].state_word('стоїть')

        plan = self.plan.get()
        if not self.cards[plan].enabled:
            plan = TR if have else (ENGINE if game else TR)
            self.plan.set(plan)
        for key, card in self.cards.items():
            card.select(key == plan)

        self.visible = [k for k, _, plans in STEPS
                        if plan in plans and not (k == 'рушій' and have)]
        self.state.clear()
        self.draw_panel()
        self.label.configure(text='Кроки', fg=LABEL)
        self.progress(0)
        self.emblem('brand')

        self.go.set_text('Оновити' if (plan == TR and has_tr) else 'Встановити')
        self.go.set_command(self.start)
        self.go.enable(bool(game) or have)
        self.rm.set_text('Вилучити')
        self.rm.set_command(self.remove)
        self.rm.enable(has_tr)

    def browse(self):
        p = filedialog.askopenfilename(
            title='Знайди файл openmw.cfg',
            filetypes=[('Налаштування OpenMW', 'openmw.cfg'),
                       ('Усі файли', '*.*')])
        if p:
            if p not in self.cfgs:
                self.cfgs.append(p)
            self.path.configure(text=p)
            self.refresh()

    # --- журнал -----------------------------------------------------------------

    def write(self, msg):
        self.log.configure(state='normal')
        self.log.insert('end', msg + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def copy_report(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log.get('1.0', 'end').strip())
        self.rm.set_text('Скопійовано')

    def toggle(self):
        self.details = not self.details
        if self.details:
            self.logwrap.pack(fill='x', pady=(20, 0))
            self.more.set_text('Сховати')
            self.resize(H_LOG)
        else:
            self.logwrap.pack_forget()
            self.more.set_text('Подробиці')
            self.resize(H_PLAIN)

    def drain(self):
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == 'log':
                    self.write(payload)
                elif kind == 'stamp':
                    self.head.itemconfigure(self.stamp, text=payload)
                else:
                    self.mark_step(*payload)
        except queue.Empty:
            pass
        self.root.after(80, self.drain)

    # --- робота -----------------------------------------------------------------

    def start(self):
        if self.busy or not self.go.enabled:
            return
        plan = self.plan.get()
        self.run(lambda cfg: self.chain(plan, cfg))

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
            self.root.after(0, lambda: self.path.configure(text=cfg))
        if plan == MODS and install.install_modlist(cfg):
            return 1
        return install.install_to(cfg)

    def remove(self):
        if self.busy or not self.rm.enabled:
            return
        self.run(install.uninstall_from)

    def run(self, fn):
        self.busy = True
        self.state.clear()
        self.draw_panel()
        self.emblem('brand')
        self.progress(0)
        self.go.enable(False)
        self.rm.enable(False)
        self.go.set_text('Працюю…', busy=True)
        cfg = self.cfg()

        def work():
            try:
                code = fn(cfg)
            except Exception:                   # noqa: BLE001 - показуємо людині
                self.queue.put(('log', 'Несподівана помилка:'))
                for ln in traceback.format_exc().splitlines()[-8:]:
                    self.queue.put(('log', '  ' + ln))
                code = 1
            self.root.after(0, lambda: self.finish(code))

        threading.Thread(target=work, daemon=True).start()

    def finish(self, code):
        self.busy = False
        total = len(self.visible)
        done = sum(1 for k in self.visible
                   if self.state.get(k) in ('ok', 'skip'))

        if code == 0:
            self.emblem('ok')
            self.progress(1.0, GOOD)
            self.label.configure(fg=GOOD,
                                 text='Готово · %d з %d' % (done, total))
            self.go.set_text('Запустити', busy=False)
            self.go.set_command(self.launch)
            self.rm.enable(True)
            self.show_steam()
        else:
            self.emblem('fail')
            self.progress(float(done) / max(1, total), BAD)
            self.label.configure(fg=BAD,
                                 text='Не вийшло · %d з %d' % (done, total))
            self.go.set_text('Ще раз', busy=False)
            self.go.set_command(self.start)
            self.rm.set_text('Копіювати звіт')
            self.rm.set_command(self.copy_report)
            self.rm.enable(True)
            if not self.details:
                self.toggle()

        self.go.enable(True)
        self.paint_spine()

    def show_steam(self):
        """Готовий рядок запуску: людині лишається вставити його в Steam."""
        exes = install.openmw_exes()
        if not exes:
            return
        self.steam_path.configure(text='"%s"' % exes[0])
        self.steam.pack(fill='x', pady=(16, 0), after=self.panel)

    def copy_path(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.steam_path.cget('text'))
        self.steam_copy.configure(text='Скопійовано', fg=GOOD)

    def launch(self):
        """Після успіху найкорисніша дія — запустити гру, а не закрити вікно."""
        exes = install.openmw_exes()
        exe = exes[0] if exes else None
        if exe and os.path.isfile(exe):
            os.startfile(exe)                   # noqa: S606 - свій же рушій
        self.root.destroy()


class Card(tk.Frame):
    """Варіант установлення: смужка з перемикачем і назвою. Решта — в підказці."""

    def __init__(self, parent, key, title, tip, app):
        tk.Frame.__init__(self, parent, bg=SURF)
        self.app, self.key, self.enabled = app, key, True

        self.edge = tk.Frame(self, width=3, bg=SURF)
        self.edge.pack(side='left', fill='y')
        inner = tk.Frame(self, bg=SURF)
        inner.pack(side='left', fill='both', expand=True, padx=(14, 16),
                   pady=(12, 13))

        # Власний індикатор, а не tk.Radiobutton: рідний малюється світлим
        # квадратом і на темному тлі виглядає як чужий елемент.
        self.dot = tk.Canvas(inner, width=14, height=17, highlightthickness=0,
                             bd=0, bg=SURF)
        self.dot.pack(side='left')
        self.ring = self.dot.create_oval(1, 2, 13, 14, outline=OFF)
        self.pip = self.dot.create_oval(4, 5, 10, 11, outline='', fill='')

        self.word = tk.Label(inner, text='', bg=SURF, fg=DEAD, font=app.f_small)
        self.word.pack(side='right')
        self.title = tk.Label(inner, text=title, bg=SURF, fg=TEXT,
                              font=app.f_card, anchor='w')
        self.title.pack(side='left', fill='x', expand=True, padx=(13, 0))

        self.parts = [self, inner, self.dot, self.title, self.word]
        for w in self.parts:
            w.bind('<Button-1>', self.click)
        Tip(self.parts, tip, app)

    def click(self, _event=None):
        if self.enabled and not self.app.busy:
            self.app.plan.set(self.key)
            self.app.refresh()

    def select(self, on):
        bg = SEL if on else (SURF if self.enabled else OFFBG)
        for w in self.parts:
            w.configure(bg=bg)
        self.edge.configure(bg=GOLD if on else bg)
        self.dot.itemconfigure(self.ring, outline=GOLD if on else OFF)
        self.dot.itemconfigure(self.pip, fill=GOLD if on else '')
        self.configure(cursor='hand2' if self.enabled else '')

    def set(self, enabled, why):
        self.enabled = enabled
        self.title.configure(fg=TEXT if enabled else OFF)
        self.word.configure(text='' if enabled else why)

    def state_word(self, text):
        self.word.configure(text=text)


class Tip:
    """Підказка під карткою.

    Пояснення варіанта живе тут, а не у вікні: у списку стоять самі назви, а
    подробиця приходить тоді, коли на неї дивляться. Затримки з обох боків —
    щоб підказка не блимала, коли курсор переходить між частинами картки.
    """

    def __init__(self, widgets, text, app):
        self.text, self.app = text, app
        self.win = self.show_id = self.hide_id = None
        for w in widgets:
            w.bind('<Enter>', self.enter, add='+')
            w.bind('<Leave>', self.leave, add='+')

    def stop(self, which):
        job = getattr(self, which)
        if job:
            self.app.root.after_cancel(job)
            setattr(self, which, None)

    def enter(self, _e=None):
        self.stop('hide_id')
        if not self.win and not self.show_id:
            self.show_id = self.app.root.after(450, self.show)

    def leave(self, _e=None):
        self.stop('show_id')
        self.hide_id = self.app.root.after(120, self.hide)

    def show(self):
        self.show_id = None
        if self.win or not self.text:
            return
        self.win = tk.Toplevel(self.app.root)
        self.win.wm_overrideredirect(True)
        self.win.configure(bg=TICK)
        tk.Label(self.win, text=self.text, bg=SURF, fg=TEXT, justify='left',
                 font=self.app.f_small, wraplength=360, padx=12,
                 pady=9).pack(padx=1, pady=1)
        self.win.wm_geometry('+%d+%d' % (self.app.root.winfo_pointerx() + 14,
                                         self.app.root.winfo_pointery() + 20))

    def hide(self):
        self.hide_id = None
        if self.win:
            self.win.destroy()
            self.win = None


class Button(tk.Frame):
    """Кнопка сталої висоти: tk.Button міряє себе в літерах, а не пікселях."""

    def __init__(self, parent, text, command, app, primary=False):
        tk.Frame.__init__(self, parent, height=44, bg=FOOT)
        self.pack_propagate(False)
        self.app, self.cmd, self.primary = app, command, primary
        self.enabled, self.busy = True, False
        self.bevel = tk.Frame(self, height=1, bg=GOLDTOP)
        self.label = tk.Label(self, text=text, cursor='hand2')
        self.label.pack(fill='both', expand=True)
        self.label.bind('<Button-1>', lambda e: self.fire())
        self.bind('<Button-1>', lambda e: self.fire())
        self.set_text(text)

    def fire(self):
        if self.enabled and self.cmd:
            self.cmd()

    def set_command(self, fn):
        self.cmd = fn

    def set_text(self, text, busy=None):
        if busy is not None:
            self.busy = busy
        self.label.configure(
            text=text, font=self.app.f_go if self.primary else self.app.f_btn)
        pad = 34 if self.primary else 18
        self.configure(width=self.label.winfo_reqwidth() + 2 * pad)
        self.paint()

    def enable(self, on):
        self.enabled = on
        self.label.configure(cursor='hand2' if on else '')
        self.paint()

    def paint(self):
        if self.primary:
            live = self.enabled and not self.busy
            bg, fg = (GOLD, GOLDINK) if live else (BUSYBG, LABEL)
            self.bevel.configure(bg=GOLDTOP if live else BUSYTOP)
            self.bevel.place(x=0, y=0, relwidth=1)
            edge, thick = bg, 0
        elif self.enabled:
            bg, fg, edge, thick = SURF, MUTED, LINE, 1
        else:
            bg, fg, edge, thick = OFFBG, DEAD, DEADEDGE, 1
        self.configure(bg=bg, highlightthickness=thick, highlightbackground=edge)
        self.label.configure(bg=bg, fg=fg)


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
