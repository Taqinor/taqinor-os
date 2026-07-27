# -*- coding: utf-8 -*-
"""Plan reconstitué — ÉCOLE SUPTECH (Bât. C) — croquis unique du 27/07/2026 (stylo bleu).

Chaînages qui se ferment :
  horizontal : 13,18 + bloc(5,02 déduit) + 7,42 = 25,62 ✓ (exact)
  vertical   : 19,36 + 2,32 + 4,50 + 10,50 = 36,68 (profondeur totale déduite)
Lecture image seule (le fichier n'est pas arrivé dans la session) : cotes basses
et cluster sud-est à confirmer par Reda.
"""
import sys
sys.path.insert(0, ".")
import dessin as D
from matplotlib.patches import Rectangle

WID = 25.62
T_MES = 19.36 + 2.32 + 4.50 + 10.50      # 36,68 couverts par le croquis
T = 51.1                                  # profondeur TOTALE au plan (memoire 2.3)
Y0 = T - T_MES                           # bas de la zone relevée : 14,42
Y_INT = T - 19.36                        # ligne interne
BLK_X1, BLK_W = 13.18, 25.62 - 13.18 - 7.42   # bloc central : x 13,18 ; larg. 5,02
BLK_Y2 = Y_INT - 2.32
BLK_H = 4.50                             # bas du bloc : 10,50

fig, ax = D.new_sheet(
    "RELEVÉ CONTRADICTOIRE TOITURE — BÂTIMENT C (ÉCOLE SUPTECH)",
    "Reconstruction cotée du croquis terrain du 27/07/2026 — cotes en mètres · bleu = mesuré · "
    "orange = lecture/rattachement à confirmer · gris = déduit des fermetures",
    (-6.5, 33.5), (-21.0, 56.0))

# contour + ligne interne (limite terrasse haute / zone basse)
ax.add_patch(Rectangle((0, 0), WID, T, fill=False, lw=2.2, edgecolor=D.NOIR, zorder=10))
ax.plot([0, WID], [Y0, Y0], color=D.ORANGE, lw=1.2, ls='--', zorder=9)
ax.add_patch(Rectangle((0, 0), WID, Y0, facecolor='#f1f5f9', edgecolor='none', zorder=2))
ax.text(WID/2, Y0/2, 'PARTIE SUD ≈ 14,4 m — au plan (51,1 total)\nNON COUVERTE par le croquis — à confirmer', fontsize=8, ha='center', color=D.GRIS, zorder=5)
prov_w, prov_h = 10.7, 9.8
pr = Rectangle((BLK_X1 + BLK_W/2 - prov_w/2, BLK_Y2 - prov_h/2 - 2.25), prov_w, prov_h, fill=False, edgecolor=D.GRIS, ls=':', lw=1.4, zorder=8)
ax.add_patch(pr)
ax.text(BLK_X1 + BLK_W/2, BLK_Y2 - prov_h - 2.9, 'provision bloc au plan : 10,7 × 9,8 « à confirmer »\n→ RELEVÉ : 5,02 × 4,50 = place LIBÉRÉE', fontsize=6.5, ha='center', color=D.GRIS, zorder=8)
ax.plot([0, BLK_X1], [Y_INT, Y_INT], color=D.NOIR, lw=1.5, zorder=10)
ax.plot([BLK_X1 + BLK_W, WID], [Y_INT, Y_INT], color=D.NOIR, lw=1.5, zorder=10)
ax.text(6.5, Y_INT + 9.0, "TERRASSE HAUTE\n(champ libre relevé)", fontsize=9,
        ha="center", color="#333333")
ax.text(6.5, 5.5, "ZONE BASSE", fontsize=9, ha="center", color="#333333")

# bloc central (édicule/cage) entre les deux niveaux
D.bloc(ax, BLK_X1, BLK_Y2 - BLK_H, BLK_W, BLK_H, label="bloc central\n5,02 (déduit) × 4,50")
ax.plot([BLK_X1, BLK_X1], [Y_INT, BLK_Y2], color=D.NOIR, lw=1.2, ls=":", zorder=9)
ax.plot([BLK_X1 + BLK_W, BLK_X1 + BLK_W], [Y_INT, BLK_Y2], color=D.NOIR, lw=1.2, ls=":",
        zorder=9)

