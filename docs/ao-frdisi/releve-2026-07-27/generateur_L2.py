# -*- coding: utf-8 -*-
"""Plan reconstitué v2 — Bât. A (L) : géométrie ANCRÉE sur les plans reçus
(mémoire §2.1 : aile 1 ≈ 48 × 11 m ; aile 2 ≈ 40,5 × 11,2 m) + cotes RELEVÉES 27/07.

Double cotation : GRIS = plan/conception · BLEU = relevé Reda · ORANGE = à confirmer.
Repère : origine = angle intérieur du L (jonction), x vers l'est (aile 1),
y négatif vers le sud (aile 2).
"""
import sys
sys.path.insert(0, ".")
import dessin as D
from solveur import chain, closure
from matplotlib.patches import Polygon

BAR_PLAN, LEG_PLAN = 48.0, 40.5
B_LEN, A_LEN = 23.58, 23.50
BAR = B_LEN + A_LEN                  # 47,08 relevé
W_B, W_A = 10.76, 10.92
LEG_W, LEG = 11.2, 40.5              # aile 2 : plan (chaînes relevées ≈ 38-40)
CUT_W, CUT_H = 2.18, 4.04
AX0 = B_LEN
LEG_BOT = W_B - LEG                  # -29,74

fig, ax = D.new_sheet(
    "RELEVÉ CONTRADICTOIRE TOITURE — BÂTIMENT A (AILE EN L) — RÉSIDENCE UNIVERSITAIRE UIB",
    "Géométrie d'ensemble : plans reçus (mémoire §2.1 — aile 1 ≈ 48×11 m, aile 2 ≈ 40,5×11,2 m) · "
    "cotes RELEVÉES le 27/07/2026 (croquis A/B/C) — GRIS = plan · BLEU = mesuré · ORANGE = à confirmer",
    (-8.5, 56.5), (-36.5, 17.0))

outline = [(0, W_B), (B_LEN, W_B), (B_LEN, W_A), (BAR, W_A), (BAR, 0),
           (LEG_W, 0), (LEG_W, LEG_BOT + CUT_H), (LEG_W - CUT_W, LEG_BOT), (0, LEG_BOT)]
ax.add_patch(Polygon(outline, closed=True, fill=False, lw=2.2, edgecolor=D.NOIR, zorder=10))
ax.plot([B_LEN, B_LEN], [0, W_B], color="#7c3aed", lw=0.9, ls="--", zorder=9)
ax.text(11.5, 13.1, "ZONE B (croquis B)", fontsize=10, fontweight="bold", color="#7c3aed",
        ha="center")
ax.text(35.5, 13.1, "ZONE A (croquis A)", fontsize=10, fontweight="bold", color="#7c3aed",
        ha="center")
ax.text(-4.6, -13.0, "AILE 2 (croquis C)", fontsize=10, fontweight="bold", color="#7c3aed",
        rotation=90)
ax.text(B_LEN, W_A + 0.5, "raccord B/A (Δl +0,16)", fontsize=5.8, ha="center",
        color="#7c3aed")

D.dim(ax, (0, 15.2), (BAR, 15.2), off=0.0, text="47,08 relevé — 48,0 au plan", color=D.GRIS)
D.dim(ax, (0, -32.3), (LEG_W, -32.3), off=0.0, text="11,2 (plan)", color=D.GRIS)
D.dim(ax, (-3.1, LEG_BOT), (-3.1, W_B), off=0.0, text="40,5 (plan) — chaînes relevées ≈ 38-40",
      color=D.GRIS)

# =================================================================== ZONE B
xb = chain(0, 3.39, 1.31, 6.47, 1.33, 6.55, 1.30, 3.23)
closure("B — chaîne basse", xb[-1], B_LEN, tol=0.05)
B4 = dict(x=xb[1], w=1.31, y=3.77, h=1.15)
B5 = dict(x=xb[3], w=1.33, y=3.84, h=1.14)
B6 = dict(x=xb[5], w=1.30, y=3.33, h=1.01)
for b, lab in ((B4, "1,31×1,15"), (B5, "1,33×1,14"), (B6, "1,30×1,01")):
    D.caisson(ax, b["x"], b["y"], b["w"], b["h"], label=lab, label_pos="below")
