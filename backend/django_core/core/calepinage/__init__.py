# -*- coding: utf-8 -*-
"""``core.calepinage`` — le moteur de calepinage PHOTOVOLTAÏQUE, paquet PUR.

Deux consommateurs qui ne peuvent pas s'importer l'un l'autre en dépendent :
``apps.ao`` (réponse à appel d'offres) et ``apps.ventes`` (villa). Le paquet est
donc logé dans la couche fondation ``core`` et sa PURETÉ est un contrat :

* stdlib + ``numpy`` UNIQUEMENT — zéro ``django``, zéro ``rest_framework``,
  zéro ``apps.*``, zéro autre module de ``core`` ;
* zéro I/O — le moteur ne lit ni n'écrit aucun fichier ; le rendu retourne des
  OCTETS que l'appelant écrit où il veut (les scripts d'origine écrivaient dans
  un chemin OneDrive absolu et plantaient sur toute autre machine) ;
* zéro globale mutable — toute configuration passe par un ``Parametres``
  immuable passé en argument (les scripts d'origine reconfiguraient le moteur
  en MUTANT les globales d'un module : ni parallélisable ni reproductible).

Bénéfice décisif : le paquet est testable SANS base de données, donc les golden
tests tournent hors du gate migrations — le poste de coût CI dominant.

La pureté est armée en CI par le contrat import-linter
``calepinage-est-un-noyau-pur`` ET par ``core/tests/test_calepinage_purete.py``
(analyse AST : tout import interdit rend le test ROUGE).
"""

from core.calepinage.version import (
    SCHEMA_VERSION,
    VERSION_MOTEUR,
    compatible,
    version_tuple,
)

__all__ = [
    "SCHEMA_VERSION",
    "VERSION_MOTEUR",
    "compatible",
    "version_tuple",
]
