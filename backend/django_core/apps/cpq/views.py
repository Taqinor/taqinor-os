"""Vues (API) de l'app CPQ.

Tous les ViewSets héritent de ``CompanyScopedModelViewSet`` (ARC2) : le
queryset est scopé société et ``perform_create`` force ``company`` côté
serveur. La liste des produits n'est jamais lue du corps pour le scope."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from core.viewsets import CompanyScopedModelViewSet
from authentication.permissions import IsResponsableOrAdmin, IsAnyRole

from .models import OptionProduit, ContrainteCompatibilite
from .serializers import (
    OptionProduitSerializer, ContrainteCompatibiliteSerializer,
)
from . import selectors


class OptionProduitViewSet(CompanyScopedModelViewSet):
    queryset = OptionProduit.objects.all()
    serializer_class = OptionProduitSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class ContrainteCompatibiliteViewSet(CompanyScopedModelViewSet):
    queryset = ContrainteCompatibilite.objects.all()
    serializer_class = ContrainteCompatibiliteSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class ValiderCompatibiliteView(APIView):
    """NTCPQ1 — POST cpq/valider-compatibilite/.

    Corps : ``{"produit_ids": [1, 2, 3]}``. Renvoie les violations, séparées en
    ``bloquantes`` (INCOMPATIBLE / REQUIERT) et ``avertissements`` (RECOMMANDE)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        company = request.user.company
        produit_ids = request.data.get('produit_ids') or []
        if not isinstance(produit_ids, (list, tuple)):
            return Response(
                {'detail': 'produit_ids doit être une liste.'},
                status=status.HTTP_400_BAD_REQUEST)
        violations = selectors.violations_compatibilite(
            company=company, produit_ids=produit_ids)
        bloquantes = [v for v in violations if v['bloquante']]
        avertissements = [v for v in violations if not v['bloquante']]
        return Response({
            'valide': not bloquantes,
            'violations': violations,
            'bloquantes': bloquantes,
            'avertissements': avertissements,
        })
