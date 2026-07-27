# -*- coding: utf-8 -*-
"""Plan reconstitué — Aile en ARC (Bât. B) — VUE DÉVELOPPÉE (bande rectifiée).

s = abscisse curviligne le long du bord extérieur depuis le mur/pignon (croquis 1).
Courbure réelle déduite : R_ext ≈ 274 m (flèche ≈ 1 m sur ~47 m) — négligeable pour
la restitution des cotes ; la bande est dessinée développée (droite), note au cartouche.

Sources : croquis 1 (départ mur), croquis 3 (segment médian, grand bloc), croquis 2
(vue d'ensemble, contre-vérification). Largeur mesurée 10,70–10,91 (10,87 confirmé Reda).
"""
import sys
sys.path.insert(0, ".")
import dessin as D
from solveur import chain, closure
from matplotlib.patches import Rectangle

W = 10.85          # largeur moyenne dessinée (mesures 10,70..10,91 cotées localement)
LEN = 47.0         # développé estimé (croquis 1: ~24 m + croquis 3: ~23 m)

fig, ax = D.new_sheet(
    "RELEVÉ CONTRADICTOIRE TOITURE — BÂTIMENT B (AILE EN ARC) — RÉSIDENCE UNIVERSITAIRE UIB",
    "Toiture courbe ≈ 90 × 11,2 m AU PLAN (mémoire §2.2) — vue DÉVELOPPÉE de la PARTIE RELEVÉE (~47 m depuis le pignon, R_ext ≈ 274 m déduit) — "
    "relevé terrain du 27/07/2026 — cotes en mètres · bleu = mesuré · orange = à confirmer · gris = déduit",
    (-5.5, 53.5), (-8.5, 17.5))

# contour bande développée + mur pignon à s=0, coupure à droite
ax.add_patch(Rectangle((0, 0), LEN, W, fill=False, lw=2.2, edgecolor=D.NOIR, zorder=10))
ax.add_patch(Rectangle((-0.45, -0.2), 0.45, W + 0.4, facecolor="none", edgecolor=D.NOIR,
                       hatch="//////", lw=1.4, zorder=10))
ax.text(-1.1, W + 0.9, "MUR / PIGNON (s = 0)", fontsize=7.5, fontweight="bold")
for i in range(6):
    ax.plot([LEN + (0 if i % 2 else 0.35), LEN + (0.35 if i % 2 else 0)],
            [W * i / 5, W * (i + 1) / 5], color=D.NOIR, lw=1.4, zorder=10)
ax.text(LEN + 0.6, W/2, "suite de la bande\n(développé total ≈ 90 m au plan ;\nsolde couvert par le croquis\nd'ensemble, à recaler)", fontsize=6.5, color=D.GRIS, va="center")

# décroché en tête près du mur (0,43 — croquis 1)
ax.add_patch(Rectangle((2.3, W), 1.65, 0.43, fill=False, edgecolor=D.ORANGE, ls="--",
                       lw=1.1, zorder=12))
D.dim(ax, (4.35, W), (4.35, W + 0.43), off=0.75, text="0,43 ou 0,9 ?", color=D.ORANGE)
D.dim(ax, (0, W + 1.7), (5.10, W + 1.7), off=0.0, text="5,10 ? (retour pignon — contre-lecture)", color=D.ORANGE)

# ---------------------------------------------------------------- croquis 1 (s 0-24)
# transects bord extérieur : 3,72 / 3,84 / 3,82 puis 6,59 / 6,4
sx = chain(0, 3.72, 3.84, 3.82, 6.59, 6.40)
closure("ARC — transects croquis 1", sx[-1], 24.37, tol=0.5)
for x in sx[1:]:
    ax.plot([x, x], [0, W], color="#475569", lw=0.8, ls=(0, (4, 3)), zorder=8)