yline = 2.45
D.dim(ax, (0, yline), (xb[1], yline), off=0.0, text="3,39")
D.dim(ax, (xb[2], yline), (xb[3], yline), off=0.0, text="6,47")
D.dim(ax, (xb[4], yline), (xb[5], yline), off=0.0, text="6,55")
D.dim(ax, (xb[6], yline), (B_LEN, yline), off=0.0, text="3,23")
D.dim(ax, (B4["x"] + 0.4, 0), (B4["x"] + 0.4, B4["y"]), off=-0.55, text="3,77")
D.dim(ax, (B5["x"] + 0.4, 0), (B5["x"] + 0.4, B5["y"]), off=-0.55, text="3,84")
D.dim(ax, (B6["x"] + 0.4, 0), (B6["x"] + 0.4, B6["y"]), off=-0.55, text="3,33")
B3x2 = B_LEN - 3.23
B3 = dict(x=B3x2 - 1.43, w=1.43, y=W_B - 3.30 - 1.44, h=1.44)
bpetit = dict(x=B3["x"] - 1.75 - 0.18, w=0.18, y=B3["y"] + 0.4, h=0.63)
bloc27_x2 = bpetit["x"] - 1.82
bloc27 = dict(x=bloc27_x2 - 2.77, w=2.77, y=W_B - 1.15, h=1.15)
B1 = dict(x=3.16, w=1.11, y=W_B - 3.74 - 1.11, h=1.11)
B2 = dict(x=3.16 + 1.11 + 3.76, w=1.11, y=W_B - 3.83 - 1.30, h=1.30)
D.caisson(ax, B1["x"], B1["y"], B1["w"], B1["h"], label="1,11×1,11")
D.caisson(ax, B2["x"], B2["y"], B2["w"], B2["h"], label="1,11×1,30")
D.caisson(ax, bpetit["x"], bpetit["y"], bpetit["w"], bpetit["h"], label="0,18×0,63",
          label_pos="below", uncertain=True)
D.caisson(ax, B3["x"], B3["y"], B3["w"], B3["h"], label="1,43×1,44")
D.bloc(ax, bloc27["x"], bloc27["y"], bloc27["w"], bloc27["h"], label="bloc 2,77")
D.dim(ax, (0, B1["y"] + 0.55), (B1["x"], B1["y"] + 0.55), off=0.0, text="3,16",
      color=D.ORANGE)
D.dim(ax, (B1["x"] + B1["w"], B1["y"] + 0.55), (B2["x"], B1["y"] + 0.55), off=0.0,
      text="3,76")
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
D.dim(ax, (B_LEN - 6.11, W_B + 0.75), (B_LEN, W_B + 0.75), off=0.0, text="6,11",
      color=D.ORANGE)
D.dim(ax, (B1["x"] + 0.9, B4["y"] + B4["h"]), (B1["x"] + 0.9, B1["y"]), off=0.4,
      text="1,35", color=D.ORANGE)
D.dim(ax, (B3["x"] + 1.1, B6["y"] + B6["h"]), (B3["x"] + 1.1, B3["y"]), off=0.4,
      text="1,31", color=D.ORANGE)
D.dim(ax, (0, 0), (0, W_B), off=1.3, text="10,76 relevé (plan 11,0)")
D.dim(ax, (B_LEN - 1.2, 0), (B_LEN - 1.2, W_B), off=-0.55, text="10,77 (est)",
      color=D.GRIS)

# =================================================================== ZONE A
raw = chain(0, 1.26, 1.53, 0.64, 0.85, 5.22, 0.84, 0.47, 0.94, 5.04, 0.46, 2.55, 0.87, 2.58)
closure("A — chaîne haute", raw[-1], A_LEN)
k = A_LEN / raw[-1]
xa = [AX0 + p * k for p in raw]
A1 = dict(x=xa[1], w=xa[2] - xa[1], y=W_A - 3.30 - 0.64, h=0.64)
A2 = dict(x=xa[3], w=xa[4] - xa[3], y=W_A - 3.84 - 0.55, h=0.55)
A3 = dict(x=xa[5], w=xa[6] - xa[5], y=W_A - 3.78 - 0.50, h=0.50)
A4 = dict(x=xa[7], w=xa[8] - xa[7], y=W_A - 3.88 - 0.47, h=0.47)
A5 = dict(x=xa[9], w=xa[10] - xa[9], y=W_A - 3.85 - 0.98, h=0.98)
A6 = dict(x=xa[11], w=xa[12] - xa[11], y=W_A - 3.84 - 0.54, h=0.54)
for b, lab, unc in ((A1, "1,53×0,64", True), (A2, "0,85×0,55", False),
                    (A3, "0,84×0,50", False), (A4, "0,94×0,47?", True),
                    (A5, "0,46×0,98", True), (A6, "0,87×0,54", False)):
    D.caisson(ax, b["x"], b["y"], b["w"], b["h"], label=lab, uncertain=unc,
              label_pos="below")
