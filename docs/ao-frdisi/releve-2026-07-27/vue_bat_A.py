# -*- coding: utf-8 -*-
"""VUE DE TOITURE DÉFINITIVE — Bât. A (aile en L), Résidence universitaire UIB, Mohammedia.
Contour relevé + locaux (cage d'escalier, décroché nord, accès sud) + TOUS les obstacles +
cotes du relevé 27/07/2026 + calepinage PV superposé (tables E-O 2,382×2,25, allées 1,20,
rives 0,35, rives d'extrémité 0,50, dégagement 0,30 dans les 2 sens, phase optimisée).
Révision : correction contradictoire (critique 27/07) — aile 2 MIROITÉE (quadruple 1,35×1,15
au SUD, cluster jonction au NORD), chaînes transversales fermées 11,20, zone B recalée
(6,08/5,97/1,15/0,55/10,77, caisson 0,8×0,63 ?), zone A complétée (liaisons 1,75/1,37,
entraxe 1,53, offsets 3,85/3,84, cluster SW 2,39/1,2/1,54, édicule 0,92×0,74 bloquant),
3 caissons transposés."""
import sys
sys.path.insert(0, ".")
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
NX0, NX1, NDY = 31.28, 32.82, 0.74      # décroché sud accès toiture — largeur 1,54

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
    (32.53, 33.03, 6.14, 6.98, "0,84×0,50", "below", False),   # TRANSPOSÉ debout 0,50×0,84
    (33.68, 34.63, 6.41, 6.88, None,        "below", True),    # 0,94×0,47? (texte à part)
    (39.50, 40.48, 6.61, 7.07, "0,98×0,46", "below", True),    # TRANSPOSÉ couché, rive 3,85
    (43.975, 44.515, 6.18, 7.05, "0,87×0,54", "below", False), # TRANSPOSÉ debout 0,54×0,87
    # zone A — rangée basse
    (32.18, 32.88, 3.74, 4.73, "0,70×0,99", "right", False),
    (39.31, 40.72, 3.75, 4.65, "1,41×0,90", "below", False),
    (45.68, 46.98, 3.75, 4.81, "1,30×1,06", "below", False),
]
CAGE = (12.23, 14.70, 6.13, 10.76)       # cage d'escalier ≈2,5×4,6 (5,97/1,15 recoupés)
DECN = (14.70, 17.47, 9.61, 10.76)       # décroché nord 2,77 — prof. 1,15 ?
NOTCH = (NX0, NX1, 0.0, NDY)             # décroché accès sud — largeur 1,54
EDIC = (30.21, 31.13, 0.0, 0.74)         # édicule ≈0,92×0,74 — obstacle réel (3,18)
obs_bar = [c[:4] for c in CAIS_BAR] + [CAGE, DECN, NOTCH, EDIC]

# ---------------- aile 2 — MIROITÉE (critique item 1) : quadruple 1,35×1,15 au SUD
# (attaches 3,38 ×2 au mur sud), cluster {1,10×0,42 · rectangle non coté …} au NORD.
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
GRECT = (0.40, 1.70, 4.95, 7.16)         # grand rectangle non coté (jonction, 4,04 de l'est)
PAN = (LEG_S - CUT_H, LEG_S, LEG_W - CUT_W, LEG_W)   # pan coupé SE (hors toiture)
obs_leg = [c[:4] for c in CAIS_LEG] + [GRECT, PAN]

# ---------------- contrôles de fermeture
xb = chain(0, 3.39, 1.31, 6.47, 1.33, 6.55, 1.30, 3.23)
closure("B — chaîne basse fermée", xb[-1], B_LEN, tol=0.05)
xn = chain(0, 12.23, 2.47, 2.77, 6.11)
closure("B — chaîne nord (cage+décroché+6,11)", xn[-1], B_LEN, tol=0.05)
tT = chain(0, 3.78, 1.15, 1.40, 1.15, 3.72)
closure("Aile 2 — transversale fermée", tT[-1], LEG_W, tol=0.02)
tW = chain(0, 3.38, 1.35, 6.54, 1.35, 6.84, 1.21, 7.37, 0.42, 1.45)
closure("Aile 2 — chaîne ouest S→N (+10,76 barre = 40,67)", tW[-1], LEG_S, tol=0.25)
tE = chain(0, 3.38, 1.35, 6.67, 1.35, 6.73, 0.63, 4.31, 5.50)
closure("Aile 2 — chaîne est S→N", tE[-1], LEG_S, tol=0.25)

