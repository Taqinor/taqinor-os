# -*- coding: utf-8 -*-
"""PLANCHE 05H — IMPLANTATION PHOTOVOLTAÏQUE — BÂTIMENT C : TERRASSE ÉCOLE
SUPTECH (Mohammedia) — format A3.

VERSION DÉPÔT (soumissionnaire ACCORDIA TECH) — Statut : Appel d'offres —
Date : Juillet 2026 — Indice : H.

GÉOMÉTRIE (identique à l'étude d'implantation — relevé contradictoire du
27/07/2026, aucun recalcul) :
  - la terrasse est relevée COMPLÈTE : le bord bas figuré = le MUR SUD
    → UN SEUL calepinage sur 51,1 m ;
  - ligne interne À DÉCROCHÉ : 13,18 (bord → décroché) + marche 0,91 → la cage
    commence à 14,09 ;
  - segment cage→local = 7,92 RELEVÉ ; la profondeur de cage reste DÉDUITE :
    51,1 − (19,36 + 7,92 + 4,50 + 10,50) = 8,82 — valeur arrondie annoncée au
    relevé : ≈8,5 (somme arrondie 42,5 ; la somme exacte fait 42,28) → cote
    ORANGE, à confirmer à l'exécution ;
  - chaîne verticale : 19,36 + ≈8,82* + 7,92 + 4,50 + 10,50 = 51,10 ✓ ;
  - LOCAL (petite chambre) 4,18 × 4,50, 7,92 SOUS la cage (y 10,50 → 15,00) ;
  - OUVRAGE BAS (angle SE) : sur LA MÊME LIGNE que le local, entre le local et
    le mur est — local → 1,19 → OUVRAGE (4,78) → 1,52 → mur est ; chaîne
    transversale 13,95 + 4,18 + 1,19 + 4,78 + 1,52 = 25,62 ✓ EXACT ; muret
    h≈0,5 × 4,78 × ≈1,0 de profondeur (nature à confirmer à l'exécution) ;
    bord sud à 13,5 du mur sud (mur de référence à confirmer) ; dégagement 0,50.
  - AUCUNE souche relevée sur la terrasse (les repères provisoires ont été
    écartés au relevé) ; AUCUN équipement de climatisation présent au relevé —
    une installation ultérieure sera coordonnée avec le champ PV à l'exécution.
Calepinage : RANGÉES EXPLICITES — allées de maintenance 1,90 m (prescription :
0,60 mini), le surplus de largeur réparti en allées larges, si bien que cage +
local + marche ne coupent qu'UNE bande et l'ouvrage bas qu'une bande.
Variantes conservatrice 1,50/0,50/0,50 et uniforme 0,60 calculées pour
information.
Sorties : 05H_IMPLANTATION_BAT_C_ECOLE.pdf (à côté du script)
          05H_IMPLANTATION_BAT_C_ECOLE.png (dossier « 06 - Schémas »)
"""
import os
import sys
import math

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.chdir(BASE)

import dessin as D
import calepinage as C
from matplotlib.patches import Rectangle, FancyArrowPatch

DOC = "05H_IMPLANTATION_BAT_C_ECOLE"
DEST_PNG = ("C:/Users/kasri/OneDrive - Atlencia/TAQINOR/"
            "AO FRDISI - Solaire Mohammedia 2026/ENVOI ACCORDIA - FINAL 27-07/"
            "06 - Schémas (8 planches)")

# ------------------------------------------------------------------ paramètres
C.MOD_L = 1.134          # table portrait : emprise LE LONG de la rangée
C.TBL_W = 4.70           # emprise transversale (2×2,382×cos15° + faîtage)
TBL_L, TBL_W = 1.134, 4.70

W_PLAN, L_TOT = 26.2, 51.1        # rectangle PLAN
W_MES = 25.62                     # largeur MESURÉE (haut du toit)
Y_INT = L_TOT - 19.36             # 31,74 — ligne interne (changement de niveau)
JOG_X0, JOG_X1, JOG_D = 13.18, 14.09, 0.45   # décroché : marche 0,91

# cage : profondeur DÉDUITE de la fermeture verticale ; segment cage→local
# RELEVÉ 7,92 (relevé contradictoire du 27/07/2026)
GAP = 7.92                                     # cage→local, RELEVÉ (bleu)
CAGE_D = L_TOT - 19.36 - GAP - 4.50 - 10.50    # = 8,82 (arrondi annoncé ≈8,5)
CAGE = (Y_INT - CAGE_D, Y_INT, 14.09, 18.20)   # y 22,92 → 31,74
CH = (CAGE[0] - GAP - 4.50, CAGE[0] - GAP, 13.95, 18.13)     # y 10,50 → 15,00
# ouvrage bas : sur la ligne du local — local → 1,19 → OUVRAGE 4,78 → 1,52 →
# mur ; bord sud à 13,5 du mur sud (mur de réf. à confirmer) ; muret h≈0,5 ×
# 4,78 × ≈1,0 de profondeur (nature à confirmer à l'exécution)
GENE_Y0, GENE_D = 13.50, 1.00
GX0 = 13.95 + 4.18 + 1.19                       # 19,32 (chaîne fermée)
GENE = (GENE_Y0, GENE_Y0 + GENE_D, GX0, GX0 + 4.78)   # (13,5 ; 14,5 ; 19,32 ; 24,10)
VERT, VERT_F = "#15803d", "#bbf7d0"
TENDU_C = "#c2410c"

