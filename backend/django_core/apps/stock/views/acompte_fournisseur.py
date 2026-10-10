from django.db import transaction  # noqa: F401
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.parsers import JSONParser
from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from ..openapi_helpers import INT, LISTE, P
from core.viewsets import CompanyScopedModelViewSet
from ..models import AcompteFournisseur
from ..serializers import AcompteFournisseurSerializer
from authentication.permissions import (  # noqa: F401
    IsAnyRole,
    IsAdminRole,
    IsResponsableOrAdmin,
    HasPermissionOrLegacy,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


@extend_schema_view(list=extend_schema(parameters=[P('bon_commande', INT)]))
class AcompteFournisseurViewSet(CompanyScopedModelViewSet):
    """XPUR8 — acomptes/avances fournisseur sur BCF. Imputés automatiquement
    (idempotent) sur la première facture du BCF via
    `services.facturer_reception` → `imputer_acomptes_bcf`, ET dès leur
    saisie quand le BCF porte déjà une facture ouverte
    (ERR-ASTK106-ACOMPTE-APRES-FACTURE-NON-IMPUTE : sans cela, un acompte
    versé après la facture n'était jamais imputé → fournisseur payé deux
    fois). Lecture tout rôle ; écriture responsable/admin. `company` posée
    côté serveur."""
    queryset = AcompteFournisseur.objects.select_related(
        'bon_commande', 'facture_imputee', 'created_by').all()
    serializer_class = AcompteFournisseurSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_versement', 'date_creation', 'montant']
    ordering = ['-date_versement', '-date_creation']

    parser_classes = [JSONParser]

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['ouverts']:
            return [IsAnyRole()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        # ASTK19 (D-ASTK-3) — verser/imputer un acompte = « payer ».
        return [HasPermissionOrLegacy('achats_payer')()]

    def get_queryset(self):
        qs = super().get_queryset()
        bcf_id = self.request.query_params.get('bon_commande')
        if bcf_id:
            qs = qs.filter(bon_commande_id=bcf_id)
        return qs

    def perform_create(self, serializer):
        from ..services import imputer_acomptes_bcf
        with transaction.atomic():
            acompte = serializer.save(
                company=self.request.user.company,
                created_by=self.request.user)
            # ERR-ASTK106 — facture(s) déjà ouverte(s) sur le BCF : l'acompte
            # s'impute tout de suite (plus ancienne d'abord, plafonné au
            # solde ; l'excédent reste un acompte ouvert). No-op sans facture.
            if acompte.bon_commande_id:
                imputer_acomptes_bcf(acompte.bon_commande)

    def perform_update(self, serializer):
        from ..services import imputer_acomptes_bcf
        with transaction.atomic():
            acompte = serializer.save()
            # ERR-ASTK106 — un acompte encore libre dont le montant/BCF change
            # s'impute aussi sur les factures ouvertes du BCF.
            if acompte.bon_commande_id:
                imputer_acomptes_bcf(acompte.bon_commande)

    @extend_schema(responses=LISTE)
    @action(detail=False, methods=['get'], url_path='ouverts')
    def ouverts(self, request):
        """XPUR8 (AUDV04/DRAFT165-113) — acomptes fournisseur PARTIELLEMENT/
        NON consommés de la société, pour l'écran Achats/trésorerie. Sélecteur
        dédié (jamais dupliqué) : `selectors.acomptes_fournisseur_ouverts`."""
        from ..selectors import acomptes_fournisseur_ouverts
        rows = acomptes_fournisseur_ouverts(request.user.company)
        return Response(rows)