# ================================================================ CALEPINAGE
ALL, RIV, CLR, ER = 1.20, 0.35, 0.30, 0.50
rows_bar = C.rows_for(W_B, ALL, RIV, 0.0)
rows_leg = C.rows_for(LEG_W, ALL, RIV, 0.0)
assert len(rows_bar) == 3 and len(rows_leg) == 3, "3 rangées/bande attendues"
n_bar, p_bar = C.best_phase(BAR, W_B, obs_bar, ALL, RIV, CLR, end_rive=ER)
n_leg, p_leg = C.best_phase(LEG_S, LEG_W, obs_leg, ALL, RIV, CLR, end_rive=ER)
N = n_bar + n_leg
KWC = N * 0.625
print(f"[CALEPINAGE] barre {n_bar} (phase {p_bar:.2f}) + aile {n_leg} "
      f"(phase {p_leg:.2f}) = {N} modules ({KWC:.1f} kWc)")

# ================================================================ FEUILLE
fig, ax = D.new_sheet(
    "VUE DE TOITURE — BÂTIMENT A (AILE EN L) — RÉSIDENCE UNIVERSITAIRE UIB, MOHAMMEDIA",
    "Contour, locaux et obstacles : RELEVÉ CONTRADICTOIRE du 27/07/2026 (croquis A/B/C) — "
    "calepinage superposé : tables E-O 2,382×2,25 m, 3 rangées/bande, allées 1,20, rives 0,35, "
    "rives d'extrémité 0,50, dégagement obstacles 0,30 (2 sens), phase optimisée — "
    "BLEU = mesuré · ORANGE = à confirmer · GRIS = plan/déduit",
    (-7.5, 57.5), (-34.8, 16.2))

# ---------------- contour (avec décroché sud 1,54 + ressaut de largeur B/A)
outline = [(0, W_B), (B_LEN, W_BE), (B_LEN, W_A), (BAR, W_A), (BAR, 0),
           (NX1, 0), (NX1, NDY), (NX0, NDY), (NX0, 0), (LEG_W, 0),
           (LEG_W, -LEG_S + CUT_H), (LEG_W - CUT_W, -LEG_S), (0, -LEG_S)]
ax.add_patch(Polygon(outline, closed=True, fill=False, lw=2.4, edgecolor=D.NOIR,
                     zorder=12))
# acrotère (ligne intérieure)
acro = [(0.28, W_B - 0.28), (B_LEN, W_BE - 0.28), (B_LEN, W_A - 0.28),
        (BAR - 0.28, W_A - 0.28), (BAR - 0.28, 0.28), (NX1 + 0.28, 0.28),
        (NX1 + 0.28, NDY + 0.28), (NX0 - 0.28, NDY + 0.28), (NX0 - 0.28, 0.28),
        (LEG_W - 0.28, 0.28), (LEG_W - 0.28, -25.63), (8.85, -LEG_S + 0.28),
        (0.28, -LEG_S + 0.28)]
ax.add_patch(Polygon(acro, closed=True, fill=False, lw=0.6, edgecolor="#666666",
                     zorder=11))

# ---------------- calepinage (dessous, vert clair)
nd_bar = C.fill_band(ax, 0, 0, BAR, W_B, obs_bar, horizontal=True,
                     allee=ALL, rive=RIV, clear=CLR, phase=p_bar, end_rive=ER)
nd_leg = C.fill_band(ax, 0, 0, LEG_S, LEG_W, obs_leg, horizontal=False,
                     allee=ALL, rive=RIV, clear=CLR, phase=p_leg, end_rive=ER)