# ------------------------------------------------- cotes principales (mesurées)
D.dim(ax, (0, T), (WID, T), off=1.4, text="25,62")
D.dim(ax, (20.0, Y_INT), (20.0, T), off=0.0, text="19,36")
D.dim(ax, (0, Y_INT + 0.9), (BLK_X1, Y_INT + 0.9), off=0.0, text="13,18")
D.dim(ax, (BLK_X1 + BLK_W, Y_INT - 0.9), (WID, Y_INT - 0.9), off=0.0, text="7,42")
D.dim(ax, (BLK_X1 + 1.2, BLK_Y2), (BLK_X1 + 1.2, Y_INT), off=0.0, text="2,32",
      color=D.ORANGE)
D.dim(ax, (BLK_X1 - 0.7, BLK_Y2 - BLK_H), (BLK_X1 - 0.7, BLK_Y2), off=0.0, text="4,5",
      color=D.ORANGE)
D.dim(ax, (BLK_X1 + 2.5, Y0), (BLK_X1 + 2.5, BLK_Y2 - BLK_H), off=0.0, text="10,5",
      color=D.ORANGE)
# 14,09 : bord gauche -> angle bas-gauche du bloc (ligne basse) — résidu 0,91 vs 13,18
D.dim(ax, (0, BLK_Y2 - BLK_H - 0.9), (14.09, BLK_Y2 - BLK_H - 0.9), off=0.0, text="14,09",
      color=D.ORANGE)
# 13,95 : partiel bord bas depuis la gauche
D.dim(ax, (0, Y0), (13.95, Y0), off=-1.3, text="13,95", color=D.ORANGE)
# profondeur totale (déduite)
D.dim(ax, (WID, Y0), (WID, T), off=-1.6, text="36,68 relevé (19,36+2,32+4,50+10,50)", color=D.GRIS)
D.dim(ax, (-1.9, 0), (-1.9, T), off=0.0, text="51,1 (plan)", color=D.GRIS)

# ------------------------------------------------- cluster sud-est (à confirmer)
ax.add_patch(Rectangle((WID - 3.2 - 1.19, Y0 + 2.0), 1.19, 0.6, fill=False, edgecolor=D.ORANGE,
                       ls="--", lw=1.2, zorder=12))
ax.text(WID - 3.2 - 0.6, Y0 + 3.0, "1,19", fontsize=6.5, color=D.ORANGE, ha="center")
D.dim(ax, (WID - 3.2, Y0 + 2.3), (WID, Y0 + 2.3), off=0.0, text="3,2", color=D.ORANGE)
D.dim(ax, (WID - 7.49, Y0), (WID, Y0), off=-2.5, text="7,49", color=D.ORANGE)
D.dim(ax, (WID - 7.49, Y0 + 0.4), (WID - 1.0, Y0 + 5.6), off=0.0, text="13,5 ? (diag. raturée)",
      color=D.ORANGE)

ax.text(0, -6.4,
        "FERMETURES : 13,18 + 5,02 + 7,42 = 25,62 ✓ exact (largeur bloc déduite) · "
        "profondeur totale 36,68 déduite de 19,36+2,32+4,50+10,50\n"
        "À CONFIRMER (lecture croquis) : 2,32 · 4,5 (ou 5,4 ?) · 10,5 (ou 1,05 ?) · 14,09 "
        "(rattachement) · 13,95 (extrémité) · cluster SE (1,19 / 3,2 / 7,49 / 13,5 raturé / 1,52 ?)",
        fontsize=6.8, va="top", color="#333333")

D.legende(ax, 27.6, 47.0, [
    ("bloc", "bloc / édicule"),
    ("caissonU", "élément à confirmer"),
    ("dim", "cote mesurée"),
    ("dimU", "cote — lecture/rattachement à confirmer"),
])
D.scale_bar(ax, 27.6, 40.0, total=10, step=2)
D.cartouche(fig, [
    ("ACCORDIA TECH — Consultation FRDISI PV + stockage, Mohammedia", True),
    ("Bât. C — ÉCOLE SUPTECH (26,2 × 51,1 au plan) — RELEVÉ RECONSTITUÉ v2", True),
    ("Relevé : R. Kasri, 27/07/2026 — restitution TAQINOR (document de travail)", False),
    ("Échelle 1:250 (A3) — cotes en mètres — NE REMPLACE PAS les planches 05E/05G", False),
])
fig.savefig("PLAN_RELEVE_ECOLE.pdf", bbox_inches="tight")
fig.savefig("PLAN_RELEVE_ECOLE.png", dpi=170, bbox_inches="tight")
print("PLAN ECOLE : render ok")
