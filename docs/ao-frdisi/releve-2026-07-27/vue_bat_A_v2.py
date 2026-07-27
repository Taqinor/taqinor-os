# -*- coding: utf-8 -*-
"""VUE DE TOITURE — Bât. A (aile en L), Résidence universitaire UIB, Mohammedia — V2.

V2 = même relevé, même géométrie, mêmes obstacles MESURÉS que vue_bat_A.py ;
seul le CALEPINAGE est refait selon les consignes client du 27/07 :

  1) CORRECTION D'ORIENTATION (la vraie raison du gain). Une table « E-O » porte
     2 modules dos à dos, l'un face EST l'autre face OUEST : son FAÎTAGE est
     forcément NORD-SUD, donc une rangée court NORD-SUD. Dans la v1, l'aile 2
     était juste (faîtage N-S) mais la BARRE était calepinée avec des rangées
     Est-Ouest, donc un faîtage E-O = des modules face NORD et face SUD —
     impossible à construire. V2 remet tout le bâtiment en rangées N-S.
  2) Le L est UNE SEULE surface : une rangée qui reste à l'ouest de l'aile
     (x ≤ 10,85) descend d'un seul tenant de la barre dans l'aile — plus de
     rive perdue à la jonction.
  3) Tables E-O PORTRAIT 1,134 × 4,70 (2 × 2,382 × cos15° + faîtage), soit la
     table CANONIQUE de la planche Bât. C — un seul type de table sur le projet.
  4) Allées « 0,60 minimum, OPTIMISÉES » (consigne client) : rangées à positions
     EXPLICITES, le surplus de largeur concentré là où il ne coûte rien
     (2,45 devant la cage d'escalier, 3,15 sur la colonne B7/A1).
     Rives 0,35 · dégagement obstacles 0,30 · 0,50 pour un obstacle de NATURE
     INCONNUE (le grand rectangle non coté de la jonction).
  5) Aucun obstacle MESURÉ n'est supprimé. Les 2 emprises qui ne viennent PAS du
     relevé sont conservées dans le compte retenu et chiffrées à part :
       · GRECT — « grand rectangle non coté » de la jonction : vu sur le croquis
         C mais JAMAIS coté ; sa taille (1,30 × 2,21) et sa position sont
         DEVINÉES → +8 modules s'il est écarté ou plus petit ;
       · PAN — pan coupé SE : il vient du PLAN, jamais relevé → +4 modules si
         l'angle est droit.
  Compte DESSINÉ = COMPTÉ (asserts) ; aucun « maximum » théorique affiché.

Sorties : VUE_TOITURE_BAT_A_L_V2.pdf / .png
"""
import os
import sys
import math

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.chdir(BASE)

import dessin as D
import calepinage as C
from solveur import chain, closure
from matplotlib.patches import Polygon, Rectangle, FancyArrowPatch

# ================================================================ GÉOMÉTRIE RELEVÉE
B_LEN, A_LEN = 23.58, 23.50
BAR = B_LEN + A_LEN                      # 47,08
W_B, W_BE, W_A = 10.76, 10.77, 10.92     # largeurs relevées B-ouest / raccord B/A / A
LEG_W, LEG_S = 11.2, 29.74               # aile 2 : bande sous la barre (40,5 - 10,76)
CUT_W, CUT_H = 2.18, 4.04                # pan coupé SE (forme du plan — non coté relevé)
NX0, NX1, NDY = 31.28, 32.82, 0.74       # décroché sud accès toiture — largeur 1,54

# ---------------- caissons barre (x0, x1, y0, y1, label, pos_label, incertain)
CAIS_BAR = [
    # zone B — rangée basse (chaîne fermée 23,58)
    (3.39, 4.70, 3.77, 4.92,   "1,31×1,15", "below", False),
    (11.17, 12.50, 3.84, 4.98, "1,33×1,14", "below", False),
    (19.05, 20.35, 3.33, 4.34, "1,30×1,01", "below", False),
    # zone B — rangée haute
    (3.16, 4.27, 5.91, 7.02,   "1,11×1,11", "above", False),
    (8.03, 9.14, 6.08, 7.38,   "1,11×1,30", "above", False),   # verticale sous = 6,08
    (16.52, 17.32, 8.43, 9.06, "0,8×0,63 ?", "below", True),   # lecture 0,18 improbable
    (18.92, 20.35, 6.02, 7.46, "1,43×1,44", "above", False),
    # zone A — rangée haute
    (24.86, 26.41, 6.82, 7.46, "1,53×0,64", "left", True),
    (27.06, 27.92, 6.53, 7.08, "0,85×0,55", "below", False),   # offset rive 3,84
    (32.53, 33.03, 6.14, 6.98, "0,84×0,50", "below", False),   # TRANSPOSÉ debout
    (33.68, 34.63, 6.41, 6.88, None,        "below", True),    # 0,94×0,47? (texte à part)
    (39.50, 40.48, 6.61, 7.07, "0,98×0,46", "below", True),    # TRANSPOSÉ couché
    (43.975, 44.515, 6.18, 7.05, "0,87×0,54", "below", False), # TRANSPOSÉ debout
    # zone A — rangée basse
    (32.18, 32.88, 3.74, 4.73, "0,70×0,99", "right", False),
    (39.31, 40.72, 3.75, 4.65, "1,41×0,90", "below", False),
    (45.68, 46.98, 3.75, 4.81, "1,30×1,06", "below", False),
]
CAGE = (12.23, 14.70, 6.13, 10.76)       # cage d'escalier ≈2,5×4,6 (5,97/1,15 recoupés)
DECN = (14.70, 17.47, 9.61, 10.76)       # décroché nord 2,77 — prof. 1,15 ?
NOTCH = (NX0, NX1, 0.0, NDY)             # décroché accès sud — largeur 1,54
EDIC = (30.21, 31.13, 0.0, 0.74)         # édicule ≈0,92×0,74 — obstacle réel (3,18)

