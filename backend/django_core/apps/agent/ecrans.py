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


def cles_offertes() -> list:
    """Clés OFFERTES au modèle (énumération de ``erp.ouvrir``) : les écrans
    sans objet, et ceux dont le type d'objet a un résolveur de libellés qui
    existe — sinon la vue répondrait toujours 404 (revue 2A : calepinage,
    visite tant que leurs lanes n'ont pas livré ``selectors_libelles.py``).
    Calculé : l'écran apparaît dès que le résolveur arrive. La table du contrat
    reste complète ; seul ce qui est offert est filtré."""
    from .libelles import type_resolu

    return [cle for cle in cles()
            if not _table()['ecrans'][cle].get('objet') or type_resolu(_table()['ecrans'][cle]['objet'])]


def onglets_calepinage() -> list:
    """Onglets du calepinage que l'assistant peut ouvrir (liste fermée)."""
    return list(_table()['onglets_calepinage'])


class ParametreEcran(ValueError):
    """Paramètre refusé (400 nommé) : écran inconnu, onglet hors liste."""


class ObjetManquant(ParametreEcran):
    """Écran à objet demandé sans ``id`` : rien à ouvrir (404 nommé — la
    demande est conforme au schéma publié, où ``id`` est facultatif)."""


def chemin(ecran: str, ident: Optional[int] = None,
           onglet: Optional[str] = None) -> str:
    """Le chemin de l'écran, construit depuis la table. Lève
    :class:`ParametreEcran` (message en français, nommant le champ) ;
    :class:`ObjetManquant` quand un écran à objet est demandé sans ``id``."""
    fiche = _table()['ecrans'].get(ecran)
    if fiche is None:
        raise ParametreEcran('ecran : écran inconnu.')
    if onglet is not None and onglet not in onglets_calepinage():
        raise ParametreEcran('onglet : onglet inconnu.')
    if fiche.get('objet') and ident is None:
        raise ObjetManquant('id : obligatoire pour cet écran.')
    # Un paramètre SANS OBJET sur cet écran (``id`` d'un écran sans objet,
    # onglet d'un écran sans onglets) est ignoré : l'écran s'ouvre quand même.
    if not fiche.get('objet'):
        ident = None
    if not fiche.get('onglets'):
        onglet = None
    sortie = fiche['chemin'].replace('{id}', str(int(ident))) if ident is not None else fiche['chemin']
    if onglet is not None:
        sortie += ('&' if '?' in sortie else '?') + f'{PARAM_ONGLET}={onglet}'
    return sortie
