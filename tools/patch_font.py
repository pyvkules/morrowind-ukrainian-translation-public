# -*- coding: utf-8 -*-
"""Add the missing Ukrainian glyphs to the UI font.

A cp1251 Cyrillic font still lacks the four letters Ukrainian needs beyond Russian:
Є є, І і, Ї ї, Ґ ґ. Without them the game draws blanks. Rather than substitute a
different typeface, this builds the missing glyphs out of ones the font already has,
so the result still looks like the original:

    І і <- I i        Ї ї <- Ï ï        Ґ ґ <- Г г        Є є <- mirrored Э э

Then it rebuilds the cmap from scratch, because editing the existing subtables in
place leaves stale entries that OpenMW's font loader trips over.

The source font is found in the modlist itself (last data dir wins, exactly as the
VFS resolves it), so this reproduces on any machine.

    py patch_font.py                 # patch Pelagiad, the modlist's UI font
    py patch_font.py --font MysticCards
    py patch_font.py --src <path.ttf>

IMPORTANT: patch the font the game actually loads. openmw.log lists it on the
"Loading font file" lines - MysticCards was patched first and had no effect at all
because this modlist never loads it.
"""
import copy
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.misc.transform import Transform


def arg(flag, default=None):
    for i, a in enumerate(sys.argv):
        if a == flag and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


NAME = arg('--font', 'Pelagiad')
SRC = arg('--src')
if not SRC:
    dirs, _ = paths.read_modlist()
    for d in dirs:
        cand = os.path.join(d, 'fonts', NAME + '.ttf')
        if os.path.abspath(d) != paths.MOD_ROOT and os.path.isfile(cand):
            SRC = cand
    if not SRC:
        raise SystemExit('No source %s.ttf found in the modlist data dirs.' % NAME)

DST_DIR = os.path.join(paths.MOD_ROOT, 'Fonts')
os.makedirs(DST_DIR, exist_ok=True)
DST = os.path.join(DST_DIR, NAME + '.ttf')
print('source:', SRC)
print('target:', DST)

font = TTFont(SRC)
cmap_old = font.getBestCmap()
glyf = font['glyf']
hmtx = font['hmtx']
order = list(font.getGlyphOrder())


def clone_glyph(src_name, new_name):
    glyf[new_name] = copy.deepcopy(glyf[src_name])
    hmtx[new_name] = hmtx[src_name]
    order.append(new_name)


def mirror_glyph(src_name, new_name):
    adv, lsb = hmtx[src_name]
    pen = TTGlyphPen(font.getGlyphSet())
    tpen = TransformPen(ReverseContourPen(pen), Transform(-1, 0, 0, 1, adv, 0))
    font.getGlyphSet()[src_name].draw(tpen)
    g = pen.glyph()
    glyf[new_name] = g
    hmtx[new_name] = (adv, getattr(g, 'xMin', 0))
    order.append(new_name)


CLONES = [(ord('I'), 'uni0406'), (ord('i'), 'uni0456'),
          (0xCF, 'uni0407'), (0xEF, 'uni0457'),
          (0x0413, 'uni0490'), (0x0433, 'uni0491')]
MIRRORS = [(0x042D, 'uni0404'), (0x044D, 'uni0454')]

added = {}
for cp, new in CLONES:
    if cp not in cmap_old:
        raise SystemExit('font lacks the source glyph U+%04X needed for %s' % (cp, new))
    clone_glyph(cmap_old[cp], new)
    added[int(new[3:], 16)] = new
for cp, new in MIRRORS:
    if cp not in cmap_old:
        raise SystemExit('font lacks the source glyph U+%04X needed for %s' % (cp, new))
    mirror_glyph(cmap_old[cp], new)
    added[int(new[3:], 16)] = new

font.setGlyphOrder(order)
if 'post' in font:
    font['post'].extraNames = []
    font['post'].mapping = {}
    font['post'].glyphOrder = None
for t in ('hdmx', 'LTSH', 'VDMX'):
    if t in font:
        del font[t]

full = dict(cmap_old)
full.update(added)
full = {cp: g for cp, g in full.items() if cp <= 0xFFFF}

tables = []
for plat, enc in ((0, 3), (3, 1)):
    sub = CmapSubtable.getSubtableClass(4)(4)
    sub.platformID, sub.platEncID, sub.format, sub.language = plat, enc, 4, 0
    sub.cmap = dict(full)
    tables.append(sub)
cmap = newTable('cmap')
cmap.tableVersion = 0
cmap.tables = tables
font['cmap'] = cmap

font['maxp'].numGlyphs = len(order)
font.save(DST)

chk = TTFont(DST).getBestCmap()
missing = [hex(cp) for cp in sorted(added) if cp not in chk]
print('missing after patch:', missing or 'NONE')
