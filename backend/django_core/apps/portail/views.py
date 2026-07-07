"""Vues du module Portail client (``apps.portail``).

ODX12 — ré-export TRANSITOIRE des ViewSets portail qui vivent encore dans
``apps.compta.views`` (adossés à ``_ComptaBaseViewSet`` = ``TenantMixin`` +
``ModelViewSet``, avec le scoping ``request.user.company`` et l'assignation
forcée de ``company`` en ``perform_create``). Ce module donne aux nouvelles
routes ``/api/django/portail/…`` un point d'entrée ``apps.portail.views``
stable ; les anciennes routes ``/api/django/compta/…`` continuent de servir les
MÊMES classes. Les mécanismes d'authentification portail (tokens/comptes
clients) sont conservés À L'IDENTIQUE — aucun élargissement d'accès. ODX22
re-logera le corps ici.
"""

from apps.compta.views import (  # noqa: F401
    AcceptationDevisPortailViewSet,
    ComptePortailClientViewSet,
    DemandeTicketPortailViewSet,
    DocumentClientPortailViewSet,
    JalonChantierPortailViewSet,
    PaiementFacturePortailViewSet,
)