# ---------------- aile 2 — MIROITÉE : quadruple 1,35×1,15 au SUD, cluster au NORD
# (s0, s1, x0, x1, label, pos, incertain) — s = distance sous le bord sud de la barre
CAIS_LEG = [
    (25.01, 26.36, 3.78, 4.93, "1,35×1,15", "below", False),   # ouest-sud (3,38 du mur)
    (17.12, 18.47, 3.78, 4.93, "1,35×1,15", "above", False),   # ouest-nord (6,54)
    (25.01, 26.36, 6.33, 7.48, "1,35×1,15", "below", False),   # est-sud (3,38 du mur)
    (16.99, 18.34, 6.33, 7.48, "1,35×1,15", "above", False),   # est-nord (6,67)
    (9.24, 10.45, 3.78, 4.85, "1,07×1,21 ?", "above", True),
    (1.45, 1.87, 3.72, 4.82,  "1,10×0,42", "below", False),    # jonction : 1,45 du mur
    (9.63, 10.26, 6.40, 7.20, "0,8×0,63", "below", True),
    (9.70, 10.40, 7.35, 7.75, "0,4×0,7 ?", "above", True),
]
GRECT = (0.40, 1.70, 4.95, 7.16)         # grand rectangle NON COTÉ (jonction) — DEVINÉ
PAN = (LEG_S - CUT_H, LEG_S, LEG_W - CUT_W, LEG_W)   # pan coupé SE — vient du PLAN

# ---------------- contrôles de fermeture (v1 — CONSERVÉS et durcis en asserts)
xb = chain(0, 3.39, 1.31, 6.47, 1.33, 6.55, 1.30, 3.23)
assert closure("B — chaîne basse fermée", xb[-1], B_LEN, tol=0.05)[0]
xn = chain(0, 12.23, 2.47, 2.77, 6.11)
assert closure("B — chaîne nord (cage+décroché+6,11)", xn[-1], B_LEN, tol=0.05)[0]
tT = chain(0, 3.78, 1.15, 1.40, 1.15, 3.72)
assert closure("Aile 2 — transversale fermée", tT[-1], LEG_W, tol=0.02)[0]
tW = chain(0, 3.38, 1.35, 6.54, 1.35, 6.84, 1.21, 7.37, 0.42, 1.45)
assert closure("Aile 2 — chaîne ouest S→N (+10,76 barre = 40,67)", tW[-1], LEG_S,
               tol=0.25)[0]
tE = chain(0, 3.38, 1.35, 6.67, 1.35, 6.73, 0.63, 4.31, 5.50)
assert closure("Aile 2 — chaîne est S→N", tE[-1], LEG_S, tol=0.25)[0]

# ================================================================ CALEPINAGE V2
TBL_W, TBL_L = 4.70, 1.134     # table E-O PORTRAIT : 4,70 d'emprise E-O, pas 1,134 N-S
RIVE, ALLEE = 0.35, 0.60
CLEAR, CLEAR_INC = 0.30, 0.50  # dégagement standard / nature inconnue
ENG = 152                      # engagement bordereau Bât. A (95,0 kWc)

# --- obstacles unifiés : (x0, x1, y0, y1, dégagement, repère, provenance)
#     provenance : "R" relevé mesuré · "R?" relevé, cote douteuse · "P" plan
#                  "X" PROVISOIRE — emprise devinée, jamais cotée au relevé
OBS = []
for (x0, x1, y0, y1, lab, pos, unc) in CAIS_BAR:
    OBS.append((x0, x1, y0, y1, CLEAR_INC if unc else CLEAR,
                "caisson barre", "R?" if unc else "R"))
OBS.append((CAGE[0], CAGE[1], CAGE[2], CAGE[3], CLEAR, "CAGE", "R"))
OBS.append((DECN[0], DECN[1], DECN[2], DECN[3], CLEAR, "DECN", "R"))
OBS.append((NOTCH[0], NOTCH[1], NOTCH[2], NOTCH[3], RIVE, "NOTCH", "R"))
OBS.append((EDIC[0], EDIC[1], EDIC[2], EDIC[3], CLEAR, "EDIC", "R"))
for (s0, s1, x0, x1, lab, pos, unc) in CAIS_LEG:
    OBS.append((x0, x1, -s1, -s0, CLEAR_INC if unc else CLEAR,
                "caisson aile", "R?" if unc else "R"))
OBS.append((GRECT[2], GRECT[3], -GRECT[1], -GRECT[0], CLEAR_INC, "GRECT", "X"))
OBS.append((PAN[2], PAN[3], -PAN[1], -PAN[0], RIVE, "PAN", "P"))

PROVISOIRES = ("GRECT", "PAN")           # jamais mesurés au relevé
assert sum(1 for o in OBS if o[6] in ("R", "R?")) == 28, "28 obstacles relevés"
assert [o[5] for o in OBS if o[6] in ("X", "P")] == ["GRECT", "PAN"]

# --- enveloppe : le L est une seule surface
X_W, X_E = RIVE, BAR - RIVE               # 0,35 → 46,73
X_LEG_E = LEG_W - RIVE                    # 10,85 : au-delà, pas d'aile
Y_N = W_B - RIVE                          # 10,41 (largeur B, conservatrice vs A 10,92)
Y_S_BAR, Y_S_LEG = RIVE, -LEG_S + RIVE    # 0,35 / -29,39


def band(x0):
    """Étendue N-S utile d'une rangée [x0, x0+TBL_W] (le L est continu à l'ouest)."""
    return (Y_S_LEG if x0 + TBL_W <= X_LEG_E + 1e-9 else Y_S_BAR), Y_N


def free_segments(x0, obs):
    """Segments N-S libres de la rangée [x0, x0+TBL_W], dégagements appliqués."""
    x1 = x0 + TBL_W
    ymin, ymax = band(x0)
    blocked = []
    for (ox0, ox1, oy0, oy1, c, lab, src) in obs:
        if ox1 + c <= x0 + 1e-9 or ox0 - c >= x1 - 1e-9:
            continue
        blocked.append((max(ymin, oy0 - c), min(ymax, oy1 + c)))
    blocked = C.merge([b for b in blocked if b[1] > b[0]])
    segs, cur = [], ymin
    for a, b in blocked:
        if a > cur:
            segs.append((cur, min(a, ymax)))
        cur = max(cur, b)
    if cur < ymax:
        segs.append((cur, ymax))
    return [(a, b) for a, b in segs if b > a]


