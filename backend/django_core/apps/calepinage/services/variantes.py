"""CAL9 — « une seule variante retenue », par un chemin d'écriture UNIQUE.

DEUX VERROUS, PAS UN
--------------------
1. **La base.** ``CalepinageVariante`` porte
   ``UniqueConstraint(fields=['calepinage'], condition=Q(retenue=True))``
   (CAL7/CAL9) : deux variantes retenues sur un même calepinage lèvent
   ``IntegrityError``. C'est la garantie qui survit à tout — script, admin,
   requête concurrente.
2. **Le chemin d'écriture.** La contrainte seule laisserait un appelant
   naïf « corriger » le problème en passant les DEUX à faux (zéro retenue,
   c'est-à-dire un calepinage sans option choisie — l'autre moitié du bug).
   Le champ ``retenue`` n'est donc écrivable QUE depuis ce module : partout
   ailleurs (vue, sérialiseur, script), une écriture est REFUSÉE en français.

Le service de bascule lui-même (``retenir_variante``), la création et la
duplication arrivent avec CAL14 — dans CE fichier, jamais dans un autre : un
second foyer d'écriture rouvrirait exactement ce que ce garde ferme.
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
    """Le message de refus, en français, qui NOMME le champ fautif.

    Appelé par ``CalepinageVariante.save`` quand une écriture de ``retenue``
    arrive hors du chemin sanctionné.
    """
    return (
        "Le champ « Retenue » ne s'écrit pas directement : la bascule passe "
        "par le service de variantes du module Calepinage, qui garantit "
        "qu'il n'y a jamais deux variantes retenues ni aucune."
    )