# fermetures numériques (garde-fous)
assert abs((13.18 + 0.91 + 4.11 + 7.42) - W_MES) < 1e-9
assert abs((13.95 + 4.18 + 1.19 + 4.78 + 1.52) - W_MES) < 1e-9
assert abs((19.36 + CAGE_D + GAP + 4.50 + 10.50) - L_TOT) < 1e-9
assert abs(CAGE_D - 8.82) < 1e-9
assert abs(CH[0] - 10.50) < 1e-9
assert abs((CAGE[3] - CAGE[2]) - 4.11) < 1e-9
assert abs((CH[3] - CH[2]) - 4.18) < 1e-9
assert abs((GENE[2] - CH[3]) - 1.19) < 1e-9      # écart local↔ouvrage bas
assert abs((W_MES - GENE[3]) - 1.52) < 1e-9      # ouvrage bas→mur est
assert abs((GENE[3] - GENE[2]) - 4.78) < 1e-9    # largeur déduite
assert abs((GENE[1] - GENE[0]) - 1.00) < 1e-9    # profondeur ≈1,0 (à confirmer)

# obstacles : (le long y0, y1, transversal x0, x1)
NIVEAU = (Y_INT, Y_INT, 0.0, W_MES)             # coupure de niveau
JOG = (Y_INT - JOG_D, Y_INT, JOG_X0, JOG_X1)    # marche du décroché
# aucune souche relevée ; aucun équipement de climatisation présent au relevé
# (une installation ultérieure sera coordonnée à l'exécution)
OBS_BASE = [NIVEAU, JOG, CAGE, CH, GENE]

# ------------------------------------------------------------------ comptages
# RANGÉES EXPLICITES (prescription : allées « 0,60 mini, optimisées » ; le
# calcul exhaustif donne 314 pour TOUTE allée de 0,60 à 1,94 m → on OFFRE des
# allées de MAINTENANCE 1,90 m, à compte identique).
# marche + cage + local ne coupent qu'UNE bande (la 3e), l'ouvrage bas une (la 4e).
# Largeur : 0,35 + 4,70 + 1,90 + 4,70 + 1,90 + 4,70 + 1,90 + 4,70 + 0,77 = 25,62 ✓
ROWS = [(0.35, 5.05), (6.95, 11.65), (13.55, 18.25), (20.15, 24.85)]
assert all(abs((x1 - x0) - TBL_W) < 1e-9 for (x0, x1) in ROWS)
assert ROWS[-1][1] <= W_MES - 0.35 + 1e-9        # rive est ≥ 0,35 (ici 0,77)
# allées ≥ 0,60 partout
for _i in range(len(ROWS) - 1):
    assert ROWS[_i + 1][0] - ROWS[_i][1] >= 0.60 - 1e-9, ("allée", _i)
# vérifs de dégagement : cage/local/marche ne touchent QUE la bande 3,
# l'ouvrage bas (dégagt 0,50) QUE la bande 4
assert ROWS[1][1] + 0.30 <= JOG_X0 + 1e-9        # bande 2 libre du décroché
assert CAGE[3] + 0.30 <= ROWS[3][0] + 1e-9       # bande 4 libre de la cage
assert CH[3] + 0.30 <= ROWS[3][0] + 1e-9         # bande 4 libre du local
assert GENE[2] - 0.50 >= ROWS[2][1] - 1e-9       # bande 3 libre de l'ouvrage bas

# ouvrage bas : dégagement 0,50 (gonflé +0,20 au-delà du dégagt 0,30)
GENE_PL = (GENE[0] - 0.20, GENE[1] + 0.20, GENE[2] - 0.20, GENE[3] + 0.20)
OBS_PL = [GENE_PL if o is GENE else o for o in OBS_BASE]

# information : uniforme conservateur 1,50/0,50/0,50 et uniforme 0,60
n_cons, ph_cons = C.best_phase(L_TOT, W_MES, OBS_BASE, 1.50, 0.50, 0.50,
                               end_rive=0.50)
n_unif, ph_unif = C.best_phase(L_TOT, W_MES, OBS_PL, 0.60, 0.35, 0.30,
                               end_rive=0.35)

ALLEE, RIVE, CLEAR, END_RIVE, OBS_U = 1.90, 0.35, 0.30, 0.35, OBS_PL
PARAMS_TXT = ("allées de maintenance 1,90 / rives 0,35 / dégagt 0,30 "
              "(ouvrage bas 0,50)")
ENGAGE = 288

