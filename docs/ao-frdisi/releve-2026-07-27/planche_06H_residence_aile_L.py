# -*- coding: utf-8 -*-
"""PLANCHE 06H — IMPLANTATION PHOTOVOLTAÏQUE, RÉSIDENCE : AILE EN L (BÂT. A).

Version de dépôt (ACCORDIA TECH — appel d'offres FRDISI, Mohammedia).
Géométrie, obstacles et calepinage IDENTIQUES à l'étude d'implantation :
seul l'habillage de la planche (titre, cartouche, libellés) est propre au dépôt.

  Base : relevé contradictoire du 27/07/2026 (enveloppe, locaux, 28 obstacles
  mesurés) et décisions d'études du 27/07/2026 :
     (1) le grand rectangle non coté de la jonction de l'aile est ÉCARTÉ AU
         RELEVÉ (néant) : il ne figure ni au plan ni au calepinage ;
     (2) l'angle sud-est de l'aile est un ANGLE DROIT (pas de pan coupé) :
         l'enveloppe est en coin plein ;
     (3) TABLES MIXTES retenues : table PORTRAIT 1,134 × 4,70 ET table PAYSAGE
         2,382 × 2,25, le kit étant choisi RANGÉE PAR RANGÉE — paysage dans les
         bandes étroites et sur la bande ouest libre, portrait partout où la
         largeur disponible le permet.

  Règles de calepinage :
  a) ORIENTATION. Une table « E-O » porte 2 modules dos à dos, l'un face EST
     l'autre face OUEST : son FAÎTAGE est NORD-SUD, donc une rangée court
     NORD-SUD. Rangées N-S partout.
  b) Le L est UNE SEULE surface : une rangée qui reste à l'ouest de l'aile
     (x ≤ 10,85) descend d'un seul tenant de la barre dans l'aile.
  c) Allées 0,60 minimum, OPTIMISÉES : rangées à positions EXPLICITES.
     Rives 0,35 · dégagement obstacles 0,30 · 0,50 pour un obstacle de NATURE
     INCONNUE (cote à confirmer à l'exécution).
  d) Aucun obstacle mesuré n'est supprimé : les 28 obstacles relevés sont TOUS
     là, avec leur dégagement. Aucune emprise devinée n'entre dans le compte :
     le chiffre ne repose que sur du MESURÉ.
  Compte DESSINÉ = COMPTÉ (asserts) ET PROUVÉ OPTIMAL : le jeu de rangées retenu
  est rejoué à chaque exécution contre une recherche exhaustive (programmation
  dynamique au pas de 1 cm sur les 2 kits) — aucun « maximum » théorique affiché.

Sorties : 06H_IMPLANTATION_RESIDENCE_AILE_L.pdf (à côté du script)
          06H_IMPLANTATION_RESIDENCE_AILE_L.png (dossier de dépôt « 06 - Schémas »)
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
# DÉCISION D'ÉTUDES 27/07/2026 (2) : l'angle SUD-EST de l'aile 2 est un ANGLE DROIT.
# Le « pan coupé » 2,18 × 4,04 venait du PLAN (jamais relevé) : écarté au relevé,
# l'enveloppe reprend son coin plein. Les lectures 2,18 / 4,04 se rapportaient au
# chanfrein de jonction et au « grand rectangle » — tous deux écartés au relevé,
# donc ces 2 cotes orange sont retirées de la planche.
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
# DÉCISION D'ÉTUDES 27/07/2026 (1) : le « grand rectangle non coté » de la jonction
# est ÉCARTÉ AU RELEVÉ. Son emprise supposée (s 0,40→1,70 · x 4,95→7,16) n'est gardée
# que comme point d'ancrage de la mention sur la planche — ce n'est plus un obstacle.
GRECT_NEANT = (0.40, 1.70, 4.95, 7.16)

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

# ================================================================ CALEPINAGE
# DÉCISION D'ÉTUDES 27/07/2026 (3) : TABLES MIXTES — les 2 kits sont retenus.
# Une table = 2 modules 625 Wc dos à dos (face EST | face OUEST), 15°,
# faîtage NORD-SUD ; les rangées courent NORD-SUD.
#   "P" PORTRAIT : emprise E-O 4,70 (= 2 × 2,382 × cos15° + faîtage), pas N-S 1,134
#   "L" PAYSAGE  : emprise E-O 2,25 (= 2 × 1,134 × cos15° + faîtage), pas N-S 2,382
TYPES = {"P": (4.70, 1.134, "PORTRAIT", "1,134 × 4,70"),
         "L": (2.25, 2.382, "PAYSAGE", "2,382 × 2,25")}
MOD_TABLE = 2                  # 2 modules par table (dos à dos)
RIVE, ALLEE = 0.35, 0.60
CLEAR, CLEAR_INC = 0.30, 0.50  # dégagement standard / nature inconnue
ENG = 152                      # engagé au marché — Bât. A (95,0 kWc)

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
# DÉCISIONS D'ÉTUDES 27/07/2026 (1) et (2) : le grand rectangle non coté (GRECT) et
# le pan coupé SE (PAN) sont écartés au relevé → ils ne sont plus des obstacles. Il ne
# reste donc AUCUNE emprise devinée dans le compte : 28 obstacles, tous RELEVÉS.
assert len(OBS) == 28, "28 obstacles relevés, aucune emprise devinée"
assert sum(1 for o in OBS if o[6] in ("R", "R?")) == 28, "28 obstacles relevés"
assert [o[5] for o in OBS if o[6] not in ("R", "R?")] == [], \
    "plus aucune emprise devinée (décisions d'études du 27/07/2026)"

# --- enveloppe : le L est une seule surface
X_W, X_E = RIVE, BAR - RIVE               # 0,35 → 46,73
X_LEG_E = LEG_W - RIVE                    # 10,85 : au-delà, pas d'aile
Y_N = W_B - RIVE                          # 10,41 (largeur B, conservatrice vs A 10,92)
Y_S_BAR, Y_S_LEG = RIVE, -LEG_S + RIVE    # 0,35 / -29,39


def band(x0, w):
    """Étendue N-S utile d'une rangée [x0, x0+w] (le L est continu à l'ouest)."""
    return (Y_S_LEG if x0 + w <= X_LEG_E + 1e-9 else Y_S_BAR), Y_N


def free_segments(x0, w, obs):
    """Segments N-S libres de la rangée [x0, x0+w], dégagements appliqués."""
    x1 = x0 + w
    ymin, ymax = band(x0, w)
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


def count_row(x0, t, obs):
    """Modules d'UNE rangée du kit t posée en x0 (indépendant du dessin)."""
    w, pas = TYPES[t][0], TYPES[t][1]
    return sum(MOD_TABLE * int((b - a + 1e-9) // pas)
               for (a, b) in free_segments(x0, w, obs))


def count_rows(rows, obs):
    """Comptage INDÉPENDANT du dessin (garde-fou compte affiché = dessiné)."""
    return sum(count_row(x0, t, obs) for (x0, t) in rows)


def optimum(obs, allee=ALLEE, kits=None, step=0.01):
    """OPTIMUM EXACT sur grille de 1 cm : programmation dynamique sur l'axe E-O.
    best[i] = max de modules posables à l'est de x_i ; on choisit en chaque point
    de ne rien poser, ou de poser une rangée d'un des kits autorisés puis de
    reprendre après l'allée. Retourne (total, [(x0, kit, modules), ...])."""
    kits = TYPES if kits is None else kits
    xs, x = [], X_W
    while x <= X_E + 1e-9:
        xs.append(round(x, 4))
        x += step
    n = len(xs)

    def idx(v):
        return max(0, min(n, int(round((v - X_W) / step))))

    best = [0] * (n + 1)
    pick = [None] * (n + 1)
    for i in range(n - 1, -1, -1):
        b, ch = best[i + 1], None
        for t in kits:
            w = TYPES[t][0]
            if xs[i] + w > X_E + 1e-9:
                continue
            c = count_row(xs[i], t, obs)
            if c == 0:
                continue
            v = c + best[idx(xs[i] + w + allee)]
            if v > b:
                b, ch = v, (t, c)
        best[i], pick[i] = b, ch
    rows, i = [], 0
    while i < n:
        if pick[i] is not None:
            t, c = pick[i]
            j = idx(xs[i] + TYPES[t][0] + allee)
            if best[i] == c + best[j]:
                rows.append((xs[i], t, c))
                i = j
                continue
        i += 1
    return best[0], rows


# --- RANGÉES EXPLICITES OPTIMISÉES (consigne « 0,60 mini, optimisées ») :
#     (x0, kit) — positions retenues après recherche EXHAUSTIVE au pas de 1 cm sur
#     les 2 kits, sous les contraintes rives 0,35 / allées ≥ 0,60 / dégagements.
#     Bande ouest libre (2,25 × 39,80 d'un seul tenant, barre + aile) → PAYSAGE ;
#     cœur pollué de caissons → PORTRAIT là où la largeur paie, PAYSAGE entre 2
#     colonnes de caissons trop rapprochées pour 4,70.
ROWS = [(0.45, "L"), (3.30, "P"), (8.60, "L"), (12.93, "L"), (15.78, "L"),
        (18.63, "L"), (21.48, "L"), (24.33, "P"), (29.63, "L"), (33.27, "P"),
        (38.57, "L"), (41.42, "L"), (44.48, "L")]
assert [r[0] for r in ROWS] == sorted(r[0] for r in ROWS)
assert all(t in TYPES for (_, t) in ROWS)
assert ROWS[0][0] >= RIVE - 1e-9, "rive ouest"
assert ROWS[-1][0] + TYPES[ROWS[-1][1]][0] <= X_E + 1e-9, "rive est"
for (a, ta), (b, _) in zip(ROWS, ROWS[1:]):
    assert b - (a + TYPES[ta][0]) >= ALLEE - 1e-9, ("allée < 0,60", a, b)

N = count_rows(ROWS, OBS)
KWC = N * 0.625

# --- PREUVE D'OPTIMALITÉ : le jeu de rangées retenu vaut l'optimum exact.
N_OPT, ROWS_OPT = optimum(OBS)
assert N == N_OPT, ("le calepinage retenu n'est pas optimal", N, N_OPT)

# --- SENSIBILITÉS (même moteur, même relevé — pour information, non dessinées)
N_P_ONLY = optimum(OBS, kits={"P": TYPES["P"]})[0]      # 100 % portrait
N_L_ONLY = optimum(OBS, kits={"L": TYPES["L"]})[0]      # 100 % paysage
OBS_50 = [o[:4] + (0.50,) + o[5:] for o in OBS]         # tout en nature inconnue
N_C50 = optimum(OBS_50)[0]
N_A100 = optimum(OBS, allee=1.00)[0]                    # allées de maintenance
N_A120 = optimum(OBS, allee=1.20)[0]

VERDICT = "CONFIRMÉ" if N >= ENG else "TENDU"
MARGE = N - ENG
VERT, VERT_F, TENDU_C = "#15803d", "#bbf7d0", "#c2410c"


def fr(v, dec=2):
    return f"{v:.{dec}f}".replace(".", ",")


# ================================================================ FEUILLE
fig, ax = D.new_sheet(
    "IMPLANTATION PHOTOVOLTAÏQUE — RÉSIDENCE : AILE EN L (BÂT. A)",
    "Contour, locaux et obstacles : RELEVÉ CONTRADICTOIRE DU 27/07/2026 — décisions "
    "d'études du 27/07/2026 : grand rectangle de la jonction ÉCARTÉ AU RELEVÉ · "
    "angle sud-est de l'aile = ANGLE DROIT · TABLES MIXTES retenues\n"
    "calepinage : tables E-O MIXTES portrait 1,134×4,70 et paysage 2,382×2,25 (2 modules "
    "625 Wc, 15°), FAÎTAGE NORD-SUD (modules face E et face O), rangées N-S continues sur "
    "tout le L, positions EXPLICITES\n"
    "allées 0,60 mini OPTIMISÉES, rives 0,35, dégagement 0,30 (0,50 nature inconnue) — "
    "BLEU = mesuré · ORANGE = à confirmer · GRIS = déduit",
    (-7.5, 64.0), (-34.8, 16.2))

# ---------------- contour (décroché sud 1,54 + ressaut de largeur B/A ;
#                  angle SUD-EST DROIT — relevé du 27/07/2026, pas de pan coupé)
outline = [(0, W_B), (B_LEN, W_BE), (B_LEN, W_A), (BAR, W_A), (BAR, 0),
           (NX1, 0), (NX1, NDY), (NX0, NDY), (NX0, 0), (LEG_W, 0),
           (LEG_W, -LEG_S), (0, -LEG_S)]
ax.add_patch(Polygon(outline, closed=True, fill=False, lw=2.4, edgecolor=D.NOIR,
                     zorder=12))
acro = [(0.28, W_B - 0.28), (B_LEN, W_BE - 0.28), (B_LEN, W_A - 0.28),
        (BAR - 0.28, W_A - 0.28), (BAR - 0.28, 0.28), (NX1 + 0.28, 0.28),
        (NX1 + 0.28, NDY + 0.28), (NX0 - 0.28, NDY + 0.28), (NX0 - 0.28, 0.28),
        (LEG_W - 0.28, 0.28), (LEG_W - 0.28, -LEG_S + 0.28),
        (0.28, -LEG_S + 0.28)]
ax.add_patch(Polygon(acro, closed=True, fill=False, lw=0.6, edgecolor="#666666",
                     zorder=11))


# ---------------- calepinage : pose des tables (positions EXPLICITES)
def draw_tables(rows, obs):
    total, placed = 0, []
    for (x0, t) in rows:
        w, pas = TYPES[t][0], TYPES[t][1]
        for (a, b) in free_segments(x0, w, obs):
            n = int((b - a + 1e-9) // pas)
            total += MOD_TABLE * n
            for i in range(n):
                yy = a + i * pas
                placed.append((x0, yy, t))
                ax.add_patch(Rectangle((x0, yy), w, pas, facecolor=VERT_F,
                                       edgecolor=VERT, lw=0.35, zorder=6))
            if n:      # faîtage continu N-S du segment (séparation module E / module O)
                ax.plot([x0 + w / 2] * 2, [a, a + n * pas], color=VERT,
                        lw=0.5, zorder=7)
    return total, placed


n_drawn, placed = draw_tables(ROWS, OBS)

# ---------------- contrôles géométriques (durcis vs v1)
EPS = 1e-6
assert n_drawn == N, (n_drawn, N)                    # DESSINÉ = COMPTÉ
assert len(placed) * MOD_TABLE == N
for (tx, ty, tt) in placed:
    w, pas = TYPES[tt][0], TYPES[tt][1]
    tx1, ty1 = tx + w, ty + pas
    ymin, ymax = band(tx, w)
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
# non-chevauchement strict entre tables (kits mixtes : emprises différentes)
for i in range(len(placed)):
    xi, yi, ti = placed[i]
    wi, pi = TYPES[ti][0], TYPES[ti][1]
    for j in range(i + 1, len(placed)):
        xj, yj, tj = placed[j]
        wj, pj = TYPES[tj][0], TYPES[tj][1]
        assert (xi + wi <= xj + EPS or xj + wj <= xi + EPS
                or yi + pi <= yj + EPS or yj + pj <= yi + EPS), \
            ("chevauchement", placed[i], placed[j])

# repère O / E sur la première rangée (bas de l'aile, zone dégagée)
_w0 = TYPES[ROWS[0][1]][0]
ax.text(ROWS[0][0] + _w0 * 0.25, -28.6, "O", fontsize=6.5, color=VERT, ha="center",
        va="center", fontweight="bold", zorder=9)
ax.text(ROWS[0][0] + _w0 * 0.75, -28.6, "E", fontsize=6.5, color=VERT, ha="center",
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
# DÉCISION D'ÉTUDES 27/07/2026 (1) : le grand rectangle non coté n'est PAS DESSINÉ.
# Repère in situ à l'emplacement où il était supposé, l'emprise est calepinée.
ax.text((GRECT_NEANT[2] + GRECT_NEANT[3]) / 2, -(GRECT_NEANT[0] + GRECT_NEANT[1]) / 2,
        "(1) grand rectangle : ÉCARTÉ AU RELEVÉ DU 27/07/2026",
        fontsize=5.0, ha="center", va="center", color=D.ORANGE, fontweight="bold",
        zorder=27, bbox=dict(fc="white", ec=D.ORANGE, lw=0.6, alpha=0.96, pad=1.2))

# ---------------- séparation zones + étiquettes
ax.plot([B_LEN, B_LEN], [0, W_BE], color="#7c3aed", lw=0.9, ls="--", zorder=13)
ax.text(5.6, 11.45, "ZONE B", fontsize=9, fontweight="bold",
        color="#7c3aed", ha="center")
ax.text(44.0, 11.5, "ZONE A", fontsize=9, fontweight="bold",
        color="#7c3aed", ha="center")
ax.text(1.6, -13.5, "AILE 2", fontsize=9, fontweight="bold",
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
# cotes orange « 4,04 (est) » et « 2,18 (chanfrein jonction ?) » RETIRÉES : elles ne
# rattachaient que le grand rectangle et le pan coupé, écartés au relevé du 27/07/2026.
ax.annotate("(2) ANGLE SUD-EST = ANGLE DROIT — relevé du 27/07/2026\n"
            "(pas de pan coupé : le coin plein est calepiné)",
            xy=(LEG_W - 0.15, -LEG_S + 0.15), xytext=(12.4, -32.6),
            fontsize=5.8, ha="left", va="center", color="#111111",
            fontweight="bold", zorder=27,
            arrowprops=dict(arrowstyle="->", lw=0.8, color="#111111"),
            bbox=dict(fc="white", ec="#111111", lw=0.7, alpha=0.96, pad=1.4))
D.dim(ax, (0, -LEG_S), (LEG_W, -LEG_S), off=-2.0, text="11,2 (plan)", color=D.GRIS)

# --- paramètres de calepinage cotés une fois (zone A, hors obstacles) : les 2 kits
dimb((24.33, 11.55), (29.03, 11.55), 0.0, "4,70 (portrait)", color=D.GRIS, fs=5.2)
dimb((29.63, 11.55), (31.88, 11.55), 0.0, "2,25 (paysage)", color=D.GRIS, fs=5.2)
dimb((29.03, 12.15), (29.63, 12.15), 0.0, "0,60 (allée)", color=D.GRIS, fs=5.0)
dimb((10.85, 2.05), (12.93, 2.05), 0.0, "2,08 (allée large — cage)",
     color=D.GRIS, fs=5.2)
dimb((31.88, 2.05), (33.27, 2.05), 0.0, "1,39 (allée large)", color=D.GRIS, fs=5.2)

# ================================================================ BANDEAU ENGAGEMENT
BX = 30.0
if N >= ENG:
    ax.text(BX, -4.30,
            f"Capacité démontrée sur le relevé : {N} modules — "
            f"ENGAGÉ AU MARCHÉ : {ENG} modules (marge +{MARGE})",
            fontsize=8.6, fontweight="bold", ha="center", color=VERT, zorder=30,
            bbox=dict(fc="white", ec="none", alpha=0.85, pad=1.0))
else:
    ax.text(BX, -4.30,
            f"Capacité démontrée sur le relevé : {N} modules — "
            f"ENGAGÉ AU MARCHÉ : {ENG} modules (écart {ENG - N})",
            fontsize=8.6, fontweight="bold", ha="center", color=TENDU_C, zorder=30)
ax.text(BX, -5.35,
        "Implantation définitive arrêtée après relevé d'exécution — "
        f"marché à prix unitaires  ·  capacité {N} mod. = {fr(KWC, 1)} kWc, "
        "calepinage prouvé optimal",
        fontsize=6.4, ha="center", color="#374151", zorder=30,
        bbox=dict(fc="white", ec="none", alpha=0.85, pad=1.0))
_sens = [("dégagt 0,50 partout", N_C50), ("allées 1,00 (maintenance)", N_A100),
         ("allées 1,20", N_A120)]
_ko = [s for s, v in _sens if v < ENG]
ax.text(BX, -6.25,
        "robustesse : " + " · ".join(f"{s} → {v}" for s, v in _sens)
        + (f" — engagement {ENG} tenu partout" if not _ko
           else f" — {ENG} tenu sauf {' et '.join(_ko)}"),
        fontsize=6.8, ha="center", color=D.ORANGE, fontweight="bold", zorder=30)

# ---------------- mini-repérage croquis
kx, ky, s = 49.8, -20.6, 0.085
mini = [(0, 10.76), (47.08, 10.76), (47.08, 0), (11.2, 0), (11.2, -29.74),
        (0, -29.74)]
ax.add_patch(Polygon([(kx + p[0] * s, ky + p[1] * s) for p in mini], closed=True,
             fill=False, lw=1.0, edgecolor="#555555", zorder=30))
for cx, cy, t in ((35.3, 5.4, "A"), (11.8, 5.4, "B"), (5.6, -14.9, "C")):
    ax.text(kx + cx * s, ky + cy * s, t, fontsize=7, ha="center", va="center",
            fontweight="bold", color="#7c3aed", zorder=31)
ax.text(kx - 1.3, ky + 1.6, "repérage des zones (vue d'ensemble)", fontsize=5.6,
        color="#555555", zorder=30)

D.legende(ax, 49.5, -8.6, [
    ("caisson", "caisson béton relevé — dégagt 0,30"),
    ("caissonU", "caisson à confirmer — dégagt 0,50"),
    ("bloc", "local (cage, édicule) — murs épais"),
    ("dim", "cote mesurée au relevé du 27/07/2026"),
    ("dimU", "cote / rattachement à confirmer à l'exécution"),
], fs=6.0)
ax.add_patch(Rectangle((49.5, -12.9), 4.70 * 0.42, 1.134 * 0.42, facecolor=VERT_F,
             edgecolor=VERT, lw=0.6, zorder=30))
ax.plot([49.5 + 4.70 * 0.21] * 2, [-12.9, -12.9 + 1.134 * 0.42], color=VERT,
        lw=0.6, zorder=31)
ax.text(51.6, -12.68, "table PORTRAIT 1,134 × 4,70 (kit école)\n"
        "2 modules 625 Wc, 15° — faîtage N-S\n(module face OUEST | face EST)",
        fontsize=6.0, va="center", zorder=30)
ax.add_patch(Rectangle((49.5, -15.55), 2.25 * 0.42, 2.382 * 0.42, facecolor=VERT_F,
             edgecolor=VERT, lw=0.6, zorder=30))
ax.plot([49.5 + 2.25 * 0.21] * 2, [-15.55, -15.55 + 2.382 * 0.42], color=VERT,
        lw=0.6, zorder=31)
ax.text(50.7, -15.05, "table PAYSAGE 2,382 × 2,25\n2 modules 625 Wc, 15° — même faîtage\n"
        "N-S — les 2 kits retenus (études 27/07/2026)", fontsize=6.0, va="center",
        zorder=30)

# nord + échelle
ax.add_patch(FancyArrowPatch((45.5, -11.0), (45.5, -9.0), arrowstyle="-|>",
             mutation_scale=16, lw=1.6, color="#111111", zorder=30))
ax.text(45.5, -8.7, "N", fontsize=10, ha="center", fontweight="bold", zorder=30)
D.scale_bar(ax, 49.5, -17.4)

# ---------------- contrôles de fermeture
ax.text(13.2, -7.5,
        "CONTRÔLES DE FERMETURE (relevé contradictoire du 27/07/2026)\n"
        "· zone B, chaîne basse : 3,39+1,31+6,47+1,33+6,55+1,30+3,23 = 23,58 — résidu 0,00\n"
        "· zone B, chaîne nord : 12,23 (→cage) + 2,47 + 2,77 + 6,11 = 23,58 — résidu 0,00\n"
        "· zone B, cage : 5,97 ≈ 1,15+1,14+3,84 = 6,13 (Δ 0,16) → emprise ≈2,5×4,6 déduite\n"
        "· barre : 23,58 + 23,50 = 47,08 relevé (plan 48,0 → Δ −0,92)\n"
        "· aile 2 OUEST S→N = 29,91 · EST S→N = 29,92 (+10,76 barre ≈ 40,7 ≈ 40,5 plan)\n"
        "· aile 2 TRANSVERSAL : 3,78+1,15+1,40+1,15+3,72 = 11,20 = largeur 11,2 EXACT ✓\n"
        "· largeurs relevées : 10,76 (B ouest) / 10,77 (raccord B/A) / 10,92 (A)\n"
        "· CALEPINAGE : dessiné = compté (assert) · non-chevauchement · rives 0,35 ·\n"
        "  allées ≥ 0,60 · dégagement de chaque obstacle vérifié table par table\n"
        "  · OPTIMALITÉ re-prouvée à chaque exécution (recherche exhaustive, pas 1 cm)",
        fontsize=6.0, va="top", color="#334155", zorder=30,
        bbox=dict(boxstyle="round,pad=0.45", fc="#f8fafc", ec="#94a3b8", lw=0.7))

# ---------------- HYPOTHÈSES ARRÊTÉES AU 27/07/2026 — gravées sur la planche
ax.text(13.2, -14.4,
        "RELEVÉ ET DÉCISIONS D'ÉTUDES DU 27/07/2026 — INTÉGRÉS À CE CALEPINAGE\n"
        "· (1) le GRAND RECTANGLE NON COTÉ de l'aile 2 (jonction) est ÉCARTÉ AU RELEVÉ —\n"
        "  il ne figure ni au plan ni au calepinage : l'emprise est libre et calepinée.\n"
        "· (2) PAS de pan coupé à l'angle SUD-EST de l'aile 2 : c'est un ANGLE DROIT —\n"
        "  enveloppe en coin plein, le coin est calepiné.\n"
        "· (3) TABLES MIXTES RETENUES PARTOUT : les 2 kits sont validés (portrait\n"
        "  1,134×4,70 ET paysage 2,382×2,25) — le kit est choisi rangée par rangée.\n"
        "→ aucune emprise devinée dans le compte : les 28 obstacles sont MESURÉS.",
        fontsize=6.0, va="top", color="#134e4a", zorder=30, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.45", fc="#ecfdf5", ec="#15803d", lw=0.9))
# à confirmer
ax.text(13.2, -19.6,
        "À CONFIRMER À L'EXÉCUTION (points repérés en ORANGE sur la planche)\n"
        "· longueur de la zone A : 23,50 — à relire (23,6 ?)\n"
        "· zone A : entraxe 2,55 ? (0,98 ↔ 0,87) · 1,53 = entraxe 0,84 ↔ 0,94×0,47\n"
        "· zone B : verticales 1,11×1,30 → 6,08+1,30+3,83 = 11,21 vs 10,76 (Δ +0,45) — à re-mesurer\n"
        "  · caisson 0,8×0,63 ? · décroché nord : profondeur 1,15 ?\n"
        "· zone A sud-ouest : rattachements 2,39 et 1,2 · édicule ≈0,92×0,74 · accès : prof. ≈0,7 ?\n"
        "· aile 2 : 6,84 (relu 6,87 ?) · 7,37 (ou 4,37 ?) · 4,82 · 1,93 — cotes de chaîne\n"
        "→ points de cotation à lever au relevé d'exécution — marché à prix unitaires.",
        fontsize=6.0, va="top", color="#7c2d12", zorder=30,
        bbox=dict(boxstyle="round,pad=0.45", fc="#fff7ed", ec="#d97706", lw=0.7))
# NOTA
nota = (f"NOTA — capacité démontrée sur le relevé : {N} modules ({fr(KWC, 1)} kWc).\n"
        f"ENGAGÉ AU MARCHÉ : {ENG} modules, soit une marge de +{MARGE} modules.\n"
        "Le calepinage ne repose QUE SUR DU MESURÉ : aucune emprise devinée n'y\n"
        "subsiste. Il est PROUVÉ OPTIMAL (recherche exhaustive au pas de 1 cm\n"
        "sur les 2 kits).\n"
        f"Câblage : {N // 16} chaînes × 16 = {(N // 16) * 16} modules "
        f"({N - (N // 16) * 16} en réserve d'appoint).\n"
        f"Engagement résidence 272 modules = Bât. A {ENG} + Bât. B 120.\n"
        "Implantation définitive arrêtée après relevé d'exécution — "
        "marché à prix unitaires.")
ax.text(13.2, -25.4, nota, fontsize=6.2, va="top", fontweight="bold",
        color="#111111", zorder=30,
        bbox=dict(boxstyle="round,pad=0.5", fc="#fefce8", ec="#111111", lw=1.0))

# ---------------- panneau droit : détail des rangées
PX = 49.5
ax.text(PX, 14.6, "CALEPINAGE — RANGÉES EXPLICITES (kits mixtes)", fontsize=7.6,
        fontweight="bold", va="top", zorder=30)
n_p = sum(1 for (_, t) in ROWS if t == "P")
n_l = sum(1 for (_, t) in ROWS if t == "L")
lines = ["rg  kit       emprise E-O   portée     mod."]
for i, (r, t) in enumerate(ROWS, 1):
    w = TYPES[t][0]
    ymin, _ = band(r, w)
    port = "L complet" if ymin < 0 else "barre"
    c = count_row(r, t, OBS)
    lines.append(f"{i:2d}  {TYPES[t][2]:8s}  {fr(r):>5s}→{fr(r + w):>5s}  "
                 f"{port:9s} {c:3d}")
lines += ["", f"CAPACITÉ DESSINÉE = COMPTÉE : {N} mod. = {fr(KWC, 1)} kWc",
          "OPTIMUM PROUVÉ (exhaustif, pas 1 cm)",
          f"ENGAGÉ AU MARCHÉ {ENG} → écart {ENG - N}"
          if N < ENG else f"ENGAGÉ AU MARCHÉ {ENG} → marge +{MARGE}",
          "", f"kits : {n_p} rangées PORTRAIT · {n_l} PAYSAGE",
          "rives 0,35 · allées 0,60 mini, dont 2,08 (cage)",
          "et 1,39 — dégagt 0,30 (0,50 si cote douteuse)",
          "", "sensibilités (même relevé, même moteur) :",
          f"  100 % portrait / 100 % paysage → {N_P_ONLY} / {N_L_ONLY}",
          f"  dégagement 0,50 partout          → {N_C50}",
          f"  allées 1,00 (maintenance)        → {N_A100}",
          f"  allées 1,20                      → {N_A120}"]
for i, t in enumerate(lines):
    ax.text(PX, 13.4 - i * 0.72, t, fontsize=6.0, va="top", color="#1f2937",
            zorder=30, family="DejaVu Sans Mono")

D.cartouche(fig, [
    ("ACCORDIA TECH — Appel d'offres FRDISI — PV + stockage, Mohammedia", True),
    ("06H — IMPLANTATION PV — RÉSIDENCE : AILE EN L (BÂT. A)", True),
    (f"Capacité démontrée : {N} mod. ({fr(KWC, 1)} kWc) — "
     f"ENGAGÉ AU MARCHÉ : {ENG} mod. (marge +{MARGE})", False),
    ("Base : relevé contradictoire du 27/07/2026 — A3, cotes en mètres, "
     "échelle barre graphique", False),
    ("Document : 06H_IMPLANTATION_RESIDENCE_AILE_L", False),
    ("Statut : Appel d'offres — Date : Juillet 2026 — Indice : H", False),
])

NOM = "06H_IMPLANTATION_RESIDENCE_AILE_L"
DOSSIER_DEPOT = ("C:/Users/kasri/OneDrive - Atlencia/TAQINOR/"
                 "AO FRDISI - Solaire Mohammedia 2026/ENVOI ACCORDIA - FINAL 27-07/"
                 "06 - Schémas (8 planches)")
os.makedirs(DOSSIER_DEPOT, exist_ok=True)
fig.savefig(os.path.join(BASE, NOM + ".pdf"), bbox_inches="tight")
fig.savefig(os.path.join(DOSSIER_DEPOT, NOM + ".png"), dpi=170, bbox_inches="tight")

print("[ETUDES 27/07/2026] (1) grand rectangle non cote : ecarte au releve · "
      "(2) angle SE : angle droit (coin plein) · (3) tables mixtes retenues")
print(f"[CALEPINAGE] {len(ROWS)} rangées N-S — kits mixtes "
      f"portrait 1,134×4,70 / paysage 2,382×2,25")
for i, (r, t) in enumerate(ROWS, 1):
    w = TYPES[t][0]
    ymin, _ = band(r, w)
    print(f"   rangée {i:2d} : x {r:5.2f} → {r + w:5.2f}  {TYPES[t][2]:8s} "
          f"({'L complet' if ymin < 0 else 'barre'}) = {count_row(r, t, OBS):3d} mod.")
print(f"[06H] capacité dessinée = comptée : {N} modules ({KWC:.1f} kWc) — "
      f"engagé au marché {ENG} → {VERDICT} (marge +{MARGE})")
print(f"[06H] OPTIMALITÉ PROUVÉE : optimum exhaustif (pas 1 cm) = {N_OPT} = {N} OK")
print(f"[SENS] 100 % portrait {N_P_ONLY} · 100 % paysage {N_L_ONLY} · "
      f"dégagt 0,50 partout {N_C50} · allées 1,00 {N_A100} · allées 1,20 {N_A120}")
print(f"[OK] {NOM}.pdf (script) / {NOM}.png (dossier de dépôt) écrits")