def count_rows(rows, obs):
    """Comptage INDÉPENDANT du dessin (garde-fou compte affiché = dessiné)."""
    return sum(2 * int((b - a + 1e-9) // TBL_L)
               for x0 in rows for (a, b) in free_segments(x0, obs))


# --- RANGÉES EXPLICITES OPTIMISÉES (consigne « 0,60 mini, optimisées ») :
#     positions retenues après optimisation exhaustive au pas de 1 cm sous les
#     contraintes rives 0,35 / allées ≥ 0,60 / dégagements ci-dessus.
#     Le surplus de largeur est concentré en 2 allées larges : 2,45 devant la
#     cage d'escalier et 3,15 sur la colonne des caissons B7 / A1.
ROWS = [0.35, 5.65, 12.80, 20.65, 25.95, 31.25, 36.55, 41.85]
assert ROWS == sorted(ROWS)
assert ROWS[0] >= RIVE - 1e-9, "rive ouest"
assert ROWS[-1] + TBL_W <= X_E + 1e-9, "rive est"
for a, b in zip(ROWS, ROWS[1:]):
    assert b - (a + TBL_W) >= ALLEE - 1e-9, ("allée < 0,60", a, b)
for r in ROWS:                       # une rangée est dans l'aile OU s'arrête à la barre
    assert r + TBL_W <= X_LEG_E + 1e-9 or r >= X_LEG_E - 1e-9, ("rive est aile", r)

N = count_rows(ROWS, OBS)
KWC = N * 0.625
# comptes AVEC / SANS les 2 emprises jamais mesurées (rangées INCHANGÉES)
OBS_NO_G = [o for o in OBS if o[5] != "GRECT"]
OBS_NO_GP = [o for o in OBS_NO_G if o[5] != "PAN"]
N_NO_G = count_rows(ROWS, OBS_NO_G)
N_NO_GP = count_rows(ROWS, OBS_NO_GP)

# --- références pour information (NON dessinées, jamais présentées comme un « max »)
#     v1 : tables paysage 2,382×2,25, allées 1,20, bandes séparées, barre en rangées E-O
obs_bar_v1 = [c[:4] for c in CAIS_BAR] + [CAGE, DECN, NOTCH, EDIC]
obs_leg_v1 = [c[:4] for c in CAIS_LEG] + [GRECT, PAN]
assert len(C.rows_for(W_B, 1.20, 0.35, 0.0)) == 3, "v1 : 3 rangées sur la barre"
assert len(C.rows_for(LEG_W, 1.20, 0.35, 0.0)) == 3, "v1 : 3 rangées sur l'aile"
n_v1 = (C.best_phase(BAR, W_B, obs_bar_v1, 1.20, 0.35, 0.30, end_rive=0.50)[0]
        + C.best_phase(LEG_S, LEG_W, obs_leg_v1, 1.20, 0.35, 0.30, end_rive=0.50)[0])
n_cons = (C.best_phase(BAR, W_B, obs_bar_v1, 1.50, 0.50, 0.50, end_rive=0.50)[0]
          + C.best_phase(LEG_S, LEG_W, obs_leg_v1, 1.50, 0.50, 0.50, end_rive=0.50)[0])

VERDICT = "CONFIRMÉ" if N >= ENG else "TENDU"
VERT, VERT_F, TENDU_C = "#15803d", "#bbf7d0", "#c2410c"


def fr(v, dec=2):
    return f"{v:.{dec}f}".replace(".", ",")


# ================================================================ FEUILLE
fig, ax = D.new_sheet(
    "VUE DE TOITURE — BÂTIMENT A (AILE EN L) — RÉSIDENCE UNIVERSITAIRE UIB, MOHAMMEDIA — V2",
    "Contour, locaux et obstacles : RELEVÉ CONTRADICTOIRE du 27/07/2026 (croquis A/B/C) — "
    "calepinage V2 : tables E-O PORTRAIT 1,134×4,70 (2 modules 625 Wc, 15°), FAÎTAGE NORD-SUD "
    "(modules face E et face O), rangées N-S continues sur tout le L, positions EXPLICITES — "
    "allées 0,60 mini OPTIMISÉES, rives 0,35, dégagement 0,30 (0,50 nature inconnue) — "
    "BLEU = mesuré · ORANGE = à confirmer · GRIS = plan/déduit",
    (-7.5, 64.0), (-34.8, 16.2))

# ---------------- contour (avec décroché sud 1,54 + ressaut de largeur B/A)
outline = [(0, W_B), (B_LEN, W_BE), (B_LEN, W_A), (BAR, W_A), (BAR, 0),
           (NX1, 0), (NX1, NDY), (NX0, NDY), (NX0, 0), (LEG_W, 0),
           (LEG_W, -LEG_S + CUT_H), (LEG_W - CUT_W, -LEG_S), (0, -LEG_S)]
ax.add_patch(Polygon(outline, closed=True, fill=False, lw=2.4, edgecolor=D.NOIR,
                     zorder=12))
acro = [(0.28, W_B - 0.28), (B_LEN, W_BE - 0.28), (B_LEN, W_A - 0.28),
        (BAR - 0.28, W_A - 0.28), (BAR - 0.28, 0.28), (NX1 + 0.28, 0.28),
        (NX1 + 0.28, NDY + 0.28), (NX0 - 0.28, NDY + 0.28), (NX0 - 0.28, 0.28),
        (LEG_W - 0.28, 0.28), (LEG_W - 0.28, -25.63), (8.85, -LEG_S + 0.28),
        (0.28, -LEG_S + 0.28)]
ax.add_patch(Polygon(acro, closed=True, fill=False, lw=0.6, edgecolor="#666666",
                     zorder=11))


# ---------------- calepinage : pose des tables (positions EXPLICITES)
def draw_tables(rows, obs):
    total, placed = 0, []
    for x0 in rows:
        for (a, b) in free_segments(x0, obs):
            n = int((b - a + 1e-9) // TBL_L)
            total += 2 * n
            for i in range(n):
                yy = a + i * TBL_L
                placed.append((x0, yy))
                ax.add_patch(Rectangle((x0, yy), TBL_W, TBL_L, facecolor=VERT_F,
                                       edgecolor=VERT, lw=0.35, zorder=6))
            if n:      # faîtage continu N-S du segment (séparation module E / module O)
                ax.plot([x0 + TBL_W / 2] * 2, [a, a + n * TBL_L], color=VERT,
                        lw=0.5, zorder=7)
    return total, placed


n_drawn, placed = draw_tables(ROWS, OBS)

# ---------------- contrôles géométriques (durcis vs v1)
EPS = 1e-6
assert n_drawn == N, (n_drawn, N)                    # DESSINÉ = COMPTÉ
assert len(placed) * 2 == N
for (tx, ty) in placed:
    tx1, ty1 = tx + TBL_W, ty + TBL_L
    ymin, ymax = band(tx)
    # rives : dans l'emprise utile, y compris la rive est de l'aile
    assert X_W - EPS <= tx and tx1 <= X_E + EPS, ("rive E-O", tx, ty)
    assert ymin - EPS <= ty and ty1 <= ymax + EPS, ("rive N-S", tx, ty)
    if ty < 0:                                        # table dans l'aile
        assert tx1 <= X_LEG_E + EPS, ("table hors aile", tx, ty)
        assert ty >= -LEG_S + RIVE - EPS, ("rive sud aile", tx, ty)
    # dégagement de CHAQUE obstacle (dégagement propre à l'obstacle)
    for (ox0, ox1, oy0, oy1, c, lab, src) in OBS:
        assert (ty >= oy1 + c - EPS or ty1 <= oy0 - c + EPS
                or tx >= ox1 + c - EPS or tx1 <= ox0 - c + EPS), \
            ("dégagement", tx, ty, lab)
# non-chevauchement strict entre tables
for i in range(len(placed)):
    xi, yi = placed[i]
    for j in range(i + 1, len(placed)):
        xj, yj = placed[j]
        assert (xi + TBL_W <= xj + EPS or xj + TBL_W <= xi + EPS
                or yi + TBL_L <= yj + EPS or yj + TBL_L <= yi + EPS), \
            ("chevauchement", placed[i], placed[j])
# les 2 emprises jamais mesurées ne peuvent que faire GAGNER des modules
assert N_NO_G >= N and N_NO_GP >= N_NO_G

# repère O / E sur la première rangée (bas de l'aile, zone dégagée)
ax.text(ROWS[0] + 1.17, -28.6, "O", fontsize=6.5, color=VERT, ha="center",
        va="center", fontweight="bold", zorder=9)
ax.text(ROWS[0] + 3.53, -28.6, "E", fontsize=6.5, color=VERT, ha="center",
        va="center", fontweight="bold", zorder=9)


# ---------------- locaux (murs épais + croix)
def local(x0, y0, x1, y1, unc=False, wall=0.18):
    ec = D.ORANGE if unc else D.NOIR
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor="#cbd5e1",
                 edgecolor=ec, lw=1.9, hatch="////", zorder=16))
    ix0, iy0, ix1, iy1 = x0 + wall, y0 + wall, x1 - wall, y1 - wall
    ax.add_patch(Rectangle((ix0, iy0), ix1 - ix0, iy1 - iy0, facecolor="white",
                 edgecolor=ec, lw=0.9, zorder=17))
    ax.plot([ix0, ix1], [iy0, iy1], color="#94a3b8", lw=0.6, zorder=18)
    ax.plot([ix0, ix1], [iy1, iy0], color="#94a3b8", lw=0.6, zorder=18)


