# -*- coding: utf-8 -*-
"""Plan reconstitué — Aile en L (Bât. A), assemblage zones A + B + C.

Repère global : origine = angle bas-gauche de la BARRE (jonction jambe/barre côté ouest).
  x = le long de la barre (vers l'est) ; y = largeur (vers le nord = bord haut).
  La jambe (zone C) descend sous la barre à x ∈ [0 ; 10,76], y < 0.

Chaînes issues du relevé Reda 27/07/2026 (croquis A B C + schéma de repérage).
Zone B : x ∈ [0 ; 23,58] (chaîne basse FERMÉE : 3,39+1,31+6,47+1,33+6,55+1,30+3,23)
Zone A : x ∈ [23,58 ; 47,08] (fermeture : Σ=23,25 vs 23,5 mesuré → compensation +1,08 %)
"""
import sys
sys.path.insert(0, ".")
import dessin as D
from solveur import chain, closure
from matplotlib.patches import Polygon, Rectangle

# ------------------------------------------------------------------ géométrie
B_LEN = 23.58          # zone B, chaîne fermée
A_LEN = 23.50          # zone A, cote totale mesurée
BAR = B_LEN + A_LEN    # 47,08
W_B = 10.76            # largeur mesurée zone B (10,76 ouest / 10,77 est)
W_A = 10.92            # largeur mesurée zone A
LEG_W = 10.76          # jambe : largeur supposée = W_B (à confirmer)
LEG_TOT = 24.91        # depuis le bord HAUT de la barre (chaîne colonne ouest C)
LEG_BOT = W_B - LEG_TOT      # y du bas de jambe = -14,15
CUT_W, CUT_H = 2.18, 4.04    # pan coupé angle SE de la jambe (lecture croquis C)

AX0 = B_LEN            # début zone A

fig, ax = D.new_sheet(
    "RELEVÉ CONTRADICTOIRE TOITURE — BÂTIMENT A (AILE EN L) — RÉSIDENCE UNIVERSITAIRE UIB",
    "Reconstruction cotée du relevé terrain du 27/07/2026 (croquis A B C de R. Kasri) — "
    "cotes en mètres · bleu = mesuré · orange = lecture/rattachement à confirmer · gris = déduit",
    (-6.5, 53.5), (-19.5, 16.5))

# contour (marche +0,16 au raccord A/B sur le bord haut ; pan coupé SE jambe)
outline = [(0, W_B), (B_LEN, W_B), (B_LEN, W_A), (BAR, W_A), (BAR, 0),
           (LEG_W, 0), (LEG_W, LEG_BOT + CUT_H), (LEG_W - CUT_W, LEG_BOT),
           (0, LEG_BOT)]
ax.add_patch(Polygon(outline, closed=True, fill=False, lw=2.2, edgecolor=D.NOIR, zorder=10))
ax.plot([0, 0], [0, W_B], color=D.GRIS, lw=0.8, ls=":", zorder=9)      # axe jonction
ax.plot([LEG_W, B_LEN], [0, 0], lw=0)  # (bord bas barre déjà dans le polygone)
ax.plot([B_LEN, B_LEN], [0, W_B], color="#7c3aed", lw=0.9, ls="--", zorder=9)
ax.text(B_LEN, W_A + 0.55, "raccord B/A\n(Δ largeur +0,16)", fontsize=6, ha="center",
        color="#7c3aed", zorder=30)
ax.text(11.5, 12.4, "ZONE B", fontsize=13, fontweight="bold", color="#7c3aed", ha="center")
ax.text(35.5, 12.4, "ZONE A", fontsize=13, fontweight="bold", color="#7c3aed", ha="center")
ax.text(-2.6, -7.0, "ZONE C", fontsize=13, fontweight="bold", color="#7c3aed", rotation=90)

# ------------------------------------------------------------------ ZONE B
# rangée basse — chaîne fermée (3,39 · B4=1,31 · 6,47 · B5=1,33 · 6,55 · B6=1,30 · 3,23)
xb = chain(0, 3.39, 1.31, 6.47, 1.33, 6.55, 1.30, 3.23)
closure("B — chaîne basse", xb[-1], B_LEN, tol=0.05)
B4 = dict(x=xb[1], w=1.31, y=3.77, h=1.15)
B5 = dict(x=xb[3], w=1.33, y=3.84, h=1.14)
B6 = dict(x=xb[5], w=1.30, y=3.33, h=1.01)
for b, lab in ((B4, "1,31×1,15"), (B5, "1,33×1,14"), (B6, "1,30×1,01")):
    D.caisson(ax, b["x"], b["y"], b["w"], b["h"], label=lab, label_pos="below")
