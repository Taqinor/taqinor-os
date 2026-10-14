"""VNT67 — « Modifier le montant » d'un BROUILLON de tranche, action de
``FactureViewSet`` (mixin : ``views/facture.py`` est un fichier-mur C20 qui ne
grossit plus). Aucune route dans ``urls.py`` : le routeur la découvre sur le
viewset. Le corps vit dans ``domain/facturation_vente.modifier_montant_tranche``.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import (
    IsAdminOrResponsableTier, IsResponsableOrAdmin,
)
from . import openapi_docs as D
from ..serializers_facturation import FactureSerializer


class FactureMontantTrancheMixin:
    """``POST factures/<id>/montant-tranche/`` (palier de l'arbitrage 5, le
    même que ``annuler`` : jamais un Commercial)."""

    # api-only: l'écran arrive avec le panneau de vente (VNT75/VNT79).
    @extend_schema(
        request=inline_serializer('FactureMontantTranche', {
            'montant_ttc': serializers.CharField()}),
        responses={200: FactureSerializer, 400: D.ErreurDevisFige,
                   409: D.ErreurDevisFige})
    @action(detail=True, methods=['post'], url_path='montant-tranche',
            permission_classes=[IsAdminOrResponsableTier,
                                IsResponsableOrAdmin])
    def montant_tranche(self, request, pk=None):
        """VNT67 — le TTC d'un brouillon de tranche : HT / TVA / ventilation
        au prorata du plan, échéancier réécrit ; 409 sur une émise."""
        from ..domain.facturation_vente import (
            FacturationVenteRefusee, modifier_montant_tranche)
        corps = request.data if isinstance(request.data, dict) else {}
        try:
            facture = modifier_montant_tranche(
                self.get_object(), corps.get('montant_ttc'),
                user=request.user)
        except FacturationVenteRefusee as exc:
            return Response(exc.corps, status=exc.status)
        return Response(FactureSerializer(facture).data)