local(CAGE[0], CAGE[2], CAGE[1], CAGE[3])
ax.text((CAGE[0] + CAGE[1]) / 2, (CAGE[2] + CAGE[3]) / 2,
        "CAGE D'ESCALIER\n≈2,5 × ≈4,6\nhors PV", fontsize=5.2, ha="center",
        va="center", rotation=90, fontweight="bold", color="#111111", zorder=25)
local(DECN[0], DECN[2], DECN[1], DECN[3])
ax.text(17.70, 10.18, "prof. 1,15 ?", fontsize=4.8, ha="left", va="center",
        color=D.ORANGE, fontweight="bold", zorder=25)
local(EDIC[0], EDIC[2], EDIC[1], EDIC[3], unc=True, wall=0.12)
ax.text(29.95, -0.32, "édicule ≈0,92×0,74", fontsize=5.6, ha="right", va="top",
        fontweight="bold", color=D.ORANGE, zorder=25)
ax.text(33.55, -0.75, "ACCÈS TOITURE (décroché 1,54)", fontsize=6.3, ha="left",
        va="center", fontweight="bold", color="#111111", zorder=25)

# ---------------- caissons barre (hachurés + étiquettes)
for x0, x1, y0, y1, lab, pos, unc in CAIS_BAR:
    D.caisson(ax, x0, y0, x1 - x0, y1 - y0, label=lab, uncertain=unc,
              label_pos=pos, fs=5.6)
ax.text(34.30, 5.42, "0,94×0,47?", fontsize=5.6, ha="center", va="top",
        color=D.ORANGE, fontweight="bold", zorder=25)

# ---------------- caissons aile 2
for s0, s1, x0, x1, lab, pos, unc in CAIS_LEG:
    D.caisson(ax, x0, -s1, x1 - x0, s1 - s0, label=lab, uncertain=unc,
              label_pos=pos, fs=5.2)
gr = Rectangle((GRECT[2], -GRECT[1]), GRECT[3] - GRECT[2], GRECT[1] - GRECT[0],
               facecolor="none", edgecolor=D.ORANGE, lw=1.4, zorder=15)
gr.set_linestyle("--")
ax.add_patch(gr)
ax.annotate("(1) grand rectangle NON COTÉ\n(emprise devinée — dégagt 0,50)\n"
            "→ +8 modules s'il est écarté",
            xy=(GRECT[3], -(GRECT[0] + GRECT[1]) / 2), xytext=(13.4, -1.9),
            fontsize=5.6, ha="left", va="center", color=D.ORANGE,
            fontweight="bold", zorder=27,
            arrowprops=dict(arrowstyle="->", lw=0.7, color=D.ORANGE),
            bbox=dict(fc="white", ec=D.ORANGE, lw=0.6, alpha=0.95, pad=1.4))

