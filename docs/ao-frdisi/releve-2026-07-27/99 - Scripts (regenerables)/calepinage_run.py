# -*- coding: utf-8 -*-
"""Calepinage RÉEL sur géométrie relevée (27/07/2026) + obstacles — 3 bâtiments.
Compte géométrique exact, puis re-vérification chaînes/onduleurs/ratios."""
import sys
sys.path.insert(0, ".")
import dessin as D
import calepinage as C
from matplotlib.patches import Polygon, Rectangle

RES = {}

# ================================================================ BÂT. A — L
fig, ax = D.new_sheet(
    "CALEPINAGE SUR RELEVÉ — BÂTIMENT A (AILE EN L) — tables Est-Ouest 2×625 Wc",
    "Géométrie relevée 27/07/2026 + obstacles — tables 2,382×2,25 m (2 modules paysage), "
    "allées 1,50 m, rives 0,50 m, dégagement obstacles 0,50 m",
    (-5.5, 53.5), (-36.5, 15.5))
BAR_L, W_BAR = 47.08, 10.76
LEG_L, LEG_W = 29.74, 11.2      # aile 2 sous la barre (40,5 - 10,76)
CUT_W, CUT_H = 2.18, 4.04
outline = [(0, W_BAR), (BAR_L, W_BAR), (BAR_L, 0), (LEG_W, 0),
           (LEG_W, -LEG_L + CUT_H), (LEG_W - CUT_W, -LEG_L), (0, -LEG_L)]
ax.add_patch(Polygon(outline, closed=True, fill=False, lw=2.2, edgecolor=D.NOIR, zorder=10))

obs_bar = [
    (3.39, 4.70, 3.77, 4.92), (11.17, 12.50, 3.84, 4.98), (19.05, 20.35, 3.33, 4.34),
    (3.16, 4.27, 5.91, 7.02), (8.03, 9.14, 5.63, 6.93), (16.99, 17.17, 6.42, 7.05),
    (18.92, 20.35, 6.02, 7.46), (12.40, 15.17, 9.61, 10.76),
    (24.86, 26.41, 6.82, 7.46), (27.06, 27.92, 6.37, 6.92), (32.36, 33.20, 6.48, 6.98),
    (33.68, 34.63, 6.41, 6.88), (39.75, 40.22, 5.93, 6.91), (43.81, 44.68, 6.38, 6.92),
    (32.18, 32.88, 3.74, 4.73), (39.31, 40.72, 3.75, 4.65), (45.68, 46.98, 3.75, 4.81),
    (31.28, 32.20, 0.0, 0.74),
]
obs_leg = [
    (0.51, 1.86, 3.5, 4.8), (8.70, 9.77, 3.5, 4.8), (17.14, 18.24, 3.5, 4.8),
    (0.78, 2.13, 6.2, 7.5), (8.86, 9.49, 6.2, 7.5), (13.80, 15.25, 6.2, 7.5),
    (25.70, 29.74, 9.02, 11.2),
]
nA_bar = C.fill_band(ax, 0, 0, BAR_L, W_BAR, obs_bar, horizontal=True)
nA_leg = C.fill_band(ax, 0, 0, LEG_L, LEG_W, obs_leg, horizontal=False)
C.draw_obstacles(ax, 0, 0, obs_bar, horizontal=True)
C.draw_obstacles(ax, 0, 0, obs_leg, horizontal=False)
nA = nA_bar + nA_leg
RES["A"] = nA
ax.text(24, 13.2, f"BARRE : {nA_bar} modules — AILE 2 : {nA_leg} modules — "
        f"TOTAL GÉOMÉTRIQUE BÂT. A : {nA} modules ({nA*0.625:.1f} kWc)",
        fontsize=11, fontweight="bold", ha="center", color="#15803d")
ax.text(24, -33.5, "ENGAGEMENT OFFRE : 152 modules (95,0 kWc) — "
        f"marge géométrique : +{nA-152} modules", fontsize=9.5, ha="center",
        color="#333333", fontweight="bold")