assert nd_bar == n_bar and nd_leg == n_leg, "dessin ≠ comptage !"

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
# accès toiture sud : décroché 1,54 dans le contour + édicule réel en rive
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

# ---------------- caissons aile 2 (miroités)
for s0, s1, x0, x1, lab, pos, unc in CAIS_LEG:
    D.caisson(ax, x0, -s1, x1 - x0, s1 - s0, label=lab, uncertain=unc,
              label_pos=pos, fs=5.2)
gr = Rectangle((GRECT[2], -GRECT[1]), GRECT[3] - GRECT[2], GRECT[1] - GRECT[0],
               facecolor="none", edgecolor=D.ORANGE, lw=1.1, zorder=15)
gr.set_linestyle("--")
ax.add_patch(gr)
ax.text(GRECT[3] + 0.15, -(GRECT[0] + GRECT[1]) / 2, "grand rect.\nnon coté ?",
        fontsize=5.2, ha="left", va="center", color=D.ORANGE, fontweight="bold",
        zorder=25)

# ---------------- séparation zones + étiquettes
ax.plot([B_LEN, B_LEN], [0, W_BE], color="#7c3aed", lw=0.9, ls="--", zorder=13)
ax.text(5.6, 11.45, "ZONE B (croquis B)", fontsize=9, fontweight="bold",
        color="#7c3aed", ha="center")
ax.text(36.0, 11.5, "ZONE A (croquis A)", fontsize=9, fontweight="bold",
        color="#7c3aed", ha="center")
ax.text(1.6, -13.5, "AILE 2 (croquis C)", fontsize=9, fontweight="bold",
        color="#7c3aed", rotation=90, va="center")