yl = 9.1
D.dim(ax, (AX0, yl), (xa[1], yl), off=0.0, text="1,26")
D.dim(ax, (xa[2], A1["y"] - 0.35), (xa[3], A1["y"] - 0.35), off=0.0, text="2,39",
      color=D.ORANGE)
D.dim(ax, (xa[4], yl), (xa[5], yl), off=0.0, text="5,22")
D.dim(ax, (xa[6], yl - 0.9), (xa[7], yl - 0.9), off=0.0, text="0,47 ou 1,53 ?",
      color=D.ORANGE)
D.dim(ax, (xa[8], yl), (xa[9], yl), off=0.0, text="5,04")
D.dim(ax, (xa[10], yl), (xa[11], yl), off=0.0, text="2,55")
D.dim(ax, (xa[12], yl), (AX0 + A_LEN, yl), off=0.0, text="2,58")
for b, t in ((A1, "3,3"), (A3, "3,78"), (A4, "3,88"), (A6, "3,84")):
    D.dim(ax, (b["x"] + b["w"] / 2, b["y"] + b["h"]), (b["x"] + b["w"] / 2, W_A),
          off=-0.5, text=t)
A7 = dict(x=AX0 + 8.60, w=0.70, y=3.74, h=0.99)
A8 = dict(x=AX0 + 8.60 + 0.70 + 6.43, w=1.41, y=3.75, h=0.90)
A9 = dict(x=A8["x"] + 6.37, w=1.30, y=3.75, h=1.06)
D.caisson(ax, A7["x"], A7["y"], A7["w"], A7["h"], label="0,70×0,99", label_pos="below")
D.caisson(ax, A8["x"], A8["y"], A8["w"], A8["h"], label="1,41×0,90", label_pos="below")
D.caisson(ax, A9["x"], A9["y"], A9["w"], A9["h"], label="1,30×1,06", label_pos="below")
D.dim(ax, (A7["x"] + 0.7, A7["y"] + 0.45), (A8["x"], A7["y"] + 0.45), off=0.0, text="6,43")
D.dim(ax, (A8["x"], A8["y"] - 0.55), (A9["x"], A8["y"] - 0.55), off=0.0, text="6,37")
D.dim(ax, (A7["x"] + 0.35, 0), (A7["x"] + 0.35, A7["y"]), off=-0.5, text="3,74")
D.dim(ax, (A8["x"] + 0.7, 0), (A8["x"] + 0.7, A8["y"]), off=-0.5, text="3,75")
D.dim(ax, (AX0 + 9.0, 0), (AX0 + 9.0, W_A), off=0.0, text="10,92 relevé (plan 11,0)")
D.dim(ax, (AX0, -2.9), (AX0 + A_LEN, -2.9), off=0.0, text="23,50 (mesuré — relire : 23,6 ?)")
D.dim(ax, (0, -2.9), (B_LEN, -2.9), off=0.0, text="23,58 (chaîne fermée)")

# =================================================================== AILE 2 (croquis C)
# Colonne OUEST — chaîne : 3,38·[1,35]·6,54·[1,35]·6,84·[1,07]·7,37·[1,10]·4,82
tW = chain(0, 3.38, 1.35, 6.54, 1.35, 6.84, 1.07, 7.37, 1.10, 4.82)
closure("AILE 2 — chaîne ouest", tW[-1], LEG, tol=7.0)
XW = 3.5
cw = [(tW[1], 1.35), (tW[3], 1.35), (tW[5], 1.07), (tW[7], 1.10)]
labs = ["1,35×1,15", "1,35×1,15", "1,07×1,21?", "1,10×0,42"]
for (t0, hh), lab in zip(cw, labs):
    D.caisson(ax, XW, W_B - t0 - hh, 1.3, hh, label=lab, uncertain=True, label_pos="right")