# cotes chaîne basse (sous la rangée, offset vers le bas)
yline = 2.45
D.dim(ax, (0, yline), (xb[1], yline), off=-0.0, text="3,39")
D.dim(ax, (xb[2], yline), (xb[3], yline), off=-0.0, text="6,47")
D.dim(ax, (xb[4], yline), (xb[5], yline), off=-0.0, text="6,55")
D.dim(ax, (xb[6], yline), (B_LEN, yline), off=-0.0, text="3,23")
# offsets bord bas -> caissons
D.dim(ax, (B4["x"] + 0.4, 0), (B4["x"] + 0.4, B4["y"]), off=-0.55, text="3,77")
D.dim(ax, (B5["x"] + 0.4, 0), (B5["x"] + 0.4, B5["y"]), off=-0.55, text="3,84")
D.dim(ax, (B6["x"] + 0.4, 0), (B6["x"] + 0.4, B6["y"]), off=-0.55, text="3,33")

# rangée haute B : B1 (1,11×1,11) à x≈3,16 ; 3,76 → B2 (1,11×1,30) ; 3,09 → bloc 2,77 ;
# 1,82 → b (0,18×0,63) ; 1,75 → B3 (1,43×1,44) ; 3,23 → bord est zone B
B3x2 = B_LEN - 3.23            # bord droit de B3
B3 = dict(x=B3x2 - 1.43, w=1.43, y=W_B - 3.30 - 1.44, h=1.44)
bpetit = dict(x=B3["x"] - 1.75 - 0.18, w=0.18, y=B3["y"] + 0.4, h=0.63)
bloc27_x2 = bpetit["x"] - 1.82
bloc27 = dict(x=bloc27_x2 - 2.77, w=2.77, y=W_B - 1.15, h=1.15)   # bloc en rive nord
B1 = dict(x=3.16, w=1.11, y=W_B - 3.74 - 1.11, h=1.11)
B2 = dict(x=3.16 + 1.11 + 3.76, w=1.11, y=W_B - 3.83 - 1.30, h=1.30)
D.caisson(ax, B1["x"], B1["y"], B1["w"], B1["h"], label="1,11×1,11")
D.caisson(ax, B2["x"], B2["y"], B2["w"], B2["h"], label="1,11×1,30")
D.caisson(ax, bpetit["x"], bpetit["y"], bpetit["w"], bpetit["h"], label="0,18×0,63",
          label_pos="below", uncertain=True)
D.caisson(ax, B3["x"], B3["y"], B3["w"], B3["h"], label="1,43×1,44")
D.bloc(ax, bloc27["x"], bloc27["y"], bloc27["w"], bloc27["h"], label="bloc 2,77")
# cotes rangée haute
D.dim(ax, (0, B1["y"] + B1["h"] / 2), (B1["x"], B1["y"] + B1["h"] / 2), off=0.0, text="3,16",
      color=D.ORANGE)
D.dim(ax, (B1["x"] + B1["w"], B1["y"] + 0.55), (B2["x"], B1["y"] + 0.55), off=0.0, text="3,76")
D.dim(ax, (B2["x"] + B2["w"], B2["y"] + 0.65), (bloc27["x"], B2["y"] + 0.65), off=0.0,
      text="3,09")
D.dim(ax, (bloc27_x2, bpetit["y"] + 0.3), (bpetit["x"], bpetit["y"] + 0.3), off=0.0,
      text="1,82")
D.dim(ax, (bpetit["x"] + 0.18, bpetit["y"] + 0.3), (B3["x"], bpetit["y"] + 0.3), off=0.0,
      text="1,75")
D.dim(ax, (B3x2, B3["y"] + 0.7), (B_LEN, B3["y"] + 0.7), off=0.0, text="3,23")
D.dim(ax, (B1["x"] + 0.5, B1["y"] + B1["h"]), (B1["x"] + 0.5, W_B), off=-0.55, text="3,74")
D.dim(ax, (B2["x"] + 0.5, B2["y"] + B2["h"]), (B2["x"] + 0.5, W_B), off=-0.55, text="3,83")
D.dim(ax, (B3["x"] + 0.7, B3["y"] + B3["h"]), (B3["x"] + 0.7, W_B), off=-0.55, text="3,3")
# bloc nord : cotes 6,11 (au bord est) + 0,95 (bloc -> petit caisson) + 3,3 haut droit
D.dim(ax, (B_LEN - 6.11, W_B + 0.75), (B_LEN, W_B + 0.75), off=0.0, text="6,11",
      color=D.ORANGE)
