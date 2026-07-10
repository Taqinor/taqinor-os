from rest_framework import viewsets

from core.viewsets import CompanyScopedModelViewSet
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from ..models import NomenclatureCodeBarres, RegleCodeBarres
from ..serializers import (
    NomenclatureCodeBarresSerializer, RegleCodeBarresSerializer,
)

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.

READ_ACTIONS = ['list', 'retrieve']


class NomenclatureCodeBarresViewSet(CompanyScopedModelViewSet):
    """ZSTK12 — nomenclatures de code-barres (Default/GS1) configurables par
    société. Lecture pour tout rôle, écriture Responsable/Admin (config
    sensible : une règle mal formée peut mal router un scan)."""
    queryset = NomenclatureCodeBarres.objects.prefetch_related('regles').all()
    serializer_class = NomenclatureCodeBarresSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class RegleCodeBarresViewSet(viewsets.ModelViewSet):
    """ZSTK12 — règles d'une nomenclature de code-barres. Scopées société via
    `nomenclature__company` (pas de FK `company` directe sur la règle — pas
    de `TenantMixin` ici, qui suppose une FK `company` directe)."""
    queryset = RegleCodeBarres.objects.select_related('nomenclature').all()
    serializer_class = RegleCodeBarresSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            return qs.filter(nomenclature__company=user.company)
        elif user.is_superuser:
            return qs
        return qs.none()

    def perform_create(self, serializer):
        nomenclature = serializer.validated_data.get('nomenclature')
        if nomenclature is not None and self.request.user.company_id and \
                nomenclature.company_id != self.request.user.company_id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Nomenclature hors de votre entreprise.')
        serializer.save()
