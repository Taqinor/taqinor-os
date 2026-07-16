"""Vues FG316 — frais d'import & lignes de coût débarqué (landed cost).

``FraisImportViewSet`` : CRUD des frais d'un dossier d'import.
``LandedCostLigneViewSet`` : CRUD des lignes de coût débarqué par SKU. Le coût
débarqué calculé (répartition pro-rata FOB) se lit via l'action ``landed-cost``
du dossier (``DossierImportViewSet``). Lecture tout rôle, écriture
responsable/admin. Multi-tenant via ``TenantMixin`` : société + ``created_by``
posés côté serveur ; le dossier et le produit sont validés tenant. Cross-app :
``stock.Produit`` en string-FK. Montants INTERNES.
"""
from rest_framework.exceptions import ValidationError

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from ..models import FraisImport, LandedCostLigne
from ..serializers import FraisImportSerializer, LandedCostLigneSerializer

READ_ACTIONS = ['list', 'retrieve']


def _check_dossier(serializer, company):
    cid = getattr(company, 'id', None)
    dossier = serializer.validated_data.get('dossier')
    if dossier is not None and getattr(dossier, 'company_id', None) != cid:
        raise ValidationError(
            {'dossier': "Dossier d'import inconnu pour cette société."})


class FraisImportViewSet(CompanyScopedModelViewSet):
    """FG316 — frais d'import. Lecture tout rôle, écriture responsable/admin.
    Société + `created_by` posés serveur ; dossier validé tenant. Filtrable par
    `dossier`, `categorie`."""
    queryset = FraisImport.objects.select_related(
        'dossier', 'created_by').all()
    serializer_class = FraisImportSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        dossier = params.get('dossier')
        if dossier:
            qs = qs.filter(dossier_id=dossier)
        categorie = params.get('categorie')
        if categorie:
            qs = qs.filter(categorie=categorie)
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company
        _check_dossier(serializer, company)
        serializer.save(company=company, created_by=self.request.user)

    def perform_update(self, serializer):
        company = self.request.user.company
        _check_dossier(serializer, company)
        serializer.save(company=company)


class LandedCostLigneViewSet(CompanyScopedModelViewSet):
    """FG316 — lignes de coût débarqué par SKU. Lecture tout rôle, écriture
    responsable/admin. Société posée serveur ; dossier/produit validés tenant.
    Filtrable par `dossier`."""
    queryset = LandedCostLigne.objects.select_related(
        'dossier', 'produit').all()
    serializer_class = LandedCostLigneSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        dossier = self.request.query_params.get('dossier')
        if dossier:
            qs = qs.filter(dossier_id=dossier)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        _check_dossier(serializer, company)
        produit = serializer.validated_data.get('produit')
        if produit is not None and getattr(
                produit, 'company_id', None) != cid:
            raise ValidationError(
                {'produit': 'Produit inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)
