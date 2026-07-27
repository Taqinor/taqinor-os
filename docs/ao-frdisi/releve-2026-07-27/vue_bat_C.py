# -*- coding: utf-8 -*-
"""VUE DE TOITURE DÉFINITIVE — BÂTIMENT C (ÉCOLE SUPTECH, Mohammedia) — A3.

MODÈLE DÉFINITIF (croquis + correctifs client 27/07) :
  - le croquis couvre le TOIT COMPLET : le bord bas dessiné = le vrai MUR SUD
    → UN SEUL calepinage sur 51,1 m, plus de zone « au plan » ni scénarios ;
  - ligne interne À DÉCROCHÉ : 13,18 (bord → décroché) + marche 0,91 → la cage
    commence à 14,09 ;
  - RÉPONSE CLIENT 27/07 (soir) : le segment cage→local vaut 7,92 (RELEVÉ,
    remplace le 2,32 lu sur croquis) ; la profondeur de cage reste déduite :
    51,1 − (19,36 + 7,92 + 4,50 + 10,50) = 8,82 — le client annonce « ≈8,5 »
    (arrondi de sa somme 42,5 ; la somme exacte fait 42,28) → ORANGE, à
    confirmer à l'exécution ;
  - chaîne verticale : 19,36 + ≈8,82* + 7,92 + 4,50 + 10,50 = 51,10 ✓ ;
  - LOCAL (petite chambre) 4,18 × 4,50, 7,92 SOUS la cage (y 10,50 → 15,00) ;
  - GÊNE (définitif) : petit ouvrage SUR LA MÊME LIGNE que la chambre, entre
    la chambre et le mur est — chambre → 1,19 → GÊNE (4,78) → 1,52 → mur est ;
    chaîne transversale 13,95 + 4,18 + 1,19 + 4,78 + 1,52 = 25,62 ✓ EXACT ;
    RÉPONSE CLIENT 27/07 (2e série) : ≈0,5 h × 4,78 × ≈1,0 prof (« clim
    probable, pas sûr ») → profondeur 1,0 (orange) ; bord SUD à 13,5 du MUR
    SUD (mur de référence à confirmer — nord ?) ; dégagement 0,50 maintenu.
  - RÉPONSES CLIENT 27/07 (2e série, Q/R sur images annotées) : AUCUNE souche
    vue sur le toit (les 4 « S » provisoires SUPPRIMÉES) ; AUCUNE clim sur le
    toit aujourd'hui — elle viendra APRÈS (à coordonner à l'exécution, ce
    n'est PAS une réserve AO — l'ancienne réserve DRV ouest est SUPPRIMÉE) ;
    allées « 0,60 mini, optimisées » (consigne client).
Calepinage : RANGÉES EXPLICITES optimisées — allées 0,60 mini, le surplus de
largeur concentré en UNE allée large (2,95) sur la colonne cage/local, si bien
que cage + local + marche ne coupent qu'UNE bande et la gêne qu'une bande.
Conservateur 1,50/0,50/0,50 et uniforme 0,60 calculés pour information.
Bandeau : ≥ 288 → CONFIRMÉ ; sinon TENDU + chiffre vrai + nota redistribution.
Jamais de « max » promotionnel.
Sorties : VUE_TOITURE_BAT_C_ECOLE.pdf / .png
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

# ------------------------------------------------------------------ paramètres
C.MOD_L = 1.134          # table portrait : emprise LE LONG de la rangée
C.TBL_W = 4.70           # emprise transversale (2×2,382×cos15° + faîtage)
TBL_L, TBL_W = 1.134, 4.70

W_PLAN, L_TOT = 26.2, 51.1        # rectangle PLAN
W_MES = 25.62                     # largeur MESURÉE (haut du toit)
Y_INT = L_TOT - 19.36             # 31,74 — ligne interne (changement de niveau)
JOG_X0, JOG_X1, JOG_D = 13.18, 14.09, 0.45   # décroché : marche 0,91

# cage : profondeur DÉDUITE de la fermeture verticale ; segment cage→local
# RELEVÉ 7,92 (réponse client 27/07 — remplace le 2,32 du croquis)
GAP = 7.92                                     # cage→local, RELEVÉ (bleu)
CAGE_D = L_TOT - 19.36 - GAP - 4.50 - 10.50    # = 8,82 (client : ≈8,5 arrondi)
CAGE = (Y_INT - CAGE_D, Y_INT, 14.09, 18.20)   # y 22,92 → 31,74
CH = (CAGE[0] - GAP - 4.50, CAGE[0] - GAP, 13.95, 18.13)     # y 10,50 → 15,00
# gêne : sur la ligne de la chambre — chambre → 1,19 → GÊNE 4,78 → 1,52 → mur ;
# bord SUD à 13,5 du MUR SUD (mur de réf. à confirmer) ; client 27/07 :
# ≈0,5 h × 4,78 × ≈1,0 prof, « clim probable, pas sûr » (orange)
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
assert abs((GENE[2] - CH[3]) - 1.19) < 1e-9      # écart chambre↔gêne
assert abs((W_MES - GENE[3]) - 1.52) < 1e-9      # gêne→mur est
assert abs((GENE[3] - GENE[2]) - 4.78) < 1e-9    # largeur déduite
assert abs((GENE[1] - GENE[0]) - 1.00) < 1e-9    # profondeur ≈1,0 (client 27/07)

# obstacles : (le long y0, y1, transversal x0, x1)
NIVEAU = (Y_INT, Y_INT, 0.0, W_MES)             # coupure de niveau
JOG = (Y_INT - JOG_D, Y_INT, JOG_X0, JOG_X1)    # marche du décroché
# client 27/07 : AUCUNE souche vue ; AUCUNE clim sur le toit aujourd'hui
# (elle viendra APRÈS → coordination d'exécution, pas une réserve AO)
OBS_BASE = [NIVEAU, JOG, CAGE, CH, GENE]

# ------------------------------------------------------------------ comptages
# RANGÉES EXPLICITES OPTIMISÉES (consigne client 27/07 : « 0,60 mini,
# optimisé ») : le surplus de largeur est CONCENTRÉ en une allée large (2,95)
# sur la colonne cage/local, si bien que marche + cage + local ne coupent
# qu'UNE bande (la 3e) et la gêne qu'une bande (la 4e).
# Largeur : 0,35 + 4,70 + 0,60 + 4,70 + 2,95 + 4,70 + 0,60 + 4,70 + 2,32 = 25,62 ✓
ROWS = [(0.35, 5.05), (5.65, 10.35), (13.30, 18.00), (18.60, 23.30)]
assert all(abs((x1 - x0) - TBL_W) < 1e-9 for (x0, x1) in ROWS)
assert ROWS[-1][1] <= W_MES - 0.35 + 1e-9        # rive est ≥ 0,35 (ici 2,32)
# vérifs de dégagement : cage/local/marche ne touchent QUE la bande 3,
# la gêne (dégagt 0,50) QUE la bande 4
assert ROWS[1][1] + 0.30 <= JOG_X0 + 1e-9        # bande 2 libre du décroché
assert CAGE[3] + 0.30 <= ROWS[3][0] + 1e-9       # bande 4 libre de la cage
assert CH[3] + 0.30 <= ROWS[3][0] + 1e-9         # bande 4 libre du local
assert GENE[2] - 0.50 >= ROWS[2][1] - 1e-9       # bande 3 libre de la gêne

# gêne : dégagement 0,50 maintenu (gonflée +0,20 au-delà du dégagt 0,30)
GENE_PL = (GENE[0] - 0.20, GENE[1] + 0.20, GENE[2] - 0.20, GENE[3] + 0.20)
OBS_PL = [GENE_PL if o is GENE else o for o in OBS_BASE]

# information : uniforme conservateur 1,50/0,50/0,50 et uniforme 0,60
n_cons, ph_cons = C.best_phase(L_TOT, W_MES, OBS_BASE, 1.50, 0.50, 0.50,
                               end_rive=0.50)
n_unif, ph_unif = C.best_phase(L_TOT, W_MES, OBS_PL, 0.60, 0.35, 0.30,
                               end_rive=0.35)

ALLEE, RIVE, CLEAR, END_RIVE, OBS_U = 0.60, 0.35, 0.30, 0.35, OBS_PL
PARAMS_TXT = "allées 0,60 optimisées / rives 0,35 / dégagt 0,30 (gêne 0,50)"

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
    "VUE DE TOITURE — BÂTIMENT C (ÉCOLE SUPTECH, MOHAMMEDIA) — 26,2 × 51,1 m (plan)",
    "Relevé terrain 27/07/2026 — croquis = TOIT COMPLET 51,1 m — bleu = mesuré · orange = à "
    "confirmer · gris = déduit — cage 4,11×≈8,82 (client ≈8,5) · local 4,18×4,50 à 7,92 · "
    "gêne 4,78×≈1,0 — souches/clim : NÉANT (client 27/07) — tables E-O portrait 1,134×4,70 "
    "(15°), allées 0,60 optimisées",
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
for (tx, ty) in placed:
    tx1, ty1 = tx + TBL_W, ty + TBL_L
    # jamais à cheval sur la ligne de niveau
    assert ty1 <= Y_INT + EPS or ty >= Y_INT - EPS, ("niveau", tx, ty)
    # dans l'emprise utile (rives / rives d'extrémité du jeu retenu)
    assert RIVE - EPS <= tx and tx1 <= W_MES - RIVE + EPS, ("rive", tx, ty)
    assert END_RIVE - EPS <= ty and ty1 <= L_TOT - END_RIVE + EPS, ("bout", tx, ty)
    # jamais dans un volume/une réserve ni à moins du dégagement retenu ;
    # autour de la GÊNE le dégagement reste 0,50 quel que soit le jeu
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

# étiquettes de zones (tout le toit est RELEVÉ — croquis complet)
for (xx, yy, txt) in ((13.1, 41.6, "TERRASSE HAUTE — relevé : champ libre"),
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
ax.text(CAGE[2] + 1.35, (CAGE[0] + CAGE[1]) / 2, "CAGE D'ESCALIER",
        fontsize=6.2, ha="center", va="center", fontweight="bold",
        color="#111", rotation=90, zorder=15)
ax.text(CAGE[2] + 2.55, (CAGE[0] + CAGE[1]) / 2,
        "4,11 × ≈8,82 (prof. déduite)", fontsize=5.0, ha="center",
        va="center", color=D.ORANGE, rotation=90, fontweight="bold",
        zorder=15)
# note détaillée en marge ouest, le long de la cote ≈8,82 (orange)
ax.text(-4.35, 25.5,
        "profondeur cage DÉDUITE de la fermeture 51,1 avec le segment "
        "cage→local RELEVÉ 7,92 (réponse client 27/07) → ≈8,82 — le client "
        "annonce ≈8,5 (arrondi) — à confirmer à l'exécution",
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

# provision plan 10,7 × 9,8 (pointillé gris) autour des volumes
PRX = (CAGE[2] + CAGE[3]) / 2 - 10.7 / 2
pr = Rectangle((PRX, Y_INT - 9.8), 10.7, 9.8, fill=False, edgecolor=D.GRIS,
               ls=":", lw=1.4, zorder=9)
ax.add_patch(pr)
ax.annotate("provision plan 10,7 × 9,8 « à confirmer » (pointillé)\n"
            "→ la cage (≈8,82) tient DANS la provision au sud",
            xy=(PRX + 0.4, Y_INT - 9.8), xytext=(1.2, 19.3), fontsize=5.2,
            ha="left", va="center", color="#475569", zorder=26,
            arrowprops=dict(arrowstyle="->", lw=0.6, color=D.GRIS),
            bbox=dict(fc="white", ec="none", alpha=0.88, pad=1.0))

# ------------------------------------------------------------------ réserves
# NÉANT (client 27/07) : aucune souche vue, aucune clim sur le toit
# aujourd'hui — la clim FUTURE se coordonnera à l'exécution (nota bas de plan).

# --------------------- GÊNE — ouvrage 4,78 × ≈1,0 (client), muret h≈0,5 (vu site)
ax.add_patch(Rectangle((GENE[2], GENE[0]), GENE[3] - GENE[2], GENE_D,
                       facecolor="#dbeafe", edgecolor=D.BLEU, lw=1.4,
                       zorder=12))
ax.add_patch(Rectangle((GENE[2] + 0.18, GENE[0] + 0.18),
                       GENE[3] - GENE[2] - 0.36, GENE_D - 0.36,
                       facecolor="white", edgecolor="none", zorder=13))
GXM = (GENE[2] + GENE[3]) / 2
ax.text(GXM, 15.65, "GÊNE — muret h≈0,5", fontsize=5.4, ha="center",
        va="center", fontweight="bold", color="#111", zorder=15,
        bbox=dict(fc="white", ec="none", alpha=0.88, pad=0.8))
ax.text(GXM, 15.00, "clim ? (client — pas sûr)", fontsize=4.8, ha="center",
        va="center", color=D.ORANGE, fontweight="bold", zorder=15,
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
      text="51,10 = 19,36 + ≈8,82 (cage, DÉDUIT — client ≈8,5) + 7,92 (relevé) + 4,50 + 10,50 ✓",
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

# chaîne horizontale LOCAL + GÊNE : 13,95 + 4,18 + 1,19 + 4,78 + 1,52 = 25,62 ✓
YC2 = 11.6
dimb((0, YC2), (CH[2], YC2), 0, "13,95")
dimb((CH[2], YC2), (CH[3], YC2), 0, "4,18 (déduit)", color=D.GRIS, fs=5.6)
dimb((CH[3], YC2), (GENE[2], YC2), 0, "1,19", fs=4.6)
dimb((GENE[2], YC2), (GENE[3], YC2), 0, "4,78 (déduit)", color=D.GRIS, fs=5.0)
dimb((GENE[3], YC2), (W_MES, YC2), 0, "1,52", fs=4.6)
ax.plot([W_MES, W_MES], [YC2 - 0.4, YC2 + 0.4], color=D.BLEU, lw=0.8, zorder=20)

# position de la gêne : bord SUD à 13,5 du MUR SUD (cote bleue verticale) —
# mur de référence à confirmer (nord ?) — AUCUNE diagonale mesurée
XG = 23.5
dimb((XG, 0), (XG, GENE[0]), 0, "13,5", color=D.BLEU, fs=5.6)
ax.text(XG + 0.55, 5.5, "mur de réf. : SUD — à confirmer (nord ?)",
        fontsize=4.8, ha="center", va="center", rotation=90, color=D.ORANGE,
        fontweight="bold", zorder=22,
        bbox=dict(fc="white", ec="none", alpha=0.88, pad=0.8))
# profondeur de la gêne ≈1,0 (client 27/07 — orange, côté est)
dimb((GENE[3], GENE[1]), (GENE[3], GENE[0]), 0.42, "≈1,0 (client)",
     color=D.ORANGE, fs=4.8)

# paramètres de calepinage cotés une fois (terrasse haute)
dimb((rows_used[0][0], 45.6), (rows_used[0][1], 45.6), 0, "4,70", color=D.GRIS,
     fs=5.2)
dimb((rows_used[0][1], 47.9), (rows_used[1][0], 47.9), 0, fr(ALLEE),
     color=D.GRIS, fs=5.2)
dimb((rows_used[1][1], 47.9), (rows_used[2][0], 47.9), 0,
     "2,95 (allée large — colonne cage)", color=D.GRIS, fs=5.2)

# nord
ax.add_patch(FancyArrowPatch((-3.8, 51.8), (-3.8, 53.4), arrowstyle="-|>",
                             mutation_scale=11, lw=1.4, color=D.NOIR, zorder=30))
ax.text(-3.8, 53.95, "N", fontsize=10, ha="center", fontweight="bold",
        zorder=30)

# bandeau engagement — chiffre VRAI, jamais masqué, jamais de « max »
if n_show >= 288:
    VERDICT = "CONFIRMÉ"
    ax.text(13.1, 56.4,
            f"ENGAGEMENT 288 (18×16) : CONFIRMÉ — {n_show} modules posables "
            "sur le relevé complet 51,1 m",
            fontsize=9.5, ha="center", fontweight="bold", color=VERT, zorder=30)
else:
    VERDICT = "TENDU"
    ax.text(13.1, 56.4,
            f"ENGAGEMENT 288 : TENDU — {n_show} modules posables sur 51,1 m "
            f"(manque {288 - n_show}) — voir redistribution",
            fontsize=9.5, ha="center", fontweight="bold", color=TENDU_C,
            zorder=30)
ax.text(13.1, 55.45,
        f"total toit complet 51,1 m ({PARAMS_TXT}) : {n_show} mod. = "
        f"{fr(n_show * 0.625)} kWc — conservateur 1,50/0,50/0,50 : {n_cons} — "
        f"marge vs 288 : {n_show - 288:+d}",
        fontsize=6.0, ha="center", color="#374151", zorder=30)
ax.text(13.1, 54.65,
        "cage : segment cage→local RELEVÉ 7,92 (réponse client 27/07) → "
        "profondeur ≈8,82 déduite de la fermeture 51,1 (client : ≈8,5 arrondi) "
        "— à confirmer à l'exécution",
        fontsize=6.0, ha="center", color=D.ORANGE, zorder=30)

# nota bas de plan
ax.text(13.1, -1.35,
        "Croquis client = toit COMPLET (bord bas = mur sud) : un seul "
        "calepinage sur 51,1 m. Aucune table à cheval sur la ligne interne.",
        fontsize=6.0, ha="center", color="#475569", zorder=30)
ax.text(13.1, -2.05,
        "GÊNE : 4,78 × ≈1,0 (client — muret h≈0,5, clim ? pas sûr) — "
        "dégagt 0,50 · SOUCHES : aucune vue (client 27/07).",
        fontsize=6.0, ha="center", color=TENDU_C, zorder=30)
ax.text(13.1, -2.75,
        "CLIM : aucune aujourd'hui — viendra plus tard (client 27/07) → "
        "à coordonner avec le champ PV à l'exécution.",
        fontsize=6.0, ha="center", color="#475569", zorder=30)
if n_show < 288:
    ax.text(13.1, -3.45,
            "NOTA : déport possible vers la résidence à l'exécution (inverse "
            "de la redistribution résidence).",
            fontsize=6.0, ha="center", color=TENDU_C, zorder=30)
    ax.text(13.1, -4.15,
            "Arbitrage possible par redistribution inter-bâtiments (ratios par "
            "installation restent dans [0,75 ; 1]) — voir note de synthèse.",
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
    ("gene", "gêne 4,78×≈1,0 (client) — muret h≈0,5, clim ? · dégagt 0,50"),
    ("prov", "provision plan (pointillé — la cage ≈8,82 tient dedans)"),
    ("dimB", "cote MESURÉE / confirmée site (bleu)"),
    ("dimO", "cote / position À CONFIRMER"),
    ("dimG", "plan / déduit des fermetures"),
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
    elif kind == "res":
        rr = Rectangle((PX, yy - 0.42), 1.3, 0.55, facecolor="#cbd5e1",
                       edgecolor=D.ORANGE, lw=0.7, hatch="///", zorder=30)
        rr.set_linestyle("--")
        ax.add_patch(rr)
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

y = titre(y, "FERMETURES DU CROQUIS (corrigées)")
y = lignes(y, [
    "13,18 + 0,91 (marche) + 4,11 (déduit) + 7,42 = 25,62 ✓ exact",
    "13,95 + 4,18 (déduit) + 1,19 + 4,78 (déduit) + 1,52 = 25,62 ✓",
    "19,36 + ≈8,82 (cage, DÉDUIT) + 7,92 (relevé) + 4,50 + 10,50 = 51,10 ✓",
    "→ cage→local = 7,92 RELEVÉ (réponse client 27/07, remplace 2,32) ;",
    "   le tronçon déduit reste la PROFONDEUR DE LA CAGE (client ≈8,5)",
    "largeur : 25,62 mesuré vs 26,2 plan → Δ 0,58 à confirmer",
    "cluster SE : le petit rectangle = LA GÊNE (4,78 × ≈1,0 client) ·",
    "1,19 = écart chambre↔gêne · 13,5 = gêne → mur sud (position)",
])

y = titre(y, "CALEPINAGE — PORTRAIT 15°")
cal = [
    "4 rangées de tables E-O PORTRAIT 1,134 × 4,70",
    "(2 × 2,382 × cos15° + faîtage) le long des 51,1 m",
    "retenu : allées 0,60 OPTIMISÉES (client 27/07) — surplus",
    "concentré en UNE allée large 2,95 sur la colonne cage/local",
    f"→ cage+local+marche ne coupent qu'1 bande ; gêne : 1 bande",
    f"rives {fr(RIVE)} · dégagt {fr(CLEAR)} (gêne : 0,50)",
    f"info : uniforme 0,60 = {n_unif} · conservateur 1,50/0,50 = {n_cons}",
    "coupure de niveau à la ligne interne (aucun chevauchement)",
    f"TOTAL toit complet 51,1 m : {n_show} mod. = {fr(n_show * 0.625)} kWc",
    f"ENGAGEMENT : 288 modules (18×16) = 180,0 kWc → {VERDICT}",
    "18 strings × 16 — 3 onduleurs 50 kW (96/96/96)",
]
if n_show < 288:
    cal += [f"manque {288 - n_show} modules → déport possible vers la",
            "résidence · redistribution inter-bâtiments (ratios [0,75;1])"]
else:
    cal += [f"marge : +{n_show - 288} modules (cage prof. déduite ≈8,82)"]
y = lignes(y, cal)

y = titre(y, "À CONFIRMER (orange)", color=D.ORANGE)
y = lignes(y, [
    "PROFONDEUR CAGE ≈8,82 : DÉDUITE de la fermeture 51,1 avec",
    "le segment 7,92 relevé (réponse client 27/07 ; il annonce ≈8,5",
    "arrondi) — à confirmer à l'exécution",
    "gêne : ≈1,0 prof (client) · muret h≈0,5 · clim ? (pas sûr)",
    "— dégagt 0,50 maintenu · mur de réf. du 13,5 : SUD (nord ?)",
    "Δ largeur 0,58 · CLIM FUTURE : aucune aujourd'hui, viendra",
    "après → implantation à coordonner avec le champ PV (exécution)",
])

D.scale_bar(ax, PX, max(y - 1.5, 3.6), total=10, step=2)

D.cartouche(fig, [
    ("ACCORDIA TECH — Consultation FRDISI PV + stockage, Mohammedia", True),
    ("BÂT. C — ÉCOLE SUPTECH — VUE DE TOITURE (relevé + calepinage)", True),
    ("Relevé R. Kasri 27/07/2026 — restitution TAQINOR — tables E-O portrait "
     "1,134×4,70, pose 15°", False),
    ("Échelle : barre graphique (impression A3) — cotes en mètres — "
     "NE REMPLACE PAS 05E/05G", False),
])

fig.savefig(os.path.join(BASE, "VUE_TOITURE_BAT_C_ECOLE.pdf"), bbox_inches="tight")
fig.savefig(os.path.join(BASE, "VUE_TOITURE_BAT_C_ECOLE.png"), dpi=170,
            bbox_inches="tight")

print(f"conservateur 1,50/0,50/0,50 : {n_cons} modules ({n_cons*0.625:.2f} kWc), phase={ph_cons:.2f}")
print(f"uniforme 0,60/0,35/0,30     : {n_unif} modules ({n_unif*0.625:.2f} kWc), phase={ph_unif:.2f}")
print(f"retenu : {PARAMS_TXT} — TOTAL toit complet 51,1 m : {n_show} "
      f"(dessiné = {n_drawn})")
print(f"engagement 288 → {VERDICT} (marge {n_show - 288:+d})")
print("VUE_TOITURE_BAT_C_ECOLE.pdf / .png écrits")
