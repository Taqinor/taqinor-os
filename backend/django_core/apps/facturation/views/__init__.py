"""Vues du module Facturation (``apps.facturation``) — surface d'import publique.

ODX18 — les ViewSets de facturation (``FactureViewSet`` et ses mixins
``Facture…Mixin``, ``LigneFactureViewSet``, ``PaiementViewSet``) VIVENT ici, déplacés tels quels depuis
``apps/ventes/views/`` ; le recouvrement vit dans ``apps.facturation.recouvrement``.
Adossés à ``TenantMixin``/``CompanyScopedModelViewSet`` : scoping
``request.user.company`` + assignation forcée de ``company`` en
``perform_create``. ``AvoirViewSet``/``NoteDebitViewSet`` vivent encore dans
``apps/ventes/views/avoir.py`` (garde ASTK de sortie de stock qui scanne
``apps/ventes``) et sont ré-exposés ici tels quels. Les MÊMES classes sont servies sous ``/api/django/facturation/…``
et sous les routes historiques ``/api/django/ventes/…`` (aucun client cassé).

Les exports UBL 2.1 / DGI sont des ``@action`` sur ``FactureViewSet`` : servir la
même classe sous les deux préfixes les expose automatiquement.

Ordre d'import : ces modules ne lisent du paquet ``apps.ventes.views`` que des
SOUS-MODULES (``openapi_docs``, ``remise_encaissement``, ``avoir``), jamais un nom de son
``__init__`` — ``apps.ventes.views`` résout ses noms de facturation
paresseusement (PEP 562), donc aucun cycle d'import quel que soit le premier
paquet chargé.
"""

from .facture import FactureViewSet
from apps.ventes.views.avoir import AvoirViewSet, NoteDebitViewSet
from .paiement import PaiementViewSet
from .ligne_facture import LigneFactureViewSet
from ..recouvrement import FollowupLevelViewSet

__all__ = [
    'AvoirViewSet', 'FactureViewSet', 'FollowupLevelViewSet', 'LigneFactureViewSet',
    'NoteDebitViewSet', 'PaiementViewSet',
]