D.dim(ax, (bpetit["x"] + 0.09, bloc27["y"]), (bpetit["x"] + 0.09, bpetit["y"] + 0.63),
      off=0.5, text="0,95", color=D.ORANGE)
# liens verticaux inter-rangées : 1,35 (B1->B4) ; 1,15 (B2->B5) ; 1,31 (B3->B6)
D.dim(ax, (B1["x"] + 0.9, B4["y"] + B4["h"]), (B1["x"] + 0.9, B1["y"]), off=0.4, text="1,35",
      color=D.ORANGE)
D.dim(ax, (B2["x"] + 0.9, B5["y"] + B5["h"]), (B2["x"] + 0.9, B2["y"]), off=0.4, text="1,15",
      color=D.ORANGE)
D.dim(ax, (B3["x"] + 1.1, B6["y"] + B6["h"]), (B3["x"] + 1.1, B3["y"]), off=0.4, text="1,31",
      color=D.ORANGE)
# grandes verticales 6,08 / 5,97 (attache à confirmer)
D.dim(ax, (B2["x"] - 0.6, 0), (B2["x"] - 0.6, B2["y"] + B2["h"]), off=0.0, text="6,08",
      color=D.ORANGE)
D.dim(ax, (12.6, 0), (12.6, B2["y"] + 0.2), off=0.0, text="5,97", color=D.ORANGE)
# largeurs zone B
D.dim(ax, (0, 0), (0, W_B), off=1.3, text="10,76")
D.dim(ax, (B_LEN - 1.6, 0), (B_LEN - 1.6, W_B), off=-0.6, text="10,77", color=D.GRIS)

# ------------------------------------------------------------------ ZONE A
# chaîne haute compensée (+1,08 % : Σ 23,25 -> 23,50)
raw = chain(0, 1.26, 1.53, 0.64, 0.85, 5.22, 0.84, 0.47, 0.94, 5.04, 0.46, 2.55, 0.87, 2.58)
ok, res = closure("A — chaîne haute", raw[-1], A_LEN)
k = A_LEN / raw[-1]
xa = [AX0 + p * k for p in raw]
A1 = dict(x=xa[1], w=xa[2] - xa[1], y=W_A - 3.30 - 0.64, h=0.64)
A2 = dict(x=xa[3], w=xa[4] - xa[3], y=W_A - 3.84 - 0.55, h=0.55)
A3 = dict(x=xa[5], w=xa[6] - xa[5], y=W_A - 3.78 - 0.50, h=0.50)
A4 = dict(x=xa[7], w=xa[8] - xa[7], y=W_A - 3.88 - 0.47, h=0.47)
A5 = dict(x=xa[9], w=xa[10] - xa[9], y=W_A - 3.85 - 0.98, h=0.98)
A6 = dict(x=xa[11], w=xa[12] - xa[11], y=W_A - 3.84 - 0.54, h=0.54)
for b, lab, unc in ((A1, "1,53×0,64", True), (A2, "0,85×0,55", False),
                    (A3, "0,84×0,50", False), (A4, "0,94×0,47", False),
                    (A5, "0,46×0,98", True), (A6, "0,87×0,54", False)):
    D.caisson(ax, b["x"], b["y"], b["w"], b["h"], label=lab, uncertain=unc, label_pos="below")
# cotes chaîne haute (au-dessus de la rangée)
yl = 8.55
D.dim(ax, (AX0, yl), (xa[1], yl), off=0.0, text="1,26")
D.dim(ax, (xa[2], yl), (xa[3], yl), off=0.0, text="0,64", color=D.ORANGE)
D.dim(ax, (xa[4], yl), (xa[5], yl), off=0.0, text="5,22")
D.dim(ax, (xa[6], yl), (xa[7], yl), off=0.0, text="0,47")
D.dim(ax, (xa[8], yl), (xa[9], yl), off=0.0, text="5,04")
D.dim(ax, (xa[10], yl), (xa[11], yl), off=0.0, text="2,55")
D.dim(ax, (xa[12], yl), (AX0 + A_LEN, yl), off=0.0, text="2,58")
# offsets bord haut -> caissons zone A
for b, t in ((A1, "3,3"), (A2, "3,84"), (A3, "3,78"), (A4, "3,88"), (A5, "3,85"),
             (A6, "3,84")):
    D.dim(ax, (b["x"] + b["w"] / 2, b["y"] + b["h"]), (b["x"] + b["w"] / 2, W_A),
          off=-0.5, text=t)
