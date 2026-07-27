# -*- coding: utf-8 -*-
"""VUE DE TOITURE DÉFINITIVE — Bât. B (aile en ARC, Résidence UIB, Mohammedia).
ASSEMBLAGE CORRIGÉ CLIENT (27/07/2026, soir) :
  l'arc = 3 SEGMENTS de toiture séparés par des MURETS HACHURÉS AU RAS
  (h = 0, ép. 0,45 — joints, confirmé client), ordre GAUCHE -> DROITE :
    S1 = croquis IMG_2936 (chaîne ext 24,37)
    S2 = croquis IMG_2948 (cage d'escalier 4,98 x 5,93 à l'angle, ≈ 23,0)
    S3 = croquis IMG_2935 (8 caissons cotés + 1 non coté + structure bord ext., ≈ 23,6)
  TOUT est relevé : AUCUNE zone « au plan ». Développé relevé ≈ 71,9 m
  (vs ≈ 90 du dossier §2.2 — écart affiché, à réconcilier).
Moteur conservé : transformation développé -> arc, R_ext = 274 m (entraxes
ext 11,38 vs int 10,93), tables posées en tronçons droits par trame.
Confirmations client intégrées : K3->K4 = 6,54 ; K4 -> bord bas = 3,85 ;
murets ép. 0,45 au ras (bleu).
"""
import math
import sys
sys.path.insert(0, ".")
import dessin as D
import calepinage as C
from solveur import chain, closure
from matplotlib.patches import Polygon, FancyArrowPatch, Rectangle

# ---------------------------------------------------------------- géométrie arc
R_EXT = 274.0
W = 10.90
R_INT = R_EXT - W

S1_LEN = 20.55                       # chaîne ext croquis 1 RECALCULÉE : 3,72+3,84+6,59+6,4
                                     # (le « 3,82 » = cote RADIALE du caisson — doublon
                                     # retiré, vigilance client confirmée au zoom)
S2_LEN = 23.00                       # ≈ (client)
S3_LEN = 23.60                       # ≈ (client)
MUR = 0.45                           # murets inter-segments au ras (confirmé)
OFF2 = S1_LEN + MUR                  # 24.82
OFF3 = OFF2 + S2_LEN + MUR           # 48.27
LEN = OFF3 + S3_LEN                  # 71.87 — développé ext total relevé

TH = LEN / R_EXT
Y0 = R_EXT * math.cos(TH / 2)

def phi(s):
    return (s - LEN / 2) / R_EXT

def P(s, y):
    """(s, y) -> feuille. s = abscisse curviligne bord EXT ; y depuis bord INT."""
    r = R_INT + y
    f = phi(s)
    return (r * math.sin(f), r * math.cos(f) - Y0)

def rigid(s0, s1, y0, y1):
    """Rectangle RIGIDE posé au repère tangent local de son centre."""
    sc, yc = (s0 + s1) / 2, (y0 + y1) / 2
    f = phi(sc)
    cx, cy = P(sc, yc)
    t = (math.cos(f), -math.sin(f))
    n = (math.sin(f), math.cos(f))
    hw, hh = (s1 - s0) / 2, (y1 - y0) / 2
    return [(cx + a * hw * t[0] + b * hh * n[0],
             cy + a * hw * t[1] + b * hh * n[1])
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]

def arcpts(s0, s1, y, n=80):
    return [P(s0 + (s1 - s0) * i / n, y) for i in range(n + 1)]

def dim(ax, p1, p2, off=0.8, text=None, color=D.BLEU, fs=6.4, gap=0.10,
        ext=0.16, text_off=0.26, box=False):
    ux, uy, L = D._unit(p1, p2)
    nx, ny = -uy, ux
    q1 = (p1[0] + nx * off, p1[1] + ny * off)
    q2 = (p2[0] + nx * off, p2[1] + ny * off)
    sg = 1 if off >= 0 else -1
    for p, q in ((p1, q1), (p2, q2)):
        a = (p[0] + nx * gap * sg, p[1] + ny * gap * sg)
        b = (q[0] + nx * ext * sg, q[1] + ny * ext * sg)
        ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=0.55, zorder=24)
    ax.add_patch(FancyArrowPatch(q1, q2, arrowstyle="<|-|>", mutation_scale=6.0,
                                 lw=0.8, color=color, shrinkA=0, shrinkB=0,
                                 zorder=25))
    if text is None:
        text = f"{L:.2f}".replace(".", ",")
    mx, my = (q1[0] + q2[0]) / 2, (q1[1] + q2[1]) / 2
    ang = math.degrees(math.atan2(uy, ux))
    if ang > 90 or ang <= -90:
        ang += 180
    kw = dict(fontsize=fs, color=color, ha="center", va="center", rotation=ang,
              rotation_mode="anchor", zorder=26)
    if box:
        kw["bbox"] = dict(fc="white", ec="none", alpha=0.85, pad=0.5)
    ax.text(mx + nx * text_off * sg, my + ny * text_off * sg, text, **kw)

