"""ACAL871 — le REGISTRE des explications : une phrase par grandeur affichée.

Le registre est une DONNÉE versionnée (``data/explications.json``, forme du
contrat ``contract_samples/calepinage_explications.json``), jamais du code :
chaque entrée dit la cause et le geste d'une grandeur de l'écran, avec des
trous ``{nom}`` que l'écran remplit par des valeurs SERVIES (``valeurs`` :
nom → chemin dans le résultat servi). Une société n'y ajoute rien : le même
registre sert tout le monde, sans aucune donnée d'une société.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

#: Chemin du dépôt, pas une mesure : ``parents[1]`` = le paquet ``apps/calepinage``
#: (ce module vit dans ``services/``), où ``data/explications.json`` est committé.
FICHIER_EXPLICATIONS = Path(__file__).resolve().parents[1] / 'data' / 'explications.json'

__all__ = ['FICHIER_EXPLICATIONS', 'charger_explications']


@lru_cache(maxsize=1)
def _lire_fichier():
    texte = FICHIER_EXPLICATIONS.read_text(encoding='utf-8')
    return tuple(json.loads(texte)['entrees'])


def charger_explications():
    """``{entrees: [...]}`` trié par famille puis par clé (ordre stable,
    identique au fichier tant que celui-ci est tenu trié)."""
    entrees = sorted(_lire_fichier(), key=lambda e: (e['famille'], e['cle']))
    return {'entrees': entrees}