# ================================================================ COTES — BARRE
# --- extérieur nord
D.dim(ax, (DECN[0], W_B), (DECN[1], W_B), off=0.75, text="2,77")
D.dim(ax, (DECN[1], W_B), (B_LEN, W_B), off=0.75, text="6,11")
D.dim(ax, (0, W_B), (B_LEN, W_BE), off=1.95, text="23,58 (chaîne fermée)")
D.dim(ax, (B_LEN, W_A), (BAR, W_A), off=1.80, text="23,50 (mesuré — relire : 23,6 ?)")
D.dim(ax, (0, W_B), (BAR, W_A), off=3.35, text="47,08 relevé (= 23,58 + 23,50) — plan : 48,0")
# --- extérieur est / ouest + raccord B/A
D.dim(ax, (BAR, 0), (BAR, W_A), off=-2.05, text="10,92 relevé")
D.dim(ax, (0, 0), (0, W_B), off=3.0, text="10,76 relevé")
D.dim(ax, (23.42, 0), (23.42, W_BE), off=0.0, text="10,77 (raccord B/A)", fs=5.8)
# --- zone B : chaîne basse (dans l'allée 1) + offsets verticaux
y_c1 = RIV + p_bar + 2.25 + ALL / 2
D.dim(ax, (0, y_c1), (3.39, y_c1), off=0.0, text="3,39")
D.dim(ax, (4.70, y_c1), (11.17, y_c1), off=0.0, text="6,47")
D.dim(ax, (12.50, y_c1), (19.05, y_c1), off=0.0, text="6,55")
D.dim(ax, (20.35, y_c1), (B_LEN, y_c1), off=0.0, text="3,23")
D.dim(ax, (4.30, 0), (4.30, 3.77), off=-0.45, text="3,77")
D.dim(ax, (11.85, 0), (11.85, 3.84), off=-0.45, text="3,84")
D.dim(ax, (19.70, 0), (19.70, 3.33), off=-0.45, text="3,33")
# --- zone B : chaîne médiane + verticales relevées
D.dim(ax, (0, 6.55), (3.16, 6.55), off=0.0, text="3,16", color=D.ORANGE)
D.dim(ax, (4.27, 6.55), (8.03, 6.55), off=0.0, text="3,76")
D.dim(ax, (9.14, 6.55), (12.23, 6.55), off=0.0, text="3,09")
D.dim(ax, (14.70, 8.74), (16.52, 8.74), off=0.0, text="1,82")
D.dim(ax, (17.32, 7.45), (18.92, 7.45), off=0.0, text="1,75")
D.dim(ax, (20.35, 6.72), (B_LEN, 6.72), off=0.0, text="3,23")
D.dim(ax, (3.70, 7.02), (3.70, W_B), off=-0.45, text="3,74")
D.dim(ax, (8.60, 7.38), (8.60, W_B), off=-0.45, text="3,83")
D.dim(ax, (8.60, 0), (8.60, 6.08), off=-0.45, text="6,08")
D.dim(ax, (12.90, 0), (12.90, 6.13), off=-0.35, text="5,97", fs=6.2)
D.dim(ax, (12.35, 4.98), (12.35, 6.13), off=0.0, text="1,15", fs=5.2)
D.dim(ax, (16.92, 9.06), (16.92, 9.61), off=0.55, text="0,55", fs=5.2)
D.dim(ax, (19.60, 7.46), (19.60, W_B), off=-0.45, text="3,3")
D.dim(ax, (3.95, 4.92), (3.95, 5.91), off=0.42, text="1,35 ?", color=D.ORANGE, fs=6)
D.dim(ax, (19.95, 4.34), (19.95, 6.02), off=0.42, text="1,31 ?", color=D.ORANGE, fs=6)
# --- zone A : chaîne haute (intérieure) + offsets nord
ya = 8.55
D.dim(ax, (B_LEN, ya), (24.86, ya), off=0.0, text="1,26")
D.dim(ax, (27.92, ya), (33.03, ya), off=0.0, text="5,22")
D.dim(ax, (34.63, ya), (39.50, ya), off=0.0, text="5,04")
D.dim(ax, (40.48, ya), (43.975, ya), off=0.0, text="2,55 ?", color=D.ORANGE)
D.dim(ax, (44.515, ya), (BAR, ya), off=0.0, text="2,58")
D.dim(ax, (25.60, 7.46), (25.60, W_A), off=-0.45, text="3,3")
D.dim(ax, (27.49, 7.08), (27.49, W_A), off=-0.45, text="3,84")
D.dim(ax, (32.80, 6.98), (32.80, W_A), off=-0.45, text="3,78")
D.dim(ax, (34.15, 6.88), (34.15, W_A), off=0.45, text="3,88")
D.dim(ax, (39.99, 7.07), (39.99, W_A), off=-0.45, text="3,85")
D.dim(ax, (44.25, 7.05), (44.25, W_A), off=-0.45, text="3,84")
# entraxe 1,53 entre 0,84×0,50 et 0,94×0,47 (adjudication du « 0,47 ou 1,53 ? »)
D.dim(ax, (32.78, 6.55), (34.155, 6.55), off=0.0, text="1,53", fs=5.4)
# liaisons verticales relevées (croquis A)
ax.plot([34.63, 37.35], [6.41, 6.41], color="#94a3b8", lw=0.45, ls=":", zorder=19)
ax.plot([36.65, 39.31], [4.65, 4.65], color="#94a3b8", lw=0.45, ls=":", zorder=19)
D.dim(ax, (37.0, 6.41), (37.0, 4.65), off=0.0, text="1,75", fs=6)
ax.plot([44.515, 45.45], [6.18, 6.18], color="#94a3b8", lw=0.45, ls=":", zorder=19)
ax.plot([44.75, 45.68], [4.81, 4.81], color="#94a3b8", lw=0.45, ls=":", zorder=19)
D.dim(ax, (45.1, 6.18), (45.1, 4.81), off=0.0, text="1,37", fs=6)
# --- zone A : chaîne basse (sud) + cluster sud-ouest
D.dim(ax, (32.88, y_c1), (39.31, y_c1), off=0.0, text="6,43")
D.dim(ax, (39.31, y_c1 - 0.85), (45.68, y_c1 - 0.85), off=0.0, text="6,37")
D.dim(ax, (32.50, 0), (32.50, 3.74), off=0.45, text="3,74")
D.dim(ax, (40.00, 0), (40.00, 3.75), off=-0.45, text="3,75")
D.dim(ax, (46.30, 0), (46.30, 3.75), off=-0.45, text="3,75")
D.dim(ax, (26.41, 6.82), (26.79, 4.46), off=0.0, text="2,39 ?", color=D.ORANGE, fs=6)
D.dim(ax, (26.79, 1.20), (26.79, 0.0), off=0.0, text="1,2 ?", color=D.ORANGE, fs=6)
D.dim(ax, (31.13, 0.74), (32.18, 3.74), off=0.0, text="3,18", fs=6)
D.dim(ax, (NX0, -0.6), (NX1, -0.6), off=0.0, text="1,54")

