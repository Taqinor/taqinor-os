# -*- coding: utf-8 -*-
"""AOF183 — RÉCONCILIATION des goldens FRDISI (et non une simple extraction).

**Risque n°1 du périmètre.** Si l'extraction du relevé vers JSON introduit une
erreur silencieuse, le golden VERROUILLE l'erreur pour toujours et le moteur
« prouve » un chiffre faux — le pire résultat possible pour un moteur dont
l'argument de vente EST la preuve.

Ce script ne convertit donc pas : il RÉCONCILIE. Il exécute côte à côte

* le comptage des scripts TÉMOINS du 27/07/2026 (transcription littérale de
  ``vue_bat_A_v2.py`` / ``vue_bat_B_v2.py`` / ``vue_bat_C.py``, partie
  comptage seule — leur partie dessin dépend de matplotlib et n'entre pas
  ici), et
* le moteur neuf ``core.calepinage``,

et exige l'ÉGALITÉ AU MODULE PRÈS avant d'écrire ou de valider un golden.

Il vérifie aussi que les scripts témoins sont INCHANGÉS (empreintes SHA-256
ci-dessous) : ``docs/ao-frdisi/`` est GELÉ, c'est le témoin.

Usage ::

    python scripts/reconcilier_calepinage_frdisi.py            # vérifie
    python scripts/reconcilier_calepinage_frdisi.py --ecrire   # régénère
"""

import argparse
import hashlib
import io
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "backend", "django_core"))

TEMOINS = os.path.join(RACINE, "docs", "ao-frdisi", "releve-2026-07-27")
GOLDEN = os.path.join(RACINE, "backend", "django_core", "core", "calepinage",
                      "golden", "frdisi_2026_07_27")

#: Empreintes des scripts TÉMOINS — ils ne doivent JAMAIS changer.
EMPREINTES_TEMOINS = (
    ("vue_bat_A_v2.py",
     "67d58c58aece0613e6decf7acb00513c9375c1614378fd3d501182e5595e8f9a"),
    ("vue_bat_B_v2.py",
     "1fdac754478b787ba030d0dc7ab1467979c1840bc724827cb46947b221168292"),
    ("vue_bat_C.py",
     "d38f43aa2c2656a188f5185beb5d27868b904e56f78872c698b2b5608d776e21"),
    ("calepinage.py",
     "50e8d588a4aea2aab6ba3123b156a668506404aaad0c4984653391747e77d546"),
    ("solveur.py",
     "887cb1187ccbbace867ed6d240f09e292c6317704bc0a90f4c8a3ae4149baf1a"),
)


# =====================================================================
# 1. TÉMOINS — transcription LITTÉRALE du comptage des scripts d'origine
# =====================================================================
def _merge(intervalles):
    """``calepinage.merge`` d'origine."""
    out = []
    for a, b in sorted(intervalles):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


# --------------------------------------------------- bâtiment A (aile en L)
A_B_LEN, A_A_LEN = 23.58, 23.50
A_BAR = A_B_LEN + A_A_LEN
A_W_B, A_LEG_W, A_LEG_S = 10.76, 11.2, 29.74
A_CUT_W, A_CUT_H = 2.18, 4.04
A_NX0, A_NX1, A_NDY = 31.28, 32.82, 0.74
A_TBL_W, A_TBL_L = 4.70, 1.134
A_RIVE, A_CLEAR, A_CLEAR_INC = 0.35, 0.30, 0.50
A_ROWS = (0.35, 5.65, 12.80, 20.65, 25.95, 31.25, 36.55, 41.85)
A_ENGAGEMENT = 152

