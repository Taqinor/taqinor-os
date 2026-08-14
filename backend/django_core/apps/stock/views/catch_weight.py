"""NTWMS37 — actions de relevé à unité variable sur une réception fournisseur.

Montées sur ``ReceptionFournisseurViewSet`` (mixin) ; les gardes de rôle sont
déclarées dans le ``get_permissions`` du viewset hôte — piège connu :
``get_permissions`` écrase le ``permission_classes`` d'une ``@action``.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin


def _pesee_payload(ligne, pesee):
    from ..services_catch_weight import (
        ecart_pesee_ligne, quantite_valorisable_ligne,
    )
    ecart = ecart_pesee_ligne(ligne)
    return {
        'ligne_reception': ligne.id,
        'quantite_nominale': ligne.quantite,
        'unite_variable': bool(pesee and pesee.unite_variable),
        'quantite_reelle': (str(pesee.quantite_reelle)
                            if pesee and pesee.quantite_reelle is not None
                            else None),
        'unite_mesure': (pesee.unite_mesure if pesee else ''),
        'quantite_valorisable': str(quantite_valorisable_ligne(ligne)),
        'ecart': (str(ecart) if ecart is not None else None),
    }


PESEE_SHAPE = {
    'ligne_reception': serializers.IntegerField(),
    'quantite_nominale': serializers.IntegerField(),
    'unite_variable': serializers.BooleanField(),
    'quantite_reelle': serializers.CharField(allow_null=True),
    'unite_mesure': serializers.CharField(allow_blank=True),
    'quantite_valorisable': serializers.CharField(),
    'ecart': serializers.CharField(allow_null=True),
}


class PeseeLigneActionsMixin:
    """NTWMS37 — consultation et saisie du relevé réel, ligne par ligne."""

    @extend_schema(responses={
        200: inline_serializer('StockReceptionPesees', {
            'lignes': serializers.ListField(
                child=inline_serializer('StockReceptionPeseeLigne',
                                        PESEE_SHAPE)),
        }),
    })
    @action(detail=True, methods=['get'], url_path='pesees',
            permission_classes=[IsAnyRole])
    def pesees(self, request, pk=None):
        """Relevés (ou leur absence) de toutes les lignes de la réception."""
        from ..services_catch_weight import pesee_de_ligne

        reception = self.get_object()
        lignes = reception.lignes.select_related('ligne_commande').all()
        return Response({
            'lignes': [_pesee_payload(li, pesee_de_ligne(li))
                       for li in lignes],
        })

    @extend_schema(request=None, responses={
        200: inline_serializer('StockReceptionPeseeSaisie', PESEE_SHAPE),
    })
    @action(detail=True, methods=['post'],
            url_path=r'lignes/(?P<ligne_id>[0-9]+)/pesee',
            permission_classes=[IsResponsableOrAdmin])
    def pesee_ligne(self, request, pk=None, ligne_id=None):
        """Saisit le relevé d'UNE ligne (``{unite_variable?, quantite_reelle,
        unite_mesure?, note?}``). Sans appel, la ligne garde exactement le
        comportement historique."""
        from ..services_catch_weight import enregistrer_pesee_ligne_reception

        reception = self.get_object()
        ligne = reception.lignes.filter(id=ligne_id).first()
        if ligne is None:
            return Response({'detail': 'Ligne introuvable sur cette '
                                       'réception.'},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            pesee = enregistrer_pesee_ligne_reception(
                ligne_reception=ligne, user=request.user,
                unite_variable=request.data.get('unite_variable', True),
                quantite_reelle=request.data.get('quantite_reelle'),
                unite_mesure=request.data.get('unite_mesure') or 'kg',
                note=request.data.get('note') or '')
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(_pesee_payload(ligne, pesee))