# ================================================================ COTES — AILE 2
# chaîne OUEST complète N→S (jonction barre → mur sud), à l'extérieur ouest
segW = [("1,45", D.BLEU, 1.45), ("0,42", D.BLEU, 0.42), ("7,37", D.ORANGE, 7.37),
        ("1,21", D.BLEU, 1.21), ("6,84 (6,87 ?)", D.ORANGE, 6.67),
        ("1,35", D.BLEU, 1.35), ("6,54", D.BLEU, 6.54), ("1,35", D.BLEU, 1.35),
        ("3,38", D.BLEU, 3.38)]
yy = 0.0
for txt, col, seg in segW:
    D.dim(ax, (-1.15, yy), (-1.15, yy - seg), off=0.25, text=txt, color=col, fs=6.2)
    yy -= seg
D.dim(ax, (0, -LEG_S), (0, W_B), off=4.55, text="40,5 (plan) = 10,76 barre + 29,74 aile",
      color=D.GRIS)
ax.text(-5.95, -14.9, "chaînes aile 2 : ≈38 – 40,7 — contre-lecture requise",
        fontsize=6.0, color=D.ORANGE, rotation=90, ha="center", va="center", zorder=25)
# chaîne EST complète N→S (jonction → mur sud), colonne extérieure est
segE = [("5,5", D.BLEU, 5.32), ("4,31", D.BLEU, 4.31), ("0,63", D.BLEU, 0.63),
        ("6,73", D.BLEU, 6.73), ("1,35", D.BLEU, 1.35), ("6,67", D.BLEU, 6.67),
        ("1,35", D.BLEU, 1.35), ("3,38", D.BLEU, 3.38)]
yy = 0.0
for txt, col, seg in segE:
    D.dim(ax, (12.55, yy), (12.55, yy - seg), off=-0.25, text=txt, color=col, fs=6.2)
    yy -= seg
D.dim(ax, (LEG_W, -LEG_S), (LEG_W, 0), off=-3.1, text="29,74 (= 40,5 − 10,76)",
      color=D.GRIS)
# chaînes TRANSVERSALES FERMÉES (preuve largeur 11,2) aux 2 rangées du quadruple
segT = [("3,78", 3.78), ("1,15", 1.15), ("1,40", 1.40), ("1,15", 1.15), ("3,72", 3.72)]
for s_row in (25.685, 17.73):
    xx = 0.0
    for txt, seg in segT:
        D.dim(ax, (xx, -s_row), (xx + seg, -s_row), off=0.0, text=txt, fs=5.4)
        xx += seg
    ax.text(11.55, -s_row, "Σ 11,20 ✓", fontsize=5.5, color="#15803d",
            fontweight="bold", rotation=90, ha="center", va="center", zorder=25)
# offset ouest du caisson 1,07×1,21
D.dim(ax, (0, -9.85), (3.78, -9.85), off=0.0, text="3,78", fs=5.4)
# cluster jonction (nord) — rattachements à confirmer
D.dim(ax, (0.55, 0), (0.55, -4.82), off=0.0, text="4,82 ?", color=D.ORANGE, fs=5.6)
D.dim(ax, (5.05, -2.7), (6.98, -2.7), off=0.0, text="1,93 ?", color=D.ORANGE, fs=5.6)
D.dim(ax, (GRECT[3], -2.55), (LEG_W, -2.55), off=0.0, text="4,04 ?", color=D.ORANGE,
      fs=5.6)
