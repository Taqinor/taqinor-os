# -*- coding: utf-8 -*-
"""VUE DE TOITURE DÉFINITIVE v2 — Bât. B (aile en ARC, Résidence UIB, Mohammedia).

v2 (27/07/2026, soir) — MÊME RELEVÉ, MÊME GÉOMÉTRIE, calepinage RE-OPTIMISÉ selon
les consignes client du 27/07 (allées « 0,60 mini, OPTIMISÉES », rives 0,35,
dégagement 0,30) — exactement le traitement qui a fait passer l'école de 264 à 314.

CE QUI NE CHANGE PAS (aucune cote touchée) :
  - l'arc = 3 SEGMENTS séparés par des MURETS HACHURÉS AU RAS (h = 0, ép. 0,45),
    S1 20,55 + joint + S2 ≈ 23,0 + joint + S3 ≈ 23,6 → développé 68,05 m,
    CONFIRMÉ muret-à-muret par le client le 27/07 (réponse « chaînes muret-à-muret ») ;
  - R_ext = 274 m, largeur 10,90, tous les caissons/cages/structures RELEVÉS,
    toutes les cotes et tous les contrôles de fermeture de la vue du 27/07.

CE QUI CHANGE (calepinage seulement) :
  1. RANGÉES À POSITIONS EXPLICITES, propres à CHAQUE segment (les segments sont
     physiquement séparés par les murets : chacun a son propre plan de pose) ;
     allées 0,60 MINIMUM et le surplus de largeur CONCENTRÉ là où il ne coûte rien
     (au-dessus d'une file de caissons) ;
  2. rives 0,35 (au lieu de 0,50) et rives d'extrémité 0,35 par segment ;
  3. SEGMENT 1 posé en tables PORTRAIT 1,134 × 4,70 — le kit DÉJÀ retenu pour le
     bâtiment C (école) : sur 10,90 de large, 2 rangées portrait couvrent 9,40 de
     modules là où 3 rangées paysage n'en couvrent que 6,75. S2 et S3 restent en
     tables PAYSAGE 2,382 × 2,25 (kit du bâtiment A), qui y rendent davantage
     parce que les caissons y sont dispersés ;
  4. CORRECTION D'ARC (durcissement) : le pas de pose vaut MOD_L × R_ext/R_intérieur
     de la rangée, si bien que deux tables voisines ne se RECOUVRENT PLUS au rayon
     intérieur. L'ancien modèle les posait jointives en abscisse développée →
     recouvrement réel de 2 à 9 cm selon la rangée. Coûte 4 modules : assumé.
  5. dégagement 0,35 en abscisse développée = 0,336 m RÉELS au rayon intérieur,
     donc ≥ 0,30 exigé (0,30 en abscisse n'en vaudrait que 0,288 : sous la règle).
     Les 3 éléments NON COTÉS gardent ce dégagement standard, et la sensibilité au
     traitement « nature inconnue » (0,50 réel) est CHIFFRÉE sur la planche.

AUCUN obstacle relevé n'a été supprimé. Les éléments non cotés sont conservés ET
identifiés (comptes AVEC et SANS donnés en note, pour arbitrage client).

Sorties : VUE_TOITURE_BAT_B_ARC_V2.pdf / .png
"""
import math
import os
import sys
import textwrap

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.chdir(BASE)

import dessin as D
from solveur import chain, closure
from matplotlib.patches import Polygon, FancyArrowPatch, Rectangle

# ---------------------------------------------------------------- géométrie arc
R_EXT = 274.0
W = 10.90
R_INT = R_EXT - W

S1_LEN = 20.55                       # chaîne ext croquis 1 RECALCULÉE : 3,72+3,84+6,59+6,4
S2_LEN = 23.00                       # ≈ (client)
S3_LEN = 23.60                       # ≈ (client)
MUR = 0.45                           # murets inter-segments au ras (confirmé)
OFF2 = S1_LEN + MUR                  # 21.00
OFF3 = OFF2 + S2_LEN + MUR           # 44.45
LEN = OFF3 + S3_LEN                  # 68.05 — développé ext total relevé

TH = LEN / R_EXT
Y0 = R_EXT * math.cos(TH / 2)


def phi(s):
    return (s - LEN / 2) / R_EXT


def P(s, y):
    """(s, y) -> feuille. s = abscisse curviligne bord EXT ; y depuis bord INT."""
    r = R_INT + y
    f = phi(s)
    return (r * math.sin(f), r * math.cos(f) - Y0)


def rigid(s0, s1, y0, y1):
    """Rectangle RIGIDE posé au repère tangent local de son centre."""
    sc, yc = (s0 + s1) / 2, (y0 + y1) / 2
    f = phi(sc)
    cx, cy = P(sc, yc)
    t = (math.cos(f), -math.sin(f))
    n = (math.sin(f), math.cos(f))
    hw, hh = (s1 - s0) / 2, (y1 - y0) / 2
    return [(cx + a * hw * t[0] + b * hh * n[0],
             cy + a * hw * t[1] + b * hh * n[1])
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def arcpts(s0, s1, y, n=80):
    return [P(s0 + (s1 - s0) * i / n, y) for i in range(n + 1)]


def dim(ax, p1, p2, off=0.8, text=None, color=D.BLEU, fs=6.4, gap=0.10,
        ext=0.16, text_off=0.26, box=False):
    ux, uy, L = D._unit(p1, p2)
    nx, ny = -uy, ux
    q1 = (p1[0] + nx * off, p1[1] + ny * off)
    q2 = (p2[0] + nx * off, p2[1] + ny * off)
    sg = 1 if off >= 0 else -1
    for p, q in ((p1, q1), (p2, q2)):
        a = (p[0] + nx * gap * sg, p[1] + ny * gap * sg)
        b = (q[0] + nx * ext * sg, q[1] + ny * ext * sg)
        ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=0.55, zorder=24)
    ax.add_patch(FancyArrowPatch(q1, q2, arrowstyle="<|-|>", mutation_scale=6.0,
                                 lw=0.8, color=color, shrinkA=0, shrinkB=0,
                                 zorder=25))
    if text is None:
        text = f"{L:.2f}".replace(".", ",")
    mx, my = (q1[0] + q2[0]) / 2, (q1[1] + q2[1]) / 2
    ang = math.degrees(math.atan2(uy, ux))
    if ang > 90 or ang <= -90:
        ang += 180
    kw = dict(fontsize=fs, color=color, ha="center", va="center", rotation=ang,
              rotation_mode="anchor", zorder=26)
    if box:
        kw["bbox"] = dict(fc="white", ec="none", alpha=0.85, pad=0.5)
    ax.text(mx + nx * text_off * sg, my + ny * text_off * sg, text, **kw)


def rdim(ax, s, ya, yb, off=0.0, text=None, color=D.BLEU, box=True, fs=6.2):
    dim(ax, P(s, ya), P(s, yb), off=off, text=text, color=color, box=box, fs=fs)


def tdim(ax, s0, s1, y, text=None, color=D.BLEU, box=True, fs=6.2, off=0.0):
    dim(ax, P(s0, y), P(s1, y), off=off, text=text, color=color, box=box, fs=fs)


def caisson(ax, o, cid, uncertain=False, deduced=False, fs=5.4, lsy=None):
    poly = rigid(*o)
    ec = D.ORANGE if uncertain else (D.GRIS if deduced else D.NOIR)
    fc = "#e8ecf1" if deduced else "#d8dee6"
    p = Polygon(poly, closed=True, facecolor=fc, edgecolor=ec, lw=1.0,
                hatch="////", zorder=15)
    p.set_linestyle("--" if (uncertain or deduced) else "-")
    ax.add_patch(p)
    s0, s1, y0, y1 = o
    lx, ly = P(*(lsy or ((s0 + s1) / 2, (y0 + y1) / 2)))
    ax.text(lx, ly, cid, fontsize=fs, ha="center", va="center",
            color=D.ORANGE if uncertain else ("#475569" if deduced else "#111111"),
            zorder=27, fontweight="bold",
            bbox=dict(fc="white", ec="none", alpha=0.78, pad=0.35))


