"""NTRET8 — Vues des Paramètres POS (Paramètres → Point de vente).

Un singleton par société (``ParametresPos``, taux horaire main-d'œuvre
comptoir) exposé en GET/PATCH — même patron que ``views_profile.get_profile``/
``update_profile`` — et un référentiel CRUD des boutiques actives
(``BoutiquePos``). Le seuil de remise ligne comptoir (T17) et la config
imprimante/TPE (XPOS18) ne sont PAS dupliqués ici : le frontend les lit sur
leurs propres endpoints existants (``parametres/update/`` et
``pos/config-materiel/``).
"""
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAdminOrResponsableTier, IsAnyRole
from core.viewsets import CompanyScopedModelViewSet

from .models_pos import BoutiquePos, ParametresPos
from .serializers_pos import BoutiquePosSerializer, ParametresPosSerializer


@extend_schema(responses=ParametresPosSerializer)
@api_view(['GET'])
@permission_classes([IsAnyRole])
def get_parametres_pos(request):
    parametres = ParametresPos.get(request.user.company)
    return Response(ParametresPosSerializer(parametres).data)


@extend_schema(request=ParametresPosSerializer, responses=ParametresPosSerializer)
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAdminOrResponsableTier])
def update_parametres_pos(request):
    parametres = ParametresPos.get(request.user.company)
    serializer = ParametresPosSerializer(
        parametres, data=request.data, partial=request.method == 'PATCH')
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


class BoutiquePosViewSet(CompanyScopedModelViewSet):
    """Référentiel des boutiques actives (NTRET8). Lecture tout rôle,
    écriture admin/responsable — même garde que les autres référentiels
    société (WIR66)."""
    queryset = BoutiquePos.objects.select_related('emplacement').all()
    serializer_class = BoutiquePosSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsAdminOrResponsableTier()]

    def perform_create(self, serializer):
        company = self.request.user.company
        from apps.stock.selectors import get_emplacement_scoped
        emplacement = serializer.validated_data.get('emplacement')
        if emplacement is None or get_emplacement_scoped(
                company, emplacement.id) is None:
            raise ValidationError({'emplacement': 'Emplacement inconnu.'})
        serializer.save(company=company)
