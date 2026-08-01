# -*- coding: utf-8 -*-
"""AOF51 — ``valider(plan)`` NON CONTOURNABLE, exécuté EN PRODUCTION.

Les scripts d'origine portaient leurs contrôles en ``assert`` : ils
disparaissent sous ``python -O`` et, surtout, ils ne vivaient QUE dans le
script de planche. Un appel d'API ou un import produisait un livrable faux
sans que rien ne s'y oppose. Ici, la validation est une PORTE : le service AO
l'appelle et refuse de publier un plan qui ne la franchit pas.

Les neuf contrôles, tous NOMMÉS (le nom sort dans l'exception) :

1. ``orientation``            — rappel du contrôle d'AOF45, pour que le chemin
                                API et le chemin villa passent la même porte ;
2. ``dessine_egale_compte``   — ``2 × len(tables) == compte`` (les deux chemins
                                de code indépendants doivent tomber d'accord) ;
3. ``compte_annonce``         — la preuve annonce EXACTEMENT ce que le plan
                                contient ;
4. ``non_chevauchement``      — VRAI test SAT polygone contre polygone : c'est
                                précisément le test que l'ancien modèle d'arc
                                échouait (tables jointives en abscisse
                                développée, recouvertes au rayon intérieur) ;
5. ``rive_laterale`` /
   ``rive_extremite``         — les quatre rives, séparément ;
6. ``degagement_obstacle``    — le dégagement de CHAQUE obstacle, un par un ;
7. ``coupure``                — aucune table à cheval sur un niveau ou un
                                muret ;
8. ``hors_developpe``         — aucune table hors de la surface ;
9. ``provenance_engageable``  — aucune emprise PLAN ou DEVINÉE dans un compte
                                présenté comme engagé.
"""

from dataclasses import dataclass
from typing import Tuple

from core.calepinage.exceptions import CalepinageIncoherent
from core.calepinage.moteur import compter_plan
from core.calepinage.obstacles import engageable
from core.calepinage.orientation import ErreurOrientation, verifier_kit
from core.calepinage.poseur import poser_plan
from core.calepinage.types import Provenance
from core.calepinage.units import TOL_SEPARATION_M

__all__ = [
    "Echec", "RapportValidation", "valider", "polygones_se_chevauchent",
    "CONTROLES",
]

#: Les neuf contrôles, dans l'ordre d'exécution (le rapport les liste ainsi).
CONTROLES = (
    "orientation", "dessine_egale_compte", "compte_annonce",
    "non_chevauchement", "rive_laterale", "rive_extremite",
    "degagement_obstacle", "coupure", "hors_developpe",
    "provenance_engageable",
)


@dataclass(frozen=True)
class Echec:
    """Un contrôle en échec, avec le repère fautif — jamais un booléen nu."""

    controle: str
    repere: str
    message: str


@dataclass(frozen=True)
class RapportValidation:
    """Le rapport complet : tous les échecs, pas seulement le premier."""

    echecs: Tuple[Echec, ...] = ()
    controles_passes: Tuple[str, ...] = ()

    @property
    def ok(self):
        return not self.echecs

    def premier(self):
        return self.echecs[0] if self.echecs else None


