"""Vues du module Appels d'offres (``apps.ao``).

ODX11 — ré-export TRANSITOIRE des ViewSets AO qui vivent encore dans
``apps.compta.views`` (adossés à ``_ComptaBaseViewSet`` = ``TenantMixin`` +
``ModelViewSet``, avec le scoping ``request.user.company`` et l'assignation
forcée de ``company`` en ``perform_create``). Ce module donne aux nouvelles
routes ``/api/django/ao/…`` un point d'entrée ``apps.ao.views`` stable ; les
anciennes routes ``/api/django/compta/…`` continuent de servir les MÊMES
classes. ODX22 re-logera le corps ici.
"""

from apps.compta.views import (  # noqa: F401
    AppelOffreViewSet,
    BordereauPrixViewSet,
    CautionSoumissionViewSet,
    DossierSoumissionViewSet,
    EcheanceAOViewSet,
    LigneBordereauViewSet,
    PieceSoumissionViewSet,
    ResultatAOViewSet,
)
