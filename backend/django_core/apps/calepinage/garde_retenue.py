"""CAL9 — le verrou d'écriture du champ ``retenue``, en stdlib PURE.

POURQUOI UN MODULE À PART
-------------------------
``CalepinageVariante.save`` doit interroger ce verrou, et le service de
variantes doit l'ouvrir. Si le modèle importait le service, la chaîne
``models -> services.variantes -> apps.ventes.services -> … -> les modèles
d'une autre app``
ferait ROUGIR le contrat import-linter ``calepinage-models-decoupled`` (CAL5)
— mesuré, pas supposé. Le verrou vit donc dans ce module minuscule qui
n'importe QUE la bibliothèque standard : le modèle en dépend sans rien
entraîner derrière lui.

``services/variantes.py`` le ré-exporte : le chemin d'écriture unique reste le
service, et c'est lui que le reste du dépôt appelle.
"""
from __future__ import annotations

import contextlib
import threading

#: État par THREAD : la bascule est-elle en cours dans ce fil d'exécution ?
#: Par thread, et jamais global — deux requêtes concurrentes ne doivent pas
#: s'ouvrir mutuellement le droit d'écrire ``retenue``.
_local = threading.local()


def bascule_en_cours():
    """``True`` seulement à l'intérieur de ``bascule_autorisee()``."""
    return getattr(_local, 'autorisee', False)


@contextlib.contextmanager
def bascule_autorisee():
    """Le SEUL contexte où ``retenue`` peut être écrit.

    Réentrant : une bascule imbriquée (duplication qui recopie une variante
    retenue) ne referme pas la porte en sortant de son bloc interne.
    """
    precedent = getattr(_local, 'autorisee', False)
    _local.autorisee = True
    try:
        yield
    finally:
        _local.autorisee = precedent


def refuser_ecriture_directe():
    """Le message de refus, en français, qui NOMME le champ fautif."""
    return (
        "Le champ « Retenue » ne s'écrit pas directement : la bascule passe "
        "par le service de variantes du module Calepinage, qui garantit "
        "qu'il n'y a jamais deux variantes retenues ni aucune."
    )