D.cartouche(fig, [
    ("ACCORDIA TECH — FRDISI PV + stockage, Mohammedia", True),
    ("Bât. A (L) — CALEPINAGE sur relevé + obstacles — v1", True),
    ("Relevé R. Kasri 27/07/2026 — restitution TAQINOR — document de travail", False),
    ("Table E-O = 2×625 Wc paysage — allées 1,5 m — NE REMPLACE PAS 05G/06G", False),
])
fig.savefig("CALEPINAGE_BAT_A_L.pdf", bbox_inches="tight")
fig.savefig("CALEPINAGE_BAT_A_L.png", dpi=165, bbox_inches="tight")

# ================================================================ BÂT. B — ARC
fig, ax = D.new_sheet(
    "CALEPINAGE SUR RELEVÉ — BÂTIMENT B (AILE EN ARC, développée 90 m) — tables Est-Ouest",
    "0-47 m : géométrie et obstacles RELEVÉS (27/07) — 47-90 m : plan + réserve DRV "
    "(position à confirmer) — tables 2,382×2,25, allées 1,50, rives 0,50",
    (-4.5, 96.5), (-7.5, 15.5))
ARC_L, ARC_W = 90.0, 10.8
ax.add_patch(Rectangle((0, 0), ARC_L, ARC_W, fill=False, lw=2.2, edgecolor=D.NOIR,
                       zorder=10))
ax.add_patch(Rectangle((-0.4, 0), 0.4, ARC_W, facecolor="none", edgecolor=D.NOIR,
                       hatch="/////", lw=1.2, zorder=10))
ax.plot([47, 47], [-0.5, ARC_W + 0.5], color="#7c3aed", ls="--", lw=1.0, zorder=9)
ax.text(47, ARC_W + 1.0, "← relevé | plan →", fontsize=7, ha="center", color="#7c3aed")
obs_arc = [
    (1.35, 2.38, 5.1, 6.0), (19.36, 20.91, 4.8, 5.76), (16.60, 17.96, 4.2, 5.15),
    (24.40, 29.38, 4.87, 10.8),                             # grand bloc
    (31.0, 32.0, 6.13, 7.03), (35.6, 36.8, 6.6, 7.4), (35.6, 36.85, 3.5, 4.3),
    (43.63, 45.08, 3.68, 4.58), (35.74, 37.54, 7.8, 8.8),
    (44.40, 45.90, 6.12, 7.02), (44.50, 46.00, 3.76, 4.62),
    (60.0, 70.0, 4.25, 6.5),                                # réserve DRV 4 unités
]
nB = C.fill_band(ax, 0, 0, ARC_L, ARC_W, obs_arc, horizontal=True)
C.draw_obstacles(ax, 0, 0, obs_arc, horizontal=True)
ax.text(65, 5.4, "réserve DRV (4 unités)\nposition à confirmer", fontsize=6.5,
        ha="center", color="white", zorder=9, fontweight="bold")
RES["B"] = nB
ax.text(45, 13.2, f"TOTAL GÉOMÉTRIQUE BÂT. B : {nB} modules ({nB*0.625:.1f} kWc) — "
        f"ENGAGEMENT : 120 modules (75,0 kWc) — marge : +{nB-120}",
        fontsize=11, fontweight="bold", ha="center", color="#15803d")
D.cartouche(fig, [
    ("ACCORDIA TECH — FRDISI PV + stockage, Mohammedia", True),
    ("Bât. B (arc, développé 90 m) — CALEPINAGE sur relevé — v1", True),
    ("Relevé R. Kasri 27/07/2026 — restitution TAQINOR — document de travail", False),
    ("Table E-O = 2×625 Wc paysage — allées 1,5 m — NE REMPLACE PAS 05G/06G", False),
])
fig.savefig("CALEPINAGE_BAT_B_ARC.pdf", bbox_inches="tight")
fig.savefig("CALEPINAGE_BAT_B_ARC.png", dpi=165, bbox_inches="tight")

# ================================================================ BÂT. C — ÉCOLE
fig, ax = D.new_sheet(
    "CALEPINAGE SUR RELEVÉ — BÂTIMENT C (ÉCOLE SUPTECH, 26,2 × 51,1) — tables Est-Ouest",
    "Nord (36,7 m) : relevé 27/07 (bloc réel 5,02×4,50 < provision 10,7×9,8) — "
    "sud (14,4 m) : plan — réserves DRV ouest + 4 souches (positions à confirmer)",
    (-4.5, 30.5), (-6.5, 56.5))