#: (x0, x1, y0, y1, douteux) — x est-ouest, y nord-sud (repère du témoin)
A_CAIS_BAR = (
    (3.39, 4.70, 3.77, 4.92, False), (11.17, 12.50, 3.84, 4.98, False),
    (19.05, 20.35, 3.33, 4.34, False), (3.16, 4.27, 5.91, 7.02, False),
    (8.03, 9.14, 6.08, 7.38, False), (16.52, 17.32, 8.43, 9.06, True),
    (18.92, 20.35, 6.02, 7.46, False), (24.86, 26.41, 6.82, 7.46, True),
    (27.06, 27.92, 6.53, 7.08, False), (32.53, 33.03, 6.14, 6.98, False),
    (33.68, 34.63, 6.41, 6.88, True), (39.50, 40.48, 6.61, 7.07, True),
    (43.975, 44.515, 6.18, 7.05, False), (32.18, 32.88, 3.74, 4.73, False),
    (39.31, 40.72, 3.75, 4.65, False), (45.68, 46.98, 3.75, 4.81, False),
)
A_CAIS_LEG = (
    (25.01, 26.36, 3.78, 4.93, False), (17.12, 18.47, 3.78, 4.93, False),
    (25.01, 26.36, 6.33, 7.48, False), (16.99, 18.34, 6.33, 7.48, False),
    (9.24, 10.45, 3.78, 4.85, True), (1.45, 1.87, 3.72, 4.82, False),
    (9.63, 10.26, 6.40, 7.20, True), (9.70, 10.40, 7.35, 7.75, True),
)
A_CAGE = (12.23, 14.70, 6.13, 10.76)
A_DECN = (14.70, 17.47, 9.61, 10.76)
A_NOTCH = (A_NX0, A_NX1, 0.0, A_NDY)
A_EDIC = (30.21, 31.13, 0.0, 0.74)
A_GRECT = (0.40, 1.70, 4.95, 7.16)
A_PAN = (A_LEG_S - A_CUT_H, A_LEG_S, A_LEG_W - A_CUT_W, A_LEG_W)


def _obstacles_temoin_A():
    """``OBS`` de ``vue_bat_A_v2.py`` — 28 relevés + GRECT + PAN."""
    obs = []
    for x0, x1, y0, y1, unc in A_CAIS_BAR:
        obs.append((x0, x1, y0, y1, A_CLEAR_INC if unc else A_CLEAR,
                    "caisson barre", "R?" if unc else "R"))
    obs.append(A_CAGE + (A_CLEAR, "CAGE", "R"))
    obs.append(A_DECN + (A_CLEAR, "DECN", "R"))
    obs.append(A_NOTCH + (A_RIVE, "NOTCH", "R"))
    obs.append(A_EDIC + (A_CLEAR, "EDIC", "R"))
    for s0, s1, x0, x1, unc in A_CAIS_LEG:
        obs.append((x0, x1, -s1, -s0, A_CLEAR_INC if unc else A_CLEAR,
                    "caisson aile", "R?" if unc else "R"))
    obs.append((A_GRECT[2], A_GRECT[3], -A_GRECT[1], -A_GRECT[0],
                A_CLEAR_INC, "GRECT", "X"))
    obs.append((A_PAN[2], A_PAN[3], -A_PAN[1], -A_PAN[0], A_RIVE, "PAN", "P"))
    assert sum(1 for o in obs if o[6] in ("R", "R?")) == 28, "28 relevés"
    return obs


def _band_A(x0):
    return ((-A_LEG_S + A_RIVE) if x0 + A_TBL_W <= A_LEG_W - A_RIVE + 1e-9
            else A_RIVE), (A_W_B - A_RIVE)


def _free_segments_A(x0, obs):
    x1 = x0 + A_TBL_W
    ymin, ymax = _band_A(x0)
    bloques = []
    for ox0, ox1, oy0, oy1, c, _lab, _src in obs:
        if ox1 + c <= x0 + 1e-9 or ox0 - c >= x1 - 1e-9:
            continue
        bloques.append((max(ymin, oy0 - c), min(ymax, oy1 + c)))
    bloques = _merge([b for b in bloques if b[1] > b[0]])
    segs, cur = [], ymin
    for a, b in bloques:
        if a > cur:
            segs.append((cur, min(a, ymax)))
        cur = max(cur, b)
    if cur < ymax:
        segs.append((cur, ymax))
    return [(a, b) for a, b in segs if b > a]