# ---------------- séparation zones + étiquettes
ax.plot([B_LEN, B_LEN], [0, W_BE], color="#7c3aed", lw=0.9, ls="--", zorder=13)
ax.text(5.6, 11.45, "ZONE B (croquis B)", fontsize=9, fontweight="bold",
        color="#7c3aed", ha="center")
ax.text(44.0, 11.5, "ZONE A (croquis A)", fontsize=9, fontweight="bold",
        color="#7c3aed", ha="center")
ax.text(1.6, -13.5, "AILE 2 (croquis C)", fontsize=9, fontweight="bold",
        color="#7c3aed", rotation=90, va="center")


# ================================================================ COTES
def dimb(p1, p2, off, text, color=D.BLEU, fs=6.4):
    """Cote avec texte sur fond blanc (lisible par-dessus le calepinage)."""
    ux, uy, _ = D._unit(p1, p2)
    nx, ny = -uy, ux
    q1 = (p1[0] + nx * off, p1[1] + ny * off)
    q2 = (p2[0] + nx * off, p2[1] + ny * off)
    s = 1 if off >= 0 else -1
    for p, q in ((p1, q1), (p2, q2)):
        a = (p[0] + nx * 0.12 * s, p[1] + ny * 0.12 * s)
        b = (q[0] + nx * 0.18 * s, q[1] + ny * 0.18 * s)
        ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=0.55, zorder=20)
    ax.add_patch(FancyArrowPatch(q1, q2, arrowstyle="<|-|>", mutation_scale=7,
                                 lw=0.8, color=color, shrinkA=0, shrinkB=0, zorder=21))
    mx, my = (q1[0] + q2[0]) / 2, (q1[1] + q2[1]) / 2
    ang = math.degrees(math.atan2(uy, ux))
    if ang > 90 or ang <= -90:
        ang += 180
    ax.text(mx, my, text, fontsize=fs, color=color, ha="center", va="center",
            rotation=ang, rotation_mode="anchor", zorder=22,
            bbox=dict(fc="white", ec="none", alpha=0.9, pad=0.8))


# --- extérieur nord
D.dim(ax, (DECN[0], W_B), (DECN[1], W_B), off=0.75, text="2,77")
D.dim(ax, (DECN[1], W_B), (B_LEN, W_B), off=0.75, text="6,11")
D.dim(ax, (0, W_B), (B_LEN, W_BE), off=1.95, text="23,58 (chaîne fermée)")
D.dim(ax, (B_LEN, W_A), (BAR, W_A), off=1.80, text="23,50 (mesuré — relire : 23,6 ?)")
D.dim(ax, (0, W_B), (BAR, W_A), off=3.35,
      text="47,08 relevé (= 23,58 + 23,50) — plan : 48,0")
# --- extérieur est / ouest + raccord B/A
D.dim(ax, (BAR, 0), (BAR, W_A), off=-2.05, text="10,92 relevé")
D.dim(ax, (0, 0), (0, W_B), off=3.0, text="10,76 relevé")
dimb((23.42, 0), (23.42, W_BE), 0.0, "10,77 (raccord B/A)", fs=5.8)
# --- zone B : chaîne basse + offsets verticaux
Y_C1 = 3.90                                   # position de la chaîne basse (inchangée v1)
dimb((0, Y_C1), (3.39, Y_C1), 0.0, "3,39")
dimb((4.70, Y_C1), (11.17, Y_C1), 0.0, "6,47")
dimb((12.50, Y_C1), (19.05, Y_C1), 0.0, "6,55")
dimb((20.35, Y_C1), (B_LEN, Y_C1), 0.0, "3,23")
dimb((4.30, 0), (4.30, 3.77), -0.45, "3,77")
dimb((11.85, 0), (11.85, 3.84), -0.45, "3,84")
dimb((19.70, 0), (19.70, 3.33), -0.45, "3,33")
# --- zone B : chaîne médiane + verticales relevées
dimb((0, 6.55), (3.16, 6.55), 0.0, "3,16", color=D.ORANGE)
dimb((4.27, 6.55), (8.03, 6.55), 0.0, "3,76")
dimb((9.14, 6.55), (12.23, 6.55), 0.0, "3,09")
dimb((14.70, 8.74), (16.52, 8.74), 0.0, "1,82")
dimb((17.32, 7.45), (18.92, 7.45), 0.0, "1,75")
dimb((20.35, 6.72), (B_LEN, 6.72), 0.0, "3,23")
dimb((3.70, 7.02), (3.70, W_B), -0.45, "3,74")
dimb((8.60, 7.38), (8.60, W_B), -0.45, "3,83")
dimb((8.60, 0), (8.60, 6.08), -0.45, "6,08")
dimb((12.90, 0), (12.90, 6.13), -0.35, "5,97", fs=6.2)
dimb((12.35, 4.98), (12.35, 6.13), 0.0, "1,15", fs=5.2)
D.dim(ax, (16.92, 9.06), (16.92, 9.61), off=0.55, text="0,55", fs=5.2)
dimb((19.60, 7.46), (19.60, W_B), -0.45, "3,3")
dimb((3.95, 4.92), (3.95, 5.91), 0.42, "1,35 ?", color=D.ORANGE, fs=6)
dimb((19.95, 4.34), (19.95, 6.02), 0.42, "1,31 ?", color=D.ORANGE, fs=6)
# --- zone A : chaîne haute (intérieure) + offsets nord
ya = 8.55
dimb((B_LEN, ya), (24.86, ya), 0.0, "1,26")
dimb((27.92, ya), (33.03, ya), 0.0, "5,22")
dimb((34.63, ya), (39.50, ya), 0.0, "5,04")
dimb((40.48, ya), (43.975, ya), 0.0, "2,55 ?", color=D.ORANGE)
dimb((44.515, ya), (BAR, ya), 0.0, "2,58")
dimb((25.60, 7.46), (25.60, W_A), -0.45, "3,3")
dimb((27.49, 7.08), (27.49, W_A), -0.45, "3,84")
dimb((32.80, 6.98), (32.80, W_A), -0.45, "3,78")
dimb((34.15, 6.88), (34.15, W_A), 0.45, "3,88")
dimb((39.99, 7.07), (39.99, W_A), -0.45, "3,85")
dimb((44.25, 7.05), (44.25, W_A), -0.45, "3,84")
dimb((32.78, 6.55), (34.155, 6.55), 0.0, "1,53", fs=5.4)
# liaisons verticales relevées (croquis A)
ax.plot([34.63, 37.35], [6.41, 6.41], color="#94a3b8", lw=0.45, ls=":", zorder=19)
ax.plot([36.65, 39.31], [4.65, 4.65], color="#94a3b8", lw=0.45, ls=":", zorder=19)
dimb((37.0, 6.41), (37.0, 4.65), 0.0, "1,75", fs=6)
ax.plot([44.515, 45.45], [6.18, 6.18], color="#94a3b8", lw=0.45, ls=":", zorder=19)
ax.plot([44.75, 45.68], [4.81, 4.81], color="#94a3b8", lw=0.45, ls=":", zorder=19)
dimb((45.1, 6.18), (45.1, 4.81), 0.0, "1,37", fs=6)
# --- zone A : chaîne basse (sud) + cluster sud-ouest
dimb((32.88, Y_C1), (39.31, Y_C1), 0.0, "6,43")
dimb((39.31, Y_C1 - 0.85), (45.68, Y_C1 - 0.85), 0.0, "6,37")
dimb((32.50, 0), (32.50, 3.74), 0.45, "3,74")
dimb((40.00, 0), (40.00, 3.75), -0.45, "3,75")
dimb((46.30, 0), (46.30, 3.75), -0.45, "3,75")
dimb((26.41, 6.82), (26.79, 4.46), 0.0, "2,39 ?", color=D.ORANGE, fs=6)
dimb((26.79, 1.20), (26.79, 0.0), 0.0, "1,2 ?", color=D.ORANGE, fs=6)
dimb((31.13, 0.74), (32.18, 3.74), 0.0, "3,18", fs=6)
D.dim(ax, (NX0, -0.6), (NX1, -0.6), off=0.0, text="1,54")

