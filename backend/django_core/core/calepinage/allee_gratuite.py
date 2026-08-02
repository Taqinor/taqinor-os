# -*- coding: utf-8 -*-
"""AOF50 — la plus grande allée à COMPTE CONSTANT : l'argument commercial offert.

Constat mesuré sur le bâtiment C : le compte est IDENTIQUE (314) de 0,60 m à
plus de 1,90 m d'allée. Autrement dit, les allées de maintenance larges étaient
GRATUITES — et on l'a écrit sur la planche remise au maître d'ouvrage
(0,35 + 4,70 + 1,90 + 4,70 + 1,90 + 4,70 + 1,90 + 4,70 + 0,77 = 25,62 exact).

**Règle produit gravée : ne JAMAIS publier l'allée minimale quand une allée
large est gratuite — la chercher SYSTÉMATIQUEMENT.** Une allée minimale
publiée par défaut, c'est un argument commercial jeté à la poubelle à chaque
dossier.

La valeur publiée n'est pas la borne haute : on garde une MARGE DE SÉCURITÉ
(10 cm par défaut) sous le point de bascule et on arrondit au multiple de
10 cm inférieur — un chantier ne se cale pas sur un optimum au centimètre.
Le plan reconstruit à cette allée est REVALIDÉ (compte + marges) avant d'être
proposé : une allée large qui casserait un garde-fou ne sort pas d'ici.
"""

from dataclasses import dataclass
from typing import Tuple

from core.calepinage.perf import optimiser_economique
from core.calepinage.robustesse import marges_du_plan, valider_marges
from core.calepinage.types import remplacer
from core.calepinage.units import TOL_LONGUEUR_M

__all__ = ["ResultatAlleeGratuite", "chercher_allee_gratuite"]

#: Marge de sécurité sous le point de bascule (mètres) et pas d'arrondi métier.
MARGE_SECURITE_M = 0.10
PAS_ARRONDI_M = 0.10


@dataclass(frozen=True)
class ResultatAlleeGratuite:
    """L'intervalle gratuit, la valeur PUBLIABLE, et la preuve qu'elle tient."""

    compte_reference: int
    allee_min_m: float
    allee_max_m: float
    allee_publiable_m: float
    compte_publiable: int
    rangees: Tuple[Tuple[float, str], ...] = ()
    marges_cm: Tuple[float, float] = (0.0, 0.0)
    valide: bool = True
    motifs: Tuple[str, ...] = ()
    bascule_verifiee: bool = False

    @property
    def gain_m(self):
        """Ce qu'on OFFRE : la largeur d'allée gagnée sans perdre un module."""
        return max(0.0, self.allee_publiable_m - self.allee_min_m)

    @property
    def gratuite(self):
        return self.allee_max_m > self.allee_min_m + TOL_LONGUEUR_M


def _compte(surface, parametres, allee, obstacles, zones):
    return optimiser_economique(surface, remplacer(parametres, allee_m=allee),
                                obstacles, zones)


def chercher_allee_gratuite(surface, parametres, obstacles=(), zones=(),
                            allee_max_m=None, pas_m=0.01,
                            marge_securite_m=MARGE_SECURITE_M,
                            pas_arrondi_m=PAS_ARRONDI_M,
                            seuils_marges=None):
    """Plus grande allée à compte constant, par DICHOTOMIE puis revalidation.

    Le compte décroît (au sens large) quand l'allée s'élargit : la dichotomie
    est donc licite, et la bascule est VÉRIFIÉE explicitement (le compte à
    ``borne + pas`` doit être strictement inférieur) — le résultat porte le
    drapeau, on ne le suppose pas.
    """
    reference = _compte(surface, parametres, parametres.allee_m, obstacles,
                        zones)
    cible = reference.modules
    _ymin, ymax = surface.bornes_transversales_utiles()
    haut = allee_max_m if allee_max_m is not None else (ymax - _ymin)
    bas = parametres.allee_m

    if _compte(surface, parametres, haut, obstacles, zones).modules >= cible:
        borne = haut
    else:
        while haut - bas > pas_m + TOL_LONGUEUR_M:
            milieu = (bas + haut) / 2.0
            if _compte(surface, parametres, milieu, obstacles,
                       zones).modules >= cible:
                bas = milieu
            else:
                haut = milieu
        borne = round(bas / pas_m) * pas_m
        while _compte(surface, parametres, borne + pas_m, obstacles,
                      zones).modules >= cible:
            borne += pas_m

    bascule = (borne >= haut - TOL_LONGUEUR_M
               or _compte(surface, parametres, borne + pas_m, obstacles,
                          zones).modules < cible)

    brut = max(parametres.allee_m, borne - marge_securite_m)
    publiable = int((brut + TOL_LONGUEUR_M) / pas_arrondi_m) * pas_arrondi_m
    publiable = max(parametres.allee_m, round(publiable, 6))

    plan = _compte(surface, parametres, publiable, obstacles, zones)
    rangees = tuple((y0, kit) for y0, kit in _rangees_kits(parametres,
                                                           plan.rangees))
    marges = marges_du_plan(surface, rangees, obstacles, zones)
    if seuils_marges is None:
        ok, motifs = valider_marges(marges, parametres.marge_troncon_min_m,
                                    parametres.marge_bande_min_m)
    else:
        ok, motifs = valider_marges(marges, *seuils_marges)
    if plan.modules < cible:
        ok = False
        motifs = motifs + (
            "l'allée publiable %.2f m perd %d modules — non publiable"
            % (publiable, cible - plan.modules),)
    return ResultatAlleeGratuite(
        compte_reference=cible,
        allee_min_m=parametres.allee_m,
        allee_max_m=round(borne, 6),
        allee_publiable_m=publiable,
        compte_publiable=plan.modules,
        rangees=plan.rangees,
        marges_cm=(marges.troncon_min_cm, marges.bande_min_cm),
        valide=ok, motifs=tuple(motifs), bascule_verifiee=bool(bascule))


def _rangees_kits(parametres, rangees):
    """``((y0, code), …)`` -> ``((y0, Kit), …)`` pour les marges."""
    for y0, code in rangees:
        yield (y0, parametres.kit(code))