def compte_temoin_A(obs=None):
    obs = _obstacles_temoin_A() if obs is None else obs
    return sum(2 * int((b - a + 1e-9) // A_TBL_L)
               for x0 in A_ROWS for a, b in _free_segments_A(x0, obs))


# ------------------------------------------------------------ bâtiment C
C_TBL_L, C_TBL_W = 1.134, 4.70
C_L_TOT, C_W_MES = 51.1, 25.62
C_Y_INT = C_L_TOT - 19.36
C_GAP = 7.92
C_CAGE_D = C_L_TOT - 19.36 - C_GAP - 4.50 - 10.50
C_CAGE = (C_Y_INT - C_CAGE_D, C_Y_INT, 14.09, 18.20)
C_CH = (C_CAGE[0] - C_GAP - 4.50, C_CAGE[0] - C_GAP, 13.95, 18.13)
C_GX0 = 13.95 + 4.18 + 1.19
C_GENE = (13.50, 14.50, C_GX0, C_GX0 + 4.78)
C_NIVEAU = (C_Y_INT, C_Y_INT, 0.0, C_W_MES)
C_JOG = (C_Y_INT - 0.45, C_Y_INT, 13.18, 14.09)
C_GENE_PL = (C_GENE[0] - 0.20, C_GENE[1] + 0.20,
             C_GENE[2] - 0.20, C_GENE[3] + 0.20)
C_OBS = (C_NIVEAU, C_JOG, C_CAGE, C_CH, C_GENE_PL)
C_ROWS = ((0.35, 5.05), (6.95, 11.65), (13.55, 18.25), (20.15, 24.85))
C_CLEAR, C_END_RIVE = 0.30, 0.35
C_ENGAGEMENT = 288


def compte_temoin_C():
    """``count_rows`` de ``vue_bat_C.py``."""
    total = 0
    for x0, x1 in C_ROWS:
        bloques = [(max(0.0, o[0] - C_CLEAR), min(C_L_TOT, o[1] + C_CLEAR))
                   for o in C_OBS
                   if not (o[3] + C_CLEAR <= x0 or o[2] - C_CLEAR >= x1)]
        bloques = _merge([b for b in bloques if b[1] > b[0]])
        cur, stop = C_END_RIVE, C_L_TOT - C_END_RIVE
        for a, b in bloques:
            if a > cur:
                total += 2 * int((min(a, stop) - cur) // C_TBL_L)
            cur = max(cur, b)
        if cur < stop:
            total += 2 * int((stop - cur) // C_TBL_L)
    return total


# ------------------------------------------------------------ bâtiment B
B_R_EXT, B_W = 274.0, 10.90
B_R_INT = B_R_EXT - B_W
B_S1, B_S2, B_S3, B_MUR = 20.55, 23.00, 23.60, 0.45
B_CLEAR, B_END_RIVE = 0.35, 0.35
B_ENGAGEMENT = 120
B_OBS = {
    "S1": (("C1", 3.27, 4.63, B_W - 4.72, B_W - 3.82),
           ("C2", 15.54, 17.09, 4.80, 5.76),
           ("C3", 12.78, 14.14, 4.20, 5.15)),
    "S2": (("cage", 0.00, 4.98, B_W - 5.93, B_W),
           ("K1", 6.28, 7.28, B_W - 4.67, B_W - 3.77),
           ("K2", 8.58, 9.78, B_W - 4.20, B_W - 3.40),
           ("K3", 8.18, 9.43, 3.50, 4.30),
           ("K4", 15.97, 17.42, 3.85, 4.75),
           ("K5", 11.34, 13.14, B_W - 3.00, B_W - 2.00),
           ("K6", 20.00, 21.50, B_W - 4.68, B_W - 3.78),
           ("K7", 20.10, 21.60, 3.86, 4.72)),
    "S3": (("A", 3.30, 4.57, B_W - 4.19, B_W - 3.61),
           ("B", 2.50, 3.55, 3.70, 5.33),
           ("X", 4.62, 5.32, 4.20, 5.30),
           ("N1", 4.92, 8.15, B_W - 1.70, B_W),
           ("N2", 8.15, 10.72, B_W - 3.15, B_W),
           ("C", 9.05, 10.59, 3.681, 4.701),
           ("D", 9.60, 10.44, B_W - 4.70, B_W - 3.93),
           ("E", 10.72, 12.52, B_W - 4.84, B_W - 3.74),
           ("G", 10.90, 12.43, 3.77, 4.67),
           ("F", 19.05, 20.27, B_W - 4.69, B_W - 3.85),
           ("H", 18.99, 20.34, 3.83, 4.69)),
}
B_LONGUEURS = {"S1": B_S1, "S2": B_S2, "S3": B_S3}
B_ROWS = {"S1": ((0.55, 5.25), (5.85, 10.55)),
          "S2": ((0.80, 3.05), (5.20, 7.45), (8.30, 10.55)),
          "S3": ((1.00, 3.25), (5.10, 7.35), (8.30, 10.55))}
B_MOD_L = {"S1": 1.134, "S2": 2.382, "S3": 2.382}


def _pas_B(mod_l, y0):
    return mod_l * B_R_EXT / (B_R_INT + y0)


def compte_temoin_B():
    """``count_seg`` de ``vue_bat_B_v2.py``, segment par segment."""
    total = 0
    for segment in ("S1", "S2", "S3"):
        longueur = B_LONGUEURS[segment]
        mod_l = B_MOD_L[segment]
        for y0, y1 in B_ROWS[segment]:
            bloques = []
            for _n, s0, s1, oy0, oy1 in B_OBS[segment]:
                if oy1 + B_CLEAR <= y0 or oy0 - B_CLEAR >= y1:
                    continue
                bloques.append((max(0.0, s0 - B_CLEAR),
                                min(longueur, s1 + B_CLEAR)))
            bloques = _merge([b for b in bloques if b[1] > b[0]])
            cur, stop = B_END_RIVE, longueur - B_END_RIVE
            runs = []
            for a, b in bloques:
                if a > cur:
                    runs.append((cur, min(a, stop)))
                cur = max(cur, b)
            if cur < stop:
                runs.append((cur, stop))
            pas = _pas_B(mod_l, y0)
            for a, b in runs:
                if b > a:
                    total += 2 * int((b - a) / pas + 1e-9)
    return total


# =====================================================================
# 2. MOTEUR NEUF — mêmes jeux, exprimés dans le contrat ``EntreeCalepinage``
# =====================================================================
def entree_A():
    from core.calepinage.obstacles import appliquer_regles
    from core.calepinage.serialisation import EntreeCalepinage
    from core.calepinage.surfaces.polygone import SurfacePolygone
    from core.calepinage.types import (KIT_AO_PORTRAIT, Obstacle, Parametres,
                                       Provenance, Rives)

    rives = Rives(laterale_m=A_RIVE, extremite_m=A_RIVE)
    contour = ((A_W_B, 0.0), (A_W_B, A_BAR), (0.0, A_BAR),
               (0.0, A_LEG_W - A_RIVE), (-A_LEG_S, A_LEG_W - A_RIVE),
               (-A_LEG_S, 0.0))
    obstacles = []
    for i, (x0, x1, y0, y1, unc) in enumerate(A_CAIS_BAR):
        obstacles.append(Obstacle(
            repere="BAR%d" % (i + 1), x0=y0, x1=y1, y0=x0, y1=x1,
            provenance=(Provenance.RELEVE_DOUTEUX if unc
                        else Provenance.RELEVE),
            degagement_m=A_CLEAR_INC if unc else A_CLEAR))
    for repere, (a0, a1, b0, b1), c in (("CAGE", A_CAGE, A_CLEAR),
                                        ("DECN", A_DECN, A_CLEAR),
                                        ("NOTCH", A_NOTCH, A_RIVE),
                                        ("EDIC", A_EDIC, A_CLEAR)):
        obstacles.append(Obstacle(repere=repere, x0=b0, x1=b1, y0=a0, y1=a1,
                                  provenance=Provenance.RELEVE,
                                  degagement_m=c))
    for i, (s0, s1, x0, x1, unc) in enumerate(A_CAIS_LEG):
        obstacles.append(Obstacle(
            repere="LEG%d" % (i + 1), x0=-s1, x1=-s0, y0=x0, y1=x1,
            provenance=(Provenance.RELEVE_DOUTEUX if unc
                        else Provenance.RELEVE),
            degagement_m=A_CLEAR_INC if unc else A_CLEAR))
    obstacles.append(Obstacle(
        repere="GRECT", x0=-A_GRECT[1], x1=-A_GRECT[0], y0=A_GRECT[2],
        y1=A_GRECT[3], provenance=Provenance.DEVINE,
        degagement_m=A_CLEAR_INC,
        regle_appliquee="emprise DEVINÉE (jonction, jamais cotée au relevé)"))
    obstacles.append(Obstacle(
        repere="PAN", x0=-A_PAN[1], x1=-A_PAN[0], y0=A_PAN[2], y1=A_PAN[3],
        provenance=Provenance.PLAN, degagement_m=A_RIVE,
        regle_appliquee="pan coupé SE venu du PLAN, jamais relevé"))
    surface = SurfacePolygone(repere="BAT_A_AILE_L", contour=contour,
                              rives=rives)
    parametres = Parametres(kits=(KIT_AO_PORTRAIT,), rives=rives,
                            allee_m=0.60, pas_recherche_m=0.01,
                            engagement_modules=A_ENGAGEMENT)
    return (EntreeCalepinage(repere="BAT_A_AILE_L", surfaces=(surface,),
                             kits=(KIT_AO_PORTRAIT,), parametres=parametres,
                             obstacles=appliquer_regles(tuple(obstacles)),
                             engagements=(("BAT_A_AILE_L", A_ENGAGEMENT),)),
            tuple(A_ROWS))


def entree_C():
    from core.calepinage.obstacles import appliquer_regles
    from core.calepinage.serialisation import EntreeCalepinage
    from core.calepinage.surfaces.rectangle import SurfaceRectangle
    from core.calepinage.types import (KIT_AO_PORTRAIT, Obstacle, Parametres,
                                       Provenance, Rives, TypeObstacle)

    rives = Rives(laterale_m=0.35, extremite_m=C_END_RIVE)
    obstacles = [
        Obstacle(repere="NIVEAU", x0=C_NIVEAU[0], x1=C_NIVEAU[1],
                 y0=C_NIVEAU[2], y1=C_NIVEAU[3],
                 type_obstacle=TypeObstacle.JOINT_DILATATION,
                 provenance=Provenance.RELEVE, degagement_m=C_CLEAR),
        Obstacle(repere="JOG", x0=C_JOG[0], x1=C_JOG[1], y0=C_JOG[2],
                 y1=C_JOG[3], type_obstacle=TypeObstacle.ACROTERE,
                 provenance=Provenance.RELEVE, degagement_m=C_CLEAR),
        Obstacle(repere="CAGE", x0=C_CAGE[0], x1=C_CAGE[1], y0=C_CAGE[2],
                 y1=C_CAGE[3], type_obstacle=TypeObstacle.CAGE_ESCALIER,
                 provenance=Provenance.RELEVE, degagement_m=C_CLEAR),
        Obstacle(repere="LOCAL", x0=C_CH[0], x1=C_CH[1], y0=C_CH[2],
                 y1=C_CH[3], type_obstacle=TypeObstacle.EDICULE,
                 provenance=Provenance.RELEVE, degagement_m=C_CLEAR),
        Obstacle(repere="GENE", x0=C_GENE_PL[0], x1=C_GENE_PL[1],
                 y0=C_GENE_PL[2], y1=C_GENE_PL[3],
                 type_obstacle=TypeObstacle.CLIMATISEUR,
                 provenance=Provenance.DECLARE_CLIENT, degagement_m=C_CLEAR,
                 regle_appliquee="emprise gonflée de 0,20 m : le dégagement "
                                 "de 0,50 m annoncé au client est tenu"),
    ]
    # ÉCARTÉS : les 4 souches provisoires supprimées par la réponse client du
    # 27/07 (« AUCUNE souche vue sur le toit »). Elles FIGURENT au golden pour
    # que les marches d'échelle qui les chiffrent restent reproductibles ; leur
    # géométrie n'a jamais été relevée et n'est donc PAS inventée ici.
    for i in range(1, 5):
        obstacles.append(Obstacle(
            repere="SOUCHE_%d" % i, x0=0.0, x1=0.0, y0=0.0, y1=0.0,
            type_obstacle=TypeObstacle.SOUCHE, provenance=Provenance.ECARTE,
            regle_appliquee="souche provisoire ÉCARTÉE (réponse client du "
                            "27/07 : aucune souche sur le toit) — géométrie "
                            "NON RELEVÉE, volontairement non inventée"))
    surface = SurfaceRectangle(repere="BAT_C_ECOLE", longueur_m=C_L_TOT,
                               largeur_m=C_W_MES, rives=rives)
    parametres = Parametres(kits=(KIT_AO_PORTRAIT,), rives=rives,
                            allee_m=0.60, pas_recherche_m=0.01,
                            engagement_modules=C_ENGAGEMENT)
    return (EntreeCalepinage(repere="BAT_C_ECOLE", surfaces=(surface,),
                             kits=(KIT_AO_PORTRAIT,), parametres=parametres,
                             obstacles=appliquer_regles(tuple(obstacles)),
                             engagements=(("BAT_C_ECOLE", C_ENGAGEMENT),)),
            tuple(r[0] for r in C_ROWS))


def entrees_B():
    """L'arc est TROIS segments séparés par des murets : trois entrées."""
    from core.calepinage.obstacles import appliquer_regles
    from core.calepinage.serialisation import EntreeCalepinage
    from core.calepinage.surfaces.arc import SurfaceArc
    from core.calepinage.types import (KIT_AO_PAYSAGE, KIT_AO_PORTRAIT,
                                       Obstacle, Parametres, Provenance,
                                       Rives)

    rives = Rives(laterale_m=0.35, extremite_m=B_END_RIVE)
    sorties = []
    for segment in ("S1", "S2", "S3"):
        kit = KIT_AO_PORTRAIT if segment == "S1" else KIT_AO_PAYSAGE
        obstacles = tuple(
            Obstacle(repere=repere, x0=s0, x1=s1, y0=y0, y1=y1,
                     provenance=Provenance.RELEVE, degagement_m=B_CLEAR)
            for repere, s0, s1, y0, y1 in B_OBS[segment])
        surface = SurfaceArc(repere="BAT_B_ARC_%s" % segment,
                             rayon_ext_m=B_R_EXT, largeur_m=B_W,
                             developpe_m=B_LONGUEURS[segment], rives=rives)
        parametres = Parametres(kits=(kit,), rives=rives, allee_m=0.60,
                                pas_recherche_m=0.01)
        sorties.append((EntreeCalepinage(
            repere=surface.repere, surfaces=(surface,), kits=(kit,),
            parametres=parametres, obstacles=appliquer_regles(obstacles),
            engagements=(("BAT_B_ARC", B_ENGAGEMENT),)),
            tuple(r[0] for r in B_ROWS[segment])))
    return sorties


# =====================================================================
# 3. RÉCONCILIATION
# =====================================================================
def _compte_moteur(entree, rangees):
    from core.calepinage.moteur import compter_plan

    kit = entree.parametres.kits[0]
    return compter_plan(entree.surfaces[0], tuple((y, kit) for y in rangees),
                        entree.obstacles).modules


def verifier_temoins():
    ecarts = []
    for nom, empreinte in EMPREINTES_TEMOINS:
        chemin = os.path.join(TEMOINS, nom)
        if not os.path.exists(chemin):
            ecarts.append("%s : ABSENT de docs/ao-frdisi/" % nom)
            continue
        with io.open(chemin, "rb") as fh:
            obtenue = hashlib.sha256(fh.read()).hexdigest()
        if obtenue != empreinte:
            ecarts.append("%s : script témoin MODIFIÉ (%s au lieu de %s)"
                          % (nom, obtenue[:12], empreinte[:12]))
    return ecarts


def reconcilier():
    """Rend ``(rapports, ecarts)`` — un écart NOMME ce qui diverge."""
    rapports, ecarts = [], []

    entree, rangees = entree_A()
    temoin, moteur = compte_temoin_A(), _compte_moteur(entree, rangees)
    rapports.append(("BAT_A_AILE_L", temoin, moteur))
    if temoin != moteur:
        ecarts.append("bâtiment A : témoin %d, moteur %d" % (temoin, moteur))

    entree_c, rangees_c = entree_C()
    temoin, moteur = compte_temoin_C(), _compte_moteur(entree_c, rangees_c)
    rapports.append(("BAT_C_ECOLE", temoin, moteur))
    if temoin != moteur:
        ecarts.append("bâtiment C : témoin %d, moteur %d" % (temoin, moteur))

    temoin = compte_temoin_B()
    moteur = sum(_compte_moteur(e, r) for e, r in entrees_B())
    rapports.append(("BAT_B_ARC", temoin, moteur))
    if temoin != moteur:
        ecarts.append("bâtiment B : témoin %d, moteur %d" % (temoin, moteur))

    return rapports, ecarts


def documents():
    """Les documents JSON des goldens, prêts à écrire."""
    entree_a, rangees_a = entree_A()
    entree_c, rangees_c = entree_C()
    segments_b = entrees_B()

    def enveloppe(entree, rangees, compte, engagement, commentaire):
        document = entree.vers_dict()
        document["golden"] = {
            "commentaire": commentaire,
            "rangees_retenues": list(rangees),
            "compte_temoin": compte,
            "engagement": engagement,
            "hash_entree": entree.hash_entree,
        }
        return document

    docs = {
        "bat_A_aile_L.json": enveloppe(
            entree_a, rangees_a, compte_temoin_A(), A_ENGAGEMENT,
            "Bâtiment A (aile en L) — relevé contradictoire du 27/07/2026. "
            "GRECT (deviné) et PAN (venu du plan) sont CONSERVÉS dans le "
            "compte et identifiés par leur provenance."),
        "bat_C_ecole.json": enveloppe(
            entree_c, rangees_c, compte_temoin_C(), C_ENGAGEMENT,
            "Bâtiment C (école SUPTECH). Les 4 souches provisoires figurent "
            "en provenance ECARTE : elles ne comptent pas et leur géométrie "
            "n'a jamais été relevée."),
    }
    document_b = segments_b[0][0].vers_dict()
    document_b["repere"] = "BAT_B_ARC"
    document_b["surfaces"] = []
    document_b["obstacles"] = []
    kits_vus = {}
    for entree, _rangees in segments_b:
        for kit in entree.parametres.kits:
            kits_vus[kit.code] = kit
    document_b["kits"] = [k for k in
                          (segments_b[0][0].vers_dict()["kits"][0],)] + [
        {"code": kit.code, "libelle": kit.libelle,
         "module_long_m": kit.module_long_m,
         "module_court_m": kit.module_court_m,
         "puissance_module_wc": kit.puissance_module_wc,
         "inclinaison_deg": kit.inclinaison_deg,
         "orientation": kit.orientation.value,
         "modules_par_table": kit.modules_par_table,
         "faitage_m": kit.faitage_m}
        for code, kit in sorted(kits_vus.items())
        if code != segments_b[0][0].parametres.kits[0].code]
    document_b["golden"] = {
        "commentaire": "Bâtiment B (arc) — 3 segments séparés par des murets "
                       "au ras (0,45) ; chaque segment a SON plan de pose.",
        "compte_temoin": compte_temoin_B(),
        "engagement": B_ENGAGEMENT,
        "segments": [],
    }
    for entree, rangees in segments_b:
        partiel = entree.vers_dict()
        document_b["surfaces"].extend(partiel["surfaces"])
        # les abscisses sont LOCALES à chaque segment : le repère d'obstacle
        # est préfixé pour rester unique, et le golden dit à quel segment
        # chacun appartient (sans quoi le lecteur ne peut pas les séparer).
        suffixe = entree.repere.rsplit("_", 1)[-1]
        reperes = []
        for obstacle in partiel["obstacles"]:
            obstacle["repere"] = "%s_%s" % (suffixe, obstacle["repere"])
            reperes.append(obstacle["repere"])
            document_b["obstacles"].append(obstacle)
        document_b["golden"]["segments"].append({
            "repere": entree.repere,
            "rangees_retenues": list(rangees),
            "kit": entree.parametres.kits[0].code,
            "obstacles": reperes,
            "compte_moteur": _compte_moteur(entree, rangees),
            "hash_entree": entree.hash_entree,
        })
    docs["bat_B_arc.json"] = document_b
    return docs


def principal(argv=None):
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--ecrire", action="store_true",
                         help="régénère les goldens après réconciliation")
    options = parseur.parse_args(argv)

    ecarts = verifier_temoins()
    if ecarts:
        sys.stderr.write("TÉMOINS MODIFIÉS — docs/ao-frdisi/ est GELÉ :\n")
        for ecart in ecarts:
            sys.stderr.write("  %s\n" % ecart)
        return 2

    rapports, ecarts = reconcilier()
    for repere, temoin, moteur in rapports:
        sys.stdout.write("%-14s témoin %4d | moteur %4d | %s\n"
                         % (repere, temoin, moteur,
                            "OK" if temoin == moteur else "ÉCART"))
    if ecarts:
        sys.stderr.write("RÉCONCILIATION EN ÉCHEC :\n")
        for ecart in ecarts:
            sys.stderr.write("  %s\n" % ecart)
        return 1

    if options.ecrire:
        if not os.path.isdir(GOLDEN):
            os.makedirs(GOLDEN)
        for nom, document in documents().items():
            chemin = os.path.join(GOLDEN, nom)
            with io.open(chemin, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(document, indent=2, ensure_ascii=False,
                                    sort_keys=True) + "\n")
            sys.stdout.write("écrit %s\n" % chemin)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