D.dim(ax, (XW + 0.6, W_B - tW[1]), (XW + 0.6, W_B - 0.05), off=0.6, text="3,38")
D.dim(ax, (XW + 0.6, W_B - tW[3]), (XW + 0.6, W_B - tW[2]), off=0.6, text="6,54")
D.dim(ax, (XW + 0.6, W_B - tW[5]), (XW + 0.6, W_B - tW[4]), off=0.6, text="6,84")
D.dim(ax, (XW + 0.6, W_B - tW[7]), (XW + 0.6, W_B - tW[6]), off=0.6, text="7,37")
D.dim(ax, (XW + 0.6, W_B - tW[9]), (XW + 0.6, W_B - tW[8]), off=0.6, text="4,82")
D.dim(ax, (0, W_B - tW[1] + 0.6), (XW, W_B - tW[1] + 0.6), off=0.0, text="3,38")
D.dim(ax, (0, W_B - tW[3] + 0.6), (XW, W_B - tW[3] + 0.6), off=0.0, text="3,77",
      color=D.ORANGE)
# Colonne EST — chaîne : 3,72·[1,15]·6,67·[1,35]·6,73·[0,63]·4,31·[1,45]·5,5
tE = chain(0, 3.72, 1.15, 6.67, 1.35, 6.73, 0.63, 4.31, 1.45, 5.50)
closure("AILE 2 — chaîne est", tE[-1], LEG, tol=10.0)
XE = LEG_W - 3.7 - 1.3
ce = [(tE[1], 1.15), (tE[3], 1.35), (tE[5], 0.63), (tE[7], 1.45)]
labsE = ["1,15×1,35", "1,15×1,35 (lié 1,4)", "0,8×0,63", "1,45×? (non résolu)"]
for (t0, hh), lab in zip(ce, labsE):
    D.caisson(ax, XE, W_B - t0 - hh, 1.3, hh, label=lab, uncertain=True, label_pos="left")
D.dim(ax, (XE + 0.6, W_B - tE[1]), (XE + 0.6, W_B - 0.05), off=-0.6, text="3,72",
      color=D.ORANGE)
D.dim(ax, (XE + 0.6, W_B - tE[3]), (XE + 0.6, W_B - tE[2]), off=-0.6, text="6,67")
D.dim(ax, (XE + 0.6, W_B - tE[5]), (XE + 0.6, W_B - tE[4]), off=-0.6, text="6,73")
D.dim(ax, (XE + 0.6, W_B - tE[7]), (XE + 0.6, W_B - tE[6]), off=-0.6, text="4,31",
      color=D.ORANGE)
D.dim(ax, (LEG_W, W_B - tE[1] + 0.55), (XE + 1.3, W_B - tE[1] + 0.55), off=0.0,
      text="3,72", color=D.ORANGE)
D.dim(ax, (LEG_W, W_B - tE[7] + 0.6), (XE + 1.3, W_B - tE[7] + 0.6), off=0.0,
      text="4,04", color=D.ORANGE)
D.dim(ax, (LEG_W - CUT_W, LEG_BOT - 0.8), (LEG_W, LEG_BOT - 0.8), off=0.0, text="2,18",
      color=D.ORANGE)
D.dim(ax, (LEG_W + 0.7, LEG_BOT), (LEG_W + 0.7, LEG_BOT + CUT_H), off=0.0, text="4,04",
      color=D.ORANGE)
ax.text(14.0, -21.0,
        "Cotes croquis C encore à rattacher (v3 après contre-lecture) :\n"
        "4,1 · 5,5 · 6,34 · 6,31 · 1,93 · 1,43 · 1,4 · 3,78 (×2) · 3,38 (bas) ·\n"
        "1,45 · 6,87 · 3,63 · 4,37 · petites cotes 0,21/0,42",
        fontsize=6.2, color=D.ORANGE, va="top")

D.legende(ax, 33.5, -9.5, [
    ("caisson", "caisson béton relevé (chaîné)"),
    ("caissonU", "caisson — lecture/position à confirmer"),
    ("bloc", "bloc/édicule en rive"),
    ("dim", "cote mesurée (croquis Reda)"),
    ("dimU", "cote mesurée — rattachement supposé"),
])
D.scale_bar(ax, 33.5, -15.5)
D.cartouche(fig, [
    ("ACCORDIA TECH — Consultation FRDISI PV + stockage, Mohammedia", True),
    ("Bât. A — aile en L (48×11 + 40,5×11,2 au plan) — RELEVÉ RECONSTITUÉ v2", True),
    ("Relevé : R. Kasri, 27/07/2026 — restitution TAQINOR (document de travail)", False),
    ("Échelle ~1:250 (A3) — cotes en m — NE REMPLACE PAS les planches 05E/05G", False),
])
fig.savefig("PLAN_RELEVE_AILE_L.pdf", bbox_inches="tight")
fig.savefig("PLAN_RELEVE_AILE_L.png", dpi=170, bbox_inches="tight")
print("PLAN AILE L v2 : render ok")