# ================================================================ COTES — AILE 2
segW = [("1,45", D.BLEU, 1.45), ("0,42", D.BLEU, 0.42), ("7,37", D.ORANGE, 7.37),
        ("1,21", D.BLEU, 1.21), ("6,84 (6,87 ?)", D.ORANGE, 6.67),
        ("1,35", D.BLEU, 1.35), ("6,54", D.BLEU, 6.54), ("1,35", D.BLEU, 1.35),
        ("3,38", D.BLEU, 3.38)]
yy = 0.0
for txt, col, seg in segW:
    D.dim(ax, (-1.15, yy), (-1.15, yy - seg), off=0.25, text=txt, color=col, fs=6.2)
    yy -= seg
D.dim(ax, (0, -LEG_S), (0, W_B), off=4.55,
      text="40,5 (plan) = 10,76 barre + 29,74 aile", color=D.GRIS)
ax.text(-5.95, -14.9, "chaînes aile 2 : ≈38 – 40,7 — contre-lecture requise",
        fontsize=6.0, color=D.ORANGE, rotation=90, ha="center", va="center", zorder=25)
segE = [("5,5", D.BLEU, 5.32), ("4,31", D.BLEU, 4.31), ("0,63", D.BLEU, 0.63),
        ("6,73", D.BLEU, 6.73), ("1,35", D.BLEU, 1.35), ("6,67", D.BLEU, 6.67),
        ("1,35", D.BLEU, 1.35), ("3,38", D.BLEU, 3.38)]
yy = 0.0
for txt, col, seg in segE:
    D.dim(ax, (12.55, yy), (12.55, yy - seg), off=-0.25, text=txt, color=col, fs=6.2)
    yy -= seg
D.dim(ax, (LEG_W, -LEG_S), (LEG_W, 0), off=-3.1, text="29,74 (= 40,5 − 10,76)",
      color=D.GRIS)
segT = [("3,78", 3.78), ("1,15", 1.15), ("1,40", 1.40), ("1,15", 1.15), ("3,72", 3.72)]
for s_row in (25.685, 17.73):
    xx = 0.0
    for txt, seg in segT:
        dimb((xx, -s_row), (xx + seg, -s_row), 0.0, txt, fs=5.4)
        xx += seg
    ax.text(11.55, -s_row, "Σ 11,20 ✓", fontsize=5.5, color="#15803d",
            fontweight="bold", rotation=90, ha="center", va="center", zorder=25)
dimb((0, -9.85), (3.78, -9.85), 0.0, "3,78", fs=5.4)
dimb((0.55, 0), (0.55, -4.82), 0.0, "4,82 ?", color=D.ORANGE, fs=5.6)
dimb((5.05, -2.7), (6.98, -2.7), 0.0, "1,93 ?", color=D.ORANGE, fs=5.6)
dimb((GRECT[3], -2.55), (LEG_W, -2.55), 0.0, "4,04 ?", color=D.ORANGE, fs=5.6)
D.dim(ax, (LEG_W, -2.18), (LEG_W, 0), off=-0.55, text="2,18 ?", color=D.ORANGE, fs=5.6)
ax.annotate("(2) pan coupé SE : vient du PLAN, jamais relevé\n"
            "→ +4 modules si l'angle est droit",
            xy=(LEG_W - CUT_W / 2, -LEG_S + CUT_H / 2), xytext=(12.9, -33.2),
            fontsize=5.6, ha="left", va="center", color="#475569",
            fontweight="bold", zorder=27,
            arrowprops=dict(arrowstyle="->", lw=0.7, color=D.GRIS),
            bbox=dict(fc="white", ec=D.GRIS, lw=0.6, alpha=0.95, pad=1.4))
D.dim(ax, (0, -LEG_S), (LEG_W, -LEG_S), off=-2.0, text="11,2 (plan)", color=D.GRIS)

# --- paramètres de calepinage cotés une fois (zone A, hors obstacles)
dimb((ROWS[5], 11.55), (ROWS[5] + TBL_W, 11.55), 0.0, "4,70 (table portrait)",
     color=D.GRIS, fs=5.4)
dimb((ROWS[5] + TBL_W, 11.55), (ROWS[6], 11.55), 0.0, "0,60 (allée)",
     color=D.GRIS, fs=5.0)
dimb((ROWS[1] + TBL_W, 2.05), (ROWS[2], 2.05), 0.0, "2,45 (allée large — cage)",
     color=D.GRIS, fs=5.2)
