# -*- coding: utf-8 -*-
"""Що встановлювач робить із чужими файлами: три поламки, за які нам писали.

Усі три знайшлися з одного звернення: «зламав мені усі сейви, шрифт крякозябли,
і видалити нормально не можна». Перевірки тут про те, чого гравець нам не
довіряв робити, і ганяти їх можна без гри: `openmw.cfg` і `settings.cfg` -
звичайні текстові файли.

    py installer/test_cfg.py

Вихід 1, якщо хоч одна перевірка впала.
"""
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.argv = [sys.argv[0]]        # install.py читає sys.argv на імпорті
import install

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                              errors='replace', write_through=True)
install.set_sink(lambda msg='': None)

FAIL = []


def check(name, ok, note=''):
    print('%-4s %s%s' % ('ОК' if ok else 'ПАДЕ', name,
                         '' if ok else '  <- ' + note))
    if not ok:
        FAIL.append(name)


def mkcfg(root, body_bytes):
    """openmw.cfg саме з тими байтами, які дав гравець."""
    path = os.path.join(root, 'openmw.cfg')
    with open(path, 'wb') as f:
        f.write(body_bytes)
    return path


# Шлях із кириличним іменем користувача, записаний системною сторінкою Windows.
# Саме так його пише лаунчер OpenMW на українській або російській Windows, і
# саме цього байта UTF-8 прочитати не може.
CYR = u'C:\\Users\\Іван\\Documents\\My Games\\OpenMW\\моди\\Тамріель'
CYR_BYTES = CYR.encode('cp1251')


def test_keeps_foreign_bytes():
    """Правка конфігу не сміє зачіпати чужі рядки.

    Було: read_cfg читав із errors='replace', кожен не-UTF-8 байт ставав
    U+FFFD, і ми писали файл назад уже без тих шляхів. Гравець із кириличним
    іменем користувача втрачав власні моди, профіль і теку сейвів - з його
    боку це «переклад зламав мені все».
    """
    root = tempfile.mkdtemp()
    try:
        cfg = mkcfg(root, b'encoding=win1252\ndata="' + CYR_BYTES + b'"\n')
        install.rewrite_cfg(cfg, os.path.join(root, 'ukr'))
        got = open(cfg, 'rb').read()
        check('чужі байти в openmw.cfg лишилися цілі', CYR_BYTES in got,
              'шлях гравця зіпсовано')
        check('наш рядок дописано останнім',
              got.rstrip().endswith(b'"' + os.path.join(root, 'ukr').encode() + b'"'))
        check('encoding виправлено на win1251', b'encoding=win1251' in got)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_heals_damaged_cfg():
    """Конфіг, який зіпсувала давніша версія, вертаємо з копії.

    Слід поломки - U+FFFD. Самі байти вже не відновити, зате копія лежить
    поруч: її знімає backup_once перед першою нашою правкою.
    """
    root = tempfile.mkdtemp()
    try:
        cfg = mkcfg(root, u'data="C:\\\\Users\\\\\ufffd\ufffd\ufffd\\\\mods"\n'
                    .encode('utf-8'))
        with open(cfg + '.ukr-backup', 'wb') as f:
            f.write(b'data="' + CYR_BYTES + b'"\n')
        install.rewrite_cfg(cfg, os.path.join(root, 'ukr'))
        got = open(cfg, 'rb').read()
        check('зіпсований конфіг відкочено з копії', CYR_BYTES in got,
              'шлях не вернувся')
        check('після відкоту слідів поломки немає',
              u'\ufffd'.encode('utf-8') not in got)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_locale_keeps_foreign_bytes():
    """Те саме для settings.cfg: там теж бувають кириличні шляхи."""
    root = tempfile.mkdtemp()
    try:
        path = os.path.join(root, 'settings.cfg')
        with open(path, 'wb') as f:
            f.write(b'[General]\nscreenshot path = ' + CYR_BYTES + b'\n')
        install.set_locale(path)
        got = open(path, 'rb').read()
        check('чужі байти в settings.cfg лишилися цілі', CYR_BYTES in got,
              'шлях гравця зіпсовано')
        check('мову меню дописано', install.LOCALE_LINE.encode('utf-8') in got)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_uninstall_spares_foreign_fonts():
    """Видалення сміє зносити лише ті шрифти, які поклали ми.

    Було: `[xml] + glob_ttf(fdir)`, тобто кожен .ttf із теки шрифтів поруч із
    openmw.cfg. А це звичайне місце, де гравці тримають власні шрифти.
    """
    root = tempfile.mkdtemp()
    try:
        mod = os.path.join(root, 'ukr')
        os.makedirs(os.path.join(mod, 'Fonts'))
        for name in ('Pelagiad.ttf', 'Pelagiad.omwfont'):
            io.open(os.path.join(mod, 'Fonts', name), 'w',
                    encoding='utf-8').write(u'<Codes></Codes>')
        fdir = os.path.join(root, 'Fonts')
        os.makedirs(fdir)
        mine = os.path.join(fdir, 'Pelagiad.ttf')
        alien = os.path.join(fdir, 'MyOwnFont.ttf')
        for p in (mine, alien):
            open(p, 'wb').write(b'ttf')
        io.open(os.path.join(fdir, 'openmw_font.xml'), 'w',
                encoding='utf-8').write(install.TES3MP_XML % ('Pelagiad', ''))
        mkcfg(root, b'data="' + mod.encode() + b'"\n')

        install.tes3mp_font(os.path.join(root, 'openmw.cfg'), mod, remove=True)
        check('чужий шрифт гравця лишився', os.path.isfile(alien),
              'видалення знесло не наш .ttf')
        check('наш шрифт прибрано', not os.path.isfile(mine))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main():
    for fn in (test_keeps_foreign_bytes, test_heals_damaged_cfg,
               test_locale_keeps_foreign_bytes,
               test_uninstall_spares_foreign_fonts):
        print()
        print('-- %s' % fn.__doc__.splitlines()[0])
        fn()
    print()
    print('перевірок упало: %d' % len(FAIL))
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