# ------------------------------------------------------------------- SAT
def _axes(polygone):
    axes = []
    n = len(polygone)
    for i in range(n):
        ax, ay = polygone[i]
        bx, by = polygone[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        longueur = (ex * ex + ey * ey) ** 0.5
        if longueur <= 0:
            continue
        axes.append((-ey / longueur, ex / longueur))
    return axes


def _projection(polygone, axe):
    valeurs = [p[0] * axe[0] + p[1] * axe[1] for p in polygone]
    return (min(valeurs), max(valeurs))


def polygones_se_chevauchent(a, b, tolerance=TOL_SEPARATION_M):
    """Théorème de l'AXE SÉPARATEUR — vrai test, pas une boîte englobante.

    Sur l'arc, deux tables voisines sont des rectangles RIGIDES posés à des
    repères tangents DIFFÉRENTS : leurs boîtes englobantes se croisent alors
    qu'elles ne se touchent pas, et inversement. Seul le SAT tranche.
    """
    if len(a) < 3 or len(b) < 3:
        return False
    for axe in _axes(a) + _axes(b):
        a0, a1 = _projection(a, axe)
        b0, b1 = _projection(b, axe)
        if a1 <= b0 + tolerance or b1 <= a0 + tolerance:
            return False
    return True


# ------------------------------------------------------------- validation
def _rectangle(x0, x1, y0, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def valider(surface, parametres, rangees, obstacles=(), zones=(), tables=None,
            preuve=None, engage=False, strict=True):
    """Valide un plan. ``strict`` LÈVE ``CalepinageIncoherent`` au 1er échec.

    ``rangees`` : ``((y0, kit), …)``. Les tables sont posées par le POSEUR si
    elles ne sont pas fournies — la validation confronte donc toujours les deux
    chemins de code.
    """
    echecs = []
    passes = []

    # 1 — orientation constructible (AOF45, rejoué sur le plan fini)
    try:
        azimut = getattr(surface, "azimut_deg", 180.0)
        for _y0, kit in rangees:
            verifier_kit(kit, parametres.axe_rangee, azimut)
        passes.append("orientation")
    except ErreurOrientation as erreur:
        echecs.append(Echec("orientation", surface.repere, str(erreur)))

    plan = compter_plan(surface, rangees, obstacles, zones)
    if tables is None:
        tables = poser_plan(surface, rangees, obstacles, zones)
    tables = tuple(tables)

    # 2 — dessiné = compté
    modules_par_pas = rangees[0][1].modules_par_pas if rangees else 2
    if modules_par_pas * len(tables) != plan.modules:
        echecs.append(Echec(
            "dessine_egale_compte", surface.repere,
            "%d tables posées × %d modules ≠ %d comptés"
            % (len(tables), modules_par_pas, plan.modules)))
    else:
        passes.append("dessine_egale_compte")

    # 3 — la preuve annonce ce que le plan contient
    if preuve is not None:
        if preuve.compte_retenu != plan.modules:
            echecs.append(Echec(
                "compte_annonce", surface.repere,
                "la preuve annonce %d modules, le plan en contient %d"
                % (preuve.compte_retenu, plan.modules)))
        else:
            passes.append("compte_annonce")

    # 4 — non-chevauchement (SAT), 5/6 — rives, 8 — coupures, 9 — développé
    ymin, ymax = surface.bornes_transversales_utiles()
    chevauchement = False
    for i, table in enumerate(tables):
        poly_a = table.polygone or _rectangle(table.x0, table.x1, table.y0,
                                              table.y1)
        for autre in tables[i + 1:]:
            poly_b = autre.polygone or _rectangle(autre.x0, autre.x1, autre.y0,
                                                  autre.y1)
            if polygones_se_chevauchent(poly_a, poly_b):
                echecs.append(Echec(
                    "non_chevauchement",
                    "table x0=%.3f y0=%.3f" % (table.x0, table.y0),
                    "recouvre la table x0=%.3f y0=%.3f"
                    % (autre.x0, autre.y0)))
                chevauchement = True
                break
        if chevauchement:
            break
    if not chevauchement:
        passes.append("non_chevauchement")

    hors_rive_laterale = False
    hors_rive_extremite = False
    a_cheval = False
    hors_developpe = False
    for table in tables:
        if table.y0 < ymin - TOL_SEPARATION_M or table.y1 > ymax + TOL_SEPARATION_M:
            echecs.append(Echec(
                "rive_laterale", "table y0=%.3f" % table.y0,
                "hors des bornes latérales utiles [%.3f ; %.3f]" % (ymin, ymax)))
            hors_rive_laterale = True
            break
    if not hors_rive_laterale:
        passes.append("rive_laterale")

    for table in tables:
        bande = surface.bande(table.y0, table.y1 - table.y0)
        if bande is None:
            echecs.append(Echec("hors_developpe", "table y0=%.3f" % table.y0,
                                "aucune bande posable à cette ordonnée"))
            hors_developpe = True
            break
        debut, fin = surface.bornes_utiles(bande)
        if table.x0 < debut - TOL_SEPARATION_M or table.x1 > fin + TOL_SEPARATION_M:
            echecs.append(Echec(
                "rive_extremite", "table x0=%.3f" % table.x0,
                "déborde le tronçon utile [%.3f ; %.3f]" % (debut, fin)))
            hors_rive_extremite = True
            break
    if not hors_rive_extremite:
        passes.append("rive_extremite")
    if not hors_developpe:
        passes.append("hors_developpe")

    for table in tables:
        if surface.enjambe_une_coupure(table.x0, table.x1, table.y0, table.y1):
            echecs.append(Echec("coupure", "table x0=%.3f" % table.x0,
                                "à cheval sur une coupure de niveau ou un muret"))
            a_cheval = True
            break
        a_cheval_multi = getattr(surface, "table_a_cheval", None)
        if a_cheval_multi is not None and a_cheval_multi(table.x0, table.x1):
            echecs.append(Echec("coupure", "table x0=%.3f" % table.x0,
                                "change de niveau en cours de table"))
            a_cheval = True
            break
    if not a_cheval:
        passes.append("coupure")

    # 7 — dégagement de CHAQUE obstacle
    fautif = None
    for o in obstacles:
        if o.provenance is Provenance.ECARTE:
            continue
        c = o.degagement_m or 0.0
        gabarit = _rectangle(o.x0 - c, o.x1 + c, o.y0 - c, o.y1 + c)
        for table in tables:
            poly = table.polygone or _rectangle(table.x0, table.x1, table.y0,
                                                table.y1)
            if polygones_se_chevauchent(poly, gabarit):
                fautif = Echec(
                    "degagement_obstacle", o.repere,
                    "dégagement de %.2f m non tenu par la table x0=%.3f "
                    "y0=%.3f" % (c, table.x0, table.y0))
                break
        if fautif is not None:
            break
    if fautif is None:
        passes.append("degagement_obstacle")
    else:
        echecs.append(fautif)

    # 10 — provenance engageable
    if engage:
        ok, motifs = engageable(obstacles)
        if not ok:
            echecs.append(Echec("provenance_engageable", surface.repere,
                                " ; ".join(motifs)))
        else:
            passes.append("provenance_engageable")

    rapport = RapportValidation(echecs=tuple(echecs),
                                controles_passes=tuple(passes))
    if strict and echecs:
        premier = echecs[0]
        raise CalepinageIncoherent(premier.controle, premier.repere,
                                   premier.message)
    return rapport