dimb((ROWS[2] + TBL_W, 2.05), (ROWS[3], 2.05), 0.0, "3,15 (allée large)",
     color=D.GRIS, fs=5.2)

# ================================================================ BANDEAU ENGAGEMENT
BX = 28.0
if N >= ENG:
    ax.text(BX, -4.30,
            f"ENGAGEMENT BORDEREAU BÂT. A = {ENG} modules : {VERDICT} — "
            f"{N} modules posables sur le relevé",
            fontsize=9.6, fontweight="bold", ha="center", color=VERT, zorder=30)
else:
    ax.text(BX, -4.30,
            f"ENGAGEMENT BORDEREAU BÂT. A = {ENG} modules : {VERDICT} — "
            f"{N} posables sur le relevé (manque {ENG - N})",
            fontsize=9.6, fontweight="bold", ha="center", color=TENDU_C, zorder=30)
ax.text(BX, -5.35,
        f"V2 (allées 0,60 optimisées / rives 0,35 / dégagt 0,30 · 0,50) : {N} mod. = "
        f"{fr(KWC, 1)} kWc — v1 : {n_v1} — conservateur 1,50/0,50/0,50 : {n_cons}",
        fontsize=6.8, ha="center", color="#374151", zorder=30)
ax.text(BX, -6.25,
        f"emprises JAMAIS MESURÉES conservées dans ce compte : sans (1) → {N_NO_G}"
        f" ({'CONFIRMÉ' if N_NO_G >= ENG else 'TENDU'}) · sans (1) et (2) → {N_NO_GP}"
        f" ({'CONFIRMÉ' if N_NO_GP >= ENG else 'TENDU'})",
        fontsize=6.8, ha="center", color=D.ORANGE, fontweight="bold", zorder=30)

# ---------------- mini-repérage croquis
kx, ky, s = 49.8, -20.6, 0.085
mini = [(0, 10.76), (47.08, 10.76), (47.08, 0), (11.2, 0), (11.2, -25.7),
        (9.0, -29.74), (0, -29.74)]
ax.add_patch(Polygon([(kx + p[0] * s, ky + p[1] * s) for p in mini], closed=True,
             fill=False, lw=1.0, edgecolor="#555555", zorder=30))
for cx, cy, t in ((35.3, 5.4, "A"), (11.8, 5.4, "B"), (5.6, -14.9, "C")):
    ax.text(kx + cx * s, ky + cy * s, t, fontsize=7, ha="center", va="center",
            fontweight="bold", color="#7c3aed", zorder=31)
ax.text(kx - 1.3, ky + 1.6, "repérage croquis (IMG 2952-2955)", fontsize=5.6,
        color="#555555", zorder=30)

D.legende(ax, 49.5, -8.6, [
    ("caisson", "caisson béton relevé — dégagt 0,30"),
    ("caissonU", "caisson à confirmer — dégagt 0,50"),
    ("bloc", "local (cage, édicule) — murs épais"),
    ("dim", "cote mesurée (croquis Reda 27/07)"),
    ("dimU", "cote / rattachement à confirmer"),
], fs=6.0)
ax.add_patch(Rectangle((49.5, -13.1), 4.70 * 0.42, 1.134 * 0.42, facecolor=VERT_F,
             edgecolor=VERT, lw=0.6, zorder=30))
ax.plot([49.5 + 4.70 * 0.21] * 2, [-13.1, -13.1 + 1.134 * 0.42], color=VERT,
        lw=0.6, zorder=31)
ax.text(51.6, -12.85, "table E-O PORTRAIT 1,134 × 4,70\n2 modules 625 Wc, 15° — faîtage\n"
        "N-S (module face OUEST | face EST)", fontsize=6.0, va="center", zorder=30)

# nord + échelle
ax.add_patch(FancyArrowPatch((45.5, -11.0), (45.5, -9.0), arrowstyle="-|>",
             mutation_scale=16, lw=1.6, color="#111111", zorder=30))
ax.text(45.5, -8.7, "N", fontsize=10, ha="center", fontweight="bold", zorder=30)
D.scale_bar(ax, 49.5, -17.4)

# ---------------- contrôles de fermeture
ax.text(13.2, -8.1,
        "CONTRÔLES DE FERMETURE (inchangés — relevé 27/07)\n"
        "· zone B, chaîne basse : 3,39+1,31+6,47+1,33+6,55+1,30+3,23 = 23,58 — résidu 0,00\n"
        "· zone B, chaîne nord : 12,23 (→cage) + 2,47 + 2,77 + 6,11 = 23,58 — résidu 0,00\n"
        "· zone B, cage : 5,97 ≈ 1,15+1,14+3,84 = 6,13 (Δ 0,16) → emprise ≈2,5×4,6 déduite\n"
        "· barre : 23,58 + 23,50 = 47,08 relevé (plan 48,0 → Δ −0,92)\n"
        "· aile 2 OUEST S→N = 29,91 · EST S→N = 29,92 (+10,76 barre ≈ 40,7 ≈ 40,5 plan)\n"
        "· aile 2 TRANSVERSAL : 3,78+1,15+1,40+1,15+3,72 = 11,20 = largeur 11,2 EXACT ✓\n"
        "· largeurs relevées : 10,76 (B ouest) / 10,77 (raccord B/A) / 10,92 (A)\n"
        "· CALEPINAGE : dessiné = compté (assert) · non-chevauchement · rives 0,35 ·\n"
        "  dégagement de chaque obstacle vérifié table par table (asserts)",
        fontsize=6.0, va="top", color="#334155", zorder=30,
        bbox=dict(boxstyle="round,pad=0.45", fc="#f8fafc", ec="#94a3b8", lw=0.7))