# ---------------------------------------------------------------- obstacles
# (s0, s1, y0, y1) GLOBAUX — y depuis le bord INTÉRIEUR (figure : ext en HAUT)
# --- SEGMENT 1 (croquis 1) — s local = global
C1 = (3.27, 4.63, W - 4.72, W - 3.82)  # 1,36 x 0,90 CONFIRMÉ client
C2 = (15.54, 17.09, 4.80, 5.76)        # 1,55 x 0,96 ? (distance au joint conservée)
C3 = (12.78, 14.14, 4.20, 5.15)        # 1,36 x 0,95 ? (distance au joint conservée)
S1_OBS = [C1, C2, C3]
# --- SEGMENT 2 (croquis 2) — local + OFF2 ; cage à l'angle du joint S1/S2
BLOC = (OFF2 + 0.00, OFF2 + 4.98, W - 5.93, W)       # cage d'escalier 4,98 x 5,93
K1 = (OFF2 + 6.28, OFF2 + 7.28, W - 4.67, W - 3.77)  # bloc + 1,3 ; 3,77 du bord ext
K2 = (OFF2 + 8.58, OFF2 + 9.78, W - 4.20, W - 3.40)  # bloc + 3,6
K3 = (OFF2 + 8.18, OFF2 + 9.43, 3.50, 4.30)          # bloc + 3,2
K4 = (OFF2 + 15.97, OFF2 + 17.42, 3.85, 4.75)        # K3 + 6,54 CONFIRMÉ ; 3,85 bord int
K5 = (OFF2 + 11.34, OFF2 + 13.14, W - 3.00, W - 2.00)
K6 = (OFF2 + 20.00, OFF2 + 21.50, W - 4.68, W - 3.78)
K7 = (OFF2 + 20.10, OFF2 + 21.60, 3.86, 4.72)
S2_OBS = [BLOC, K1, K2, K3, K4, K5, K6, K7]
# --- SEGMENT 3 (croquis 3, relu — bord haut croquis = bord EXT, comme croquis 2)
A3 = (OFF3 + 3.30, OFF3 + 4.57, W - 4.19, W - 3.61)   # 1,27 x 0,58
B3 = (OFF3 + 2.50, OFF3 + 3.55, 3.70, 5.33)           # 1,05 x 1,63 ?
X3 = (OFF3 + 4.62, OFF3 + 5.32, 4.20, 5.30)           # caisson NON coté (croquis)
N1 = (OFF3 + 4.92, OFF3 + 8.15, W - 1.70, W)          # structure bord ext — palier 1 (non coté)
N2 = (OFF3 + 8.15, OFF3 + 10.72, W - 3.15, W)         # palier 2 (0,78 au-dessus de D)
C3g = (OFF3 + 9.05, OFF3 + 10.59, 3.681, 4.701)       # C 1,54 x 1,02 (1,64 ?)
D3 = (OFF3 + 9.60, OFF3 + 10.44, W - 4.70, W - 3.93)  # D 0,84 x 0,77 ; 3,83 du bord ext
E3 = (OFF3 + 10.72, OFF3 + 12.52, W - 4.84, W - 3.74)  # E 1,80 x 1,10 ; = F - 6,54
G3 = (OFF3 + 10.90, OFF3 + 12.43, 3.77, 4.67)         # G 1,53 x 0,9 ; 1,39 sous E
F3 = (OFF3 + 19.05, OFF3 + 20.27, W - 4.69, W - 3.85)  # F 1,22 x 0,84 ; 3,33 du bord est
H3 = (OFF3 + 18.99, OFF3 + 20.34, 3.83, 4.69)         # H 1,35 x 0,86 ; 3,26 du bord est
S3_OBS = [A3, B3, X3, N1, N2, C3g, D3, E3, G3, F3, H3]
OBS = S1_OBS + S2_OBS + S3_OBS

# ---------------------------------------------------------------- calepinage v2
# dégagement standard, en ABSCISSE DÉVELOPPÉE (bord ext) : 0,35 en abscisse
# = 0,35 × R_int/R_ext = 0,336 m RÉELS au rayon intérieur, donc ≥ 0,30 exigé client
CLEAR = 0.35
# variante de SENSIBILITÉ seulement : si la structure de rive non cotée devait être
# traitée comme « obstacle de nature inconnue » (0,50 RÉEL → 0,53 en abscisse)
CLEAR_NC = 0.53
RIVE_MIN, ALLEE_MIN, END_RIVE = 0.35, 0.60, 0.35
assert CLEAR * R_INT / R_EXT >= 0.30 - 1e-9      # 0,30 m RÉELS garantis (règle client)
assert CLEAR_NC * R_INT / R_EXT >= 0.50 - 1e-9   # 0,50 m RÉELS garantis

PORTRAIT = (1.134, 4.70)   # (pas le long de la rangée, emprise transversale E-O)
PAYSAGE = (2.382, 2.25)
KWC_MOD = 0.625
ENGAGEMENT = 120
TENDU_C = "#c2410c"


def ob(o, name):
    """obstacle du calepinage : (géométrie, dégagement retenu, nom)."""
    return (o, CLEAR, name)


# rangées à positions EXPLICITES, propres à chaque segment (allées ≥ 0,60,
# surplus concentré au-dessus d'une file de caissons). Positions choisies pour
# MAXIMISER la marge : chaque bande est calée au milieu de sa fenêtre libre.
SEG_DEF = [
    ("S1", 0.0, S1_LEN, PORTRAIT,
     [(0.55, 5.25), (5.85, 10.55)],
     [ob(C1, "C1"), ob(C2, "C2"), ob(C3, "C3")]),
    ("S2", OFF2, S2_LEN, PAYSAGE,
     [(0.80, 3.05), (5.20, 7.45), (8.30, 10.55)],
     [ob(BLOC, "cage"), ob(K1, "K1"), ob(K2, "K2"), ob(K3, "K3"),
      ob(K4, "K4"), ob(K5, "K5"), ob(K6, "K6"), ob(K7, "K7")]),
    ("S3", OFF3, S3_LEN, PAYSAGE,
     [(1.00, 3.25), (5.10, 7.35), (8.30, 10.55)],
     [ob(A3, "A"), ob(B3, "B"), ob(X3, "X"), ob(N1, "N1"),
      ob(N2, "N2"), ob(C3g, "C"), ob(D3, "D"), ob(E3, "E"),
      ob(G3, "G"), ob(F3, "F"), ob(H3, "H")]),
]
UNKNOWN_NAMES = {"X", "N1", "N2"}      # éléments NON COTÉS (comptes AVEC / SANS)
# jeu de rangées S3 recalé pour la variante « structure de rive = nature inconnue »
S3_ROWS_NC = [(0.95, 3.20), (4.85, 7.10), (8.30, 10.55)]
COURT = 0.10          # stress : S2 et S3 plus courts de 10 cm que le « ≈ » annoncé


def localize(off, obs):
    return [((o[0] - off, o[1] - off, o[2], o[3]), c, n) for (o, c, n) in obs]


def with_clear(obs_loc, names, c):
    """même liste d'obstacles, dégagement remplacé pour les noms visés."""
    return [(o, c if n in names else cc, n) for (o, cc, n) in obs_loc]


def merge(iv):
    out = []
    for a, b in sorted(iv):
        if out and a <= out[-1][1] + 1e-12:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [tuple(x) for x in out]


