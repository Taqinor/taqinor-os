# -*- coding: utf-8 -*-
"""AOF52 — batterie de sensibilités DÉFAVORABLES, plancher publié, verdict GÉNÉRÉ.

Un engagement de bordereau ne se défend pas avec un chiffre : il se défend avec
un PLANCHER. La batterie rejoue le MÊME moteur sur le MÊME relevé en durcissant
une hypothèse à la fois — kit unique, dégagement maximal, allées de
maintenance, non-cotés retirés ou traités en « nature inconnue », longueurs
raccourcies de 10 cm, rives majorées — et publie le pire compte obtenu.

**La phrase de verdict est GÉNÉRÉE, jamais rédigée.** Un gabarit choisi dans
une liste de phrases toutes faites finit toujours par mentir : il survit à un
changement de chiffres. Ici la phrase porte les nombres calculés, et un
non-coté d'impact nul s'annonce « impact chiffré de 0 module » — pas
« incertitude négligeable », qui ne veut rien dire pour un maître d'ouvrage.
"""

from dataclasses import dataclass, replace
from typing import Optional, Tuple

from core.calepinage.obstacles import appliquer_regles
from core.calepinage.perf import optimiser_economique
from core.calepinage.types import Provenance, Sensibilite, remplacer

__all__ = [
    "BatterieSensibilites", "raccourcir", "batterie", "PROVENANCES_NON_COTEES",
]

#: Provenances qui ne viennent PAS d'une cote relevée : ce sont elles que le
#: client doit arbitrer (les retirer ou les confirmer).
PROVENANCES_NON_COTEES = (Provenance.PLAN, Provenance.DEVINE,
                          Provenance.RELEVE_DOUTEUX)


@dataclass(frozen=True)
class BatterieSensibilites:
    """Résultat de la batterie : les variantes, le PLANCHER, le verdict."""

    reference: int
    sensibilites: Tuple[Sensibilite, ...]
    engagement: Optional[int] = None
    non_applicables: Tuple[str, ...] = ()

    @property
    def plancher(self):
        """Le pire compte obtenu — c'est LUI qu'on publie face à l'engagement."""
        if not self.sensibilites:
            return self.reference
        return min([self.reference] + [s.modules for s in self.sensibilites])

    @property
    def sensibilites_perdantes(self):
        return tuple(s for s in self.sensibilites if s.delta < 0)

    def verdict(self):
        """Phrase GÉNÉRÉE à partir des nombres — jamais choisie dans une liste."""
        if self.engagement is None:
            return ("plancher de sensibilité %d modules (aucun engagement "
                    "déclaré)" % self.plancher)
        manquantes = tuple(s for s in self.sensibilites
                           if s.modules < self.engagement)
        if not manquantes:
            return ("engagement tenu partout : plancher %d modules pour un "
                    "engagement de %d (%d variantes défavorables rejouées)"
                    % (self.plancher, self.engagement, len(self.sensibilites)))
        details = ", ".join("%s (%d)" % (s.code, s.modules)
                            for s in manquantes)
        return ("engagement tenu sauf %s : plancher %d modules pour un "
                "engagement de %d" % (details, self.plancher, self.engagement))


def raccourcir(surface, delta_m):
    """Surface RACCOURCIE de ``delta_m`` le long des rangées, ou ``None``.

    Le relevé annonce plusieurs longueurs « ≈ » : les raccourcir de 10 cm est
    la sensibilité la plus honnête qui soit — elle chiffre ce que coûterait une
    contre-mesure défavorable.
    """
    if hasattr(surface, "longueur_m"):
        if surface.longueur_m - delta_m <= 0:
            return None
        return replace(surface, longueur_m=surface.longueur_m - delta_m)
    if hasattr(surface, "developpe_m"):
        if surface.developpe_m - delta_m <= 0:
            return None
        return replace(surface, developpe_m=surface.developpe_m - delta_m)
    contour = getattr(surface, "contour", None)
    if contour:
        limite = max(p[0] for p in contour) - delta_m
        return replace(surface, contour=tuple((min(x, limite), y)
                                              for x, y in contour))
    if hasattr(surface, "paliers") and surface.paliers:
        dernier = surface.paliers[-1]
        if dernier.longueur_m - delta_m <= 0:
            return None
        return replace(surface, paliers=surface.paliers[:-1] + (
            replace(dernier, x1=dernier.x1 - delta_m),))
    return None


