"""Serializers du module Portail client (``apps.portail``).

ODX12 — ré-export TRANSITOIRE des serializers portail qui vivent encore dans
``apps.compta.serializers`` (interleavés avec les serializers comptables). Ce
module expose ``apps.portail.serializers`` pour les ViewSets portail et les
nouvelles routes ``/api/django/portail/…`` ; ODX22 re-logera leur corps ici.
"""

from apps.compta.serializers import (  # noqa: F401
    AcceptationDevisPortailSerializer,
    ComptePortailClientSerializer,
    DemandeTicketPortailSerializer,
    DocumentClientPortailSerializer,
    JalonChantierPortailSerializer,
    PaiementFacturePortailSerializer,
)