D.dim(ax, (LEG_W, -2.18), (LEG_W, 0), off=-0.55, text="2,18 ?", color=D.ORANGE, fs=5.6)
# pan coupé (forme du plan) + largeur
ax.text(10.30, -28.30, "pan coupé (plan)", fontsize=5.0, color=D.GRIS, rotation=62,
        ha="center", va="center", zorder=25)
D.dim(ax, (0, -LEG_S), (LEG_W, -LEG_S), off=-2.0, text="11,2 (plan)", color=D.GRIS)

# ================================================================ HABILLAGE
ax.text(30.5, -4.35,
        "RETENU EXÉCUTION — BÂT. A : 128 modules (8 chaînes ×16) — voir NOTA",
        fontsize=11, fontweight="bold", ha="center", color="#15803d", zorder=30)
ax.text(30.5, -5.55,
        f"posable sur le relevé : {N} modules ({KWC:.1f} kWc) — barre {n_bar} · aile 2 {n_leg}",
        fontsize=8.5, ha="center", color="#15803d", zorder=30)

# mini-repérage croquis
kx, ky, s = 17.2, -8.2, 0.085
mini = [(0, 10.76), (47.08, 10.76), (47.08, 0), (11.2, 0), (11.2, -25.7),
        (9.0, -29.74), (0, -29.74)]
ax.add_patch(Polygon([(kx + p[0] * s, ky + p[1] * s) for p in mini], closed=True,
             fill=False, lw=1.0, edgecolor="#555555", zorder=30))
for cx, cy, t in ((35.3, 5.4, "A"), (11.8, 5.4, "B"), (5.6, -14.9, "C")):
    ax.text(kx + cx * s, ky + cy * s, t, fontsize=7, ha="center", va="center",
            fontweight="bold", color="#7c3aed", zorder=31)
ax.text(kx + 2.0, ky + 1.6, "repérage croquis (IMG 2952-2955)", fontsize=5.6,
        color="#555555", zorder=30)

D.legende(ax, 25.5, -7.6, [
    ("caisson", "caisson béton relevé (chaîné)"),
    ("caissonU", "caisson — lecture / position à confirmer"),
    ("bloc", "local (cage d'escalier, édicule) — murs épais"),
    ("dim", "cote mesurée (croquis Reda 27/07)"),
    ("dimU", "cote à confirmer / rattachement supposé"),
])
ax.add_patch(Rectangle((25.5, -11.55), 1.19, 1.125, facecolor="#bbf7d0",
             edgecolor="#15803d", lw=0.6, zorder=30))
ax.plot([25.5, 26.69], [-10.99, -10.99], color="#15803d", lw=0.5, zorder=31)
ax.text(26.9, -11.0, "table PV 2 modules E-O (2,382×2,25) + faîtage", fontsize=7,
        va="center", zorder=30)

# nord + échelle
ax.add_patch(FancyArrowPatch((46.8, -7.9), (46.8, -5.9), arrowstyle="-|>",
             mutation_scale=16, lw=1.6, color="#111111", zorder=30))
ax.text(46.8, -5.6, "N", fontsize=10, ha="center", fontweight="bold", zorder=30)
D.scale_bar(ax, 40.5, -12.8)

