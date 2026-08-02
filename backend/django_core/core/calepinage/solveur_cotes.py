# -*- coding: utf-8 -*-
"""AOF37 — chaînes de cotes : port STRUCTURÉ de ``chain``/``closure``/``spread``.

Le solveur d'origine faisait trois choses qu'un moteur de production ne peut
pas faire : il ÉCRIVAIT ses contrôles en console (``print``), il rendait des
tuples anonymes, et sa tolérance de fermeture était un défaut unique (0,30)
alors que le relevé FRDISI a constaté des tolérances de 0,02 (chaîne fermée au
centimètre) à 0,30 (chaîne longue reconstituée). Ici :

* la TOLÉRANCE est un attribut de la CHAÎNE, jamais un défaut planqué ;
* une cote peut être MANQUANTE : elle est DÉDUITE par fermeture et bascule
  automatiquement en ``A_CONFIRMER`` (c'est exactement la profondeur de cage de
  l'école : 51,10 − (19,36 + 7,92 + 4,50 + 10,50) = 8,82, quand le client
  annonçait « ≈8,5 ») ;
* un dépassement de tolérance produit un objet en ÉCHEC — pas une exception :
  un relevé mal fermé doit REMONTER à l'écran, pas faire tomber un calcul ;
* la compensation au prorata (cheminement topographique) est disponible et
  n'est jamais appliquée en douce.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from core.calepinage.units import TOL_FERMETURE_DEFAUT_M, arrondi_mm

__all__ = [
    "StatutCote", "Cote", "Chaine", "ResultatChaine",
    "positions_cumulees", "fermeture", "compenser", "resoudre",
]


class StatutCote(Enum):
    MESUREE = "MESUREE"
    DEDUITE = "DEDUITE"
    A_CONFIRMER = "A_CONFIRMER"


@dataclass(frozen=True)
class Cote:
    """Une cote de chaîne. ``valeur=None`` = cote MANQUANTE à déduire."""

    nom: str
    valeur: Optional[float] = None
    statut: StatutCote = StatutCote.MESUREE

    @property
    def manquante(self):
        return self.valeur is None


@dataclass(frozen=True)
class Chaine:
    """Une chaîne 1D avec SA tolérance de fermeture (jamais un défaut global)."""

    nom: str
    cotes: Tuple[Cote, ...]
    total_mesure: Optional[float] = None
    tolerance_m: float = TOL_FERMETURE_DEFAUT_M
    depart: float = 0.0

    def __post_init__(self):
        if self.tolerance_m < 0:
            raise ValueError("tolérance de fermeture négative")
        if sum(1 for c in self.cotes if c.manquante) > 1:
            raise ValueError(
                "chaîne %s : une seule cote manquante peut être déduite par "
                "fermeture" % self.nom)


@dataclass(frozen=True)
class ResultatChaine:
    """Objet de sortie — AUCUN effet console, tout est lisible et testable."""

    nom: str
    cotes: Tuple[Cote, ...]
    positions: Tuple[float, ...]
    somme: float
    total_mesure: Optional[float]
    residu_m: float
    residu_pct: float
    tolerance_m: float
    ok: bool
    motif: str = ""

    @property
    def cotes_a_confirmer(self):
        return tuple(c for c in self.cotes if c.statut is StatutCote.A_CONFIRMER)

    @property
    def en_echec(self):
        return not self.ok


def positions_cumulees(depart, segments):
    """``chain`` d'origine : positions cumulées, arrondies au MILLIMÈTRE.

    L'arrondi mm est celui de ``units`` : c'est lui qui rend la chaîne
    reproductible entre le poste Windows et la CI Linux.
    """
    positions = [depart]
    for s in segments:
        positions.append(arrondi_mm(positions[-1] + s))
    return tuple(positions)


def fermeture(nom, calcule, mesure, tolerance=TOL_FERMETURE_DEFAUT_M):
    """``closure`` d'origine, SANS ``print`` : ``(ok, résidu_m, résidu_pct)``."""
    residu = arrondi_mm(calcule - mesure)
    pct = (100.0 * residu / mesure) if mesure else 0.0
    return (abs(residu) <= tolerance + 1e-12, residu, pct)


def compenser(residu, positions):
    """``spread`` d'origine : répartition du résidu au prorata (topographie)."""
    if not positions:
        return ()
    total = positions[-1] - positions[0]
    if total == 0:
        return tuple(positions)
    return tuple(arrondi_mm(p - residu * (p - positions[0]) / total)
                 for p in positions)


def resoudre(chaine, compensation=False):
    """Résout une chaîne : déduction d'une cote manquante + contrôle de fermeture.

    * une cote manquante est DÉDUITE du total mesuré et marquée ``A_CONFIRMER`` ;
    * sinon, le résidu est calculé et comparé à la tolérance DE LA CHAÎNE ;
    * ``compensation=True`` répartit le résidu au prorata sur les positions.
    """
    manquantes = [i for i, c in enumerate(chaine.cotes) if c.manquante]
    cotes = list(chaine.cotes)
    motif = ""

    if manquantes:
        if chaine.total_mesure is None:
            return ResultatChaine(
                nom=chaine.nom, cotes=tuple(cotes), positions=(), somme=0.0,
                total_mesure=None, residu_m=0.0, residu_pct=0.0,
                tolerance_m=chaine.tolerance_m, ok=False,
                motif="cote manquante SANS total mesuré : rien à déduire")
        connue = sum(c.valeur for c in cotes if not c.manquante)
        deduite = arrondi_mm(chaine.total_mesure - connue)
        i = manquantes[0]
        if deduite <= 0:
            return ResultatChaine(
                nom=chaine.nom, cotes=tuple(cotes), positions=(), somme=connue,
                total_mesure=chaine.total_mesure,
                residu_m=arrondi_mm(connue - chaine.total_mesure),
                residu_pct=0.0, tolerance_m=chaine.tolerance_m, ok=False,
                motif="déduction impossible : la cote %s serait ≤ 0"
                      % cotes[i].nom)
        cotes[i] = Cote(nom=cotes[i].nom, valeur=deduite,
                        statut=StatutCote.A_CONFIRMER)
        motif = ("cote %s DÉDUITE par fermeture (%.3f m) — à confirmer à "
                 "l'exécution" % (cotes[i].nom, deduite))

    segments = [c.valeur for c in cotes]
    positions = positions_cumulees(chaine.depart, segments)
    somme = arrondi_mm(positions[-1] - chaine.depart)

    if chaine.total_mesure is None:
        return ResultatChaine(
            nom=chaine.nom, cotes=tuple(cotes), positions=positions, somme=somme,
            total_mesure=None, residu_m=0.0, residu_pct=0.0,
            tolerance_m=chaine.tolerance_m, ok=True, motif=motif)

    ok, residu, pct = fermeture(chaine.nom, somme, chaine.total_mesure,
                                chaine.tolerance_m)
    if compensation and residu:
        positions = compenser(residu, positions)
    if not ok:
        motif = ("fermeture NON tenue : résidu %+.3f m (%+.2f %%) pour une "
                 "tolérance de %.3f m" % (residu, pct, chaine.tolerance_m))
    return ResultatChaine(
        nom=chaine.nom, cotes=tuple(cotes), positions=positions, somme=somme,
        total_mesure=chaine.total_mesure, residu_m=residu, residu_pct=pct,
        tolerance_m=chaine.tolerance_m, ok=ok, motif=motif)
