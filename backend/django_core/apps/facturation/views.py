"""Vues du module Facturation (``apps.facturation``).

ODX18 — ré-export TRANSITOIRE des ViewSets de facturation + recouvrement qui
vivent encore dans ``apps.ventes.views`` / ``apps.ventes.recouvrement`` (adossés
à ``TenantMixin`` + ``ModelViewSet`` : scoping ``request.user.company`` +
assignation forcée de ``company`` en ``perform_create``). Ce module donne aux
nouvelles routes ``/api/django/facturation/…`` un point d'entrée
``apps.facturation.views`` stable ; les anciennes routes ``/api/django/ventes/…``
continuent de servir les MÊMES classes. ODX22 re-logera le corps ici.

Les exports UBL 2.1 / DGI sont des ``@action`` sur ``FactureViewSet`` : servir la
même classe sous le nouveau préfixe les expose automatiquement.
"""

from apps.ventes.views import (  # noqa: F401
    AvoirViewSet,
    FactureViewSet,
    LigneFactureViewSet,
    NoteDebitViewSet,
    PaiementViewSet,
)
from apps.ventes.recouvrement import (  # noqa: F401
    FollowupLevelViewSet,
    ParametrageRelanceClientViewSet,
    PromessePaiementViewSet,
)