yt = W - 0.85
D.dim(ax, (sx[0], yt), (sx[1], yt), off=0.0, text="3,72")
D.dim(ax, (sx[1], yt), (sx[2], yt), off=0.0, text="3,84")
D.dim(ax, (sx[2], yt), (sx[3], yt), off=0.0, text="3,82")
D.dim(ax, (sx[3], yt), (sx[4], yt), off=0.0, text="6,59")
D.dim(ax, (sx[4], yt), (sx[5], yt), off=0.0, text="6,4")
# entraxes bord intérieur : 3,42? / 3,78 / 3,73 (chaîne intérieure plus courte -> courbure)
yb = 0.85
D.dim(ax, (0, yb), (3.42, yb), off=0.0, text="3,42")
D.dim(ax, (3.42, yb), (7.20, yb), off=0.0, text="3,78")
D.dim(ax, (7.20, yb), (10.93, yb), off=0.0, text="3,73")
# largeurs croquis 1 : 10,81 (mur) ; 10,87 (s~7,6 CONFIRMÉ) ; 10,9 (s~15)
D.dim(ax, (0.65, 0), (0.65, W), off=0.0, text="10,81")
D.dim(ax, (sx[2] + 0.5, 0), (sx[2] + 0.5, W), off=0.0, text="10,87 (confirmé)")
D.dim(ax, (15.1, 0), (15.1, W), off=0.0, text="10,9")
# caissons croquis 1 : C1 (1,03×0,9, 1,34 avant T1) ; C2 (1,55?×0,96, 1,39 après T3) ;
# C3 (1,36?×0,95 vers s=16,6)
C1 = dict(x=3.72 - 1.34 - 1.03, y=5.1, w=1.03, h=0.90)
C2 = dict(x=sx[3] + 1.39, y=4.8, w=1.55, h=0.96)
C3 = dict(x=16.6, y=4.2, w=1.36, h=0.95)
D.caisson(ax, C1["x"], C1["y"], C1["w"], C1["h"], label="1,03×0,90", label_pos="below")
D.caisson(ax, C2["x"], C2["y"], C2["w"], C2["h"], label="1,55×0,96", uncertain=True,
          label_pos="below")
D.caisson(ax, C3["x"], C3["y"], C3["w"], C3["h"], label="1,36×0,95", uncertain=True,
          label_pos="below")
D.dim(ax, (C1["x"] + C1["w"], C1["y"] + 0.45), (3.72, C1["y"] + 0.45), off=0.0, text="1,34")
D.dim(ax, (sx[3], C2["y"] + 0.5), (C2["x"], C2["y"] + 0.5), off=0.0, text="1,39")
# cotes basses croquis 1 : 4,75 (bord int. après T3) ; 5,5 diag ; 0,78 (extrémité)
D.dim(ax, (sx[3], 1.9), (sx[3] + 4.75, 1.9), off=0.0, text="4,75", color=D.ORANGE)
D.dim(ax, (sx[4], 2.6), (sx[4] + 5.5, 3.4), off=0.0, text="5,5", color=D.ORANGE)
D.dim(ax, (23.6, 0), (23.6, 0.78), off=-0.6, text="0,78", color=D.ORANGE)

# ---------------------------------------------------------------- croquis 3 (s 24-47)
S3 = 24.4          # raccord estimé croquis 1 -> croquis 3 (à confirmer)
ax.plot([S3, S3], [-0.6, W + 0.6], color="#7c3aed", lw=0.9, ls="--", zorder=9)
ax.text(S3, W + 1.5, "raccord croquis 1↔3 (position estimée)", fontsize=6, ha="center",
        color="#7c3aed")
# grand bloc (édicule) : angle repère + 4,98 / 5,93
D.bloc(ax, S3, W - 5.93, 4.98, 5.93, label="grand bloc\n4,98 × 5,93")
D.dim(ax, (S3, W + 0.6), (S3 + 4.98, W + 0.6), off=0.0, text="4,98")
D.dim(ax, (S3 - 0.55, W - 5.93), (S3 - 0.55, W), off=0.0, text="5,93")
# K1 (3,77 du bord ext.) ; K2 à 3,6 de K1 (1,6 sous) ; K3 (3,2) ; K4 (6,78? de K3, 3,68? du bord int.)
K1 = dict(x=S3 + 6.6, y=W - 3.77 - 0.9, w=1.0, h=0.9)
K2 = dict(x=K1["x"] + 1.0 + 3.6, y=W - 3.4 - 0.8, w=1.2, h=0.8)
K3 = dict(x=K2["x"], y=3.5, w=1.25, h=0.8)
K4 = dict(x=K3["x"] + 1.25 + 6.78, y=3.68, w=1.45, h=0.9)
D.caisson(ax, K1["x"], K1["y"], K1["w"], K1["h"], label="≈1,0×0,9", label_pos="below")
D.caisson(ax, K2["x"], K2["y"], K2["w"], K2["h"], label="≈1,2×0,8", label_pos="below")
D.caisson(ax, K3["x"], K3["y"], K3["w"], K3["h"], label="≈1,25×0,8", label_pos="below",
          uncertain=True)
D.caisson(ax, K4["x"], K4["y"], K4["w"], K4["h"], label="≈1,45×0,9", label_pos="below",
          uncertain=True)
