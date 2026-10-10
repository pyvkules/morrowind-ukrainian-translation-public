# -*- coding: utf-8 -*-
"""Чи збігаються списки кроків збірки у build.py та installer/install.py.

Точок входу дві. `build.py` збирає в перекладача, а `install.py` - на
машині гравця, і кожна тримає власний список кроків: у встановлювача
свої підписи, свій порядок доводів і свій спосіб запуску (runpy замість
subprocess, бо заморожений exe не є інтерпретатором Python).

Одного разу вони розійшлися. Крок `patch_scripts.py` додали в build.py і
забули в install.py, тож у перекладача все було на місці, а гравець
діставав гру без субтитрів і віконець зі скриптів. Знайшов це не ми, а
людина, яка уважно прочитала журнал встановлення.

Тут ми читаємо обидва файли розбором синтаксису, без запуску, і
звіряємо набір скриптів. `patch_font.py` у встановлювача свій окремий
хід (`font_steps` шукає шрифти на машині гравця), тож його минаємо.

    py tools\\check_steps.py
"""
import ast
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                              errors='replace', write_through=True)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
BUILD = os.path.join(ROOT, 'build.py')
INSTALL = os.path.join(ROOT, 'installer', 'install.py')
APART = {'tools/patch_font.py'}


def steps_of(path):
    """Шляхи скриптів зі списку STEPS, у порядку запису."""
    tree = ast.parse(io.open(path, encoding='utf-8').read(), path)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(getattr(t, 'id', None) == 'STEPS' for t in node.targets):
            continue
        out = []
        for item in node.value.elts:
            for piece in ast.walk(item):
                if isinstance(piece, ast.Constant) \
                        and isinstance(piece.value, str) \
                        and piece.value.endswith('.py'):
                    out.append(piece.value)
                    break
        return out
    raise SystemExit('не знайшов STEPS у %s' % path)


def main():
    build = [s for s in steps_of(BUILD) if s not in APART]
    install = [s for s in steps_of(INSTALL) if s not in APART]
    print('build.py   : %s' % ', '.join(build))
    print('install.py : %s' % ', '.join(install))
    if build == install:
        print('списки збігаються')
        return 0
    only_build = [s for s in build if s not in install]
    only_inst = [s for s in install if s not in build]
    if only_build:
        print('! немає у встановлювача: %s' % ', '.join(only_build))
    if only_inst:
        print('! немає у build.py: %s' % ', '.join(only_inst))
    if not only_build and not only_inst:
        print('! той самий набір, але інший порядок')
    return 1


if __name__ == '__main__':
    sys.exit(main())
