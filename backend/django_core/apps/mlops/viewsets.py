"""ViewSets du module « mlops » (Groupe NTAI, P3).

Réservé Responsable/Admin : le réglage des paramètres de scorers est une
décision technique d'entreprise, pas un écran métier courant.
"""
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from .models import ModeleML
from .serializers import ModeleMLSerializer


class ModeleMLViewSet(CompanyScopedModelViewSet):
    """CRUD des versions de paramètres de scorer, company-scopé."""

    queryset = ModeleML.objects.all()
    serializer_class = ModeleMLSerializer
    permission_classes = [IsResponsableOrAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        nom = self.request.query_params.get('nom')
        if nom:
            qs = qs.filter(nom=nom)
        return qs

    @action(detail=True, methods=['post'], url_path='activer')
    def activer(self, request, pk=None):
        """NTAI27 — ``POST modeles/<id>/activer/`` : active cette version,
        désactive toutes les autres du même scorer (au plus une active)."""
        from .services import activer_version

        instance = activer_version(request.user.company, pk)
        if instance is None:
            return Response({'detail': 'Introuvable.'}, status=404)
        return Response(ModeleMLSerializer(instance).data)