# à confirmer
ax.text(13.2, -16.9,
        "À CONFIRMER À LA PROCHAINE VISITE (impact calepinage chiffré)\n"
        "· (1) GRAND RECTANGLE de la jonction (aile 2, nord) : VU sur le croquis C mais JAMAIS COTÉ —\n"
        "  emprise 1,30×2,21 et position DEVINÉES, dégagement 0,50 (nature inconnue) → +8 modules\n"
        "  s'il n'existe pas / est plus petit. Nature ? dimensions ? distance au mur ouest ?\n"
        "· (2) PAN COUPÉ SE de l'aile (2,18 × 4,04) : vient du PLAN, jamais relevé → +4 modules si\n"
        "  l'angle est droit. L'angle sud-est de l'aile est-il coupé, oui ou non ?\n"
        "· 23,50 ou 23,6 (longueur zone A) · 2,55 ? (0,98↔0,87) · 1,53 = entraxe 0,84↔0,94×0,47\n"
        "· zone B : verticales 1,11×1,30 → 6,08+1,30+3,83 = 11,21 vs 10,76 (Δ +0,45, à re-mesurer)\n"
        "  · caisson 0,8×0,63 ? (lu « 0,18 ») · décroché nord : prof. 1,15 ? (0 module d'impact)\n"
        "· zone A SW : 2,39 & 1,2 — rattachements supposés · édicule ≈0,92×0,74 · accès : prof. ≈0,7 ?\n"
        "· aile 2 : 6,84 (relu 6,87 ?) · 7,37 (ou 4,37 ?) · 4,82 · 1,93 · 2,18 · 4,04 (est)",
        fontsize=6.0, va="top", color="#7c2d12", zorder=30,
        bbox=dict(boxstyle="round,pad=0.45", fc="#fff7ed", ec="#d97706", lw=0.7))
# NOTA
nota = (f"NOTA EXÉCUTION — calepinage V2 : {N} modules posables ({fr(KWC, 1)} kWc)\n"
        f"contre {n_v1} en v1, à géométrie et obstacles RELEVÉS identiques. Le gain\n"
        "vient de la CORRECTION D'ORIENTATION (rangées et faîtages N-S : la v1\n"
        "posait la barre en rangées E-O, donc des modules face NORD), de la\n"
        "CONTINUITÉ du L (rangées d'un seul tenant barre → aile) et des allées\n"
        f"0,60 optimisées. Câblage : {N // 16} chaînes × 16 = {(N // 16) * 16} modules.\n"
        f"Si les 2 emprises jamais mesurées (1)(2) sont levées : {N_NO_GP} = "
        f"{N_NO_GP // 16} × 16\n"
        f"→ A {N_NO_GP // 16 * 16} + B 112 = {N_NO_GP // 16 * 16 + 112} = engagement "
        "résidence 272. Marché à prix\nunitaires — NE REMPLACE PAS les planches "
        "05E/05G.")
ax.text(13.2, -26.6, nota, fontsize=6.2, va="top", fontweight="bold",
        color="#111111", zorder=30,
        bbox=dict(boxstyle="round,pad=0.5", fc="#fefce8", ec="#111111", lw=1.0))

# ---------------- panneau droit : détail des rangées
PX = 49.5
ax.text(PX, 14.6, "CALEPINAGE V2 — RANGÉES EXPLICITES", fontsize=7.6,
        fontweight="bold", va="top", zorder=30)
lines = ["rangée  emprise E-O     portée      mod."]
for i, r in enumerate(ROWS, 1):
    ymin, ymax = band(r)
    port = "L complet" if ymin < 0 else "barre"
    c = count_rows([r], OBS)
    lines.append(f"  {i}    {fr(r):>5s} → {fr(r + TBL_W):>5s}  {port:9s}  {c:3d}")
lines += ["", f"TOTAL DESSINÉ = COMPTÉ : {N} mod. = {fr(KWC, 1)} kWc",
          f"engagement bordereau {ENG} → {VERDICT} (manque {ENG - N})"
          if N < ENG else f"engagement bordereau {ENG} → {VERDICT}",
          "", "allées : 0,60 · 2,45 (cage) · 3,15 (B7/A1) ·",
          "0,60 · 0,60 · 0,60 · 0,60 — rives 0,35 (est 0,53)",
          "", "emprises JAMAIS MESURÉES (conservées ici) :",
          f"  sans (1) grand rectangle non coté → {N_NO_G}",
          f"  sans (1) et (2) pan coupé (plan)    → {N_NO_GP}",
          "", "pour information (non dessiné) :",
          f"  ancien calepinage v1 (allées 1,20) → {n_v1}",
          f"  conservateur 1,50 / 0,50 / 0,50     → {n_cons}"]
for i, t in enumerate(lines):
    ax.text(PX, 13.4 - i * 0.82, t, fontsize=6.0, va="top", color="#1f2937",
            zorder=30, family="DejaVu Sans Mono")

D.cartouche(fig, [
    ("ACCORDIA TECH — Consultation FRDISI PV + stockage, Mohammedia", True),
    (f"Bât. A (aile en L) — VUE DE TOITURE V2 : relevé 27/07/2026 — "
     f"{N} modules posables ({fr(KWC, 1)} kWc)", True),
    ("Relevé : R. Kasri — restitution TAQINOR — document de travail", False),
    ("A3 — cotes en m — échelle : barre graphique — NE REMPLACE PAS les planches 05E/05G",
     False),
])
fig.savefig(os.path.join(BASE, "VUE_TOITURE_BAT_A_L_V2.pdf"), bbox_inches="tight")
fig.savefig(os.path.join(BASE, "VUE_TOITURE_BAT_A_L_V2.png"), dpi=170,
            bbox_inches="tight")

print(f"[CALEPINAGE V2] {len(ROWS)} rangées N-S, table portrait {TBL_L}×{TBL_W}")
for i, r in enumerate(ROWS, 1):
    ymin, _ = band(r)
    print(f"   rangée {i} : x {r:5.2f} → {r + TBL_W:5.2f} "
          f"({'L complet' if ymin < 0 else 'barre'}) = {count_rows([r], OBS):3d} mod.")
print(f"[V2] TOTAL dessiné = compté : {N} modules ({KWC:.1f} kWc) — "
      f"engagement {ENG} → {VERDICT}")
print(f"[V2] sans le grand rectangle non coté : {N_NO_G} · "
      f"sans lui ni le pan coupé : {N_NO_GP}")
print(f"[REF] ancien calepinage v1 : {n_v1} · conservateur 1,50/0,50/0,50 : {n_cons}")
print("[OK] VUE_TOITURE_BAT_A_L_V2.pdf / .png écrits")
