# -*- coding: utf-8 -*-
"""AOF70 — profils INTERNE / DÉPÔT : le lexique, les blocs sensibles, les métadonnées.

Le constat est mesuré sur les scripts réels de la session du 27/07/2026 : les
vues INTERNES emploient massivement le mot « client » (``vue_bat_A_v2.py`` 12
occurrences, ``vue_bat_B_v2.py`` 31, ``vue_bat_C.py`` 31), et les trois scripts
de DÉPÔT n'en contiennent **aucune**. La traduction n'a pas été inventée : elle
a été faite à la main, systématiquement, et c'est exactement le genre de travail
qu'on oublie une fois sur dix — la fois qui compte.

Le lexique de substitution, tel qu'il a réellement été appliqué :

===========================================  ==================================
interne                                      dépôt
===========================================  ==================================
« décision client »                          « DÉCISION D'ÉTUDES DU <date> »
« le client dit que ça n'existe pas »        « ÉCARTÉ AU RELEVÉ »
« consigne client »                          « prescription »
« croquis »                                  « relevé contradictoire du <date> »
===========================================  ==================================

Un mot du lexique interdit qui SURVIT à la traduction fait ÉCHOUER le rendu de
dépôt, en citant le mot : mieux vaut une planche non produite qu'une planche
remise qui raconte l'intérieur du candidat au maître d'ouvrage.

Le profil pilote trois choses, et rien d'autre :

* le **lexique** injecté (traduction + refus) ;
* la présence des **blocs sensibles** — marges, provenance crue d'une donnée,
  maximum agrégé du site : trois informations parfaitement légitimes en
  interne, et qui, remises, donnent au maître d'ouvrage de quoi négocier
  contre le candidat ;
* les **métadonnées** du binaire (``rendu/metadata.py``).
"""

import re
from dataclasses import dataclass
from enum import Enum

#: Blocs qu'une planche peut porter. Les trois derniers sont SENSIBLES.
BLOC_MARGES = "marges"
BLOC_PROVENANCE_CRUE = "provenance_crue"
BLOC_MAXIMUM_AGREGE = "maximum_agrege"

#: Blocs réservés à l'usage interne — jamais dans un dépôt.
BLOCS_SENSIBLES = (BLOC_MARGES, BLOC_PROVENANCE_CRUE, BLOC_MAXIMUM_AGREGE)

#: Mots dont la seule présence dans un rendu de DÉPÔT est un défaut. Ils
#: décrivent la relation commerciale ou la cuisine interne, pas l'ouvrage.
#: La recherche se fait sur un DÉBUT de mot : « client » attrape aussi
#: « clients » et « clientèle », inutile de les énumérer.
MOTS_INTERDITS_AU_DEPOT = ("client", "croquis", "prix d'achat", "prix achat",
                           "coût d'achat", "marge commerciale", "notre marge",
                           "sous-traitance", "sous-traitant")


class LexiqueInterdit(ValueError):
    """Un mot réservé à l'interne a survécu jusqu'au rendu de dépôt."""


class BlocInterditAuDepot(ValueError):
    """Un bloc sensible a été demandé dans un rendu de dépôt."""


@dataclass(frozen=True)
class ContexteLexique:
    """Les dates que la traduction a besoin de nommer.

    Elles ne sont PAS codées en dur : « relevé contradictoire du 27/07/2026 »
    est vrai pour ce dossier-là et faux pour le suivant.
    """

    date_releve: str
    date_decision: str = ""

    def __post_init__(self):
        if not (self.date_releve or "").strip():
            raise ValueError(
                "la traduction de « croquis » nomme la date du relevé "
                "contradictoire : elle est obligatoire")


def _substitutions(contexte):
    """Les couples ``(motif, remplacement)``, du plus long au plus court.

    L'ordre est le contrat : traduire « client » avant « décision client »
    laisserait des phrases bancales derrière lui.
    """
    decision = contexte.date_decision or contexte.date_releve
    return (
        (r"le\s+client\s+dit\s+que\s+ça\s+n['’]existe\s+pas",
         "ÉCARTÉ AU RELEVÉ"),
        (r"décision\s+client", "DÉCISION D'ÉTUDES DU %s" % (decision,)),
        (r"consigne\s+client", "prescription"),
        (r"croquis", "relevé contradictoire du %s" % (contexte.date_releve,)),
    )


class Profil(Enum):
    """À qui la planche est destinée. Tout le reste en découle."""

    INTERNE = "interne"
    DEPOT = "depot"

    @property
    def applique_le_lexique(self):
        return self is Profil.DEPOT

    @property
    def blocs_sensibles_autorises(self):
        """En dépôt : aucun. En interne : tous."""
        return BLOCS_SENSIBLES if self is Profil.INTERNE else ()

    def autorise(self, bloc):
        return bloc not in BLOCS_SENSIBLES or self is Profil.INTERNE


def traduire(texte, contexte):
    """Applique le lexique de substitution, dans l'ordre du contrat."""
    resultat = texte or ""
    for motif, remplacement in _substitutions(contexte):
        resultat = re.sub(motif, remplacement, resultat, flags=re.IGNORECASE)
    return resultat


def mot_interdit(texte):
    """Le premier mot interdit trouvé, ou ``None``. Insensible à la casse."""
    minuscule = (texte or "").casefold()
    for mot in MOTS_INTERDITS_AU_DEPOT:
        if re.search(r"\b" + re.escape(mot.casefold()), minuscule):
            return mot
    return None


def verifier_depot(texte):
    """Refuse un texte de dépôt portant un mot interdit, en le CITANT."""
    mot = mot_interdit(texte)
    if mot is not None:
        raise LexiqueInterdit(
            "mot interdit dans un rendu de dépôt : « %s » (texte : « %s »)"
            % (mot, texte))
    return texte


def preparer(texte, profil, contexte=None):
    """Le texte tel qu'il doit paraître pour ce profil.

    * INTERNE : inchangé — c'est le document de travail, il dit les choses.
    * DÉPÔT : traduit par le lexique, puis VÉRIFIÉ. Ce qui n'a pas de
      traduction fait échouer le rendu au lieu de passer inaperçu.
    """
    if not profil.applique_le_lexique:
        return texte
    if contexte is None:
        raise ValueError(
            "un rendu de dépôt exige son contexte de lexique (date du relevé)")
    return verifier_depot(traduire(texte, contexte))


def preparer_tous(textes, profil, contexte=None):
    return tuple(preparer(texte, profil, contexte) for texte in textes)


@dataclass(frozen=True)
class BlocDePlanche:
    """Un bloc de texte de la planche, avec sa clé de sensibilité."""

    cle: str
    lignes: tuple

    @property
    def sensible(self):
        return self.cle in BLOCS_SENSIBLES


def filtrer_blocs(blocs, profil):
    """Ne garde que les blocs que ce profil a le droit de montrer."""
    return tuple(bloc for bloc in blocs if profil.autorise(bloc.cle))


def exiger_blocs_permis(blocs, profil):
    """Refuse un bloc sensible explicitement demandé dans un dépôt.

    ``filtrer_blocs`` retire en silence ; cette fonction-ci proteste. Les deux
    existent parce qu'un pipeline qui filtre tout seul finit par masquer une
    erreur d'assemblage.
    """
    for bloc in blocs:
        if not profil.autorise(bloc.cle):
            raise BlocInterditAuDepot(
                "bloc réservé à l'interne dans un rendu de dépôt : « %s »"
                % (bloc.cle,))
    return tuple(blocs)
