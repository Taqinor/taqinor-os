"""Sérialiseurs du module Notes de frais (``apps.frais``) — ODX15.

Ré-export TRANSITOIRE des sérialiseurs qui vivent encore dans
``apps.compta.serializers`` (interleavés avec les sérialiseurs comptables).
Il donne aux routes ``/api/django/frais/…`` un point d'entrée stable ; les
anciennes routes ``/api/django/compta/…`` servent les MÊMES classes.
Le corps sera relogé ici en même temps que celui des vues.
"""

from apps.compta.serializers import (  # noqa: F401
    BaremeIndemniteSerializer,
    IndemniteChantierSerializer,
    NoteFraisSerializer,
    PlafondNoteFraisSerializer,
    RapportNoteFraisSerializer,
)

__all__ = [
    'BaremeIndemniteSerializer',
    'IndemniteChantierSerializer',
    'NoteFraisSerializer',
    'PlafondNoteFraisSerializer',
    'RapportNoteFraisSerializer',
]
