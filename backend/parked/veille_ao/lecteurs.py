"""VAO21 — le REGISTRE des lecteurs de source : la prise où se branchera le
collecteur portail, sans réécrire une ligne de l'orchestration.

Pourquoi un registre plutôt qu'un ``if type_source == …`` dans le service
--------------------------------------------------------------------------
Le collecteur du portail public (VAO15-VAO20) est **gaté par une action
fondateur** (VAO2 : ouvrir le compte entreprise et aller voir si le flux RSS
authentifié existe — s'il existe, VAO15-VAO20 ne sont JAMAIS construites). Le
service de collecte (VAO21) doit donc exister et être testable AUJOURD'HUI,
sans ce collecteur, et l'accueillir DEMAIN sans être réécrit.

Un lecteur est une fonction ``lecteur(source, mots_cles) -> iterable[dict]``
qui rend des dictionnaires d'avis BRUTS (les clés de
``services.CHAMPS_RECTIFIABLES``). Il est enregistré pour un **type de
source**, jamais pour une URL en dur — la carte des sources vit en base
(``SourceVeille``, VAO7).

Aucun lecteur RÉSEAU n'est enregistré ici, et c'est délibéré : ce module
n'importe ni ``httpx`` ni aucun client HTTP, et le seul lecteur fourni est
celui des portes HUMAINES (saisie manuelle, import de fichier, tuyau
partenaire), qui ne lit RIEN — les avis y arrivent par VAO27/VAO28, pas par
une collecte. Brancher le portail se fera en UN appel
``enregistrer_lecteur(TypeSource.PORTAIL_OFFICIEL, portail.collecter_avis)``
depuis le paquet ``portail/``, le jour où la règle #5 l'autorise.
"""
from __future__ import annotations

from .models import TYPES_COLLECTABLES, TypeSource


class LecteurIndisponible(RuntimeError):
    """Aucun lecteur n'est branché pour ce type de source.

    Ce n'est PAS « 0 résultat » : la distinction est le cœur de VAO20/VAO24
    (« échouer FORT, jamais 0 résultat en silence »). Un type collectable sans
    lecteur est une collecte IMPOSSIBLE, et le journal d'exécution doit le
    dire — sinon on se croit couvert alors que rien ne tourne.
    """


#: {type_source: lecteur}. Peuplé par ``enregistrer_lecteur`` ; volontairement
#: VIDE pour les types réseau tant que VAO2 n'a pas tranché.
_LECTEURS: dict = {}


def enregistrer_lecteur(type_source, lecteur):
    """Branche un lecteur pour un type de source (idempotent : remplace)."""
    _LECTEURS[str(type_source)] = lecteur


def retirer_lecteur(type_source):
    """Débranche un lecteur (surtout utile en test, pour isoler le registre)."""
    _LECTEURS.pop(str(type_source), None)


def lecteurs_enregistres():
    """Les types de source qui ont un lecteur branché (triés, stables)."""
    return sorted(_LECTEURS)


def lecteur_pour(source):
    """Le lecteur de CETTE source, ou ``LecteurIndisponible``.

    Une source dont le type n'est pas collectable (les trois portes humaines)
    n'a rien à interroger : c'est une erreur d'appel, dite en français.
    """
    type_source = str(source.type_source)
    if type_source not in {str(t) for t in TYPES_COLLECTABLES}:
        raise LecteurIndisponible(
            f'La source « {source.libelle} » est une porte humaine '
            f'({source.get_type_source_display()}) : elle ne se collecte pas, '
            "les avis y entrent par la saisie manuelle ou l'import.")
    lecteur = _LECTEURS.get(type_source)
    if lecteur is None:
        raise LecteurIndisponible(
            f'Aucun collecteur n\'est branché pour « '
            f'{source.get_type_source_display()} ». Le collecteur du portail '
            'public attend la décision fondateur (compte entreprise + flux '
            'RSS officiel) avant d\'être construit et armé.')
    return lecteur


def lecteur_porte_humaine(source, mots_cles):  # noqa: ARG001 — signature du contrat
    """Lecteur NEUTRE des portes humaines : ne lit rien, ne rend rien.

    Il existe pour que le contrat de lecteur soit démontrable sans réseau (un
    test peut l'enregistrer et prouver que l'orchestration tourne à vide sans
    exploser). Il n'est PAS enregistré par défaut.
    """
    return []


__all__ = [
    'LecteurIndisponible', 'TypeSource', 'enregistrer_lecteur',
    'lecteur_porte_humaine', 'lecteur_pour', 'lecteurs_enregistres',
    'retirer_lecteur',
]
