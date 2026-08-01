# -*- coding: utf-8 -*-
"""AOF70 — les métadonnées d'un livrable sont FORCÉES, jamais laissées par défaut.

Trou réel et mesuré : les trois scripts de dépôt du 27/07/2026 n'appellent
``savefig`` avec **aucun** ``metadata=…``. Les trois PDF remis sont donc partis
avec les ``Creator`` / ``Producer`` par défaut de matplotlib — c'est-à-dire en
annonçant au maître d'ouvrage l'outil de leur auteur — et leurs chemins de
sortie contenaient « OneDrive - Atlencia » et le nom de la société propriétaire
en dur.

Ce module produit le dictionnaire de métadonnées à appliquer et fournit les
deux contrôles binaires correspondants. Il n'importe PAS matplotlib : il
décrit, il ne rend pas. ``Feuille.png()`` / ``Feuille.pdf()`` reçoivent le
dictionnaire ; le rendu ne connaissant aucun chemin, aucun chemin ne peut
entrer dans le binaire.

Reproductibilité : ``date_creation`` doit être fournie avec son fuseau
(``timezone.utc`` de préférence). Sans elle, matplotlib horodate à l'instant du
rendu et deux rendus de la même donnée cessent d'être comparables octet à
octet — ce qui interdit de prouver qu'une planche n'a pas bougé entre deux
remises.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

#: Ce que le livrable annonce comme outil de production. Neutre par décision :
#: le maître d'ouvrage n'a pas à connaître la chaîne technique du candidat.
CREATOR_NEUTRE = "Calepinage photovoltaïque"

#: Marqueurs des métadonnées laissées par défaut : leur présence dans un
#: binaire signe un ``savefig`` sans ``metadata=``.
MARQUEURS_PAR_DEFAUT = (b"Matplotlib", b"matplotlib")

#: Fragments de chemins de poste de travail relevés dans les livrables réels.
MARQUEURS_DE_CHEMIN = (b"OneDrive", b"Atlencia", b"C:/Users", b"C:\\Users",
                       b"/home/", b"/Users/", b"\\Documents\\")

#: Horodatage neutre et STABLE, pour un artefact dont on veut prouver qu'il
#: n'a pas bougé entre deux remises.
DATE_STABLE = datetime(2000, 1, 1, tzinfo=timezone.utc)


class MetadonneesParDefaut(ValueError):
    """Le binaire porte encore les métadonnées par défaut du moteur de rendu."""


class CheminLocalDansLeLivrable(ValueError):
    """Un chemin de poste de travail a fui dans un livrable."""


@dataclass(frozen=True)
class MetadonneesPdf:
    """Ce qu'un PDF remis a le droit de déclarer sur lui-même.

    ``Author`` est le SOUMISSIONNAIRE — pas l'exploitant du moteur : en marque
    blanche, c'est la seule identité qui doit paraître (voir
    ``rendu/cartouche.py``).
    """

    code_document: str
    soumissionnaire: str
    objet: str = ""
    mots_cles: str = ""
    date_creation: datetime = None

    def __post_init__(self):
        if not (self.code_document or "").strip():
            raise ValueError("un livrable sans code document n'est pas traçable")
        if not (self.soumissionnaire or "").strip():
            raise ValueError("un livrable sans soumissionnaire n'est pas remissible")
        if self.date_creation is not None and self.date_creation.tzinfo is None:
            raise ValueError(
                "date de création sans fuseau : l'horodatage dépendrait du "
                "poste qui rend la planche")

    def pour_matplotlib(self):
        """Le dictionnaire à passer à ``Feuille.pdf(metadonnees=…)``."""
        valeurs = {
            "Title": self.code_document,
            "Author": self.soumissionnaire,
            "Subject": self.objet,
            "Keywords": self.mots_cles,
            "Creator": CREATOR_NEUTRE,
            "Producer": CREATOR_NEUTRE,
        }
        if self.date_creation is not None:
            valeurs["CreationDate"] = self.date_creation
        return valeurs

    def pour_png(self):
        """Le PNG n'a qu'une clé d'outil : ``Software``. Elle est neutralisée."""
        return {"Software": CREATOR_NEUTRE,
                "Title": self.code_document,
                "Author": self.soumissionnaire,
                "Description": self.objet}

    def horodatee(self, date=DATE_STABLE):
        """La même déclaration, horodatée de façon STABLE et reproductible."""
        return MetadonneesPdf(code_document=self.code_document,
                              soumissionnaire=self.soumissionnaire,
                              objet=self.objet, mots_cles=self.mots_cles,
                              date_creation=date)


def verifier_sans_metadonnees_par_defaut(octets):
    """Refuse un binaire qui annonce encore son moteur de rendu."""
    for marqueur in MARQUEURS_PAR_DEFAUT:
        if marqueur in octets:
            raise MetadonneesParDefaut(
                "métadonnée par défaut du moteur de rendu dans le livrable : "
                "« %s » — le rendu a été fait sans métadonnées forcées"
                % (marqueur.decode("ascii"),))
    return True


def verifier_sans_chemin_local(octets, marqueurs=MARQUEURS_DE_CHEMIN):
    """Refuse un binaire qui porte un chemin de poste de travail."""
    for marqueur in marqueurs:
        if marqueur in octets:
            raise CheminLocalDansLeLivrable(
                "chemin local dans le livrable : « %s »"
                % (marqueur.decode("latin-1"),))
    return True


def verifier_sans_terme_interdit(octets, termes):
    """Refuse un binaire portant un terme interdit (nom de société, mot interne).

    Attention : un PDF matplotlib encode son texte en glyphes (police Type 3),
    donc ce contrôle porte sur ce qui EST littéral — au premier chef le
    dictionnaire de métadonnées. Le contrôle du texte rendu, lui, se fait sur
    les chaînes avant tracé (``profils.preparer``).
    """
    for terme in termes:
        if not terme:
            continue
        for encodage in ("utf-8", "latin-1", "utf-16-be"):
            try:
                motif = terme.encode(encodage)
            except UnicodeEncodeError:      # pragma: no cover
                continue
            if motif and motif in octets:
                raise CheminLocalDansLeLivrable(
                    "terme interdit dans le livrable : « %s »" % (terme,))
    return True
