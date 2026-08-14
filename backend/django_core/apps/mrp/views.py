"""Vues de l'app `mrp` (Groupe NTMFG — Production / MRP II)."""
from core.viewsets import CompanyScopedModelViewSet

from .models import PosteDeCharge
from .serializers import PosteDeChargeSerializer


class PosteDeChargeViewSet(CompanyScopedModelViewSet):
    """NTMFG1 — CRUD des postes de charge (company-scopé)."""
    queryset = PosteDeCharge.objects.all()
    serializer_class = PosteDeChargeSerializer
    filterset_fields = ['type_poste', 'actif']