# contrôles de fermeture
ax.text(17.2, -13.6,
        "CONTRÔLES DE FERMETURE\n"
        "· zone B, chaîne basse : 3,39+1,31+6,47+1,33+6,55+1,30+3,23 = 23,58 — résidu 0,00\n"
        "· zone B, chaîne nord : 12,23 (→cage) + 2,47 + 2,77 + 6,11 = 23,58 — résidu 0,00\n"
        "· zone B, cage : 5,97 ≈ 1,15+1,14+3,84 = 6,13 (Δ 0,16) → emprise ≈2,5×4,6 déduite\n"
        "· barre : 23,58 + 23,50 = 47,08 relevé (plan 48,0 → Δ −0,92)\n"
        "· aile 2 OUEST S→N : 3,38+1,35+6,54+1,35+6,84*+1,21+7,37*+0,42+1,45 = 29,91\n"
        "  (+10,76 barre = 40,67 ≈ 40,5 plan) — EST : 3,38+1,35+6,67+1,35+6,73+0,63+4,31+5,5 = 29,92\n"
        "· aile 2 TRANSVERSAL : 3,78+1,15+1,40+1,15+3,72 = 11,20 = largeur 11,2 EXACT ✓\n"
        "· largeurs relevées : 10,76 (B ouest) / 10,77 (raccord B/A) / 10,92 (A)\n"
        "· (*) ORANGE : contre-lecture requise (6,84↔6,87 · 7,37↔4,37 → ouest ≈38 à 40,7)",
        fontsize=6.4, va="top", color="#334155", zorder=30,
        bbox=dict(boxstyle="round,pad=0.45", fc="#f8fafc", ec="#94a3b8", lw=0.7))
# à confirmer
ax.text(17.2, -20.6,
        "À CONFIRMER À LA PROCHAINE VISITE\n"
        "· 23,50 ou 23,6 (longueur zone A) · 2,55 ? (0,98↔0,87) · 1,53 = entraxe 0,84↔0,94×0,47\n"
        "· zone B : verticales 1,11×1,30 → 6,08+1,30+3,83 = 11,21 vs 10,76 (Δ +0,45, à re-mesurer)\n"
        "  · caisson 0,8×0,63 ? (lu « 0,18 », improbable) · décroché nord : prof. 1,15 ?\n"
        "· zone A SW : 2,39 (diag. dep. 1,53×0,64) & 1,2 (descente façade sud) — rattachements supposés\n"
        "  · édicule ≈0,92×0,74 (3,18 → caisson 0,70×0,99) · décroché accès : prof. ≈0,7 ?\n"
        "· aile 2 : 6,84 (relu 6,87 ?) · 7,37 (ou 4,37 ?) · 4,82 ≈ 3,38+1,45 (recoup. jonction)\n"
        "  · grand rectangle non coté · 1,93 · 2,18 (chanfrein jonction ?) · 4,04 (est)\n"
        "· cotes C non rattachées : 4,1 · 6,34 · 6,31 · 3,63 · 1,43/1,4 (jeu files) · 0,21/0,42",
        fontsize=6.4, va="top", color="#7c2d12", zorder=30,
        bbox=dict(boxstyle="round,pad=0.45", fc="#fff7ed", ec="#d97706", lw=0.7))
# NOTA obligatoire
ax.text(17.2, -27.6,
        "NOTA EXÉCUTION — la ligne bordereau A = 152 modules N'EST PAS atteignable sur le "
        "bât. A seul ;\nla résidence A+B = 272 modules EST CONFIRMÉE via redistribution "
        "A = 128 (8×16) + B = 144 (9×16),\ncharges onduleurs 96/80/96 et ratio "
        "150/170 = 0,882 INCHANGÉS — marché à prix unitaires,\nimplantation ajustée au "
        "relevé contradictoire (mémoire §2.1).",
        fontsize=7.0, va="top", fontweight="bold", color="#111111", zorder=30,
        bbox=dict(boxstyle="round,pad=0.5", fc="#fefce8", ec="#111111", lw=1.0))

D.cartouche(fig, [
    ("ACCORDIA TECH — Consultation FRDISI PV + stockage, Mohammedia", True),
    (f"Bât. A (aile en L) — VUE DE TOITURE : relevé 27/07/2026 — exécution 128 mod. "
     f"(posable {N})", True),
    ("Relevé : R. Kasri — restitution TAQINOR — document de travail", False),
    ("A3 — cotes en m — échelle : barre graphique — NE REMPLACE PAS les planches 05E/05G",
     False),
])
fig.savefig("VUE_TOITURE_BAT_A_L.pdf", bbox_inches="tight")
fig.savefig("VUE_TOITURE_BAT_A_L.png", dpi=170, bbox_inches="tight")
print(f"[OK] VUE_TOITURE_BAT_A_L.pdf/.png — {N} modules dessinés")