# lien 2,39 A1->A2 (diagonal sur croquis, tracé comme mesuré)
D.dim(ax, (xa[2], A1["y"]), (xa[3], A2["y"] + 0.55), off=0.3, text="2,39", color=D.ORANGE)
# rangée basse zone A : A7 (0,70×0,99) ; 6,43 -> A8 (1,41×0,90) ; 6,37 (A8g->A9g) ;
# A9 (1,30×1,06) ; offsets bas 3,74 / 3,75 ; liens 1,75 / 1,37
A7 = dict(x=AX0 + 8.60, w=0.70, y=3.74, h=0.99)
A8 = dict(x=AX0 + 8.60 + 0.70 + 6.43, w=1.41, y=3.75, h=0.90)
A9 = dict(x=A8["x"] + 6.37, w=1.30, y=3.75, h=1.06)
D.caisson(ax, A7["x"], A7["y"], A7["w"], A7["h"], label="0,70×0,99", label_pos="below")
D.caisson(ax, A8["x"], A8["y"], A8["w"], A8["h"], label="1,41×0,90", label_pos="below")
D.caisson(ax, A9["x"], A9["y"], A9["w"], A9["h"], label="1,30×1,06", label_pos="below")
D.dim(ax, (A7["x"] + 0.7, A7["y"] + 0.45), (A8["x"], A7["y"] + 0.45), off=0.0, text="6,43")
D.dim(ax, (A8["x"], A8["y"] - 0.5), (A9["x"], A8["y"] - 0.5), off=0.0, text="6,37")
D.dim(ax, (A7["x"] + 0.35, 0), (A7["x"] + 0.35, A7["y"]), off=-0.5, text="3,74")
D.dim(ax, (A8["x"] + 0.7, 0), (A8["x"] + 0.7, A8["y"]), off=-0.5, text="3,75")
D.dim(ax, (A4["x"] + 0.45, A8["y"] + A8["h"]), (A4["x"] + 0.45, A4["y"]), off=0.45,
      text="1,75", color=D.ORANGE)
D.dim(ax, (A6["x"] + 0.4, A9["y"] + A9["h"]), (A6["x"] + 0.4, A6["y"]), off=0.45,
      text="1,37", color=D.ORANGE)
# décroché bord bas (0,92×0,74) + bloc accès 1,54 + cote 3,18 + 1,2 (attache à confirmer)
dec_x = AX0 + 7.70
ax.add_patch(Rectangle((dec_x, 0), 0.92, 0.74, fill=False, edgecolor=D.ORANGE, lw=1.2,
                       ls="--", zorder=14))
ax.text(dec_x + 0.46, 0.95, "décroché\n0,92×0,74", fontsize=5.5, ha="center",
        color=D.ORANGE, zorder=16)
D.bloc(ax, AX0 + 0.2, -1.35, 1.54, 1.1, label="1,54")
D.dim(ax, (AX0 + 1.74, -0.8), (dec_x, -0.8), off=0.0, text="3,18", color=D.ORANGE)
D.dim(ax, (AX0 + 0.2, -1.9), (AX0 + 1.74, -1.9), off=0.0, text="1,54", color=D.ORANGE)
# largeur + longueur totales zone A
D.dim(ax, (AX0 + 9.0, 0), (AX0 + 9.0, W_A), off=0.0, text="10,92")
D.dim(ax, (AX0, -2.9), (AX0 + A_LEN, -2.9), off=0.0, text="23,50 (mesuré)")
D.dim(ax, (0, -2.9), (B_LEN, -2.9), off=0.0, text="23,58 (chaîne fermée)")
D.dim(ax, (0, 14.2), (BAR, 14.2), off=0.0, text="47,08 (reconstitué)", color=D.GRIS)

# ------------------------------------------------------------------ ZONE C (jambe)
# colonne ouest : C1 = B1 (angle, commun aux 2 croquis) ; 6,67 -> C2 ; 6,54 -> C3
# t mesuré depuis le bord HAUT de la barre (y = W_B), vers le bas.
C2 = dict(x=3.38, w=1.35, top=W_B - 3.40 - 1.90 - 6.67, h=1.50)   # top = y du HAUT du caisson
C2["top"] = W_B - (3.40 + 1.90 + 6.67)          # = -1.21
C3top = C2["top"] - C2["h"] - 6.54              # = -9.25
C2r = dict(x=3.38, y=C2["top"] - 1.50, w=1.35, h=1.50)
C3r = dict(x=3.77, y=C3top - 1.15, w=1.35, h=1.15)
D.caisson(ax, C2r["x"], C2r["y"], C2r["w"], C2r["h"], label="1,35×1,50", uncertain=True,
          label_pos="right")
