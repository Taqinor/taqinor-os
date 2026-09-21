"""Le chargeur des fixtures HTML — SUPPORT DE TEST, jamais du code de collecte.

C'est le SEUL module du paquet ``portail`` autorisé à lire le disque, et il
est explicitement exclu du contrat de pureté pour cette raison
(``tests/test_purete_portail.py`` vérifie qu'aucun module de collecte ne
l'importe : un parseur qui lirait une fixture serait un parseur qui fait de
l'E/S).

Les fichiers sont lus en UTF-8 strict — le portail sert de l'UTF-8 et une
mauvaise reconnaissance d'encodage se voit immédiatement sur les accents des
objets d'avis (« Fourniture et installation d'une centrale… »).

Provenance des fichiers : voir ``README.md`` du même dossier. Elle est écrite
sans détour — ce sont des reconstructions fidèles des ancres relevées le
2026-08-01, pas des captures octet-pour-octet.
"""
from __future__ import annotations

from pathlib import Path

DOSSIER = Path(__file__).resolve().parent

#: Les fixtures du groupe, nommées — un test qui écrit « le fichier des 500 »
#: en dur casse au premier renommage.
RESULTATS_10 = 'resultats_solaire_10.html'
RESULTATS_500 = 'resultats_solaire_500.html'
RESULTATS_VIDE = 'resultats_vide.html'
RESULTATS_INCOHERENT = 'resultats_incoherent.html'
RESULTATS_DERIVE = 'resultats_derive.html'
ERREUR_403 = 'erreur_403.html'
DETAIL = 'detail_consultation.html'

#: Les cinq fixtures exigées par VAO15, plus les deux cas de dérive dont
#: VAO20 a besoin pour prouver qu'un HTML dérivé lève une erreur NOMMÉE.
TOUTES = (
    RESULTATS_10, RESULTATS_500, RESULTATS_VIDE,
    RESULTATS_INCOHERENT, RESULTATS_DERIVE, ERREUR_403, DETAIL,
)


def charger(nom):
    """Le contenu d'une fixture, en texte UTF-8.

    Lève ``FileNotFoundError`` avec le nom fautif : un test qui échoue sur une
    fixture absente doit dire LAQUELLE, pas rendre une chaîne vide (ce serait
    exactement le « 0 résultat en silence » que ce groupe combat).
    """
    chemin = DOSSIER / nom
    if not chemin.is_file():
        raise FileNotFoundError(
            f'Fixture « {nom} » introuvable dans {DOSSIER}. '
            f'Fixtures disponibles : {", ".join(sorted(TOUTES))}.')
    return chemin.read_text(encoding='utf-8')


__all__ = [
    'DETAIL', 'DOSSIER', 'ERREUR_403', 'RESULTATS_10', 'RESULTATS_500',
    'RESULTATS_DERIVE', 'RESULTATS_INCOHERENT', 'RESULTATS_VIDE', 'TOUTES',
    'charger',
]
