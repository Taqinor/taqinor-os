"""Gestes de CYCLE d'une facture, hors ``views/facture.py`` (C20 : le
fichier ne grossit pas). VNT67 y pose ``montant-tranche`` ; VNT97 y déplace
émettre, remettre en brouillon, marquer payée et annuler
(``FactureCycleActionsMixin``, en tête des bases de ``FactureViewSet``)."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import (
    IsAdminOrResponsableTier, IsResponsableOrAdmin,
)

from . import openapi_docs as D
from ..serializers_facturation import FactureSerializer


def refuser_devis_du_corps(donnees, facture=None):
    """VNT89 — la porte MANUELLE (création / modification d'une facture) est
    fermée aux devis : 400 ``facture_de_devis`` (« passez par Facturer la
    vente ») ; règle : ``facturation_vente.devis_impose_au_corps``."""
    from ..domain.facturation_vente import (
        FACTURE_DE_DEVIS_REFUSE, devis_impose_au_corps)
    if devis_impose_au_corps(donnees, facture):
        raise ValidationError(FACTURE_DE_DEVIS_REFUSE)


class FactureCycleActionsMixin:
    """Actions de cycle de ``FactureViewSet`` (mixin, aucune base)."""

    @extend_schema(request=OpenApiTypes.OBJECT,
                   responses={200: FactureSerializer, 400: D.ErreurDetail,
                              409: D.ErreurDetail})
    # api-only: le geste « Modifier le montant » du panneau de vente
    # (peut.modifier_montant, VNT23) arrive avec les lanes frontend M2.
    @action(detail=True, methods=['post'], url_path='montant-tranche',
            permission_classes=[IsAdminOrResponsableTier,
                                IsResponsableOrAdmin])
    def montant_tranche(self, request, pk=None):
        """VNT67 — le TTC d'un BROUILLON de tranche (arbitrage 5 : palier
        responsable/admin ET code d'écriture) : ``facturation_vente.
        modifier_montant_tranche`` ; refus rendus tels quels (400 / 409)."""
        from ..domain.facturation_vente import (
            FacturationVenteRefusee, modifier_montant_tranche)
        facture = self.get_object()
        try:
            facture = modifier_montant_tranche(
                facture, request.data.get('montant_ttc'), user=request.user)
        except FacturationVenteRefusee as exc:
            return Response(exc.corps, status=exc.status)
        facture.refresh_from_db()
        return Response(FactureSerializer(facture).data)
