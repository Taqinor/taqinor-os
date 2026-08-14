"""NTSCM38 — API publique LECTURE SEULE de la planification supply chain
(apps.scm), sous /api/public/v1/scm/. Authentifiée par clé d'API (scope
``read:scm``), scopée à la société de la clé — jamais un paramètre client.

Trois surfaces, réservées à une intégration externe (TMS, connecteur
planification tiers) :

  * ``previsions-demande/`` — ``PrevisionDemande`` (NTSCM1/2/3), liste paginée.
  * ``politiques-stock/`` — ``PolitiqueStock`` (NTSCM6), liste paginée.
    JAMAIS ``Produit.prix_achat``.
  * ``tableau-bord-reappro/`` — agrégat NTSCM7 (``apps.scm.selectors.
    tableau_bord_reappro``), objet unique wrappé ``{'lignes': [...]}`` (même
    contrat ``endpoints_lecture_simple`` que ``public_licence_views.py``,
    NTADM42) — le champ interne ``prix_achat_unitaire`` de l'agrégat est
    TOUJOURS retiré avant sérialisation publique (jamais de coût d'achat
    client-facing, règle transverse)."""
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.scm.models import PolitiqueStock, PrevisionDemande

from .auth import ApiKeyAuthentication, ApiKeyRateThrottle, HasApiScope
from .constants import SCOPE_READ_SCM
from .public_response import PublicApiResponseMixin
from .public_serializers import (
    PublicPolitiqueStockSerializer, PublicPrevisionDemandeSerializer,
)
from .public_views import PublicReadOnlyViewSet


class PublicPrevisionDemandeViewSet(PublicReadOnlyViewSet):
    required_scope = SCOPE_READ_SCM
    serializer_class = PublicPrevisionDemandeSerializer
    queryset = PrevisionDemande.objects.select_related('produit').order_by('-periode')
    filter_whitelist = ('produit', 'segment', 'periode', 'methode')
    ordering_fields = ('periode', 'id')
    sync_field = 'genere_le'


class PublicPolitiqueStockViewSet(PublicReadOnlyViewSet):
    required_scope = SCOPE_READ_SCM
    serializer_class = PublicPolitiqueStockSerializer
    queryset = PolitiqueStock.objects.select_related('produit').order_by('produit_id')
    filter_whitelist = ('produit', 'classe_abc')
    ordering_fields = ('id', 'revise_le')
    sync_field = 'revise_le'


class PublicScmTableauBordReapproView(PublicApiResponseMixin, APIView):
    """``GET /api/public/v1/scm/tableau-bord-reappro/`` — tableau de bord
    réappro consolidé (NTSCM7) de la société porteuse de la clé. Jamais
    ``prix_achat_unitaire`` (retiré de chaque ligne)."""

    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [HasApiScope]
    throttle_classes = [ApiKeyRateThrottle]
    required_scope = SCOPE_READ_SCM

    def get(self, request):
        from apps.scm import selectors

        lignes = selectors.tableau_bord_reappro(request.auth.company)
        lignes_publiques = [
            {k: v for k, v in ligne.items() if k != 'prix_achat_unitaire'}
            for ligne in lignes
        ]
        return Response({'lignes': lignes_publiques})