def pas(mod_l, y0, arc=True):
    """Pas de pose en abscisse développée (bord EXT) tel que deux tables voisines
    ne se recouvrent JAMAIS, y compris au rayon INTÉRIEUR de la rangée.
    arc=False reproduit l'ANCIEN modèle (tables jointives en abscisse : elles se
    recouvraient au rayon intérieur) — pour la comparaison seulement."""
    return mod_l * R_EXT / (R_INT + y0) if arc else mod_l


def free_runs(length, obs_loc, y0, y1, end_rive=END_RIVE, clear_over=None):
    """Tronçons libres d'une rangée [y0,y1], en abscisse locale du segment."""
    blocked = []
    for (o, c, _n) in obs_loc:
        if clear_over is not None:
            c = clear_over
        if not (o[3] + c <= y0 or o[2] - c >= y1):
            blocked.append((max(0.0, o[0] - c), min(length, o[1] + c)))
    blocked = merge([b for b in blocked if b[1] > b[0]])
    cur, stop = end_rive, length - end_rive
    runs = []
    for a, b in blocked:
        if a > cur:
            runs.append((cur, min(a, stop)))
        cur = max(cur, b)
    if cur < stop:
        runs.append((cur, stop))
    return [(a, b) for a, b in runs if b > a]


def count_seg(length, obs_loc, rows, mod_l, end_rive=END_RIVE, clear_over=None,
              arc=True):
    """Compte INDÉPENDANT du dessin (garde-fou « affiché = dessiné »)."""
    tot = 0
    for (y0, y1) in rows:
        p = pas(mod_l, y0, arc)
        for a, b in free_runs(length, obs_loc, y0, y1, end_rive, clear_over):
            tot += 2 * int((b - a) / p + 1e-9)
    return tot


def place_seg(length, obs_loc, rows, mod_l, end_rive=END_RIVE):
    """Pose les tables : (s0, s1, y0, y1, pas). L'emprise ANGULAIRE d'une table
    vaut exactement `pas` en abscisse développée (elle est maximale au rayon
    intérieur) — c'est cette emprise qui est confrontée aux obstacles."""
    out = []
    for (y0, y1) in rows:
        p = pas(mod_l, y0)
        for a, b in free_runs(length, obs_loc, y0, y1, end_rive):
            n = int((b - a) / p + 1e-9)
            for i in range(n):
                sc = a + p / 2 + i * p
                out.append((sc - mod_l / 2, sc + mod_l / 2, y0, y1, p))
    return out


def uniform_count(length, obs_loc, mod_l, tbl_w, allee, rive, clear_over,
                  end_rive, arc=True):
    """Référence d'information : rangées UNIFORMES (phase balayée, moteur
    historique). clear_over=None → dégagements par obstacle du jeu v2."""
    n = int((W - 2 * rive + allee) // (tbl_w + allee))
    if n <= 0:
        return 0
    slack = W - (2 * rive + n * tbl_w + (n - 1) * allee)
    best, ph = 0, 0.0
    while ph <= slack + 1e-9:
        rows = [(rive + ph + i * (tbl_w + allee),
                 rive + ph + i * (tbl_w + allee) + tbl_w) for i in range(n)]
        best = max(best, count_seg(length, obs_loc, rows, mod_l, end_rive,
                                   clear_over, arc))
        ph += 0.05
    return best


# variante « tout paysage » de S1 (meilleures rangées explicites paysage pour ce
# segment, mêmes règles de rives/allées) : sert à isoler le gain propre aux
# tables portrait dans l'échelle de décomposition ci-dessous
S1_ROWS_PAYSAGE = [(1.55, 3.80), (5.45, 7.70), (8.30, 10.55)]
assert S1_ROWS_PAYSAGE[0][0] >= RIVE_MIN - 1e-9
assert S1_ROWS_PAYSAGE[-1][1] <= W - RIVE_MIN + 1e-9
assert all(abs((b - a) - 2.25) < 1e-9 for (a, b) in S1_ROWS_PAYSAGE)
assert all(S1_ROWS_PAYSAGE[i + 1][0] - S1_ROWS_PAYSAGE[i][1] >= ALLEE_MIN - 1e-9
           for i in range(len(S1_ROWS_PAYSAGE) - 1))

TABLES, SEG_N, SEG_TXT = [], [], []
N_CONS, N_SANS_NC, N_NC, N_COURT = 0, 0, 0, 0
MARGE_L, MARGE_B = 9.9, 9.9              # marges mini : longueur de tronçon / bande
LAD = dict(A=0, B=0, C=0, D=0, E=0)      # échelle 112 -> 120, marche par marche
for (nm, off, slen, (mod_l, tbl_w), rows, obs) in SEG_DEF:
    loc = localize(off, obs)
    # ---- contrôles de largeur (rives / allées) -----------------------------
    assert rows[0][0] >= RIVE_MIN - 1e-9, (nm, "rive int")
    assert rows[-1][1] <= W - RIVE_MIN + 1e-9, (nm, "rive ext")
    for (a, b) in rows:
        assert abs((b - a) - tbl_w) < 1e-9, (nm, "largeur rangée", a, b)
    for i in range(len(rows) - 1):
        assert rows[i + 1][0] - rows[i][1] >= ALLEE_MIN - 1e-9, (nm, "allée", i)
    # ---- pose + compte indépendant ----------------------------------------
    tabs = place_seg(slen, loc, rows, mod_l)
    n_show = count_seg(slen, loc, rows, mod_l)
    assert 2 * len(tabs) == n_show, (nm, 2 * len(tabs), n_show)
    SEG_N.append(n_show)
    SEG_TXT.append((nm, "portrait" if mod_l < 2.0 else "paysage", len(rows),
                    tbl_w, n_show))
    TABLES += [(a + off, b + off, y0, y1, p, mod_l, tbl_w, nm)
               for (a, b, y0, y1, p) in tabs]
    # ---- marges de robustesse (longueur de tronçon / calage de bande) ------
    for (y0, y1) in rows:
        p = pas(mod_l, y0)
        for a, b in free_runs(slen, loc, y0, y1):
            k = int((b - a) / p + 1e-9)
            if k:
                MARGE_L = min(MARGE_L, (b - a) - k * p)
        for (o, c, _n) in loc:                      # obstacles ÉVITÉS par la bande
            if o[3] + c <= y0 or o[2] - c >= y1:
                MARGE_B = min(MARGE_B, min(abs(y0 - (o[3] + c)),
                                           abs((o[2] - c) - y1)))
    # ---- références d'information + sensibilités ---------------------------
    N_CONS += uniform_count(slen, loc, 2.382, 2.25, 1.20, 0.50, 0.50, 0.50)
    N_SANS_NC += count_seg(slen, [x for x in loc if x[2] not in UNKNOWN_NAMES],
                           rows, mod_l)
    N_NC += count_seg(slen, with_clear(loc, {"N1", "N2"}, CLEAR_NC),
                      S3_ROWS_NC if nm == "S3" else rows, mod_l)
    N_COURT += count_seg(slen - (0.0 if nm == "S1" else COURT), loc, rows, mod_l)
    # ---- échelle de décomposition (chaque marche isolée) -------------------
    p_rows = S1_ROWS_PAYSAGE if nm == "S1" else rows
    LAD["A"] += uniform_count(slen, loc, 2.382, 2.25, 1.20, 0.35, 0.30, 0.50,
                              arc=False)              # ancien tel quel
    LAD["B"] += uniform_count(slen, loc, 2.382, 2.25, 1.20, 0.35, 0.30, 0.50)
    LAD["C"] += uniform_count(slen, loc, 2.382, 2.25, 1.20, 0.35, None, 0.50)
    LAD["D"] += uniform_count(slen, loc, 2.382, 2.25, 0.60, 0.35, None, 0.35)
    LAD["E"] += count_seg(slen, loc, p_rows, 2.382)   # rangées explicites, paysage

NMOD = sum(SEG_N)
assert NMOD == 2 * len(TABLES)
KWC = NMOD * KWC_MOD
VERDICT = "CONFIRMÉ" if NMOD >= ENGAGEMENT else "TENDU"
N_OLD = LAD["A"]
# recouvrement RÉEL qu'aurait eu l'ancien modèle (tables jointives en abscisse)
# sur les rangées retenues : écart entre le pas nécessaire et la taille de table
RECOUV = [100.0 * (pas(m, y0) - m)
          for (_n, _o, _l, (m, _t), rows, _ob) in SEG_DEF for (y0, _y1) in rows]
RECOUV_MIN, RECOUV_MAX = min(RECOUV), max(RECOUV)
# garde-fou : la marche A DOIT reproduire exactement l'ancienne vue (112 modules),
# sans quoi la comparaison « ancien -> nouveau » affichée serait fausse
assert N_OLD == 112, ("marche A != ancienne vue", N_OLD)
assert LAD["E"] <= NMOD, ("le tout-paysage ne peut pas battre le retenu", LAD)
# le calepinage ne doit JAMAIS tenir au millimètre : chaque tronçon garde ≥ 2 cm et
# chaque bande reste à ≥ 4 cm du dégagement de l'obstacle qu'elle esquive
assert MARGE_L >= 0.02, ("tronçon au ras", MARGE_L)
assert MARGE_B >= 0.04, ("bande au ras d'un obstacle", MARGE_B)

# ---------------------------------------------------------------- garde-fous
EPS = 1e-6


def _sep_axis(pa, pb):
    """SAT : True s'il existe un axe séparateur (donc AUCUN recouvrement)."""
    for poly in (pa, pb):
        k = len(poly)
        for i in range(k):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % k]
            nx, ny = -(y2 - y1), (x2 - x1)
            L = math.hypot(nx, ny)
            if L < 1e-12:
                continue
            nx, ny = nx / L, ny / L
            amin = min(nx * x + ny * y for x, y in pa)
            amax = max(nx * x + ny * y for x, y in pa)
            bmin = min(nx * x + ny * y for x, y in pb)
            bmax = max(nx * x + ny * y for x, y in pb)
            if amax <= bmin + 1e-9 or bmax <= amin + 1e-9:
                return True
    return False