def _sans_non_cotes(obstacles):
    return appliquer_regles(tuple(
        remplacer(o, provenance=Provenance.ECARTE)
        if o.provenance in PROVENANCES_NON_COTEES else o
        for o in obstacles))


def _non_cotes_inconnus(obstacles, degagement):
    return appliquer_regles(tuple(
        remplacer(o, degagement_m=degagement)
        if o.provenance in PROVENANCES_NON_COTEES else o
        for o in obstacles))


def _degagement_maximal(obstacles, degagement):
    return appliquer_regles(tuple(
        remplacer(o, degagement_m=max(degagement, o.degagement_m or 0.0))
        for o in obstacles))


def batterie(surface, parametres, obstacles=(), zones=(), engagement=None,
             degagement_maximal_m=0.50, allees_maintenance=(1.00, 1.20, 1.90),
             raccourcissement_m=0.10, majoration_rive_m=0.15,
             politique=None):
    """Rejoue la batterie complète et rend le PLANCHER + les deltas signés."""
    reference = optimiser_economique(surface, parametres, obstacles, zones,
                                     politique).modules
    engagement = (engagement if engagement is not None
                  else parametres.engagement_modules)
    resultats = []
    non_applicables = []

    def ajouter(code, libelle, surface_v, parametres_v, obstacles_v):
        modules = optimiser_economique(surface_v, parametres_v, obstacles_v,
                                       zones, politique).modules
        delta = modules - reference
        resultats.append(Sensibilite(
            code=code,
            libelle="%s — impact chiffré de %+d module%s" % (
                libelle, delta, "" if abs(delta) <= 1 else "s"),
            modules=modules, delta=delta,
            tenu=(engagement is None or modules >= engagement)))

    if parametres.multi_kits:
        for kit in parametres.kits:
            ajouter("KIT_UNIQUE_%s" % kit.code,
                    "kit unique %s imposé" % kit.code, surface,
                    remplacer(parametres, kits=(kit,)), obstacles)

    ajouter("DEGAGEMENT_MAX",
            "dégagement de %.2f m partout" % degagement_maximal_m,
            surface, parametres,
            _degagement_maximal(obstacles, degagement_maximal_m))

    for allee in allees_maintenance:
        ajouter("ALLEE_%03d" % round(allee * 100),
                "allée de maintenance de %.2f m" % allee, surface,
                remplacer(parametres, allee_m=allee), obstacles)

    if any(o.provenance in PROVENANCES_NON_COTEES for o in obstacles):
        ajouter("NON_COTES_ABSENTS", "non-cotés retirés du compte", surface,
                parametres, _sans_non_cotes(obstacles))
        ajouter("NON_COTES_INCONNUS",
                "non-cotés traités en nature inconnue (%.2f m)"
                % degagement_maximal_m, surface, parametres,
                _non_cotes_inconnus(obstacles, degagement_maximal_m))
    else:
        non_applicables.append(
            "non-cotés : aucun obstacle non coté dans ce relevé")

    courte = raccourcir(surface, raccourcissement_m)
    if courte is None:
        non_applicables.append(
            "longueurs raccourcies : la surface ne sait pas se raccourcir")
    else:
        ajouter("LONGUEUR_COURTE",
                "longueurs raccourcies de %.2f m" % raccourcissement_m,
                courte, parametres, obstacles)

    rives = parametres.rives
    majorees = remplacer(
        parametres,
        rives=replace(rives,
                      laterale_m=rives.laterale_m + majoration_rive_m,
                      extremite_m=rives.extremite_m + majoration_rive_m))
    surface_majoree = replace(surface, rives=majorees.rives)
    ajouter("RIVES_MAJOREES",
            "rives majorées de %.2f m" % majoration_rive_m, surface_majoree,
            majorees, obstacles)

    return BatterieSensibilites(reference=reference,
                                sensibilites=tuple(resultats),
                                engagement=engagement,
                                non_applicables=tuple(non_applicables))
