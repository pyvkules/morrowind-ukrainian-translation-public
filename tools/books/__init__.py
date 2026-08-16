# -*- coding: utf-8 -*-
"""Переклад текстів книг, спільний для rebuild_esm.py і patch_plugins.py.

Ключ - SHA-1 англійського тексту, а не порядковий номер: книги приходять із
327 плагінів, чий склад і порядок у кожного гравця свій, тож нумерація збилася б.
Див. extract_books.py, там це розписано докладніше.
"""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def key(text):
    return hashlib.sha1(text.encode('cp1251', 'replace')).hexdigest()[:16]


def load():
    """Хеш англійського тексту -> український текст. Порожньо, якщо ще нема."""
    p = os.path.join(HERE, 'uk_books.json')
    if not os.path.isfile(p):
        return {}
    d = json.load(open(p, encoding='utf-8'))
    d.pop('_comment', None)
    return {k: v for k, v in d.items() if isinstance(v, str) and v.strip()}