ECO_W, ECO_T = 25.62, 51.1
ax.add_patch(Rectangle((0, 0), ECO_W, ECO_T, fill=False, lw=2.2, edgecolor=D.NOIR,
                       zorder=10))
ax.plot([0, ECO_W], [ECO_T - 36.68, ECO_T - 36.68], color="#7c3aed", ls="--", lw=1.0,
        zorder=9)
ax.text(ECO_W + 0.4, ECO_T - 36.68, "← plan\n← relevé", fontsize=6.5, va="center",
        color="#7c3aed")
# obstacles (y depuis le bord SUD ; bloc central relevé : haut à 51,1-21,68)
obs_eco = [
    (13.18, 18.20, ECO_T - 26.18, ECO_T - 21.68),   # bloc central relevé 5,02×4,50
    (0.0, 3.5, 21.6, 31.6),                          # réserve DRV façade ouest (centrale)
    (6.0, 7.0, 10.0, 11.0), (12.0, 13.0, 6.0, 7.0),  # 4 provisions souches
    (18.0, 19.0, 9.0, 10.0), (22.0, 23.0, 4.0, 5.0),
    (21.23, 22.42, ECO_T - 36.68 + 2.0, ECO_T - 36.68 + 2.6),   # cluster SE relevé
]
nC = C.fill_band(ax, 0, 0, ECO_W, ECO_T, obs_eco, horizontal=True)
C.draw_obstacles(ax, 0, 0, obs_eco, horizontal=True)
ax.text(1.75, 26.6, "réserve\nDRV ouest", fontsize=6, ha="center", color="white",
        zorder=9, fontweight="bold", rotation=90)
# provision plan du bloc (pointillé gris, pour mémoire)
pr = Rectangle((15.69 - 5.35, ECO_T - 26.18 - 2.65), 10.7, 9.8, fill=False,
               edgecolor=D.GRIS, ls=":", lw=1.3, zorder=8)
ax.add_patch(pr)
RES["C"] = nC
ax.text(12.8, 53.4, f"TOTAL GÉOMÉTRIQUE BÂT. C : {nC} modules ({nC*0.625:.1f} kWc) — "
        f"ENGAGEMENT : 288 (180,0 kWc) — marge : {nC-288:+d}",
        fontsize=10.5, fontweight="bold", ha="center", color="#15803d")
D.cartouche(fig, [
    ("ACCORDIA TECH — FRDISI PV + stockage, Mohammedia", True),
    ("Bât. C (école 26,2×51,1) — CALEPINAGE sur relevé — v1", True),
    ("Relevé R. Kasri 27/07/2026 — restitution TAQINOR — document de travail", False),
    ("Table E-O = 2×625 Wc paysage — allées 1,5 m — NE REMPLACE PAS 05G", False),
])
fig.savefig("CALEPINAGE_BAT_C_ECOLE.pdf", bbox_inches="tight")
fig.savefig("CALEPINAGE_BAT_C_ECOLE.png", dpi=165, bbox_inches="tight")

# ================================================================ RECALCUL ÉLECTRIQUE
print("=" * 72)
print(f"COMPTAGE GÉOMÉTRIQUE RÉEL : A={RES['A']}  B={RES['B']}  C={RES['C']}  "
      f"TOTAL={sum(RES.values())}")
for bat, engage in (("A", 152), ("B", 120), ("C", 288)):
    n = RES[bat]
    kwc = n * 0.625
    s16 = n // 16
    reste = n - s16 * 16
    ond_max = -(-n // 96)            # onduleurs si on posait TOUT (96 mod/60 kWc max)
    print(f"Bât {bat}: géo={n} mod ({kwc:.1f} kWc) | engagement={engage} "
          f"(marge {n-engage:+d}) | si maxé: {s16} strings de 16 (+{reste}) → "
          f"{ond_max} onduleurs 50 kW à ≤60 kWc | ratio si maxé: "
          f"{ond_max*50/kwc:.3f}")
print("-" * 72)
print("OFFRE DÉPOSÉE (inchangée) : 560 modules / 6 onduleurs / ratios 0,882 & 0,833")
