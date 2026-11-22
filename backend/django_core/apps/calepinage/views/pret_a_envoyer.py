"""ACAL860 — ``GET /calepinages/<pk>/pret-a-envoyer/`` : « prêt à envoyer ? ».

Lecture seule, recalculée à chaque lecture (``services/pret_a_envoyer.py``) :
ni statut, ni version, ni devis touché (D-ACAL-1). Greffée sur
``CalepinageViewSet`` comme les autres actions rattachées
(``views/rattachements.py``) ; la société est bornée par ``get_object()`` :
un calepinage d'une autre société est INTROUVABLE (404).
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage
from ..services import pret_a_envoyer as controles
from .calepinages import CalepinageViewSet

__all__ = ['pret_a_envoyer', 'PRODUCTEURS']

#: Les producteurs du contrat ``calepinage_pret_a_envoyer.json``, dans
#: l'ordre de ses ``codes_produits`` (ACAL857 à ACAL864, puis les pentes).
PRODUCTEURS = (
    controles.controles_de_porte,  # ACAL857
    controles.controles_electriques,  # ACAL858
    controles.controles_du_resultat,  # ACAL859
    controles.controle_pentes_confirmees,  # ACAL860
    controles.controle_taille_sans_facture,  # ACAL861
    controles.controle_kwc_coherent,  # ACAL862
    controles.controle_obstacle_hors_pan,  # ACAL863
    controles.controle_pans_vides,  # ACAL864
    controles.controle_un_seul_chiffre,  # ACAL1171
    controles.controle_compatibilite,  # ACAL906
)


@extend_schema(responses={200: inline_serializer('CalepinagePretAEnvoyer', {
    'calepinage': serializers.IntegerField(),
    'pret': serializers.BooleanField(),
    'nombre_bloquants': serializers.IntegerField(),
    'nombre_a_regler': serializers.IntegerField(),
    'controles': serializers.ListField(child=serializers.DictField()),
})})
@action(detail=True, methods=['get'], url_path='pret-a-envoyer',
        permission_classes=[PeutVoirCalepinage])
def pret_a_envoyer(self, request, pk=None):
    """Les contrôles d'envoi, rouge en tête ; ``pret`` sans rouge ni orange."""
    return Response(controles.agreger(self.get_object(), PRODUCTEURS))


CalepinageViewSet.pret_a_envoyer = pret_a_envoyer