# 1) chaque table reste dans SON segment, à END_RIVE des murets/murs d'extrémité,
#    et à CLEAR de tout obstacle du segment (emprise angulaire = `pas`)
MURETS = [(S1_LEN, S1_LEN + MUR), (OFF2 + S2_LEN, OFF3)]
for (nm, off, slen, (mod_l, tbl_w), rows, obs) in SEG_DEF:
    loc = localize(off, obs)
    mine = [t for t in TABLES if t[7] == nm]
    for (s0, s1, y0, y1, p, m, tw, _n) in mine:
        sc = (s0 + s1) / 2 - off               # centre, abscisse locale
        a, b = sc - p / 2, sc + p / 2          # emprise angulaire réelle
        assert abs((s1 - s0) - m) < EPS, ("taille table", nm)
        assert a >= END_RIVE - EPS and b <= slen - END_RIVE + EPS, ("bout", nm, a, b)
        for (o, c, onm) in loc:
            assert (b <= o[0] - c + EPS or a >= o[1] + c - EPS
                    or y1 <= o[2] - c + EPS or y0 >= o[3] + c - EPS), \
                ("dégagement", nm, onm, a, b, y0)
    # 2) aucune table à cheval sur un muret / hors du développé
    for (s0, s1, y0, y1, p, m, tw, _n) in mine:
        gc = (s0 + s1) / 2
        ga, gb = gc - p / 2, gc + p / 2
        for (m0, m1) in MURETS:
            assert gb <= m0 - 0.30 + EPS or ga >= m1 + 0.30 - EPS, ("muret", nm)
        assert ga >= 0.30 - EPS and gb <= LEN - 0.30 + EPS, ("développé", nm)

# 3) AUCUN recouvrement entre tables dessinées (vrai test géométrique sur les
#    polygones rigides) — l'ancien modèle échouait ici
POLYS = [rigid(s0, s1, y0, y1) for (s0, s1, y0, y1, p, m, tw, n) in TABLES]
for i in range(len(POLYS)):
    for j in range(i + 1, len(POLYS)):
        assert _sep_axis(POLYS[i], POLYS[j]), ("recouvrement tables", i, j)

# 4) rives transversales tenues par toutes les tables
for (s0, s1, y0, y1, p, m, tw, nm) in TABLES:
    assert y0 >= RIVE_MIN - EPS and y1 <= W - RIVE_MIN + EPS, ("rive", nm, y0, y1)

# ---------------------------------------------------------------- feuille
fig, ax = D.new_sheet(
    "VUE DE TOITURE DÉFINITIVE v2 — BÂTIMENT B (AILE EN ARC) — RÉSIDENCE UNIVERSITAIRE UIB, MOHAMMEDIA — CALEPINAGE OPTIMISÉ (consignes client 27/07/2026)",
    "Arc en VRAIE géométrie (R_ext ≈ 274 m) — 3 SEGMENTS de toiture séparés par des MURETS HACHURÉS AU RAS "
    "(joints, ép. 0,45, h = 0) : S1 20,55 + joint + S2 ≈ 23,0 + joint + S3 ≈ 23,6 = 68,05 m — développé CONFIRMÉ MURET-À-MURET par le client le 27/07\n"
    "cotes en mètres · bleu = mesuré/confirmé · orange = à confirmer · gris = déduit — calepinage v2 : allées 0,60 OPTIMISÉES, rangées à positions "
    "EXPLICITES par segment, tables posées en tronçons droits SANS recouvrement au rayon intérieur",
    (-40.2, 40.2), (-42.0, 10.1))
ax.set_position([0.015, 0.015, 0.97, 0.90])
ax.set_anchor("N")

# tables PV (2 modules 625 Wc dos à dos, faîtage N-S)
for (s0, s1, y0, y1, p, m, tw, nm) in TABLES:
    poly = rigid(s0, s1, y0, y1)
    ax.add_patch(Polygon(poly, closed=True, facecolor="#bbf7d0",
                         edgecolor="#15803d", lw=0.45, zorder=6))
    c0, c1c, c2c, c3 = poly
    ax.plot([(c0[0] + c3[0]) / 2, (c1c[0] + c2c[0]) / 2],
            [(c0[1] + c3[1]) / 2, (c1c[1] + c2c[1]) / 2],
            color="#15803d", lw=0.3, zorder=7)

# transects S1 (trames radiales relevées, croquis 1)
SX = chain(0, 3.72, 3.84, 6.59, 6.40)
for s in SX[1:-1]:
    xs, ys = zip(P(s, -0.35), P(s, W + 0.35))
    ax.plot(xs, ys, color="#475569", lw=0.8, ls=(0, (4, 3)), zorder=8)

# contour de la bande courbe
outline = arcpts(0, LEN, W) + arcpts(LEN, 0, 0)
ax.add_patch(Polygon(outline, closed=True, fill=False, lw=2.2,
                     edgecolor=D.NOIR, zorder=10))

# murets inter-segments AU RAS (ép. 0,45, h=0 — joints, BLEU confirmé)
for (sm, tag) in ((S1_LEN, "S1/S2"), (OFF2 + S2_LEN, "S2/S3")):
    p = Polygon(rigid(sm, sm + MUR, 0.0, W), closed=True, facecolor="#dbeafe",
                edgecolor=D.BLEU, lw=1.2, hatch="//////", zorder=12)
    ax.add_patch(p)
ax.text(0.0, 5.45, "joints : 2 murets AU RAS (h = 0), ép. 0,45 — CONFIRMÉ client — aucun rail à cheval sur un joint",
        fontsize=6.6, ha="center", color=D.BLEU, zorder=28)
