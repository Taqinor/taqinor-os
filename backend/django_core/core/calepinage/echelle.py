# -*- coding: utf-8 -*-
"""AOF53 — échelle de décomposition marche par marche + ASSERTIONS D'HONNÊTETÉ.

« On est passé de 112 à 126 » est l'argument le plus puissant d'un dossier
technique — et le plus facile à falsifier sans le vouloir. Chaque état
antérieur est donc REJOUÉ AVEC LE MOTEUR COURANT, jamais recopié d'une note :
si une correction du moteur change ce que valait l'ancien modèle, le récit
change avec lui, immédiatement et visiblement.

L'arc du bâtiment B, marche par marche :

* **A** — ancien modèle tel quel (uniforme 1,20, tables jointives en abscisse
  développée) : 112 ;
* **B** — durcissement de la correction d'arc (le pas ne recouvre plus au
  rayon intérieur) : le vrai prix de la correction ;
* **C** — dégagement porté de 0,30 à 0,35 en abscisse (0,336 m RÉELS) ;
* **D** — allées 0,60 et rives d'extrémité 0,35 ;
* **E** — rangées explicites, tout paysage ;
* **F** — segment 1 en tables portrait : 120, le chiffre PUBLIÉ ;
* **G** — structures de rive non cotées hors zone PV ;
* **H** — recalage du segment 3 : 126.

Sans les assertions d'honnêteté, ce récit peut être silencieusement FAUX : une
marche déclarée ``attendu=112`` DOIT redonner 112, et falsifier un état rend le
test rouge EN NOMMANT la marche. S'y ajoutent les monotonies MÉTIER — retirer
un obstacle ne peut pas faire perdre, un recalage ne peut pas faire perdre, un
kit unique ne peut pas battre un jeu mixte.
"""

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from core.calepinage.exceptions import CalepinageIncoherent
from core.calepinage.types import Marche

__all__ = [
    "EtatNomme", "MonotonieMetier", "Echelle", "comparer",
    "verifier_honnetete", "verifier_monotonies", "MONOTONIES_STANDARD",
]


@dataclass(frozen=True)
class EtatNomme:
    """Un état antérieur, rejouable : son calcul est une FONCTION, pas un nombre."""

    code: str
    libelle: str
    calculer: Callable[[], int]
    attendu: Optional[int] = None


@dataclass(frozen=True)
class MonotonieMetier:
    """Une règle de bon sens que le moteur doit respecter, code contre code."""

    code_avant: str
    code_apres: str
    sens: str                      # ">=" : après ne peut pas être inférieur
    libelle: str = ""

    def __post_init__(self):
        if self.sens not in (">=", "<="):
            raise ValueError("sens de monotonie inconnu : %r" % (self.sens,))


@dataclass(frozen=True)
class Echelle:
    """Les marches calculées + leurs deltas signés."""

    marches: Tuple[Marche, ...]

    def marche(self, code):
        for m in self.marches:
            if m.code == code:
                return m
        raise KeyError("aucune marche %r dans l'échelle" % (code,))

    @property
    def depart(self):
        return self.marches[0].modules if self.marches else 0

    @property
    def arrivee(self):
        return self.marches[-1].modules if self.marches else 0

    @property
    def gain_total(self):
        return self.arrivee - self.depart

    def recit(self):
        """Phrase GÉNÉRÉE du récit — jamais rédigée à la main."""
        if not self.marches:
            return "aucune marche"
        return "%s (%d) → %s (%d) : %+d modules en %d marches" % (
            self.marches[0].code, self.depart, self.marches[-1].code,
            self.arrivee, self.gain_total, len(self.marches))


#: Monotonies applicables à l'échelle de l'arc (codes de ce dossier).
MONOTONIES_STANDARD = (
    MonotonieMetier("F", "G", ">=",
                    "retirer un obstacle ne peut pas faire perdre de modules"),
    MonotonieMetier("G", "H", ">=",
                    "un recalage de rangées ne peut pas faire perdre"),
)


def comparer(etats):
    """Rejoue chaque état AVEC LE MOTEUR COURANT et publie les deltas signés."""
    marches = []
    precedent = None
    for etat in etats:
        modules = int(etat.calculer())
        delta = 0 if precedent is None else modules - precedent
        marches.append(Marche(code=etat.code, libelle=etat.libelle,
                              modules=modules, delta=delta,
                              attendu=etat.attendu))
        precedent = modules
    return Echelle(marches=tuple(marches))


def verifier_honnetete(echelle, strict=True):
    """Une marche déclarée ``attendu`` DOIT redonner ce nombre — sinon rouge."""
    motifs = []
    for marche in echelle.marches:
        if marche.attendu is None:
            continue
        if marche.modules != marche.attendu:
            motifs.append(
                "marche %s (%s) : attendu %d modules, le moteur courant en "
                "rend %d — le récit « ancien → aujourd'hui » serait FAUX"
                % (marche.code, marche.libelle, marche.attendu,
                   marche.modules))
    if motifs and strict:
        premier = echelle.marches[0]
        for marche in echelle.marches:
            if marche.attendu is not None and marche.modules != marche.attendu:
                premier = marche
                break
        raise CalepinageIncoherent("echelle", premier.code, motifs[0])
    return tuple(motifs)


def verifier_monotonies(echelle, regles=MONOTONIES_STANDARD, strict=True):
    """Les règles de bon sens métier, code contre code, NOMMÉES en cas d'échec."""
    motifs = []
    for regle in regles:
        try:
            avant = echelle.marche(regle.code_avant)
            apres = echelle.marche(regle.code_apres)
        except KeyError:
            continue
        tenu = (apres.modules >= avant.modules if regle.sens == ">="
                else apres.modules <= avant.modules)
        if not tenu:
            motifs.append(
                "monotonie non tenue entre %s (%d) et %s (%d) : %s"
                % (regle.code_avant, avant.modules, regle.code_apres,
                   apres.modules, regle.libelle))
    if motifs and strict:
        raise CalepinageIncoherent("monotonie", regles[0].code_apres, motifs[0])
    return tuple(motifs)