D.dim(ax, (K1["x"] + 0.5, K1["y"] + K1["h"]), (K1["x"] + 0.5, W), off=-0.55, text="3,77")
D.dim(ax, (K1["x"] + 1.0, K1["y"] + 0.45), (K2["x"], K1["y"] + 0.45), off=0.0, text="3,6")
D.dim(ax, (K2["x"] + 0.6, K3["y"] + 0.8), (K2["x"] + 0.6, K2["y"]), off=0.45, text="1,6")
D.dim(ax, (K3["x"] + 1.25, K3["y"] + 0.4), (K4["x"], K3["y"] + 0.4), off=0.0, text="6,78 ? (relire : 9,78/8,76 possibles)",
      color=D.ORANGE)
D.dim(ax, (K4["x"] + 0.7, 0), (K4["x"] + 0.7, K4["y"]), off=-0.55, text="3,68 ?",
      color=D.ORANGE)
# K5 -> K6 : 6,86 ; K6 : 3,78 du bord ext ; K7 : 1,5 sous K6, 0,86 de large, 3,86 au bord int
K6 = dict(x=LEN - 2.6, y=W - 3.78 - 0.9, w=1.5, h=0.9)
K5 = dict(x=K6["x"] - 6.86 - 1.8, y=W - 2.0 - 1.0, w=1.8, h=1.0)
K7 = dict(x=K6["x"] + 0.1, y=K6["y"] - 1.5 - 0.86, w=1.5, h=0.86)
D.caisson(ax, K5["x"], K5["y"], K5["w"], K5["h"], label="≈1,8×1,0", label_pos="left")
D.caisson(ax, K6["x"], K6["y"], K6["w"], K6["h"], label="≈1,5×0,9", label_pos="left")
D.caisson(ax, K7["x"], K7["y"], K7["w"], K7["h"], label="1,5×0,86", label_pos="below",
          uncertain=True)
D.dim(ax, (K5["x"] + 1.8, K5["y"] + 0.5), (K6["x"], K6["y"] + 0.5), off=0.0, text="6,86")
D.dim(ax, (K6["x"] + 0.75, K6["y"] + K6["h"]), (K6["x"] + 0.75, W), off=-0.55, text="3,78")
D.dim(ax, (K6["x"] + 0.75, K7["y"] + 0.86), (K6["x"] + 0.75, K6["y"]), off=0.55, text="1,5")
D.dim(ax, (K7["x"] + 0.75, 0), (K7["x"] + 0.75, K7["y"]), off=-0.55, text="3,86")
# largeur croquis 3 : 10,9 au droit du bloc
D.dim(ax, (S3 + 6.0, 0), (S3 + 6.0, W), off=0.0, text="10,9")
D.dim(ax, (LEN - 1.2, 0), (LEN - 1.2, W), off=0.0, text="10,91")

# contrôle transversal K6/K7 (fermeture)
ax.text(28.5, -2.6,
        "CONTRÔLE DE FERMETURE transversal (zone K6/K7) : 3,78 + 0,90 + 1,50 + 0,86 + 3,86 "
        "= 10,90 ≡ largeur mesurée 10,90/10,91 ✓ (<5 cm)\n"
        "COURBURE : entraxes ext. 11,38 vs int. 10,93 sur largeur 10,81 → R_ext ≈ 274 m "
        "(ouverture ≈ 9,8° sur 47 m, flèche ≈ 1,0 m) — rails posables en tronçons droits par trame.\n"
        "Cotes croquis 2 (vue d'ensemble) recoupées : 10,7 · 10,91 · 3,83 · 3,74 · 3,85 · 3,67 · "
        "3,33 · 6,59 · caissons A–H ↔ C/K (résidu max 27 cm sur 6,59/6,86).",
        fontsize=6.6, va="top", color="#333333")

D.legende(ax, 1.0, -3.4, [
    ("caisson", "caisson béton relevé (chaîné)"),
    ("caissonU", "caisson — lecture/position à confirmer"),
    ("bloc", "grand bloc / édicule"),
    ("dim", "cote mesurée (croquis Reda)"),
    ("dimU", "cote mesurée — rattachement supposé"),
])
D.scale_bar(ax, 14.5, -5.4)
D.cartouche(fig, [
    ("ACCORDIA TECH — Consultation FRDISI PV + stockage, Mohammedia", True),
    ("Bât. B — aile en ARC (≈90 × 11,2 au plan) — PARTIE RELEVÉE ~47 m — v2", True),
    ("Relevé : R. Kasri, 27/07/2026 — restitution TAQINOR (document de travail)", False),
    ("Échelle 1:200 (A3) — cotes en m — largeur 10,70–10,91 — NE REMPLACE PAS 05E/06G", False),
])
fig.savefig("PLAN_RELEVE_AILE_ARC.pdf", bbox_inches="tight")
fig.savefig("PLAN_RELEVE_AILE_ARC.png", dpi=170, bbox_inches="tight")
print("PLAN ARC : render ok")
