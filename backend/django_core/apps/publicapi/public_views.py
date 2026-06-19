"""Vues LECTURE SEULE de l'API publique (N89), sous /api/public/.

Chaque vue est authentifiée par clé d'API (ApiKeyAuthentication), scopée à la
société de la clé (jamais cross-tenant), paginée et protégée par un scope
précis (`required_scope`). Aucune écriture, aucun prix d'achat.
"""
from rest_framework import viewsets

from apps.crm.models import Lead
from apps.ventes.models import Devis, Facture
from apps.installations.models import Installation

from .auth import ApiKeyAuthentication, HasApiScope, ApiKeyRateThrottle
from .constants import (
    SCOPE_READ_LEADS, SCOPE_READ_DEVIS,
    SCOPE_READ_FACTURES, SCOPE_READ_CHANTIERS,
)
from .public_serializers import (
    PublicLeadSerializer, PublicDevisSerializer,
    PublicFactureSerializer, PublicChantierSerializer,
)


class PublicReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    """Base commune : auth par clé, scope, throttle par clé, scope société.

    La société vient TOUJOURS de la clé (request.auth.company_id), jamais d'un
    paramètre client — pas de fuite cross-tenant possible.
    """
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [HasApiScope]
    throttle_classes = [ApiKeyRateThrottle]
    required_scope = None  # défini par chaque sous-classe

    def get_company_id(self):
        return self.request.auth.company_id

    def get_queryset(self):
        return super().get_queryset().filter(company_id=self.get_company_id())


class PublicLeadViewSet(PublicReadOnlyViewSet):
    required_scope = SCOPE_READ_LEADS
    serializer_class = PublicLeadSerializer
    queryset = Lead.objects.all().order_by('-date_creation')


class PublicDevisViewSet(PublicReadOnlyViewSet):
    required_scope = SCOPE_READ_DEVIS
    serializer_class = PublicDevisSerializer
    queryset = Devis.objects.prefetch_related('lignes').order_by('-date_creation')


class PublicFactureViewSet(PublicReadOnlyViewSet):
    required_scope = SCOPE_READ_FACTURES
    serializer_class = PublicFactureSerializer
    queryset = Facture.objects.prefetch_related('lignes').order_by('-date_emission')


class PublicChantierViewSet(PublicReadOnlyViewSet):
    required_scope = SCOPE_READ_CHANTIERS
    serializer_class = PublicChantierSerializer
    queryset = Installation.objects.all().order_by('-id')