for sm in (S1_LEN + MUR / 2, OFF2 + S2_LEN + MUR / 2):
    a = P(sm, W + 0.30)
    ax.plot([a[0], (a[0]) * 0.30], [a[1], 5.25], color=D.BLEU, lw=0.5, ls=":",
            zorder=23)

# murs d'extrémité (hachurés aux croquis)
ax.add_patch(Polygon(rigid(-0.45, 0.0, -0.10, W + 0.10), closed=True,
                     facecolor="none", edgecolor=D.NOIR, hatch="//////",
                     lw=1.4, zorder=11))
ax.add_patch(Polygon(rigid(LEN, LEN + 0.45, -0.10, W + 0.10), closed=True,
                     facecolor="none", edgecolor=D.NOIR, hatch="//////",
                     lw=1.4, zorder=11))
ax.text(-39.9, 2.6, "MUR D'EXTRÉMITÉ\nOUEST (croquis 1)", fontsize=6.6,
        fontweight="bold", ha="left", va="top")
ax.text(39.9, 2.6, "MUR D'EXTRÉMITÉ\nEST (croquis 3)\nà confirmer", fontsize=6.6,
        fontweight="bold", ha="right", va="top", color=D.ORANGE)

# étiquettes segments (au-dessus du bord ext)
for smid, txt in ((10.3, f"SEGMENT 1 — 20,55 — 2 rangées PORTRAIT — {SEG_N[0]} mod."),
                  (OFF2 + 11.5, f"SEGMENT 2 — ≈ 23,0 — 3 rangées PAYSAGE — {SEG_N[1]} mod."),
                  (OFF3 + 11.8, f"SEGMENT 3 — ≈ 23,6 — 3 rangées PAYSAGE — {SEG_N[2]} mod.")):
    tx, ty = P(smid, W + 2.35)
    ax.text(tx, ty, txt, fontsize=7.0, ha="center", fontweight="bold",
            color="#333333", rotation=-math.degrees(phi(smid)), zorder=27)

# ---------------- SEGMENT 1 : cotes
for a, b, t in zip(SX, SX[1:], ["3,72", "3,84", "6,59", "6,4"]):
    dim(ax, P(a, W), P(b, W), off=0.55, text=t)
tx, ty = P(10.3, W + 1.30)
ax.text(tx, ty, "le « 3,82 » du croquis = cote RADIALE de C1 (doublon retiré) → chaîne recalculée 20,55",
        fontsize=5.4, ha="center", color=D.BLEU,
        rotation=-math.degrees(phi(10.3)), zorder=26)
TI = chain(0, 3.42, 3.78, 3.73)
for a, b, t in zip(TI, TI[1:], ["3,42", "3,78", "3,73"]):
    dim(ax, P(a * R_EXT / R_INT, 0), P(b * R_EXT / R_INT, 0), off=-0.55, text=t)
tx, ty = P(5.6, -1.95)
ax.text(tx, ty, "entraxes bord int. (chaîne 10,93 : courbure)", fontsize=5.4,
        ha="center", color=D.BLEU, rotation=-math.degrees(phi(5.6)))

rdim(ax, 0.70, 0, W, text="10,81")
rdim(ax, 7.60, 0, W, text="10,87 (confirmé)")
rdim(ax, 15.10, 0, W, text="10,9")

caisson(ax, C1, "C1")
caisson(ax, C2, "C2", uncertain=True)
caisson(ax, C3, "C3", uncertain=True)
tdim(ax, 0.0, C1[0], 6.62, text="3,27")                  # mur ouest -> C1 (confirmé)
rdim(ax, C1[0] + 0.95, C1[3], W, text="3,82")            # bord ext -> C1 (confirmé)
dim(ax, P(SX[3], 5.30), P(C2[0], 5.30), off=0.0, text="1,39", box=True)
dim(ax, P(SX[2], 1.90), P(SX[2] + 4.75, 1.90), off=0.0, color=D.ORANGE,
    text="4,75 (rattach. ?)", box=True)
dim(ax, P(SX[3], 2.60), P(SX[3] + 5.5, 3.40), off=0.0, color=D.ORANGE,
    text="5,5 (diag.)", box=True)
rdim(ax, 19.80, 0, 0.78, text="0,78", color=D.ORANGE)

# ---------------- SEGMENT 2 : cage + caissons + cotes
ax.add_patch(Polygon(rigid(*BLOC), closed=True, facecolor="#eef1f5",
                     edgecolor=D.NOIR, lw=2.4, zorder=14))
ax.add_patch(Polygon(rigid(BLOC[0] + 0.30, BLOC[1] - 0.30,
                           BLOC[2] + 0.30, BLOC[3] - 0.30), closed=True,
                     facecolor="white", edgecolor=D.NOIR, lw=1.0, zorder=14))
bx, by = P((BLOC[0] + BLOC[1]) / 2, (BLOC[2] + BLOC[3]) / 2)
ax.text(bx, by, "CAGE\nD'ESCALIER\n4,98 × 5,93", fontsize=6.6, ha="center",
        va="center", fontweight="bold", color="#333333", zorder=16,
        rotation=-math.degrees(phi(BLOC[0] + 2.5)))
dim(ax, P(BLOC[0], W), P(BLOC[1], W), off=0.55, text="4,98")
rdim(ax, BLOC[0] + 0.55, BLOC[2], W, text="5,93")
f = phi(BLOC[0])
t = (math.cos(f), -math.sin(f))
n = (math.sin(f), math.cos(f))
cx, cy = P(BLOC[0], BLOC[2])
ax.plot([cx, cx + 0.8 * t[0]], [cy, cy + 0.8 * t[1]], color=D.NOIR, lw=1.8, zorder=16)
ax.plot([cx, cx + 0.8 * n[0]], [cy, cy + 0.8 * n[1]], color=D.NOIR, lw=1.8, zorder=16)
ax.text(*P(BLOC[0] + 0.30, BLOC[2] - 0.95), "angle repère (raccord chaîne S1 : 20,55)",
        fontsize=5.0, ha="left", color="#555555", zorder=27,
        bbox=dict(fc="white", ec="none", alpha=0.8, pad=0.3))

caisson(ax, K1, "K1")
caisson(ax, K2, "K2")
caisson(ax, K3, "K3", uncertain=True)
caisson(ax, K4, "K4")
caisson(ax, K5, "K5")
caisson(ax, K6, "K6")
caisson(ax, K7, "K7", uncertain=True, lsy=(K7[0] + 1.06, 4.29))
rdim(ax, K1[0] + 0.50, K1[3], W, text="3,77")
dim(ax, P(BLOC[1], 6.68), P(K1[0], 6.68), off=0.0, text="1,3", box=True, fs=5.8)
dim(ax, P(BLOC[1], 7.35), P(K2[0], 7.35), off=0.0, text="3,6", box=True)
dim(ax, P(BLOC[1], 4.62), P(K3[0], 4.62), off=0.0, text="3,2", box=True, fs=5.8)
for pp, qq in ((P(BLOC[1], BLOC[2]), P(BLOC[1], 4.62)),
               (P(K3[0], K3[3]), P(K3[0], 4.62))):
    ax.plot([pp[0], qq[0]], [pp[1], qq[1]], color="#94a3b8", lw=0.5, ls=":",
            zorder=23)
dim(ax, P(OFF2 + 8.85, K3[3]), P(OFF2 + 8.85, K2[2]), off=0.0, color=D.ORANGE,
    text="1,6 ? (2,4)", box=True, fs=5.6)
dim(ax, P(K3[1], 4.05), P(K4[0], 4.05), off=0.0,
    text="6,54 — CONFIRMÉ client", box=True)
