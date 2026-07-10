"""Vues FG319 — emplacements fins zone/allée/casier (bin locations).

``BinLocationViewSet`` : CRUD des casiers adressables sous un
``stock.EmplacementStock`` (string-FK), filtrable par `emplacement` /
`archived`. ``BinAffectationViewSet`` : affectation produit ↔ casier
(quantité indicative). Lecture tout rôle, écriture responsable/admin.
Multi-tenant via ``TenantMixin`` ; l'emplacement/produit référencés sont
validés tenant. Cross-app : ``stock`` en string-FK uniquement.
"""
from rest_framework.exceptions import ValidationError

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from ..models import (
    BinLocation, BinAffectation, CategorieStockage, RegleRangement,
)
from ..serializers import (
    BinLocationSerializer, BinAffectationSerializer,
    CategorieStockageSerializer, RegleRangementSerializer,
)

READ_ACTIONS = ['list', 'retrieve']


class BinLocationViewSet(CompanyScopedModelViewSet):
    """FG319 — casiers de rangement. Lecture tout rôle, écriture
    responsable/admin. Société + `created_by` posés serveur ; `emplacement`
    validé tenant. Filtrable par `emplacement`, `archived`."""
    queryset = BinLocation.objects.select_related(
        'emplacement', 'created_by').prefetch_related('affectations').all()
    serializer_class = BinLocationSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        emplacement = params.get('emplacement')
        if emplacement:
            qs = qs.filter(emplacement_id=emplacement)
        archived = params.get('archived')
        if archived in ('0', 'false', 'False'):
            qs = qs.filter(archived=False)
        elif archived in ('1', 'true', 'True'):
            qs = qs.filter(archived=True)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        emplacement = serializer.validated_data.get('emplacement')
        if emplacement is not None and getattr(
                emplacement, 'company_id', None) != cid:
            raise ValidationError(
                {'emplacement': 'Emplacement inconnu pour cette société.'})
        categorie = serializer.validated_data.get('categorie')
        if categorie is not None and getattr(
                categorie, 'company_id', None) != cid:
            raise ValidationError(
                {'categorie': 'Catégorie de stockage inconnue pour cette '
                 'société.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)


class CategorieStockageViewSet(CompanyScopedModelViewSet):
    """ZSTK9 — catégories de stockage (capacité/compatibilité). Lecture tout
    rôle, écriture responsable/admin. Société posée serveur."""
    queryset = CategorieStockage.objects.all()
    serializer_class = CategorieStockageSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class RegleRangementViewSet(CompanyScopedModelViewSet):
    """ZSTK9 — règles de rangement configurables (produit/catégorie →
    casier cible, priorité). Lecture tout rôle, écriture responsable/admin.
    Société posée serveur ; `produit`/`bin_cible` validés tenant."""
    queryset = RegleRangement.objects.select_related(
        'produit', 'bin_cible').all()
    serializer_class = RegleRangementSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        produit = params.get('produit')
        if produit:
            qs = qs.filter(produit_id=produit)
        actif = params.get('actif')
        if actif in ('0', 'false', 'False'):
            qs = qs.filter(actif=False)
        elif actif in ('1', 'true', 'True'):
            qs = qs.filter(actif=True)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        produit = serializer.validated_data.get('produit')
        if produit is not None and getattr(
                produit, 'company_id', None) != cid:
            raise ValidationError(
                {'produit': 'Produit inconnu pour cette société.'})
        bin_cible = serializer.validated_data.get('bin_cible')
        if bin_cible is not None and getattr(
                bin_cible, 'company_id', None) != cid:
            raise ValidationError(
                {'bin_cible': 'Casier inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)


class BinAffectationViewSet(CompanyScopedModelViewSet):
    """FG319 — affectation produit ↔ casier. Société posée serveur ; `bin` et
    `produit` validés tenant. Filtrable par `bin`, `produit`."""
    queryset = BinAffectation.objects.select_related(
        'bin', 'produit').all()
    serializer_class = BinAffectationSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        bin_id = params.get('bin')
        if bin_id:
            qs = qs.filter(bin_id=bin_id)
        produit = params.get('produit')
        if produit:
            qs = qs.filter(produit_id=produit)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        bin_loc = serializer.validated_data.get('bin')
        if bin_loc is not None and getattr(
                bin_loc, 'company_id', None) != cid:
            raise ValidationError(
                {'bin': 'Casier inconnu pour cette société.'})
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