D.caisson(ax, C3r["x"], C3r["y"], C3r["w"], C3r["h"], label="1,35×1,15", uncertain=True,
          label_pos="right")
# colonne est : C4 (1,07×1,32) ; C5 (1,10×0,42) — offsets bord est 3,72/4,04 (lecture C)
C4 = dict(x=LEG_W - 3.72 - 1.07, y=-2.3, w=1.07, h=1.32)
C5 = dict(x=LEG_W - 4.04 - 1.10, y=-10.1, w=1.10, h=0.42)
D.caisson(ax, C4["x"], C4["y"], C4["w"], C4["h"], label="1,07×1,32", uncertain=True,
          label_pos="below")
D.caisson(ax, C5["x"], C5["y"], C5["w"], C5["h"], label="1,10×0,42", uncertain=True,
          label_pos="below")
# cotes jambe
D.dim(ax, (C2r["x"] + 0.6, C2r["y"] + C2r["h"]), (B1["x"] + 0.6, B1["y"]), off=0.6,
      text="6,67", color=D.ORANGE)
D.dim(ax, (C3r["x"] + 0.6, C3r["y"] + C3r["h"]), (C2r["x"] + 0.6, C2r["y"]), off=0.6,
      text="6,54", color=D.ORANGE)
D.dim(ax, (0, C2r["y"] + 0.7), (C2r["x"], C2r["y"] + 0.7), off=0.0, text="3,38")
D.dim(ax, (0, C3r["y"] + 0.55), (C3r["x"], C3r["y"] + 0.55), off=0.0, text="3,77",
      color=D.ORANGE)
D.dim(ax, (C4["x"] + C4["w"], C4["y"] + 0.65), (LEG_W, C4["y"] + 0.65), off=0.0,
      text="3,72", color=D.ORANGE)
D.dim(ax, (C5["x"] + C5["w"], C5["y"] + 0.2), (LEG_W, C5["y"] + 0.2), off=0.0,
      text="4,04", color=D.ORANGE)
D.dim(ax, (0, LEG_BOT), (0, W_B), off=1.3, text="24,91 (chaîne ouest)", color=D.ORANGE)
D.dim(ax, (LEG_W - CUT_W, LEG_BOT - 0.75), (LEG_W, LEG_BOT - 0.75), off=0.0, text="2,18",
      color=D.ORANGE)
D.dim(ax, (LEG_W + 0.6, LEG_BOT), (LEG_W + 0.6, LEG_BOT + CUT_H), off=0.0, text="4,04",
      color=D.ORANGE)
D.dim(ax, (0, LEG_BOT - 1.6), (LEG_W, LEG_BOT - 1.6), off=0.0, text="10,76 (supposé = B)",
      color=D.GRIS)
# cotes C non rattachées (tracées en marge pour mémoire)
ax.text(-6.2, -16.6,
        "Cotes croquis C en attente de rattachement sûr :\n"
        "4,1 · 5,5 · 6,34 · 6,73 · 6,84 · 7,37 · 4,82 · 1,93 · 1,45 · 1,43 · 1,4 ·\n"
        "3,72 (×2) · 3,78 (×2) · 3,38 · 6,31 · 0,63×0,8 · petites cotes 0,21/0,42",
        fontsize=6.2, color=D.ORANGE, va="top", zorder=30)

# ------------------------------------------------------------------ habillage
D.legende(ax, 40.5, -6.2, [
    ("caisson", "caisson béton relevé (chaîné)"),
    ("caissonU", "caisson — lecture/position à confirmer"),
    ("bloc", "bloc/édicule en rive"),
    ("dim", "cote mesurée (croquis Reda)"),
    ("dimU", "cote mesurée — rattachement supposé"),
])
D.scale_bar(ax, 40.5, -11.5)
D.cartouche(fig, [
    ("ACCORDIA TECH — Consultation FRDISI PV + stockage, Mohammedia", True),
    ("Bât. A — Résidence UIB, aile en L — RELEVÉ TERRAIN RECONSTITUÉ", True),
    ("Relevé : R. Kasri, 27/07/2026 — restitution TAQINOR (document de travail)", False),
    ("Échelle 1:200 (A3) — cotes en mètres — NE REMPLACE PAS les planches 05E/05G", False),
])
fig.savefig("PLAN_RELEVE_AILE_L.pdf", bbox_inches="tight")
fig.savefig("PLAN_RELEVE_AILE_L.png", dpi=170, bbox_inches="tight")
print("PLAN AILE L : render ok")