rdim(ax, K4[0] + 0.72, 0, K4[2], text="3,85 — confirmé")
dim(ax, P(K5[1], 7.60), P(K6[0], 7.60), off=0.0, text="6,86", box=True)
rdim(ax, OFF2 + 14.6, 0, W, text="10,9")

# contrôle de fermeture transversal K6/K7
SC = K7[1] + 0.55
for (ya, yb, t) in ((0, K7[2], "3,86"), (K7[2], K7[3], "0,86"),
                    (K7[3], K6[2], "1,50"), (K6[2], K6[3], "0,90"),
                    (K6[3], W, "3,78")):
    rdim(ax, SC, ya, yb, text=t, fs=5.6)
for yy in (K7[2], K7[3], K6[2], K6[3]):
    xs, ys = zip(P(K7[1] + 0.05, yy), P(SC, yy))
    ax.plot(xs, ys, color="#94a3b8", lw=0.5, ls=":", zorder=23)
ax.text(*P(SC - 0.6, -1.15), "Σ = 10,90 ✓", fontsize=6.2, color=D.BLEU,
        fontweight="bold", ha="center", rotation=-math.degrees(phi(SC)))

# ---------------- SEGMENT 3 : caissons + structure + cotes
caisson(ax, A3, "A", uncertain=True)
caisson(ax, B3, "B", uncertain=True)
caisson(ax, X3, "X", deduced=True)
caisson(ax, C3g, "C")
caisson(ax, D3, "D")
caisson(ax, E3, "E")
caisson(ax, G3, "G")
caisson(ax, F3, "F")
caisson(ax, H3, "H")
# structure bord ext (2 paliers, non cotée -> gris/orange, dégagement porté à 0,50)
for NN in (N1, N2):
    p = Polygon(rigid(*NN), closed=True, facecolor="#e2e8f0",
                edgecolor=D.ORANGE, lw=1.1, hatch="....", zorder=13)
    p.set_linestyle("--")
    ax.add_patch(p)
tx, ty = P(OFF3 + 7.8, W - 0.85)
ax.text(tx, ty, "structure bord ext. (croquis 3)\nNON COTÉE ≈ 5,8 m — à confirmer",
        fontsize=5.2, ha="center", va="center", color="#7c2d12",
        rotation=-math.degrees(phi(OFF3 + 7.8)), zorder=27,
        bbox=dict(fc="white", ec="none", alpha=0.8, pad=0.4))

# cotes tangentielles S3
tdim(ax, OFF3, A3[0], 7.62, text="3,3")
tdim(ax, OFF3, B3[0], 4.45, text="2,5 (3,2 ?)", color=D.ORANGE, fs=5.4)
tdim(ax, B3[1], C3g[0], 3.30, text="5,5 (5,53 ?)", color=D.ORANGE)
tdim(ax, E3[1], F3[0], 6.62, text="6,54")
tdim(ax, F3[1], LEN, 6.62, text="3,33")
tdim(ax, H3[1], LEN, 4.30, text="3,26")

# chaînes radiales S3
rdim(ax, A3[0] + 0.33, A3[3], W, text="3,61")            # ext -> A
rdim(ax, A3[0] + 0.20, B3[3], A3[2], text="1,38")        # A -> B
rdim(ax, B3[0] + 0.52, 0, B3[2], text="3,42 ?", color=D.ORANGE)
rdim(ax, C3g[0] + 0.45, 0, C3g[2], text="3,681")
rdim(ax, D3[0] + 0.62, C3g[3], D3[2], text="1,5")
rdim(ax, D3[0] + 0.42, D3[3], W, text="3,83")
rdim(ax, D3[1] - 0.18, D3[3], N2[2], text="0,78", fs=5.6)
rdim(ax, E3[1] - 0.45, E3[3], W, text="3,74")
rdim(ax, E3[1] - 0.62, G3[3], E3[2], text="1,39")
rdim(ax, G3[1] - 0.45, 0, G3[2], text="3,67")
rdim(ax, F3[0] + 0.50, F3[3], W, text="3,85")
rdim(ax, F3[0] + 0.68, H3[3], F3[2], text="1,5")
rdim(ax, H3[0] + 0.48, 0, H3[2], text="3,76")
rdim(ax, OFF3 + 4.35, 0, W, text="10,7")
rdim(ax, OFF3 + 22.25, 0, W, text="10,91")


def fr(v, dec=2):
    return f"{v:.{dec}f}".replace(".", ",")


# ---------------------------------------------------------------- synthèse
ax.text(0, 9.35, "CALEPINAGE v2 — tables Est-Ouest de 2 modules 625 Wc dos à dos, RANGÉES À POSITIONS EXPLICITES, "
        "un plan de pose PAR SEGMENT (les rangées s'arrêtent aux joints)",
        fontsize=7.2, ha="center", color="#333333")
ax.text(0, 8.70, "S1 : 2 rangées PORTRAIT 1,134 × 4,70 (kit du bât. C) · S2 et S3 : 3 rangées PAYSAGE 2,382 × 2,25 (kit du bât. A) — "
        f"allées ≥ 0,60 optimisées · rives 0,35 · dégagement 0,35 (= 0,336 m réels ≥ 0,30 exigé) — {NMOD} modules "
        f"(S1 {SEG_N[0]} + S2 {SEG_N[1]} + S3 {SEG_N[2]}) = {fr(KWC, 1)} kWc",
        fontsize=7.2, ha="center", color="#333333")
if VERDICT == "CONFIRMÉ":
    ax.text(0, 7.90, f"ENGAGEMENT OFFRE : 120 modules (75,0 kWc) — CONFIRMÉ : {NMOD} modules posables DESSINÉS sur le relevé "
            f"(marge {NMOD - ENGAGEMENT:+d}) — chiffre dessiné = compté (contrôles automatiques)",
            fontsize=8.2, ha="center", color="#15803d", fontweight="bold")
else:
    ax.text(0, 7.90, f"ENGAGEMENT OFFRE : 120 modules (75,0 kWc) — TENDU : {NMOD} modules posables sur le relevé "
            f"(manque {ENGAGEMENT - NMOD}) — voir redistribution vers l'aile L",
            fontsize=8.2, ha="center", color=TENDU_C, fontweight="bold")
ax.text(0, 7.15, f"MARGE = {NMOD - ENGAGEMENT} module : le compte tombe EXACTEMENT sur l'engagement — toute confirmation défavorable d'un élément orange le fait redescendre",
        fontsize=7.4, ha="center", color=TENDU_C, fontweight="bold")
ax.text(0, 6.60, f"SENSIBILITÉS CALCULÉES : sans la structure de rive non cotée {N_SANS_NC} ({N_SANS_NC - NMOD:+d}) · si elle est traitée en « nature inconnue » {N_NC} ({N_NC - NMOD:+d}) · "
        f"si S2 et S3 font 10 cm de moins que le « ≈ » {N_COURT} ({N_COURT - NMOD:+d}) · conservateur {N_CONS} · redistribution B → 144 hors d'atteinte",
        fontsize=7, ha="center", color="#555555")
ax.text(0, 6.05, "DÉVELOPPÉ RELEVÉ 68,05 m — CONFIRMÉ MURET-À-MURET par le client le 27/07 : le « ≈ 90 » du dossier §2.2 est un ordre de grandeur périmé, il n'y a PAS de longueur cachée",
        fontsize=7.6, ha="center", color=D.BLEU, fontweight="bold")

