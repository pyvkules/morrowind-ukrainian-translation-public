# -*- coding: utf-8 -*-
"""Чи `resolve_plugins` справді обходить нашу власну теку.

Наші зібрані плагіни лежать у MOD_ROOT, і в openmw.cfg це останній рядок
`data=`, тож за правилом «пізніша тека виграє» вони виграють кожну назву
файла. Усе тримається на одному порівнянні, і воно було чутливе до регістру:
`os.path.abspath` віддає літеру диска так, як її бачить процес (`e:\\` після
запуску відносним шляхом, `E:\\` після абсолютного), а openmw.cfg пише її
так, як набрав гравець. Коли регістри розходилися, інструменти читали вже
перекладені плагіни замість першотворів: витяг книг бачив 2490 «унікальних»
текстів замість 2327 і 277 перекладів замість 1157. З `--apply` це перезаписало
б `_source.json` українським текстом і відірвало від книг дев'ять сотень
готових перекладів.

    py tools/test_paths.py

Вихід 1, якщо хоч одна перевірка впала. Гри й мережі не потребує.
"""
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                              errors='replace', write_through=True)

FAIL = []


def check(name, ok, note=''):
    print('%-4s %s%s' % ('ОК' if ok else 'ПАДЕ', name,
                         '' if ok else '  <- ' + note))
    if not ok:
        FAIL.append(name)


def swapcase_drive(path):
    """Той самий шлях, але з іншим регістром літери диска."""
    if len(path) > 1 and path[1] == ':':
        head = path[0].lower() if path[0].isupper() else path[0].upper()
        return head + path[1:]
    return path


def test_our_dir_is_skipped():
    """Наша тека не дає плагінів, хай як написано літеру диска."""
    root = tempfile.mkdtemp(prefix='ukr-paths-')
    try:
        # першотвір у чужій теці й наш «переклад» тієї ж назви в MOD_ROOT
        orig = os.path.join(root, 'original')
        os.makedirs(orig)
        io.open(os.path.join(orig, 'Morrowind.esm'), 'w').close()
        ours = os.path.join(paths.MOD_ROOT, 'Morrowind.esm')
        made = not os.path.exists(ours)
        if made:
            io.open(ours, 'w').close()
        try:
            for name, mine in (('як є', paths.MOD_ROOT),
                               ('з іншим регістром диска',
                                swapcase_drive(paths.MOD_ROOT)),
                               ('зі скісною в кінці', paths.MOD_ROOT + os.sep)):
                got = paths.resolve_plugins([orig, mine])
                p = got.get('morrowind.esm', '')
                check('нашу теку обійдено (%s)' % name,
                      os.path.normcase(os.path.dirname(os.path.abspath(p)))
                      == os.path.normcase(orig),
                      'узяли %s' % p)
        finally:
            if made:
                os.remove(ours)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_later_dir_still_wins():
    """Решта правила лишається: пізніша тека виграє назву файла."""
    root = tempfile.mkdtemp(prefix='ukr-paths-')
    try:
        a, b = os.path.join(root, 'a'), os.path.join(root, 'b')
        os.makedirs(a)
        os.makedirs(b)
        io.open(os.path.join(a, 'Mod.esp'), 'w').close()
        io.open(os.path.join(b, 'mod.esp'), 'w').close()
        got = paths.resolve_plugins([a, b])
        check('пізніша тека виграє',
              os.path.normcase(os.path.dirname(got.get('mod.esp', '')))
              == os.path.normcase(b),
              'узяли %s' % got.get('mod.esp'))
    finally:
        shutil.rmtree(root, ignore_errors=True)


test_our_dir_is_skipped()
test_later_dir_still_wins()
print()
print('перевірок упало: %d' % len(FAIL))
sys.exit(1 if FAIL else 0)
