from django.db import transaction  # noqa: F401
from django.db.models import ProtectedError, Count, Min, Max  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from rest_framework.parsers import MultiPartParser, JSONParser  # noqa: F401
from core.viewsets import CompanyScopedModelViewSet
from apps.ventes.utils.references import create_with_reference  # noqa: F401
from ..models import (  # noqa: F401
    Produit, Categorie, Fournisseur, MouvementStock, Marque,
    BonCommandeFournisseur, EmplacementStock, TransfertStock, PrixFournisseur,
    RetourFournisseur, ReceptionFournisseur, FactureFournisseur,
    PaiementFournisseur,
)
from ..serializers import (  # noqa: F401
    ProduitSerializer,
    CategorieSerializer,
    FournisseurSerializer,
    MouvementStockSerializer,
    MarqueSerializer,
    BonCommandeFournisseurSerializer,
    EmplacementStockSerializer,
    TransfertStockSerializer,
    PrixFournisseurSerializer,
    RetourFournisseurSerializer,
    ReceptionFournisseurSerializer,
    FactureFournisseurSerializer,
    PaiementFournisseurSerializer,
)
from authentication.permissions import (  # noqa: F401
    IsAnyRole,
    IsAdminRole,
    IsResponsableOrAdmin,
    HasPermissionOrLegacy,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


class PrixFournisseurViewSet(CompanyScopedModelViewSet):
    """N17 — prix d'achat multi-fournisseurs par SKU (INTERNE). Lecture tout
    rôle, écriture stock_modifier. `company` posé serveur ; produit/fournisseur
    doivent appartenir à la société."""
    queryset = PrixFournisseur.objects.select_related(
        'produit', 'fournisseur').all()
    serializer_class = PrixFournisseurSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['prix_achat', 'date_dernier_achat']
    ordering = ['prix_achat']

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['export_xlsx']:
            return [IsAnyRole()]
        return [HasPermissionOrLegacy('stock_modifier')()]

    def get_queryset(self):
        qs = super().get_queryset()
        produit_id = self.request.query_params.get('produit')
        if produit_id:
            qs = qs.filter(produit_id=produit_id)
        return qs

    def _check_company(self, serializer):
        company = self.request.user.company
        produit = serializer.validated_data.get('produit')
        fournisseur = serializer.validated_data.get('fournisseur')
        from rest_framework.exceptions import ValidationError
        if produit is not None and produit.company_id != getattr(
                company, 'id', None):
            raise ValidationError({'produit': 'Produit hors de votre entreprise.'})
        if fournisseur is not None and fournisseur.company_id != getattr(
                company, 'id', None):
            raise ValidationError(
                {'fournisseur': 'Fournisseur hors de votre entreprise.'})

    def perform_create(self, serializer):
        self._check_company(serializer)
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        self._check_company(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=False, methods=['get'], url_path='export-xlsx')
    def export_xlsx(self, request):
        """XPUR14 — export xlsx du tarif d'un fournisseur (query param
        ``fournisseur`` requis)."""
        from ..services import export_prix_fournisseur_xlsx
        fournisseur_id = request.query_params.get('fournisseur')
        if not fournisseur_id:
            return Response(
                {'detail': 'Le paramètre fournisseur est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        fournisseur = Fournisseur.objects.filter(
            pk=fournisseur_id, company=request.user.company).first()
        if fournisseur is None:
            return Response(
                {'detail': 'Fournisseur introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        return export_prix_fournisseur_xlsx(request.user.company, fournisseur)

    @action(detail=False, methods=['post'], url_path='import-xlsx',
            parser_classes=[MultiPartParser])
    def import_xlsx(self, request):
        """XPUR14 — import/mise à jour du tarif d'un fournisseur depuis un
        xlsx (même format que l'export). Corps multipart : ``fournisseur``
        (id), ``file``. CRÉATION + MISE À JOUR par SKU — jamais de
        suppression silencieuse."""
        from ..services import import_prix_fournisseur_xlsx
        fournisseur_id = request.data.get('fournisseur')
        upload = request.FILES.get('file')
        if not fournisseur_id or upload is None:
            return Response(
                {'detail': 'fournisseur et file sont requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        fournisseur = Fournisseur.objects.filter(
            pk=fournisseur_id, company=request.user.company).first()
        if fournisseur is None:
            return Response(
                {'detail': 'Fournisseur introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        result = import_prix_fournisseur_xlsx(
            request.user.company, fournisseur, upload.read())
        return Response(result, status=status.HTTP_200_OK)