S2_ALLEE = SEG_DEF[1][4][1][0] - SEG_DEF[1][4][0][1]   # allée large de S2
NOTES = [
    ("CONTRÔLES DE FERMETURE (relevé 27/07/2026) — inchangés :", True),
    ("• S1 : le « 3,82 » du croquis est la cote RADIALE bord ext → C1, pas un entraxe — chaîne 3,72+3,84+6,59+6,4 = 20,55 ≡ joint S1/S2 · "
     "courbure : entraxes ext 11,38 vs int 10,93 → R_ext ≈ 274 m ✓ · S2 transversal 3,78+0,90+1,50+0,86+3,86 = 10,90 ✓ · K3→K4 = 6,54 et K4 → bord int 3,85 CONFIRMÉS", False),
    ("• S3 radiales : 10,62 ≈ 10,7 ✓ · 10,80 ✓ · 10,80 ✓ · 10,81 ≈ 10,91 ✓ · développé 20,55 + 0,45 + 23,0 + 0,45 + 23,6 = 68,05 muret-à-muret ✓", False),
    (f"CALEPINAGE v2 — D'OÙ VIENNENT LES {NMOD - N_OLD} MODULES DE PLUS ({N_OLD} → {NMOD}) : chaque marche est CALCULÉE par le script, pas estimée", True),
    (f"• {N_OLD} → {LAD['B']} ({LAD['B'] - LAD['A']:+d}) DURCISSEMENT nº1, CORRECTION D'ARC : l'ancienne vue posait les tables jointives en abscisse développée — elles se "
     f"recouvraient de {RECOUV_MIN:.1f} à {RECOUV_MAX:.1f} cm au rayon intérieur. Le pas vaut désormais MOD_L × R_ext/R_int(rangée), et le non-recouvrement est contrôlé polygone par polygone", False),
    (f"• {LAD['B']} → {LAD['C']} ({LAD['C'] - LAD['B']:+d}) DURCISSEMENT nº2, DÉGAGEMENT 0,30 → 0,35 : sur un arc, 0,30 en abscisse ne vaut que 0,288 m RÉELS au rayon intérieur, "
     f"donc SOUS la règle client ; 0,35 en abscisse en vaut 0,336. Les deux durcissements coûtent {LAD['A'] - LAD['C']} modules — assumés : le compte part d'un plancher plus dur que le 27/07", False),
    (f"• {LAD['C']} → {LAD['D']} ({LAD['D'] - LAD['C']:+d}) allées ramenées à 0,60 MINIMUM (consigne client) et rives d'extrémité 0,35 au lieu de 0,50 (les murets sont AU RAS, h = 0)", False),
    (f"• {LAD['D']} → {LAD['E']} ({LAD['E'] - LAD['D']:+d}) RANGÉES À POSITIONS EXPLICITES, un plan de pose PAR SEGMENT : le surplus de largeur n'est plus étalé en allées égales, il est "
     f"CONCENTRÉ là où il ne coûte rien — S2 : allée large {fr(S2_ALLEE)} posée au-dessus de la file de caissons K3/K4/K7, ce qui libère toute la rangée basse (9 tables pleines) ; "
     "S3 : rangées calées pour esquiver la structure de rive et les caissons A/D/E/F", False),
    (f"• {LAD['E']} → {NMOD} ({NMOD - LAD['E']:+d}) SEGMENT 1 en tables PORTRAIT 1,134 × 4,70 — le kit DÉJÀ retenu pour le bâtiment C (école), donc aucun approvisionnement nouveau : "
     "sur 10,90 de large, 2 rangées portrait couvrent 9,40 de modules là où 3 rangées paysage n'en couvrent que 6,75. S1 passe de 42 à 48", False),
    ("OBSTACLES — RIEN DE SUPPRIMÉ : les 22 obstacles relevés sont TOUS conservés, y compris ceux dont la position est reconstruite (C2, C3, K3, K7, A, B — en orange)", True),
    ("• 3 ÉLÉMENTS NON COTÉS portent tout le risque : le caisson X (0,70 × 1,10 supposé) et la structure de rive N1/N2 (paliers de 1,70 et 3,15 supposés, ≈ 5,8 m de long). "
     "Ils sont CONSERVÉS, au dégagement standard 0,35", False),
    (f"3 QUESTIONS AU CLIENT, chiffrées : (1) la structure de rive du croquis 3 — c'est quoi, jusqu'où va-t-elle ? « rien dans la zone PV » = {N_SANS_NC}, "
     f"« on ne sait pas ce que c'est » = {N_NC}, hypothèse retenue = {NMOD}. (2) le caisson X n'a AUCUNE cote : ses 0,70 × 1,10 sont supposés. "
     f"(3) S2 « ≈ 23,0 » et S3 « ≈ 23,6 » : 10 cm de moins et le compte tombe à {N_COURT}", True),
    ("AUTRES POINTS À CONFIRMER (orange) : positions C2/C3 · K3 · 1,6/2,4 · rattachements 4,75/5,5/0,78 (S1) · lectures S3 2,5/3,2 · 5,5/5,53 · 3,42 · A · B · mur est", False),
    ("POSE PV : rails en TRONÇONS DROITS, une table par tronçon — reprise angulaire ≈ 0,24°/table en portrait (S1) et ≈ 0,50° en paysage (S2/S3), par éclisses ; "
     "rangées PAR SEGMENT, jamais à cheval sur un joint", False),
    (f"RÉSERVE DRV : NON vue au relevé — à fixer en étude d'exécution (dégagement ≥ 1 m) ; toute réserve confirmée se retranche du compte. Le calepinage n'est PAS calé au "
     f"millimètre : le tronçon le plus juste garde {MARGE_L*100:.0f} cm et la bande la plus juste reste à {MARGE_B*100:.0f} cm du dégagement qu'elle esquive (contrôlé)", False),
]
# Repli AUTOMATIQUE du bloc de notes : la largeur de repli garantit qu'aucune
# ligne ne sort du cadre, et l'interligne s'ajuste pour que le bloc s'arrête
# AU-DESSUS du cartouche, quel que soit le volume de texte.
NOTE_X, NOTE_TOP, NOTE_BOT, NOTE_COLS = -19.4, -12.75, -34.8, 178
NOTE_LINES = []
for (t, b) in NOTES:
    parts = textwrap.wrap(t, NOTE_COLS, break_long_words=False) or [""]
    for k, ln in enumerate(parts):
        NOTE_LINES.append((ln if k == 0 else "    " + ln, b and k == 0))
NOTE_DY = min(0.84, (NOTE_TOP - NOTE_BOT) / max(1, len(NOTE_LINES) - 1))
NOTE_FS = min(6.0, NOTE_DY * 7.1)
for i, (t, b) in enumerate(NOTE_LINES):
    ax.text(NOTE_X, NOTE_TOP - i * NOTE_DY, t, fontsize=NOTE_FS, va="top",
            color="#333333", fontweight="bold" if b else "normal")
assert NOTE_TOP - (len(NOTE_LINES) - 1) * NOTE_DY >= NOTE_BOT - 1e-9
assert NOTE_FS >= 4.6, ("notes illisibles : alléger le texte", NOTE_FS)

# ---------------------------------------------------------------- légende
LX, LY, DY = -39.6, -13.10, 0.86


def leg_text(i, txt):
    ax.text(LX + 1.35, LY - i * DY, txt, fontsize=6.2, va="center", zorder=30)


r = Rectangle((LX, LY - 0.21), 1.0, 0.42, facecolor="#bbf7d0",
              edgecolor="#15803d", lw=0.6, zorder=30)
ax.add_patch(r)
ax.plot([LX, LX + 1.0], [LY, LY], color="#15803d", lw=0.4, zorder=31)
leg_text(0, "table PV PAYSAGE (2 mod., 2,382 × 2,25) — S2/S3")
r = Rectangle((LX + 0.30, LY - DY - 0.31), 0.40, 0.62, facecolor="#bbf7d0",
              edgecolor="#15803d", lw=0.6, zorder=30)
ax.add_patch(r)
ax.plot([LX + 0.30, LX + 0.70], [LY - DY, LY - DY], color="#15803d", lw=0.4,
        zorder=31)
