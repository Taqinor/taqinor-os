# -*- coding: utf-8 -*-
"""Moteur de calepinage E-O : tables 2 modules paysage (2,382 le long de la rangée,
2,25 d'emprise transversale), allées 1,50, rives 0,50, dégagement obstacles 0,50.
Compte le nombre RÉEL de modules posables sur la géométrie RELEVÉE + obstacles."""
import sys
sys.path.insert(0, ".")
import dessin as D
from matplotlib.patches import Rectangle

MOD_L = 2.382      # table (2 modules paysage dos à dos) : emprise le long de la rangée
TBL_W = 2.25       # emprise transversale d'une table E-O
ALLEE = 1.50
RIVE = 0.50
CLEAR = 0.50       # dégagement autour d'un obstacle

def rows_for(width, allee=None, rive=None, phase=0.0):
    allee = ALLEE if allee is None else allee
    rive = RIVE if rive is None else rive
    n = int((width - 2 * rive + allee) // (TBL_W + allee))
    return [(phase + rive + i * (TBL_W + allee),
             phase + rive + i * (TBL_W + allee) + TBL_W) for i in range(n)]

def merge(iv):
    out = []
    for a, b in sorted(iv):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out

def count_band(length, width, obstacles, allee, rive, clear, phase,
               mod_l=None, tbl_w=None, end_rive=0.5):
    mod_l = MOD_L if mod_l is None else mod_l
    total = 0
    for (y0, y1) in rows_for(width, allee, rive, phase):
        if y1 > width - rive + 1e-6:
            continue
        blocked = [(max(0.0, o[0] - clear), min(length, o[1] + clear))
                   for o in obstacles if not (o[3] + clear <= y0 or o[2] - clear >= y1)]
        blocked = merge([b for b in blocked if b[1] > b[0]])
        cur = end_rive
        stop = length - end_rive
        for a, b in blocked:
            if a > cur:
                total += 2 * int((min(a, stop) - cur) // mod_l)
            cur = max(cur, b)
        if cur < stop:
            total += 2 * int((stop - cur) // mod_l)
    return total

def best_phase(length, width, obstacles, allee, rive, clear,
               mod_l=None, tbl_w=None, end_rive=0.5):
    n = int((width - 2 * rive + allee) // (TBL_W + allee))
    slack = width - (2 * rive + n * TBL_W + (n - 1) * allee)
    best, bph = -1, 0.0
    p = 0.0
    while p <= slack + 1e-9:
        c = count_band(length, width, obstacles, allee, rive, clear, p,
                       mod_l=mod_l, tbl_w=tbl_w, end_rive=end_rive)
        if c > best:
            best, bph = c, p
        p += 0.05
    return best, bph

def fill_band(ax, ox, oy, length, width, obstacles, horizontal=True, draw=True,
              allee=None, rive=None, clear=None, phase=0.0, end_rive=0.0):
    """end_rive : rive d'extrémité aux 2 bouts de la bande (0.0 = ancien comportement).
    Avec end_rive identique, fill_band et count_band donnent le MÊME total."""
    allee = ALLEE if allee is None else allee
    rive = RIVE if rive is None else rive
    clear = CLEAR if clear is None else clear
    total = 0
    for (y0, y1) in rows_for(width, allee, rive, phase):
        if y1 > width - rive + 1e-6:
            continue
        blocked = [(max(0.0, o[0] - clear), min(length, o[1] + clear))
                   for o in obstacles if not (o[3] + clear <= y0 or o[2] - clear >= y1)]
        blocked = merge([b for b in blocked if b[1] > b[0]])
        stop = length - end_rive
        segs, cur = [], end_rive
        for a, b in blocked:
            if a > cur:
                segs.append((cur, min(a, stop)))
            cur = max(cur, b)
        if cur < stop:
            segs.append((cur, stop))
        segs = [(a, b) for a, b in segs if b > a]
        for a, b in segs:
            n = int((b - a) // MOD_L)
            total += 2 * n
            if not draw:
                continue
            for i in range(n):
                xa = a + i * MOD_L
                if horizontal:
                    r = Rectangle((ox + xa, oy + y0), MOD_L, TBL_W)
                else:
                    r = Rectangle((ox + y0, oy - xa - MOD_L), TBL_W, MOD_L)
                r.set(facecolor="#bbf7d0", edgecolor="#15803d", lw=0.5, zorder=6)
                ax.add_patch(r)
                # faîtage (séparation des 2 modules E/O)
                if horizontal:
                    ax.plot([ox + xa, ox + xa + MOD_L],
                            [oy + y0 + TBL_W / 2] * 2, color="#15803d", lw=0.35,
                            zorder=7)
                else:
                    ax.plot([ox + y0 + TBL_W / 2] * 2,
                            [oy - xa, oy - xa - MOD_L], color="#15803d", lw=0.35,
                            zorder=7)
    return total

def draw_obstacles(ax, ox, oy, obstacles, horizontal=True, color="#334155"):
    for (x0, x1, y0, y1) in obstacles:
        if horizontal:
            r = Rectangle((ox + x0, oy + y0), x1 - x0, y1 - y0)
        else:
            r = Rectangle((ox + y0, oy - x1), y1 - y0, x1 - x0)
        r.set(facecolor=color, edgecolor="black", lw=0.8, hatch="////", zorder=8)
        ax.add_patch(r)