def rdim(ax, s, ya, yb, off=0.0, text=None, color=D.BLEU, box=True, fs=6.2):
    dim(ax, P(s, ya), P(s, yb), off=off, text=text, color=color, box=box, fs=fs)

def tdim(ax, s0, s1, y, text=None, color=D.BLEU, box=True, fs=6.2, off=0.0):
    dim(ax, P(s0, y), P(s1, y), off=off, text=text, color=color, box=box, fs=fs)

def caisson(ax, o, cid, uncertain=False, deduced=False, fs=5.4, lsy=None):
    poly = rigid(*o)
    ec = D.ORANGE if uncertain else (D.GRIS if deduced else D.NOIR)
    fc = "#e8ecf1" if deduced else "#d8dee6"
    p = Polygon(poly, closed=True, facecolor=fc, edgecolor=ec, lw=1.0,
                hatch="////", zorder=15)
    p.set_linestyle("--" if (uncertain or deduced) else "-")
    ax.add_patch(p)
    s0, s1, y0, y1 = o
    lx, ly = P(*(lsy or ((s0 + s1) / 2, (y0 + y1) / 2)))
    ax.text(lx, ly, cid, fontsize=fs, ha="center", va="center",
            color=D.ORANGE if uncertain else ("#475569" if deduced else "#111111"),
            zorder=27, fontweight="bold",
            bbox=dict(fc="white", ec="none", alpha=0.78, pad=0.35))

# ---------------------------------------------------------------- obstacles
# (s0, s1, y0, y1) GLOBAUX — y depuis le bord INTÉRIEUR (figure : ext en HAUT)
# --- SEGMENT 1 (croquis 1) — s local = global
C1 = (3.27, 4.63, W - 4.72, W - 3.82)  # 1,36 x 0,90 CONFIRMÉ client :
                                       # 3,27 du mur ouest, 3,82 du bord EXT
C2 = (15.54, 17.09, 4.80, 5.76)        # 1,55 x 0,96 ? (1,39 après la trame 14,15 —
                                       # distance au joint conservée)
C3 = (12.78, 14.14, 4.20, 5.15)        # 1,36 x 0,95 ? (distance au joint conservée)
S1_OBS = [C1, C2, C3]
# --- SEGMENT 2 (croquis 2) — local + OFF2 ; cage à l'angle du joint S1/S2
BLOC = (OFF2 + 0.00, OFF2 + 4.98, W - 5.93, W)       # cage d'escalier 4,98 x 5,93
K1 = (OFF2 + 6.28, OFF2 + 7.28, W - 4.67, W - 3.77)  # bloc + 1,3 ; 3,77 du bord ext
K2 = (OFF2 + 8.58, OFF2 + 9.78, W - 4.20, W - 3.40)  # bloc + 3,6
K3 = (OFF2 + 8.18, OFF2 + 9.43, 3.50, 4.30)          # bloc + 3,2
K4 = (OFF2 + 15.97, OFF2 + 17.42, 3.85, 4.75)        # K3 + 6,54 CONFIRMÉ ; 3,85 bord int CONFIRMÉ
K5 = (OFF2 + 11.34, OFF2 + 13.14, W - 3.00, W - 2.00)
K6 = (OFF2 + 20.00, OFF2 + 21.50, W - 4.68, W - 3.78)
K7 = (OFF2 + 20.10, OFF2 + 21.60, 3.86, 4.72)
S2_OBS = [BLOC, K1, K2, K3, K4, K5, K6, K7]
# --- SEGMENT 3 (croquis 3, relu — bord haut croquis = bord EXT, comme croquis 2)
A3 = (OFF3 + 3.30, OFF3 + 4.57, W - 4.19, W - 3.61)   # 1,27 x 0,58 (client : 0,58 x 0,27)
B3 = (OFF3 + 2.50, OFF3 + 3.55, 3.70, 5.33)           # 1,05 x 1,63 ? (chaîne radiale ferme)
X3 = (OFF3 + 4.62, OFF3 + 5.32, 4.20, 5.30)           # caisson NON coté (croquis)
N1 = (OFF3 + 4.92, OFF3 + 8.15, W - 1.70, W)          # structure bord ext — palier 1 (non coté)
N2 = (OFF3 + 8.15, OFF3 + 10.72, W - 3.15, W)         # palier 2 (0,78 au-dessus de D)
C3g = (OFF3 + 9.05, OFF3 + 10.59, 3.681, 4.701)       # C 1,54 x 1,02 (1,64 ?)
D3 = (OFF3 + 9.60, OFF3 + 10.44, W - 4.70, W - 3.93)  # D 0,84 x 0,77 ; 3,83 du bord ext
E3 = (OFF3 + 10.72, OFF3 + 12.52, W - 4.84, W - 3.74)  # E 1,80 x 1,10 ; = F - 6,54
G3 = (OFF3 + 10.90, OFF3 + 12.43, 3.77, 4.67)         # G 1,53 x 0,9 ; 1,39 sous E
F3 = (OFF3 + 19.05, OFF3 + 20.27, W - 4.69, W - 3.85)  # F 1,22 x 0,84 ; 3,33 du bord est
H3 = (OFF3 + 18.99, OFF3 + 20.34, 3.83, 4.69)         # H 1,35 x 0,86 ; 3,26 du bord est
S3_OBS = [A3, B3, X3, N1, N2, C3g, D3, E3, G3, F3, H3]
OBS = S1_OBS + S2_OBS + S3_OBS

