# -*- coding: utf-8 -*-
"""AOF55 — l'ÉTUDE : plusieurs variantes, UN comparatif CALCULÉ.

Le dépôt du dossier FRDISI garde aujourd'hui côte à côte deux bordereaux
homonymes divergents et un LISEZ-MOI figé sur un montant mort. C'est la
signature d'un livrable qui COHABITE avec son prédécesseur au lieu de le
REMPLACER — et au niveau du moteur, cela veut dire une seule structure
porteuse de toutes les variantes.

Deux propriétés rendent la dérive impossible :

* le comparatif est une PROPRIÉTÉ calculée à la lecture, jamais un tableau
  stocké : il ne peut pas être périmé, il n'existe pas séparément des
  variantes ;
* l'``empreinte`` d'une étude change dès qu'une entrée change ; un artefact
  publié porte cette empreinte, donc on sait immédiatement qu'il ne
  correspond plus.
"""

import hashlib
from dataclasses import dataclass
from typing import Optional, Tuple

from core.calepinage.perf import optimiser_economique
from core.calepinage.robustesse import marges_du_plan
from core.calepinage.sensibilites import batterie

__all__ = ["Variante", "LigneComparatif", "Etude", "construire_variante"]


@dataclass(frozen=True)
class Variante:
    """Une variante : son entrée, son résultat, ses marges, son plancher."""

    code: str
    libelle: str
    entree: object
    modules: int
    kwc: float
    kit_codes: Tuple[str, ...]
    allee_m: float
    marge_troncon_cm: float
    marge_bande_cm: float
    plancher: int
    verdict: str
    optimal: bool = False

    @property
    def empreinte(self):
        """Empreinte STABLE de la variante (entrée + résultat)."""
        graine = "|".join((
            self.code, "%d" % self.modules, "%.3f" % self.allee_m,
            "+".join(sorted(self.kit_codes)), "%d" % self.plancher))
        return hashlib.sha256(graine.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class LigneComparatif:
    """Une ligne du tableau comparatif — CALCULÉE, jamais saisie."""

    code: str
    libelle: str
    modules: int
    kwc: float
    kits: str
    allee_m: float
    marge_troncon_cm: float
    marge_bande_cm: float
    plancher: int
    verdict: str
    retenue: bool


@dataclass(frozen=True)
class Etude:
    """``Etude(variantes, retenue, comparatif)`` — le comparatif est calculé."""

    repere: str
    variantes: Tuple[Variante, ...]
    code_retenue: Optional[str] = None

    def __post_init__(self):
        codes = [v.code for v in self.variantes]
        if len(set(codes)) != len(codes):
            raise ValueError("deux variantes portent le même code")
        if self.code_retenue is not None and self.code_retenue not in codes:
            raise ValueError("la variante retenue %r n'est pas dans l'étude"
                             % (self.code_retenue,))

    @property
    def retenue(self):
        """La variante retenue — EXPLICITE, jamais « la première »."""
        if self.code_retenue is None:
            return None
        for v in self.variantes:
            if v.code == self.code_retenue:
                return v
        return None

    @property
    def comparatif(self):
        """Tableau comparatif CALCULÉ à la lecture — donc jamais périmé."""
        return tuple(LigneComparatif(
            code=v.code, libelle=v.libelle, modules=v.modules, kwc=v.kwc,
            kits="+".join(v.kit_codes), allee_m=v.allee_m,
            marge_troncon_cm=v.marge_troncon_cm,
            marge_bande_cm=v.marge_bande_cm, plancher=v.plancher,
            verdict=v.verdict, retenue=(v.code == self.code_retenue))
            for v in self.variantes)

    @property
    def empreinte(self):
        """Empreinte de l'ÉTUDE : elle change dès qu'une variante change."""
        graine = "|".join([self.repere, self.code_retenue or ""]
                          + [v.empreinte for v in self.variantes])
        return hashlib.sha256(graine.encode("utf-8")).hexdigest()[:16]

    @property
    def meilleure(self):
        """La variante au plus grand compte — pas forcément la retenue."""
        if not self.variantes:
            return None
        return max(self.variantes, key=lambda v: (v.modules, v.code))

    def avec_variante(self, variante):
        """Rend une NOUVELLE étude — une étude ne se mute pas."""
        gardees = tuple(v for v in self.variantes if v.code != variante.code)
        return Etude(repere=self.repere,
                     variantes=gardees + (variante,),
                     code_retenue=self.code_retenue)

    def retenir(self, code):
        return Etude(repere=self.repere, variantes=self.variantes,
                     code_retenue=code)


def construire_variante(code, libelle, entree, engagement=None,
                        avec_sensibilites=True, politique=None):
    """Calcule TOUT ce que porte une variante — rien n'est saisi à la main."""
    resultat = optimiser_economique(entree.surface, entree.parametres,
                                    entree.obstacles, entree.zones, politique)
    rangees = tuple((y0, entree.parametres.kit(code_kit))
                    for y0, code_kit in resultat.rangees)
    marges = marges_du_plan(entree.surface, rangees, entree.obstacles,
                            entree.zones)
    if avec_sensibilites:
        batterie_resultat = batterie(entree.surface, entree.parametres,
                                     entree.obstacles, entree.zones,
                                     engagement=engagement,
                                     politique=politique)
        plancher = batterie_resultat.plancher
        verdict = batterie_resultat.verdict()
    else:
        plancher = resultat.modules
        verdict = ("plancher non calculé (sensibilités désactivées) : "
                   "%d modules" % resultat.modules)
    kit = entree.parametres.kits[0]
    return Variante(
        code=code, libelle=libelle, entree=entree, modules=resultat.modules,
        kwc=resultat.modules * kit.puissance_module_wc / 1000.0,
        kit_codes=tuple(sorted({c for _y0, c in resultat.rangees})),
        allee_m=entree.parametres.allee_m,
        marge_troncon_cm=marges.troncon_min_cm,
        marge_bande_cm=marges.bande_min_cm,
        plancher=plancher, verdict=verdict, optimal=resultat.optimal)
