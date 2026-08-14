"""Vues de l'app `mrp` (Groupe NTMFG — Production / MRP II)."""
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from core.viewsets import CompanyScopedModelViewSet

from .models import Gamme, OperationGamme, PosteDeCharge
from .serializers import GammeSerializer, OperationGammeSerializer, PosteDeChargeSerializer


class PosteDeChargeViewSet(CompanyScopedModelViewSet):
    """NTMFG1 — CRUD des postes de charge (company-scopé)."""
    queryset = PosteDeCharge.objects.all()
    serializer_class = PosteDeChargeSerializer
    filterset_fields = ['type_poste', 'actif']


class GammeViewSet(CompanyScopedModelViewSet):
    """NTMFG2 — CRUD des gammes opératoires (company-scopé)."""
    queryset = Gamme.objects.select_related('produit').prefetch_related(
        'operations__poste_charge').all()
    serializer_class = GammeSerializer
    filterset_fields = ['produit', 'actif']


class OperationGammeViewSet(viewsets.ModelViewSet):
    """NTMFG2 — opérations d'une gamme. Pas de `company` propre : scope via
    la gamme parente (même convention que
    `installations.KitComposantViewSet`). Filtrable par `?gamme=`."""
    queryset = OperationGamme.objects.select_related(
        'gamme', 'poste_charge').all()
    serializer_class = OperationGammeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            qs = qs.filter(gamme__company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
        gamme = self.request.query_params.get('gamme')
        if gamme:
            qs = qs.filter(gamme_id=gamme)
        return qs

    def _check_parent(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        gamme = serializer.validated_data.get('gamme')
        if gamme is not None and getattr(gamme, 'company_id', None) != cid:
            raise ValidationError({'gamme': 'Gamme inconnue pour cette société.'})
        poste = serializer.validated_data.get('poste_charge')
        if poste is not None and getattr(poste, 'company_id', None) != cid:
            raise ValidationError(
                {'poste_charge': 'Poste de charge inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_parent(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._check_parent(serializer)
        serializer.save()
