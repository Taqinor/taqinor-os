"""Copilote vague 2 (FND2, FND8) — la table des écrans que l'assistant ouvre.

Source UNIQUE : ``contract_samples/assistant_ecrans.json`` (contrat d'abord,
A0). Le registre en tire l'énumération de l'action ``erp.ouvrir`` ; la vue
``GET agent/ouvrir/`` y construit le chemin. Le chemin n'est JAMAIS une chaîne
venue du modèle : il naît ici, d'un gabarit de la table et d'un entier.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

FICHIER = Path(__file__).resolve().parent / 'contract_samples' / 'assistant_ecrans.json'
PARAM_ONGLET = 'onglet'


@lru_cache(maxsize=1)
def _table() -> dict:
    return json.loads(FICHIER.read_text(encoding='utf-8'))


def ecrans() -> dict:
    """``{clé: {chemin, objet, titre[, onglets]}}`` (copie : jamais modifiée)."""
    return {cle: dict(v) for cle, v in _table()['ecrans'].items()}


def cles() -> list:
    """Clés des écrans, triées (énumération de l'action ``erp.ouvrir``)."""
    return sorted(_table()['ecrans'])


def onglets_calepinage() -> list:
    """Onglets du calepinage que l'assistant peut ouvrir (liste fermée)."""
    return list(_table()['onglets_calepinage'])


class ParametreEcran(ValueError):
    """Paramètre refusé (400 nommé) : écran inconnu, id manquant ou en trop,
    onglet hors liste."""


def chemin(ecran: str, ident: Optional[int] = None,
           onglet: Optional[str] = None) -> str:
    """Le chemin de l'écran, construit depuis la table. Lève
    :class:`ParametreEcran` (message en français, nommant le champ)."""
    fiche = _table()['ecrans'].get(ecran)
    if fiche is None:
        raise ParametreEcran('ecran : écran inconnu.')
    if fiche.get('objet') and ident is None:
        raise ParametreEcran('id : obligatoire pour cet écran.')
    if not fiche.get('objet') and ident is not None:
        raise ParametreEcran("id : cet écran n'ouvre aucun objet.")
    if onglet is not None and (not fiche.get('onglets')
                               or onglet not in onglets_calepinage()):
        raise ParametreEcran('onglet : onglet inconnu pour cet écran.')
    sortie = fiche['chemin'].replace('{id}', str(int(ident))) if ident is not None else fiche['chemin']
    if onglet is not None:
        sortie += ('&' if '?' in sortie else '?') + f'{PARAM_ONGLET}={onglet}'
    return sortie
