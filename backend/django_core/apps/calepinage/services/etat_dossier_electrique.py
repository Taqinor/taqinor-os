"""ACAL934 — l'état à trois valeurs du dossier électrique, défini UNE fois.

``pret`` / ``a_completer`` / ``bloquant`` et ses ``points`` ; la classification
à quatre mots de ``verdict_de_conception`` (inchangée) vit à côté. Ni l'une ni
l'autre ne touche ``publiable`` (D-ACAL-9 : « à compléter » publie).
"""
from __future__ import annotations

from core.electrique.types import (
    STATUT_ALERTE, STATUT_BLOQUANT, STATUT_NON_VERIFIABLE,
)

#: Les trois états, définis ICI seulement : prêt, à compléter, bloquant.
ETATS_DOSSIER = ('pret', 'a_completer', 'bloquant')


def etat_a_chaud(bloquants, manquantes):
    """Bloquants ⇒ ``bloquant`` ; manquantes ⇒ ``a_completer`` ; ``pret``."""
    pret, a_completer, bloquant = ETATS_DOSSIER
    if bloquants:
        return {'etat': bloquant, 'points': len(bloquants)}
    if manquantes:
        return {'etat': a_completer, 'points': len(manquantes)}
    return {'etat': pret, 'points': 0}


def _statuts_a_completer():
    from .electrique import STATUT_MOTIF_OMIS, STATUT_MOTIF_SANS_SOURCE

    return (STATUT_NON_VERIFIABLE, STATUT_MOTIF_OMIS, STATUT_MOTIF_SANS_SOURCE)


def etat_de_publication(motifs):
    """Motifs ``bloquant`` d'abord, puis ``non_verifiable``/``omis``/``sans_source``."""
    statuts = [motif.get('statut') for motif in motifs or ()]
    a_completer = _statuts_a_completer()
    return etat_a_chaud([s for s in statuts if s == STATUT_BLOQUANT],
                        [s for s in statuts if s in a_completer])


def motifs_comptes(motifs):
    """T4-U4-007 — les motifs que ``points`` compte, dans l'ordre servi :
    les bloquants s'il y en a, sinon ceux à compléter (même règle que
    :func:`etat_de_publication`)."""
    motifs = [m for m in motifs or () if isinstance(m, dict)]
    bloquants = [m for m in motifs if m.get('statut') == STATUT_BLOQUANT]
    return bloquants or [m for m in motifs
                         if m.get('statut') in _statuts_a_completer()]


def verdict_a_quatre_mots(bloquants, manquantes, motifs):
    """``bloquant`` | ``indetermine`` | ``alerte`` | ``conforme``."""
    if bloquants:
        return 'bloquant'
    if manquantes:
        return 'indetermine'
    if any(motif['statut'] == STATUT_ALERTE for motif in motifs):
        return 'alerte'
    return 'conforme'