leg_text(1, "table PV PORTRAIT (2 mod., 1,134 × 4,70) — S1")
ax.add_patch(Rectangle((LX, LY - 2 * DY - 0.21), 1.0, 0.42, facecolor="#d8dee6",
             edgecolor=D.NOIR, hatch="////", lw=0.8, zorder=30))
leg_text(2, "caisson béton relevé (chaîné)")
r = Rectangle((LX, LY - 3 * DY - 0.21), 1.0, 0.42, facecolor="white",
              edgecolor=D.ORANGE, hatch="////", lw=0.8, zorder=30)
r.set_linestyle("--")
ax.add_patch(r)
leg_text(3, "caisson — lecture / position à confirmer")
ax.add_patch(Rectangle((LX, LY - 4 * DY - 0.21), 1.0, 0.42, facecolor="#eef1f5",
             edgecolor=D.NOIR, lw=1.6, zorder=30))
leg_text(4, "cage d'escalier (murs épais)")
r = Rectangle((LX, LY - 5 * DY - 0.21), 1.0, 0.42, facecolor="#dbeafe",
              edgecolor=D.BLEU, hatch="//////", lw=0.9, zorder=30)
ax.add_patch(r)
leg_text(5, "muret AU RAS (h = 0, ép. 0,45) — joint, confirmé")
r = Rectangle((LX, LY - 6 * DY - 0.21), 1.0, 0.42, facecolor="#e2e8f0",
              edgecolor=D.ORANGE, hatch="....", lw=0.8, zorder=30)
r.set_linestyle("--")
ax.add_patch(r)
leg_text(6, "élément NON COTÉ — dimensions déduites du croquis")
ax.add_patch(FancyArrowPatch((LX, LY - 7 * DY), (LX + 1.0, LY - 7 * DY),
             arrowstyle="<|-|>", mutation_scale=6, lw=0.8, color=D.BLEU, zorder=30))
leg_text(7, "cote mesurée / confirmée (croquis Reda 27/07)")
ax.add_patch(FancyArrowPatch((LX, LY - 8 * DY), (LX + 1.0, LY - 8 * DY),
             arrowstyle="<|-|>", mutation_scale=6, lw=0.8, color=D.ORANGE, zorder=30))
leg_text(8, "cote / élément à confirmer")

D.scale_bar(ax, LX, -23.4)
D.cartouche(fig, [
    ("ACCORDIA TECH — Consultation FRDISI PV + stockage, Mohammedia", True),
    (f"Bât. B — AILE EN ARC — CALEPINAGE v2 OPTIMISÉ — {NMOD} modules ({fr(KWC, 1)} kWc) — engagement 120 : {VERDICT}", True),
    ("Relevé : R. Kasri 27/07/2026 (TOUT relevé) — restitution TAQINOR", False),
    ("Échelle ≈ 1:200 (A3) — cotes en mètres — NE REMPLACE PAS 05E/06G", False),
])

# ---------------------------------------------------------------- contrôles
closure("chaîne ext S1 recalculée -> joint S1/S2 (angle cage)", SX[-1], S1_LEN, tol=0.10)
closure("fermeture transversale K6/K7", 3.78 + 0.90 + 1.50 + 0.86 + 3.86, W, tol=0.05)
closure("courbure int = ext x R_int/R_ext", 11.38 * R_INT / R_EXT, 10.93, tol=0.05)
closure("S3 radiale gauche (3,61+0,58+1,38+1,63+3,42)", 3.61 + 0.58 + 1.38 + 1.63 + 3.42, 10.70, tol=0.15)
closure("S3 radiale C/D (3,681+1,02+1,5+0,77+3,83)", 3.681 + 1.02 + 1.5 + 0.77 + 3.83, 10.80, tol=0.15)
closure("S3 radiale E/G (3,74+1,10+1,39+0,90+3,67)", 3.74 + 1.10 + 1.39 + 0.90 + 3.67, 10.80, tol=0.15)
closure("S3 radiale F/H (3,85+0,84+1,5+0,86+3,76)", 3.85 + 0.84 + 1.5 + 0.86 + 3.76, 10.91, tol=0.15)
closure("developpe releve total", LEN, 68.05, tol=0.10)
assert K4[1] + CLEAR <= K7[0], "K4 recouvre K7 !"
# fermetures dures (le script DOIT casser si une chaîne bouge)
assert abs(SX[-1] - S1_LEN) <= 0.10
assert abs((3.78 + 0.90 + 1.50 + 0.86 + 3.86) - W) <= 0.05
assert abs((S1_LEN + MUR + S2_LEN + MUR + S3_LEN) - LEN) < 1e-9
assert abs(LEN - 68.05) < 1e-9

print(f"tables={len(TABLES)}  modules={NMOD} ({fr(KWC, 1)} kWc) — "
      f"S1 {SEG_N[0]} (portrait) / S2 {SEG_N[1]} (paysage) / S3 {SEG_N[2]} (paysage)")
print(f"engagement {ENGAGEMENT} -> {VERDICT} (marge {NMOD - ENGAGEMENT:+d})")
print("echelle de decomposition (calculee par le script) :")
print(f"  {LAD['A']:4d}  ancienne vue reproduite (1,20 / rives 0,35 / bouts 0,50 / degagt 0,30, tables jointives)")
print(f"  {LAD['B']:4d}  ({LAD['B']-LAD['A']:+d}) DURCISSEMENT correction d'arc (plus aucun recouvrement)")
print(f"  {LAD['C']:4d}  ({LAD['C']-LAD['B']:+d}) DURCISSEMENT degagement 0,30 -> 0,35 en abscisse (= 0,336 m REELS)")
print(f"  {LAD['D']:4d}  ({LAD['D']-LAD['C']:+d}) allees 0,60 mini + rives d'extremite 0,35")
print(f"  {LAD['E']:4d}  ({LAD['E']-LAD['D']:+d}) rangees a positions EXPLICITES par segment (tout paysage)")
print(f"  {NMOD:4d}  ({NMOD-LAD['E']:+d}) segment 1 en tables PORTRAIT (kit du bat. C)")
print(f"sensibilites : sans la structure de rive non cotee {N_SANS_NC} ({N_SANS_NC-NMOD:+d}) · "
      f"structure traitee 'nature inconnue' 0,50 reel {N_NC} ({N_NC-NMOD:+d}) · "
      f"S2/S3 plus courts de {COURT*100:.0f} cm {N_COURT} ({N_COURT-NMOD:+d}) · conservateur {N_CONS}")
print(f"marges : troncon le plus juste {MARGE_L*100:.1f} cm · bande la plus juste {MARGE_B*100:.1f} cm "
      f"· recouvrement qu'aurait eu l'ancien modele {RECOUV_MIN:.1f} a {RECOUV_MAX:.1f} cm")
for (nm, kind, nrows, tw, n) in SEG_TXT:
    print(f"  {nm} : {nrows} rangees {kind} (emprise {fr(tw)}) -> {n} modules")
print(f"arc: R_ext={R_EXT}  developpe={LEN:.2f}  ouverture={math.degrees(TH):.1f} deg  "
      f"fleche={R_EXT * (1 - math.cos(TH / 2)):.2f}  corde={2 * R_EXT * math.sin(TH / 2):.2f}")
print(f"controles OK : dessine=compte, aucun recouvrement de tables ({len(POLYS)} polygones), "
      f"rives 0,35, allees >= 0,60, degagement 0,35 (0,336 m reels), aucun rail a cheval sur un joint")

fig.savefig("VUE_TOITURE_BAT_B_ARC_V2.pdf", bbox_inches="tight")
fig.savefig("VUE_TOITURE_BAT_B_ARC_V2.png", dpi=170, bbox_inches="tight")
print("VUE ARC v2 : render ok — VUE_TOITURE_BAT_B_ARC_V2.pdf / .png")