# ---------------------------------------------------------------- calepinage
ALLEE, RIVE, CLEAR, END_RIVE = 1.20, 0.35, 0.30, 0.50
SEGS = [(0.0, S1_LEN, S1_OBS), (OFF2, S2_LEN, S2_OBS), (OFF3, S3_LEN, S3_OBS)]

def layout(length, width, obstacles, allee, rive, clear, ph, end_rive):
    """Réplique EXACTE de calepinage.count_band, mais retourne les tables."""
    rects = []
    for (y0, y1) in C.rows_for(width, allee, rive, ph):
        if y1 > width - rive + 1e-6:
            continue
        blocked = [(max(0.0, o[0] - clear), min(length, o[1] + clear))
                   for o in obstacles if not (o[3] + clear <= y0 or o[2] - clear >= y1)]
        blocked = C.merge([b for b in blocked if b[1] > b[0]])
        cur, stop = end_rive, length - end_rive
        for a, b in blocked:
            if a > cur:
                n = max(0, int((min(a, stop) - cur) // C.MOD_L))
                rects += [(cur + i * C.MOD_L, cur + (i + 1) * C.MOD_L, y0, y1)
                          for i in range(n)]
            cur = max(cur, b)
        if cur < stop:
            n = int((stop - cur) // C.MOD_L)
            rects += [(cur + i * C.MOD_L, cur + (i + 1) * C.MOD_L, y0, y1)
                      for i in range(n)]
    return rects

TABLES, SEG_N = [], []
for off, slen, obs in SEGS:
    loc = [(o[0] - off, o[1] - off, o[2], o[3]) for o in obs]
    best, ph = C.best_phase(slen, W, loc, ALLEE, RIVE, CLEAR, end_rive=END_RIVE)
    tabs = layout(slen, W, loc, ALLEE, RIVE, CLEAR, ph, END_RIVE)
    assert 2 * len(tabs) == best == C.count_band(slen, W, loc, ALLEE, RIVE,
                                                 CLEAR, ph, end_rive=END_RIVE)
    SEG_N.append(best)
    TABLES += [(a + off, b + off, y0, y1) for (a, b, y0, y1) in tabs]
NMOD = sum(SEG_N)
assert NMOD == 2 * len(TABLES)
CAP144 = NMOD >= 144

# ---------------------------------------------------------------- feuille
fig, ax = D.new_sheet(
    "VUE DE TOITURE DÉFINITIVE — BÂTIMENT B (AILE EN ARC) — RÉSIDENCE UNIVERSITAIRE UIB, MOHAMMEDIA — ASSEMBLAGE CORRIGÉ (client, 27/07/2026)",
    "Arc en VRAIE géométrie (R_ext ≈ 274 m) — 3 SEGMENTS de toiture séparés par des MURETS HACHURÉS AU RAS "
    "(joints, ép. 0,45, h = 0 — confirmé client) : S1 20,55 (chaîne recalée) + joint + S2 ≈ 23,0 + joint + S3 ≈ 23,6 ≈ 68,1 m — TOUT RELEVÉ 27/07/2026, aucune zone « au plan »\n"
    "cotes en mètres · bleu = mesuré/confirmé · orange = à confirmer · gris = déduit — calepinage : tables E-O 2,382 × 2,25 posées en tronçons "
    "droits par trame, PAR SEGMENT (les rangées s'arrêtent aux joints)",
    (-40.2, 40.2), (-23.8, 9.6))
ax.set_position([0.015, 0.015, 0.97, 0.90])
ax.set_anchor("N")

# tables PV
for (s0, s1, y0, y1) in TABLES:
    poly = rigid(s0, s1, y0, y1)
    ax.add_patch(Polygon(poly, closed=True, facecolor="#bbf7d0",
                         edgecolor="#15803d", lw=0.45, zorder=6))
    c0, c1c, c2c, c3 = poly
    ax.plot([(c0[0] + c3[0]) / 2, (c1c[0] + c2c[0]) / 2],
            [(c0[1] + c3[1]) / 2, (c1c[1] + c2c[1]) / 2],
            color="#15803d", lw=0.3, zorder=7)

# transects S1 (trames radiales relevées, croquis 1)
SX = chain(0, 3.72, 3.84, 6.59, 6.40)
for s in SX[1:-1]:
    xs, ys = zip(P(s, -0.35), P(s, W + 0.35))
    ax.plot(xs, ys, color="#475569", lw=0.8, ls=(0, (4, 3)), zorder=8)

# contour de la bande courbe
outline = arcpts(0, LEN, W) + arcpts(LEN, 0, 0)
ax.add_patch(Polygon(outline, closed=True, fill=False, lw=2.2,
                     edgecolor=D.NOIR, zorder=10))

# murets inter-segments AU RAS (ép. 0,45, h=0 — joints, BLEU confirmé)
for (sm, tag) in ((S1_LEN, "S1/S2"), (OFF2 + S2_LEN, "S2/S3")):
    p = Polygon(rigid(sm, sm + MUR, 0.0, W), closed=True, facecolor="#dbeafe",
                edgecolor=D.BLEU, lw=1.2, hatch="//////", zorder=12)
    ax.add_patch(p)
mx, my = P(S1_LEN + MUR / 2, W + 1.15)
ax.text(0.0, 5.15, "joints : 2 murets hachurés AU RAS (h = 0), ép. 0,45 — CONFIRMÉ client — "
        "pas de rail à cheval sur un joint (dégagement 0,30 de part et d'autre)",
        fontsize=6.6, ha="center", color=D.BLEU, zorder=28)
for sm in (S1_LEN + MUR / 2, OFF2 + S2_LEN + MUR / 2):
    a = P(sm, W + 0.30)
    ax.plot([a[0], (a[0]) * 0.30], [a[1], 4.95], color=D.BLEU, lw=0.5, ls=":",
            zorder=23)

# murs d'extrémité (hachurés aux croquis)
ax.add_patch(Polygon(rigid(-0.45, 0.0, -0.10, W + 0.10), closed=True,
                     facecolor="none", edgecolor=D.NOIR, hatch="//////",
                     lw=1.4, zorder=11))
ax.add_patch(Polygon(rigid(LEN, LEN + 0.45, -0.10, W + 0.10), closed=True,
                     facecolor="none", edgecolor=D.NOIR, hatch="//////",
                     lw=1.4, zorder=11))
ax.text(-39.9, 2.6, "MUR D'EXTRÉMITÉ\nOUEST (croquis 1)", fontsize=6.6,
        fontweight="bold", ha="left", va="top")
ax.text(39.9, 2.6, "MUR D'EXTRÉMITÉ\nEST (croquis 3)\nà confirmer", fontsize=6.6,
        fontweight="bold", ha="right", va="top", color=D.ORANGE)

# étiquettes segments (au-dessus du bord ext)
for smid, txt in ((10.3, "SEGMENT 1 — croquis 1 — chaîne ext 20,55 (recalée)"),
                  (OFF2 + 11.5, "SEGMENT 2 — croquis 2 — L ≈ 23,0 (à confirmer)"),
                  (OFF3 + 11.8, "SEGMENT 3 — croquis 3 — L ≈ 23,6 (à confirmer)")):
    tx, ty = P(smid, W + 2.35)
    ax.text(tx, ty, txt, fontsize=7.0, ha="center", fontweight="bold",
            color="#333333", rotation=-math.degrees(phi(smid)), zorder=27)

# ---------------- SEGMENT 1 : cotes
for a, b, t in zip(SX, SX[1:], ["3,72", "3,84", "6,59", "6,4"]):
    dim(ax, P(a, W), P(b, W), off=0.55, text=t)
tx, ty = P(10.3, W + 1.30)
ax.text(tx, ty, "le « 3,82 » du croquis = cote RADIALE de C1 (doublon retiré) → chaîne recalculée 20,55",
        fontsize=5.4, ha="center", color=D.BLEU,
        rotation=-math.degrees(phi(10.3)), zorder=26)
TI = chain(0, 3.42, 3.78, 3.73)
for a, b, t in zip(TI, TI[1:], ["3,42", "3,78", "3,73"]):
    dim(ax, P(a * R_EXT / R_INT, 0), P(b * R_EXT / R_INT, 0), off=-0.55, text=t)
tx, ty = P(5.6, -1.95)
ax.text(tx, ty, "entraxes bord int. (chaîne 10,93 : courbure)", fontsize=5.4,
        ha="center", color=D.BLEU, rotation=-math.degrees(phi(5.6)))

rdim(ax, 0.70, 0, W, text="10,81")
rdim(ax, 7.60, 0, W, text="10,87 (confirmé)")
rdim(ax, 15.10, 0, W, text="10,9")

caisson(ax, C1, "C1")
caisson(ax, C2, "C2", uncertain=True)
caisson(ax, C3, "C3", uncertain=True)
tdim(ax, 0.0, C1[0], 6.62, text="3,27")                  # mur ouest -> C1 (confirmé)
rdim(ax, C1[0] + 0.95, C1[3], W, text="3,82")            # bord ext -> C1 (confirmé)
dim(ax, P(SX[3], 5.30), P(C2[0], 5.30), off=0.0, text="1,39", box=True)
dim(ax, P(SX[2], 1.90), P(SX[2] + 4.75, 1.90), off=0.0, color=D.ORANGE,
    text="4,75 (rattach. ?)", box=True)
dim(ax, P(SX[3], 2.60), P(SX[3] + 5.5, 3.40), off=0.0, color=D.ORANGE,
    text="5,5 (diag.)", box=True)
rdim(ax, 19.80, 0, 0.78, text="0,78", color=D.ORANGE)

# ---------------- SEGMENT 2 : cage + caissons + cotes
ax.add_patch(Polygon(rigid(*BLOC), closed=True, facecolor="#eef1f5",
                     edgecolor=D.NOIR, lw=2.4, zorder=14))
ax.add_patch(Polygon(rigid(BLOC[0] + 0.30, BLOC[1] - 0.30,
                           BLOC[2] + 0.30, BLOC[3] - 0.30), closed=True,
                     facecolor="white", edgecolor=D.NOIR, lw=1.0, zorder=14))
bx, by = P((BLOC[0] + BLOC[1]) / 2, (BLOC[2] + BLOC[3]) / 2)
ax.text(bx, by, "CAGE\nD'ESCALIER\n4,98 × 5,93", fontsize=6.6, ha="center",
        va="center", fontweight="bold", color="#333333", zorder=16,
        rotation=-math.degrees(phi(BLOC[0] + 2.5)))
dim(ax, P(BLOC[0], W), P(BLOC[1], W), off=0.55, text="4,98")
rdim(ax, BLOC[0] + 0.55, BLOC[2], W, text="5,93")
f = phi(BLOC[0])
t = (math.cos(f), -math.sin(f)); n = (math.sin(f), math.cos(f))
cx, cy = P(BLOC[0], BLOC[2])
ax.plot([cx, cx + 0.8 * t[0]], [cy, cy + 0.8 * t[1]], color=D.NOIR, lw=1.8, zorder=16)
ax.plot([cx, cx + 0.8 * n[0]], [cy, cy + 0.8 * n[1]], color=D.NOIR, lw=1.8, zorder=16)
ax.text(*P(BLOC[0] + 0.30, BLOC[2] - 0.95), "angle repère (raccord chaîne S1 : 20,55)",
        fontsize=5.0, ha="left", color="#555555", zorder=27,
        bbox=dict(fc="white", ec="none", alpha=0.8, pad=0.3))

caisson(ax, K1, "K1")
caisson(ax, K2, "K2")
caisson(ax, K3, "K3", uncertain=True)
caisson(ax, K4, "K4")
caisson(ax, K5, "K5")
caisson(ax, K6, "K6")
caisson(ax, K7, "K7", uncertain=True, lsy=(K7[0] + 1.06, 4.29))
rdim(ax, K1[0] + 0.50, K1[3], W, text="3,77")
dim(ax, P(BLOC[1], 6.68), P(K1[0], 6.68), off=0.0, text="1,3", box=True, fs=5.8)
dim(ax, P(BLOC[1], 7.35), P(K2[0], 7.35), off=0.0, text="3,6", box=True)
dim(ax, P(BLOC[1], 4.62), P(K3[0], 4.62), off=0.0, text="3,2", box=True, fs=5.8)
for pp, qq in ((P(BLOC[1], BLOC[2]), P(BLOC[1], 4.62)),
               (P(K3[0], K3[3]), P(K3[0], 4.62))):
    ax.plot([pp[0], qq[0]], [pp[1], qq[1]], color="#94a3b8", lw=0.5, ls=":",
            zorder=23)
dim(ax, P(OFF2 + 8.85, K3[3]), P(OFF2 + 8.85, K2[2]), off=0.0, color=D.ORANGE,
    text="1,6 ? (2,4)", box=True, fs=5.6)
dim(ax, P(K3[1], 4.05), P(K4[0], 4.05), off=0.0,
    text="6,54 — CONFIRMÉ client", box=True)
rdim(ax, K4[0] + 0.72, 0, K4[2], text="3,85 — confirmé")
dim(ax, P(K5[1], 7.60), P(K6[0], 7.60), off=0.0, text="6,86", box=True)
rdim(ax, OFF2 + 14.6, 0, W, text="10,9")

# contrôle de fermeture transversal K6/K7
SC = K7[1] + 0.55
for (ya, yb, t) in ((0, K7[2], "3,86"), (K7[2], K7[3], "0,86"),
                    (K7[3], K6[2], "1,50"), (K6[2], K6[3], "0,90"),
                    (K6[3], W, "3,78")):
    rdim(ax, SC, ya, yb, text=t, fs=5.6)
for yy in (K7[2], K7[3], K6[2], K6[3]):
    xs, ys = zip(P(K7[1] + 0.05, yy), P(SC, yy))
    ax.plot(xs, ys, color="#94a3b8", lw=0.5, ls=":", zorder=23)
ax.text(*P(SC - 0.6, -1.15), "Σ = 10,90 ✓", fontsize=6.2, color=D.BLEU,
        fontweight="bold", ha="center", rotation=-math.degrees(phi(SC)))

# ---------------- SEGMENT 3 : caissons + structure + cotes
caisson(ax, A3, "A", uncertain=True)
caisson(ax, B3, "B", uncertain=True)
caisson(ax, X3, "X", deduced=True)
caisson(ax, C3g, "C")
caisson(ax, D3, "D")
caisson(ax, E3, "E")
caisson(ax, G3, "G")
caisson(ax, F3, "F")
caisson(ax, H3, "H")
# structure bord ext (2 paliers, non cotée -> gris/orange)
for NN in (N1, N2):
    p = Polygon(rigid(*NN), closed=True, facecolor="#e2e8f0",
                edgecolor=D.ORANGE, lw=1.1, hatch="....", zorder=13)
    p.set_linestyle("--")
    ax.add_patch(p)
tx, ty = P(OFF3 + 7.8, W - 0.85)
ax.text(tx, ty, "structure bord ext. (croquis 3)\nNON COTÉE ≈ 5,8 m — à confirmer",
        fontsize=5.2, ha="center", va="center", color="#7c2d12",
        rotation=-math.degrees(phi(OFF3 + 7.8)), zorder=27,
        bbox=dict(fc="white", ec="none", alpha=0.8, pad=0.4))

# cotes tangentielles S3
tdim(ax, OFF3, A3[0], 7.62, text="3,3")
tdim(ax, OFF3, B3[0], 4.45, text="2,5 (3,2 ?)", color=D.ORANGE, fs=5.4)
tdim(ax, B3[1], C3g[0], 3.30, text="5,5 (5,53 ?)", color=D.ORANGE)
tdim(ax, E3[1], F3[0], 6.62, text="6,54")
tdim(ax, F3[1], LEN, 6.62, text="3,33")
tdim(ax, H3[1], LEN, 4.30, text="3,26")

# chaînes radiales S3
rdim(ax, A3[0] + 0.33, A3[3], W, text="3,61")            # ext -> A
rdim(ax, A3[0] + 0.20, B3[3], A3[2], text="1,38")        # A -> B
rdim(ax, B3[0] + 0.52, 0, B3[2], text="3,42 ?", color=D.ORANGE)
rdim(ax, C3g[0] + 0.45, 0, C3g[2], text="3,681")
rdim(ax, D3[0] + 0.62, C3g[3], D3[2], text="1,5")
rdim(ax, D3[0] + 0.42, D3[3], W, text="3,83")
rdim(ax, D3[1] - 0.18, D3[3], N2[2], text="0,78", fs=5.6)
rdim(ax, E3[1] - 0.45, E3[3], W, text="3,74")
rdim(ax, E3[1] - 0.62, G3[3], E3[2], text="1,39")
rdim(ax, G3[1] - 0.45, 0, G3[2], text="3,67")
rdim(ax, F3[0] + 0.50, F3[3], W, text="3,85")
rdim(ax, F3[0] + 0.68, H3[3], F3[2], text="1,5")
rdim(ax, H3[0] + 0.48, 0, H3[2], text="3,76")
rdim(ax, OFF3 + 4.35, 0, W, text="10,7")
rdim(ax, OFF3 + 22.25, 0, W, text="10,91")

# ---------------------------------------------------------------- synthèse
ax.text(0, 9.15, "CALEPINAGE tables Est-Ouest 2,382 × 2,25 m (2 modules 625 Wc paysage) — 3 rangées suivant la courbe, "
        "PAR SEGMENT (tronçons droits par trame, arrêt aux joints)", fontsize=7.2, ha="center", color="#333333")
ax.text(0, 8.45, f"allées 1,20 · rives 0,35 · rives d'extrémité 0,50 PAR SEGMENT · dégagement obstacles 0,30 (2 sens) — "
        f"capacité géométrique ≈ {NMOD} modules (S1 {SEG_N[0]} + S2 {SEG_N[1]} + S3 {SEG_N[2]}) — INFORMATION d'étude, pas une promesse",
        fontsize=7.2, ha="center", color="#333333")
ax.text(0, 7.45, "ENGAGEMENT OFFRE : 120 modules — TENDU : posable relevé 112 (développé relevé ≈ 68 m vs ≈ 90 m aux plans — "
        "chaînes possiblement partielles, réconciliation site requise)",
        fontsize=8.2, ha="center", color=D.ORANGE, fontweight="bold")
if CAP144:
    ax.text(0, 6.55, "nota : la géométrie absorbe la redistribution résidence — Bât. B → 144 modules (9 strings de 16) ; "
            f"déport 3×16 vers l'aile L ; onduleurs 96/80/96 et ratio 0,882 inchangés — capacité ≥ 144 vérifiée ({NMOD}) ✓",
            fontsize=7, ha="center", color="#555555")
else:
    ax.text(0, 6.55, f"⚠ nota : capacité relevée ≈ {NMOD} modules < 144 — la redistribution B → 144 (9×16) "
            "N'EST PAS absorbée par la géométrie relevée : à REVOIR (déport vers aile L à augmenter) — onduleurs/ratio à recalculer",
            fontsize=7.2, ha="center", color="#b91c1c", fontweight="bold")
ax.text(0, 5.85, "DÉVELOPPÉ RELEVÉ ≈ 68 m (après retrait du doublon 3,82) — le « ≈ 90 × 11,2 » du dossier (§2.2, approximatif) reste À RÉCONCILIER — rien de masqué",
        fontsize=7.6, ha="center", color=D.ORANGE, fontweight="bold")

NOTES = [
    ("CONTRÔLES DE FERMETURE (relevé 27/07/2026) :", True),
    ("• S1 RECALCULÉE (vigilance client confirmée au zoom) : le « 3,82 » du croquis est la cote RADIALE bord ext → C1, PAS un entraxe — "
     "chaîne ext 3,72+3,84+6,59+6,4 = 20,55 ≡ joint S1/S2 + angle repère de la cage (raccord recalé)", False),
    ("• courbure : entraxes ext 11,38 vs int 10,93 → R_ext ≈ 274 m ; 10,93 ≡ 11,38 × R_int/R_ext ✓ — l'arc est DESSINÉ à cette géométrie", False),
    ("• S2 transversal K6/K7 : 3,78 + 0,90 + 1,50 + 0,86 + 3,86 = 10,90 ≡ largeur mesurée ✓ · K3→K4 = 6,54 CONFIRMÉ client (K4 s₂ 15,97–17,42 : "
     "aucun recouvrement K7 s₂ 20,10–21,60 ✓) · K4 → bord int = 3,85 CONFIRMÉ", False),
    ("• S3 radiales : 3,61+0,58+1,38+1,63+3,42 = 10,62 ≈ 10,7 (Δ 8 cm) ✓ · 3,681+1,02+1,50+0,77+3,83 = 10,80 ✓ · 3,74+1,10+1,39+0,90+3,67 = 10,80 ✓ · "
     "3,85+0,84+1,50+0,86+3,76 = 10,81 ≈ 10,91 ✓", False),
    ("• développé : 20,55 + 0,45 + 23,0 + 0,45 + 23,6 = 68,05 ≈ 68 m (≈ 71,9 si le 3,82 était maintenu en entraxe — retiré au zoom) — "
     "écart vs dossier ≈ 90 AFFICHÉ ci-dessus", False),
    ("CAISSONS S1/S2 : C1 1,36×0,90 CONFIRMÉ (3,27 du mur ouest · 3,82 du bord ext · largeur 10,81 au mur) · C2 1,55×0,96 ? · C3 1,36×0,95 ? · "
     "K1 ≈1,0×0,9 · K2 ≈1,2×0,8 · K3 ≈1,25×0,8 ? · K4 ≈1,45×0,9 (position confirmée) · K5 ≈1,8×1,0 · K6 ≈1,5×0,9 · K7 1,5×0,86 · cage 4,98×5,93", False),
    ("CAISSONS S3 : A 1,27×0,58 ? (client : 0,58×0,27 — 1,27 retenu, la chaîne radiale ferme) · B 1,05×1,63 ? (2ᵉ nombre lu 1,63/1,03) · X non coté (gris) · "
     "C 1,54×1,02 (1,64 ?) · D 0,84×0,77 · E 1,80×1,10 · G 1,53×0,9 · F 1,22×0,84 (0,86 lu) · H 1,35×0,86", False),
    ("S3 — À RÉCONCILIER : cote croquis « 6,59 » (C→G) INCOMPATIBLE avec l'ancrage droit (E = F − 6,54 ; F/H ancrés 3,33/3,26 du bord est) pour L ≈ 23,6 — "
     "position E/G retenue par l'ancrage DROIT + fermetures radiales ; orientation croquis 3 supposée = croquis 2 (bord haut = ext.)", False),
    ("POSE PV : rails en TRONÇONS DROITS par trame — reprise angulaire ≈ 0,5°/table (éclisses) ; rangées PAR SEGMENT, jamais à cheval sur un joint", False),
    ("À CONFIRMER (orange) : positions C2/C3 (recalées au joint) · K3 · 1,6/2,4 · rattachements 4,75/5,5/0,78/0,97×2 (S1) · lectures S3 : 2,5/3,2 · "
     "5,5/5,53 · 3,42 · A · B · structure bord ext (≈ 5,8 m, paliers ≈ 1,7/3,15) · X · L S2 ≈ 23,0 · L S3 ≈ 23,6 · mur est", False),
    ("À CONFIRMER (suite) : les chaînes de chaque segment couvrent-elles bout en bout (muret à muret) ? question posée au client — "
     "si chaînes partielles, développé et posable remontent", False),
    ("RÉSERVE DRV (mémoire) : NON vue au relevé — position à fixer en étude d'exécution (dégagement ≥ 1 m)", False),
]
for i, (t, b) in enumerate(NOTES):
    ax.text(-19.4, -12.75 - i * 0.88, t, fontsize=6.0, va="top", color="#333333",
            fontweight="bold" if b else "normal")

# ---------------------------------------------------------------- légende
LX, LY, DY = -39.6, -13.10, 0.86
def leg_text(i, txt):
    ax.text(LX + 1.35, LY - i * DY, txt, fontsize=6.2, va="center", zorder=30)
r = Rectangle((LX, LY - 0.21), 1.0, 0.42, facecolor="#bbf7d0",
              edgecolor="#15803d", lw=0.6, zorder=30)
ax.add_patch(r)
ax.plot([LX, LX + 1.0], [LY, LY], color="#15803d", lw=0.4, zorder=31)
leg_text(0, "table PV E-O (2 modules, 2,382 × 2,25)")
ax.add_patch(Rectangle((LX, LY - DY - 0.21), 1.0, 0.42, facecolor="#d8dee6",
             edgecolor=D.NOIR, hatch="////", lw=0.8, zorder=30))
leg_text(1, "caisson béton relevé (chaîné)")
r = Rectangle((LX, LY - 2 * DY - 0.21), 1.0, 0.42, facecolor="white",
              edgecolor=D.ORANGE, hatch="////", lw=0.8, zorder=30)
r.set_linestyle("--")
ax.add_patch(r)
leg_text(2, "caisson — lecture / position à confirmer")
ax.add_patch(Rectangle((LX, LY - 3 * DY - 0.21), 1.0, 0.42, facecolor="#eef1f5",
             edgecolor=D.NOIR, lw=1.6, zorder=30))
leg_text(3, "cage d'escalier (murs épais)")
r = Rectangle((LX, LY - 4 * DY - 0.21), 1.0, 0.42, facecolor="#dbeafe",
              edgecolor=D.BLEU, hatch="//////", lw=0.9, zorder=30)
ax.add_patch(r)
leg_text(4, "muret AU RAS (h = 0, ép. 0,45) — joint, confirmé")
r = Rectangle((LX, LY - 5 * DY - 0.21), 1.0, 0.42, facecolor="#e2e8f0",
              edgecolor=D.ORANGE, hatch="....", lw=0.8, zorder=30)
r.set_linestyle("--")
ax.add_patch(r)
leg_text(5, "structure / caisson déduit du croquis (non coté)")
ax.add_patch(FancyArrowPatch((LX, LY - 6 * DY), (LX + 1.0, LY - 6 * DY),
             arrowstyle="<|-|>", mutation_scale=6, lw=0.8, color=D.BLEU, zorder=30))
leg_text(6, "cote mesurée / confirmée (croquis Reda 27/07)")
ax.add_patch(FancyArrowPatch((LX, LY - 7 * DY), (LX + 1.0, LY - 7 * DY),
             arrowstyle="<|-|>", mutation_scale=6, lw=0.8, color=D.ORANGE, zorder=30))
leg_text(7, "cote / élément à confirmer")

D.scale_bar(ax, LX, -22.6)
D.cartouche(fig, [
    ("ACCORDIA TECH — Consultation FRDISI PV + stockage, Mohammedia", True),
    ("Bât. B — AILE EN ARC — VUE EN ARC (R_ext ≈ 274 m) — ASSEMBLAGE CORRIGÉ 3 SEGMENTS — DÉFINITIVE", True),
    ("Relevé : R. Kasri 27/07/2026 (TOUT relevé) — restitution TAQINOR", False),
    ("Échelle ≈ 1:200 (A3) — cotes en mètres — NE REMPLACE PAS 05E/06G", False),
])

# ---------------------------------------------------------------- contrôles
closure("chaîne ext S1 recalculée -> joint S1/S2 (angle cage)", SX[-1], S1_LEN, tol=0.10)
closure("fermeture transversale K6/K7", 3.78 + 0.90 + 1.50 + 0.86 + 3.86, W, tol=0.05)
closure("courbure int = ext x R_int/R_ext", 11.38 * R_INT / R_EXT, 10.93, tol=0.05)
closure("S3 radiale gauche (3,61+0,58+1,38+1,63+3,42)", 3.61 + 0.58 + 1.38 + 1.63 + 3.42, 10.70, tol=0.15)
closure("S3 radiale C/D (3,681+1,02+1,5+0,77+3,83)", 3.681 + 1.02 + 1.5 + 0.77 + 3.83, 10.80, tol=0.15)
closure("S3 radiale E/G (3,74+1,10+1,39+0,90+3,67)", 3.74 + 1.10 + 1.39 + 0.90 + 3.67, 10.80, tol=0.15)
closure("S3 radiale F/H (3,85+0,84+1,5+0,86+3,76)", 3.85 + 0.84 + 1.5 + 0.86 + 3.76, 10.91, tol=0.15)
closure("developpe releve total", LEN, 68.05, tol=0.10)
assert K4[1] + CLEAR <= K7[0], "K4 recouvre K7 !"
print(f"tables={len(TABLES)}  modules={NMOD} (S1 {SEG_N[0]} / S2 {SEG_N[1]} / S3 {SEG_N[2]}) — "
      f"capacite >= 144 : {'OUI' if CAP144 else 'NON — A SIGNALER'}")
print(f"arc: R_ext={R_EXT}  developpe={LEN:.2f}  ouverture={math.degrees(TH):.1f} deg  "
      f"fleche={R_EXT * (1 - math.cos(TH / 2)):.2f}  corde={2 * R_EXT * math.sin(TH / 2):.2f}")

fig.savefig("VUE_TOITURE_BAT_B_ARC.pdf", bbox_inches="tight")
fig.savefig("VUE_TOITURE_BAT_B_ARC.png", dpi=170, bbox_inches="tight")
print("VUE ARC corrigee : render ok")