def count_rows(rows, obs, clear_, end_rive):
    """Compte indépendant du dessin (garde-fou compte affiché = dessiné)."""
    total = 0
    for (x0, x1) in rows:
        blocked = [(max(0.0, o[0] - clear_), min(L_TOT, o[1] + clear_))
                   for o in obs
                   if not (o[3] + clear_ <= x0 or o[2] - clear_ >= x1)]
        blocked = C.merge([b for b in blocked if b[1] > b[0]])
        cur, stop = end_rive, L_TOT - end_rive
        for a, b in blocked:
            if a > cur:
                total += 2 * int((min(a, stop) - cur) // TBL_L)
            cur = max(cur, b)
        if cur < stop:
            total += 2 * int((stop - cur) // TBL_L)
    return total

n_show = count_rows(ROWS, OBS_PL, CLEAR, END_RIVE)


def fr(v, dec=2):
    return f"{v:.{dec}f}".replace(".", ",")

# ------------------------------------------------------------------ feuille
fig, ax = D.new_sheet(
    "IMPLANTATION PHOTOVOLTAÏQUE — BÂTIMENT C : TERRASSE ÉCOLE SUPTECH",
    "Relevé contradictoire du 27/07/2026 — terrasse complète 26,2 × 51,1 m (plan) — "
    "bleu = mesuré · orange = à confirmer · gris = déduit — cage 4,11×≈8,82 (arrondi "
    "annoncé ≈8,5) · local 4,18×4,50 à 7,92 · ouvrage bas 4,78×≈1,0 — aucune souche, "
    "aucun équipement de climatisation au relevé — tables E-O portrait 1,134×4,70 "
    "(15°), allées de maintenance 1,90 (compte identique à 0,60 — démontré)",
    (-5.5, 45.5), (-3.7, 57.6))

# ------------------------------------------------------------------ calepinage
def draw_tables(rows, obs, clear_, end_rive):
    """Pose les tables rangée par rangée (positions EXPLICITES) + dessin."""
    total, placed = 0, []
    for (x0, x1) in rows:
        blocked = [(max(0.0, o[0] - clear_), min(L_TOT, o[1] + clear_))
                   for o in obs
                   if not (o[3] + clear_ <= x0 or o[2] - clear_ >= x1)]
        blocked = C.merge([b for b in blocked if b[1] > b[0]])
        cur, stop = end_rive, L_TOT - end_rive
        segs = []
        for a, b in blocked:
            if a > cur:
                segs.append((cur, min(a, stop)))
            cur = max(cur, b)
        if cur < stop:
            segs.append((cur, stop))
        for a, b in segs:
            n = int((b - a) // TBL_L)
            total += 2 * n
            for i in range(n):
                yy = a + i * TBL_L
                placed.append((x0, yy))
                ax.add_patch(Rectangle((x0, yy), TBL_W, TBL_L,
                             facecolor=VERT_F, edgecolor=VERT, lw=0.35,
                             zorder=5))
            if n > 0:      # faîtage continu du segment
                ax.plot([x0 + TBL_W / 2] * 2, [a, a + n * TBL_L],
                        color=VERT, lw=0.5, zorder=6)
    return total, placed

n_drawn, placed = draw_tables(ROWS, OBS_U, CLEAR, END_RIVE)

# ---- contrôles géométriques (cahier des charges) --------------------------
EPS = 1e-6
assert n_drawn == n_show, (n_drawn, n_show)          # compte affiché = dessiné
rows_used = list(ROWS)
assert len(rows_used) == 4, rows_used                # 4 rangées exactement
# non-chevauchement TABLE/TABLE
for _a in range(len(placed)):
    for _b in range(_a + 1, len(placed)):
        (xa, ya), (xb, yb) = placed[_a], placed[_b]
        assert (xa + TBL_W <= xb + EPS or xb + TBL_W <= xa + EPS
                or ya + TBL_L <= yb + EPS or yb + TBL_L <= ya + EPS), \
            ("chevauchement", placed[_a], placed[_b])
for (tx, ty) in placed:
    tx1, ty1 = tx + TBL_W, ty + TBL_L
    # jamais à cheval sur la ligne de niveau
    assert ty1 <= Y_INT + EPS or ty >= Y_INT - EPS, ("niveau", tx, ty)
    # dans l'emprise utile (rives / rives d'extrémité du jeu retenu)
    assert RIVE - EPS <= tx and tx1 <= W_MES - RIVE + EPS, ("rive", tx, ty)
    assert END_RIVE - EPS <= ty and ty1 <= L_TOT - END_RIVE + EPS, ("bout", tx, ty)
    # jamais dans un volume ni à moins du dégagement retenu ; autour de
    # l'OUVRAGE BAS le dégagement reste 0,50 quel que soit le jeu
    for o in OBS_BASE:
        c = 0.50 if o is GENE else CLEAR
        (oy0, oy1, ox0, ox1) = o
        assert (ty >= oy1 + c - EPS or ty1 <= oy0 - c + EPS
                or tx >= ox1 + c - EPS or tx1 <= ox0 - c + EPS), \
            ("obstacle", tx, ty, o)

# étiquettes O / E en tête de chaque rangée (au-dessus du mur nord)
for (x0, x1) in rows_used:
    ax.text(x0 + 1.17, 51.45, "O", fontsize=5.5, color=VERT, ha="center",
            va="center", fontweight="bold", zorder=7)
    ax.text(x0 + 3.53, 51.45, "E", fontsize=5.5, color=VERT, ha="center",
            va="center", fontweight="bold", zorder=7)

# ------------------------------------------------------------------ géométrie
# contour PLAN 26,2 × 51,1
ax.add_patch(Rectangle((0, 0), W_PLAN, L_TOT, fill=False, lw=2.2,
                       edgecolor=D.NOIR, zorder=10))
# ligne interne À DÉCROCHÉ : 13,18 → marche 0,91 → reprise à 14,09
ax.plot([0, JOG_X0], [Y_INT, Y_INT], color=D.NOIR, lw=2.0, zorder=10)
ax.plot([JOG_X0, JOG_X0], [Y_INT, Y_INT - JOG_D], color=D.NOIR, lw=2.0, zorder=10)
ax.plot([JOG_X0, JOG_X1], [Y_INT - JOG_D, Y_INT - JOG_D], color=D.NOIR, lw=2.0,
        zorder=10)
ax.plot([JOG_X1, JOG_X1], [Y_INT - JOG_D, Y_INT], color=D.NOIR, lw=2.0, zorder=10)
ax.plot([JOG_X1, W_PLAN], [Y_INT, Y_INT], color=D.NOIR, lw=2.0, zorder=10)
ax.text(6.3, Y_INT, "ligne interne relevée — CHANGEMENT DE NIVEAU (à décroché)",
        fontsize=5.8, ha="center", va="center", zorder=26,
        bbox=dict(fc="white", ec="none", alpha=0.9, pad=1.2))

# étiquettes de zones (toute la terrasse est relevée)
for (xx, yy, txt) in ((13.1, 41.6, "TERRASSE HAUTE — champ libre au relevé"),
                      (7.5, 8.5, "ZONE BASSE — relevée")):
    ax.text(xx, yy, txt, fontsize=6.6, ha="center", va="center",
            color="#334155", fontweight="bold", zorder=26,
            bbox=dict(fc="white", ec="#94a3b8", lw=0.5, alpha=0.88, pad=1.6))

# ------------------------------------------- VOLUME 1 : cage d'escalier (prof. déduite)
ax.add_patch(Rectangle((CAGE[2], CAGE[0]), 4.11, CAGE_D, facecolor="#475569",
                       edgecolor="black", lw=1.2, zorder=12))
ax.add_patch(Rectangle((CAGE[2] + 0.30, CAGE[0] + 0.30), 4.11 - 0.60,
                       CAGE_D - 0.60, facecolor="white", edgecolor="none",
                       zorder=13))
# bord SUD de la cage = limite DÉDUITE (jamais cotée) → surlignée orange tirets
ax.plot([CAGE[2], CAGE[3]], [CAGE[0], CAGE[0]], color=D.ORANGE, lw=1.8,
        ls=(0, (4, 2)), zorder=14)
xm = CAGE[2] + 0.50
while xm < CAGE[3] - 0.45:
    ax.plot([xm, xm], [CAGE[1] - 1.60, CAGE[1] - 0.80], color="#64748b", lw=0.6,
            zorder=14)
    xm += 0.32
ax.add_patch(FancyArrowPatch((CAGE[2] + 0.50, CAGE[1] - 1.20),
                             (CAGE[3] - 0.50, CAGE[1] - 1.20),
                             arrowstyle="-|>", mutation_scale=6, lw=0.7,
                             color="#334155", zorder=15))
ax.text(CAGE[2] + 1.35, CAGE[0] + 2.78, "CAGE D'ESCALIER",
        fontsize=6.2, ha="center", va="center", fontweight="bold",
        color="#111", rotation=90, zorder=15)
ax.text(CAGE[2] + 2.55, CAGE[0] + 2.78,
        "≈8,82 (déduit)", fontsize=5.0, ha="center",
        va="center", color=D.ORANGE, rotation=90, fontweight="bold",
        zorder=15)
# note détaillée en marge ouest, le long de la cote ≈8,82 (orange)
ax.text(-4.35, 25.5,
        "profondeur de cage DÉDUITE de la fermeture 51,1 avec le segment "
        "cage→local RELEVÉ 7,92 → ≈8,82 — valeur arrondie annoncée au relevé : "
        "≈8,5 — à confirmer à l'exécution",
        fontsize=4.8, ha="center", va="center", color=D.ORANGE, rotation=90,
        fontweight="bold", zorder=26)

# ------------------------------------------- VOLUME 2 : local (petite chambre)
ax.add_patch(Rectangle((CH[2], CH[0]), 4.18, 4.50, facecolor="#475569",
                       edgecolor="black", lw=1.2, zorder=12))
ax.add_patch(Rectangle((CH[2] + 0.30, CH[0] + 0.30), 4.18 - 0.60, 4.50 - 0.60,
                       facecolor="white", edgecolor="none", zorder=13))
ax.text((CH[2] + CH[3]) / 2, CH[0] + 3.75, "LOCAL", fontsize=5.9, ha="center",
        va="center", fontweight="bold", color="#111", zorder=15)
ax.text((CH[2] + CH[3]) / 2, CH[0] + 3.15, "(petite chambre)", fontsize=5.2,
        ha="center", va="center", color="#111", zorder=15)
ax.text((CH[2] + CH[3]) / 2, CH[0] + 2.55, "4,18 × 4,50", fontsize=5.0,
        ha="center", va="center", color="#334155", zorder=15)

# emprise portée aux plans 10,7 × 9,8 (pointillé gris) autour des volumes
PRX = (CAGE[2] + CAGE[3]) / 2 - 10.7 / 2
pr = Rectangle((PRX, Y_INT - 9.8), 10.7, 9.8, fill=False, edgecolor=D.GRIS,
               ls=":", lw=1.4, zorder=9)
ax.add_patch(pr)
ax.annotate("emprise portée aux plans 10,7 × 9,8 (pointillé) : PÉRIMÉE —\n"
            "remplacée par la CAGE RELEVÉE (≈8,82), qui s'y inscrit",
            xy=(PRX + 0.4, Y_INT - 9.8), xytext=(1.2, 19.3), fontsize=5.2,
            ha="left", va="center", color="#475569", zorder=26,
            arrowprops=dict(arrowstyle="->", lw=0.6, color=D.GRIS),
            bbox=dict(fc="white", ec="none", alpha=0.88, pad=1.0))

# ----------- OUVRAGE BAS — 4,78 × ≈1,0, muret h≈0,5 (nature à confirmer)
ax.add_patch(Rectangle((GENE[2], GENE[0]), GENE[3] - GENE[2], GENE_D,
                       facecolor="#dbeafe", edgecolor=D.BLEU, lw=1.4,
                       zorder=12))
ax.add_patch(Rectangle((GENE[2] + 0.18, GENE[0] + 0.18),
                       GENE[3] - GENE[2] - 0.36, GENE_D - 0.36,
                       facecolor="white", edgecolor="none", zorder=13))
GXM = (GENE[2] + GENE[3]) / 2 - 0.5
ax.text(GXM, 15.65, "OUVRAGE BAS — muret h≈0,5", fontsize=5.4, ha="center",
        va="center", fontweight="bold", color="#111", zorder=15,
        bbox=dict(fc="white", ec="none", alpha=0.88, pad=0.8))
ax.text(GXM, 15.00, "nature à confirmer à l'exécution", fontsize=4.8,
        ha="center", va="center", color=D.ORANGE, fontweight="bold", zorder=15,
        bbox=dict(fc="white", ec="none", alpha=0.88, pad=0.8))

# ------------------------------------------------------------------ cotes
def dimb(p1, p2, off, text, color=D.BLEU, fs=6.4, boxed=True):
    """Cote avec texte sur fond blanc (lisible sur le calepinage)."""
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
                                 lw=0.8, color=color, shrinkA=0, shrinkB=0,
                                 zorder=21))
    mx, my = (q1[0] + q2[0]) / 2, (q1[1] + q2[1]) / 2
    ang = math.degrees(math.atan2(uy, ux))
    if ang > 90 or ang <= -90:
        ang += 180
    bb = dict(fc="white", ec="none", alpha=0.88, pad=0.8) if boxed else None
    ax.text(mx + nx * 0.02 * s, my + ny * 0.02 * s, text, fontsize=fs,
            color=color, ha="center", va="center", rotation=ang,
            rotation_mode="anchor", zorder=22, bbox=bb)

# largeurs (haut)
D.dim(ax, (0, L_TOT), (W_MES, L_TOT), off=1.2, text="25,62 (mesuré — haut du toit)")
D.dim(ax, (0, L_TOT), (W_PLAN, L_TOT), off=2.6, text="26,2 (plan)", color=D.GRIS)
ax.annotate("Δ 0,58 (plan − mesuré)\nà confirmer", xy=(25.91, 52.30),
            xytext=(28.2, 53.6), fontsize=5.4, color=D.ORANGE,
            arrowprops=dict(arrowstyle="->", lw=0.7, color=D.ORANGE), zorder=25)

# chaîne verticale ouest : 19,36 + ≈8,82* + 7,92 + 4,50 + 10,50 = 51,10 ✓
D.dim(ax, (0, L_TOT), (0, Y_INT), off=-1.3, text="19,36")
D.dim(ax, (0, Y_INT), (0, CAGE[0]), off=-1.3, text="≈8,82 (déduit)",
      color=D.ORANGE)
D.dim(ax, (0, CAGE[0]), (0, CH[1]), off=-1.3, text="7,92 (relevé)")
D.dim(ax, (0, CH[1]), (0, CH[0]), off=-1.3, text="4,50")
D.dim(ax, (0, CH[0]), (0, 0), off=-1.3, text="10,50")
D.dim(ax, (0, L_TOT), (0, 0), off=-2.9,
      text="51,10 = 19,36 + ≈8,82 (cage, DÉDUIT — arrondi annoncé ≈8,5) + 7,92 (relevé) + 4,50 + 10,50 ✓",
      color=D.GRIS)
# projections des niveaux des volumes vers le bord ouest
for (yy, xx) in ((CAGE[0], CAGE[2]), (CH[1], CH[2]), (CH[0], CH[2])):
    ax.plot([0, xx], [yy, yy], color=D.GRIS, lw=0.5, ls=(0, (2, 2)), zorder=9)

# côté est : total plan
D.dim(ax, (W_PLAN, L_TOT), (W_PLAN, 0), off=1.2, text="51,1 (plan)",
      color=D.GRIS)

# chaîne horizontale de la CAGE : 13,18 + 0,91 (marche) + 4,11 + 7,42 = 25,62
YC1 = 28.9
dimb((0, YC1), (JOG_X0, YC1), 0, "13,18")
dimb((JOG_X0, YC1), (JOG_X1, YC1), 0, "0,91", fs=5.0)
dimb((JOG_X1, YC1), (CAGE[3], YC1), 0, "4,11 (déduit)", color=D.GRIS, fs=5.6)
dimb((CAGE[3], YC1), (W_MES, YC1), 0, "7,42")
ax.plot([W_MES, W_MES], [YC1 - 0.4, YC1 + 0.4], color=D.BLEU, lw=0.8, zorder=20)

# chaîne horizontale LOCAL + OUVRAGE BAS : 13,95 + 4,18 + 1,19 + 4,78 + 1,52 = 25,62 ✓
YC2 = 11.6
dimb((0, YC2), (CH[2], YC2), 0, "13,95")
dimb((CH[2], YC2), (CH[3], YC2), 0, "4,18 (déduit)", color=D.GRIS, fs=5.6)
dimb((CH[3], YC2), (GENE[2], YC2), 0, "1,19", fs=4.6)
dimb((GENE[2], YC2), (GENE[3], YC2), 0, "4,78 (déduit)", color=D.GRIS, fs=5.0)
dimb((GENE[3], YC2), (W_MES, YC2), 0, "1,52", fs=4.6)
ax.plot([W_MES, W_MES], [YC2 - 0.4, YC2 + 0.4], color=D.BLEU, lw=0.8, zorder=20)

# position de l'ouvrage bas : bord sud à 13,5 du mur sud (cote bleue verticale)
# — mur de référence à confirmer à l'exécution
XG = 23.5
dimb((XG, 0), (XG, GENE[0]), 0, "13,5", color=D.BLEU, fs=5.6)
ax.text(XG + 0.55, 5.5, "mur de référence : SUD — à confirmer",
        fontsize=4.8, ha="center", va="center", rotation=90, color=D.ORANGE,
        fontweight="bold", zorder=22,
        bbox=dict(fc="white", ec="none", alpha=0.88, pad=0.8))
# profondeur de l'ouvrage bas ≈1,0 (orange = à confirmer, côté est)
dimb((GENE[3], GENE[1]), (GENE[3], GENE[0]), 0.42, "≈1,0",
     color=D.ORANGE, fs=4.8)

# paramètres de calepinage cotés une fois (terrasse haute)
dimb((rows_used[0][0], 45.6), (rows_used[0][1], 45.6), 0, "4,70", color=D.GRIS,
     fs=5.2)
dimb((rows_used[0][1], 47.9), (rows_used[1][0], 47.9), 0, fr(ALLEE),
     color=D.GRIS, fs=5.2)
dimb((rows_used[1][1], 47.9), (rows_used[2][0], 47.9), 0, fr(ALLEE),
     color=D.GRIS, fs=5.2)

# nord
ax.add_patch(FancyArrowPatch((-3.8, 50.4), (-3.8, 52.0), arrowstyle="-|>",
                             mutation_scale=11, lw=1.4, color=D.NOIR, zorder=30))
ax.text(-3.8, 52.55, "N", fontsize=10, ha="center", fontweight="bold",
        zorder=30)

# ---------------------------------------------------- bandeau d'engagement
if n_show >= ENGAGE:
    MARGE_TXT = f"marge +{n_show - ENGAGE}"
    ax.text(13.1, 57.05,
            f"Capacité démontrée sur le relevé : {n_show} modules — "
            f"ENGAGÉ AU MARCHÉ : {ENGAGE} modules ({MARGE_TXT})",
            fontsize=9.5, ha="center", fontweight="bold", color=VERT, zorder=30)
else:
    MARGE_TXT = f"écart {n_show - ENGAGE}"
    ax.text(13.1, 57.05,
            f"Capacité démontrée sur le relevé : {n_show} modules — "
            f"ENGAGÉ AU MARCHÉ : {ENGAGE} modules ({MARGE_TXT})",
            fontsize=9.5, ha="center", fontweight="bold", color=TENDU_C,
            zorder=30)
ax.text(13.1, 56.2,
        "Implantation définitive arrêtée après relevé d'exécution — "
        "marché à prix unitaires",
        fontsize=7.2, ha="center", fontweight="bold", color="#334155", zorder=30)
ax.text(13.1, 55.42,
        f"terrasse complète 51,1 m ({PARAMS_TXT}) : {n_show} mod. = "
        f"{fr(n_show * 0.625)} kWc — variante conservatrice 1,50/0,50/0,50 : "
        f"{n_cons} — engagement {ENGAGE} mod. = 180,0 kWc",
        fontsize=6.0, ha="center", color="#374151", zorder=30)
ax.text(13.1, 54.65,
        "cage : segment cage→local RELEVÉ 7,92 → profondeur ≈8,82 déduite de "
        "la fermeture 51,1 (valeur arrondie annoncée au relevé : ≈8,5) — "
        "à confirmer à l'exécution",
        fontsize=6.0, ha="center", color=D.ORANGE, zorder=30)

# nota bas de plan
ax.text(13.1, -1.35,
        "Relevé contradictoire du 27/07/2026 : terrasse COMPLÈTE (bord bas = "
        "mur sud) — un seul calepinage sur 51,1 m. Aucune table à cheval sur "
        "la ligne interne.",
        fontsize=6.0, ha="center", color="#475569", zorder=30)
ax.text(13.1, -2.05,
        "OUVRAGE BAS (angle SE) : 4,78 × ≈1,0 — muret h≈0,5, nature à "
        "confirmer à l'exécution — dégagement 0,50 · aucune souche relevée "
        "sur la terrasse.",
        fontsize=6.0, ha="center", color=D.ORANGE, zorder=30)
ax.text(13.1, -2.75,
        "Aucun équipement de climatisation présent sur la terrasse au relevé ; "
        "une installation ultérieure sera coordonnée avec le champ PV à "
        "l'exécution.",
        fontsize=6.0, ha="center", color="#475569", zorder=30)
if n_show < ENGAGE:
    ax.text(13.1, -3.45,
            "Répartition des modules entre bâtiments ajustable à l'exécution "
            "dans le cadre du marché à prix unitaires.",
            fontsize=6.0, ha="center", color=TENDU_C, zorder=30)

# ------------------------------------------------------------------ panneau droit
PX = 30.4

def titre(y, txt, color="#111111"):
    ax.text(PX, y, txt, fontsize=7.6, fontweight="bold", color=color,
            va="top", zorder=30)
    return y - 1.15

def lignes(y, rows, fs=5.9):
    for i, t in enumerate(rows):
        ax.text(PX, y - i * 0.82, t, fontsize=fs, va="top", color="#1f2937",
                zorder=30)
    return y - len(rows) * 0.82 - 1.0

y = titre(50.6, "LÉGENDE")
leg = [
    ("table", "table E-O portrait 1,134×4,70 — 2 modules 625 Wc, pose 15°"),
    ("bloc", "volume relevé (cage 4,11×≈8,82 déduit · local 4,18×4,50)"),
    ("gene", "ouvrage bas 4,78×≈1,0 — muret h≈0,5 · dégagement 0,50"),
    ("prov", "emprise portée aux plans — périmée (cage relevée retenue)"),
    ("dimB", "cote MESURÉE au relevé contradictoire (bleu)"),
    ("dimO", "cote / position À CONFIRMER À L'EXÉCUTION (orange)"),
    ("dimG", "cote de plan / déduite des fermetures (gris)"),
]
for i, (kind, txt) in enumerate(leg):
    yy = y - i * 0.95
    if kind == "table":
        ax.add_patch(Rectangle((PX, yy - 0.42), 1.3, 0.55, facecolor=VERT_F,
                     edgecolor=VERT, lw=0.5, zorder=30))
        ax.plot([PX + 0.65] * 2, [yy - 0.42, yy + 0.13], color=VERT, lw=0.6,
                zorder=31)
    elif kind == "bloc":
        ax.add_patch(Rectangle((PX, yy - 0.42), 1.3, 0.55, facecolor="#475569",
                     edgecolor="black", lw=0.6, zorder=30))
        ax.add_patch(Rectangle((PX + 0.18, yy - 0.30), 0.94, 0.31,
                     facecolor="white", edgecolor="none", zorder=31))
    elif kind == "gene":
        ax.add_patch(Rectangle((PX, yy - 0.42), 1.3, 0.55, facecolor="#dbeafe",
                     edgecolor=D.BLEU, lw=0.9, zorder=30))
        ax.add_patch(Rectangle((PX + 0.20, yy - 0.30), 0.90, 0.31,
                     facecolor="white", edgecolor="none", zorder=31))
    elif kind == "prov":
        rr = Rectangle((PX, yy - 0.42), 1.3, 0.55, fill=False,
                       edgecolor=D.GRIS, ls=":", lw=1.1, zorder=30)
        ax.add_patch(rr)
    else:
        col = {"dimB": D.BLEU, "dimO": D.ORANGE, "dimG": D.GRIS}[kind]
        ax.add_patch(FancyArrowPatch((PX, yy - 0.14), (PX + 1.3, yy - 0.14),
                     arrowstyle="<|-|>", mutation_scale=6, lw=0.8, color=col,
                     zorder=30))
    ax.text(PX + 1.65, yy - 0.14, txt, fontsize=5.9, va="center",
            color="#1f2937", zorder=30)
y -= len(leg) * 0.95 + 0.9

y = titre(y, "CONTRÔLES DE FERMETURE DU RELEVÉ")
y = lignes(y, [
    "13,18 + 0,91 (marche) + 4,11 (déduit) + 7,42 = 25,62 ✓ exact",
    "13,95 + 4,18 (déduit) + 1,19 + 4,78 (déduit) + 1,52 = 25,62 ✓",
    "19,36 + ≈8,82 (cage, DÉDUIT) + 7,92 (relevé) + 4,50 + 10,50 = 51,10 ✓",
    "→ segment cage→local = 7,92 RELEVÉ le 27/07/2026 ; le seul",
    "   tronçon déduit est la PROFONDEUR DE LA CAGE (arrondi",
    "   annoncé au relevé : ≈8,5) — à confirmer à l'exécution",
    "largeur : 25,62 mesuré vs 26,2 plan → Δ 0,58 à confirmer",
    "angle SE : le petit rectangle = l'OUVRAGE BAS (4,78 × ≈1,0) ·",
    "1,19 = écart local↔ouvrage · 13,5 = ouvrage → mur sud",
])

y = titre(y, "CALEPINAGE — PORTRAIT 15°")
cal = [
    "4 rangées de tables E-O PORTRAIT 1,134 × 4,70",
    "(2 × 2,382 × cos15° + faîtage) le long des 51,1 m",
    "retenu : allées de MAINTENANCE 1,90 m (prescription :",
    "0,60 mini) — le calcul exhaustif donne le même compte pour",
    "TOUTE allée de 0,60 à 1,94 m : 1,90 ne coûte AUCUN module",
    "→ cage+local+marche ne coupent qu'1 bande ; ouvrage bas : 1",
    f"rives {fr(RIVE)} · dégagt {fr(CLEAR)} (ouvrage bas : 0,50)",
    f"information : uniforme 0,60 = {n_unif} · conservateur 1,50/0,50 = {n_cons}",
    "rive est 0,77 + allées : une 5e rangée exigerait 26,60 m",
    "de largeur (5×4,70 + 4×0,60 + 2×0,35) > 25,62 disponibles",
    "coupure de niveau à la ligne interne (aucun chevauchement)",
    f"CAPACITÉ DÉMONTRÉE sur 51,1 m : {n_show} mod. = {fr(n_show * 0.625)} kWc",
    f"ENGAGÉ AU MARCHÉ : {ENGAGE} modules (18×16) = 180,0 kWc",
    "18 strings × 16 — 3 onduleurs 50 kW (96/96/96)",
    (f"marge de capacité : +{n_show - ENGAGE} modules" if n_show >= ENGAGE
     else f"écart de capacité : {n_show - ENGAGE} modules"),
]
y = lignes(y, cal)

y = titre(y, "À CONFIRMER À L'EXÉCUTION (orange)", color=D.ORANGE)
y = lignes(y, [
    "profondeur de la cage ≈8,82, déduite de la fermeture 51,1",
    "(valeur arrondie annoncée au relevé : ≈8,5)",
    "ouvrage bas de l'angle SE : profondeur ≈1,0 · muret h≈0,5 ·",
    "nature de l'ouvrage · mur de référence de la cote 13,5 (sud)",
    "Δ de largeur 0,58 entre plan (26,2) et relevé (25,62)",
    "implantation des équipements de climatisation à venir —",
    "aucun sur la terrasse au relevé, à coordonner avec le champ PV",
])

D.scale_bar(ax, PX, max(y - 1.5, 3.6), total=10, step=2)

D.cartouche(fig, [
    ("ACCORDIA TECH — Consultation FRDISI : PV + stockage, Mohammedia", True),
    ("BÂT. C — TERRASSE ÉCOLE SUPTECH — IMPLANTATION PHOTOVOLTAÏQUE", True),
    (f"Document {DOC} — Statut : Appel d'offres", False),
    ("Date : Juillet 2026 — Indice : H — relevé contradictoire du 27/07/2026",
     False),
    ("Échelle : barre graphique (impression A3) — cotes en mètres", False),
])

fig.savefig(os.path.join(BASE, DOC + ".pdf"), bbox_inches="tight")
fig.savefig(os.path.join(DEST_PNG, DOC + ".png"), dpi=170, bbox_inches="tight")

print(f"conservateur 1,50/0,50/0,50 : {n_cons} modules ({n_cons*0.625:.2f} kWc), phase={ph_cons:.2f}")
print(f"uniforme 0,60/0,35/0,30     : {n_unif} modules ({n_unif*0.625:.2f} kWc), phase={ph_unif:.2f}")
print(f"retenu : {PARAMS_TXT} — capacité démontrée 51,1 m : {n_show} "
      f"(dessiné = {n_drawn})")
print(f"engage au marche {ENGAGE} : {MARGE_TXT}")
print(f"{DOC}.pdf (local) / {DOC}.png (06 - Schémas) écrits")
