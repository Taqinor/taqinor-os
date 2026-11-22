"""ACAL860 — ``GET /calepinages/<pk>/pret-a-envoyer/`` : « prêt à envoyer ? ».

Lecture seule, recalculée à chaque lecture (``services/pret_a_envoyer.py``) :
ni statut, ni version, ni devis touché (D-ACAL-1). Greffée sur
``CalepinageViewSet`` comme les autres actions rattachées
(``views/rattachements.py``) ; la société est bornée par ``get_object()`` :
un calepinage d'une autre société est INTROUVABLE (404).
"""
from __future__ import annotations

from drf_spectacular.utils import (
    OpenApiParameter, OpenApiResponse, extend_schema, inline_serializer,
)
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage
from ..services import pret_a_envoyer as controles
from .calepinages import CalepinageViewSet

__all__ = ['pret_a_envoyer', 'PRODUCTEURS', 'PRODUCTEURS_PAR_ETAPE']

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

#: H3 (22/11) — ``?etape=<clé>`` : seuls les producteurs dont un code se règle
#: dans CETTE étape (le rangement de l'écran, ``PretAEnvoyer.helpers.js::
#: ETAPE_DU_CODE``) ; l'étape Électrique ne paie plus le dimensionnement du
#: lead ni la porte. Sans ``etape`` : tous, comme avant.
PRODUCTEURS_PAR_ETAPE = {
    'toit': (controles.controles_de_porte, controles.controle_pentes_confirmees,
             controles.controle_obstacle_hors_pan,
             controles.controle_pans_vides),
    'panneaux': (controles.controles_de_porte, controles.controles_du_resultat,
                 controles.controle_taille_sans_facture,
                 controles.controle_kwc_coherent,
                 controles.controle_un_seul_chiffre),
    'electrique': (controles.controles_electriques,
                   controles.controle_compatibilite),
    'resultats': (controles.controles_de_porte,
                  controles.controles_du_resultat),
}


_ETAPE = OpenApiParameter(
    'etape', str, enum=sorted(PRODUCTEURS_PAR_ETAPE), required=False,
    description="Seuls les contrôles de cette étape ; ``pret`` et les "
                "comptes portent alors sur eux seuls.")


@extend_schema(parameters=[_ETAPE], responses={200: inline_serializer(
    'CalepinagePretAEnvoyer', {
        'calepinage': serializers.IntegerField(),
        'etape': serializers.CharField(allow_null=True),
        'pret': serializers.BooleanField(),
        'nombre_bloquants': serializers.IntegerField(),
        'nombre_a_regler': serializers.IntegerField(),
        'controles': serializers.ListField(child=serializers.DictField()),
    }), 400: OpenApiResponse(description="Refus nommant « etape » (étape "
                                         "inconnue).")})
@action(detail=True, methods=['get'], url_path='pret-a-envoyer',
        permission_classes=[PeutVoirCalepinage])
def pret_a_envoyer(self, request, pk=None):
    """Les contrôles d'envoi, rouge en tête ; ``pret`` sans rouge ni orange."""
    etape = request.query_params.get('etape') or None
    if etape is not None and etape not in PRODUCTEURS_PAR_ETAPE:
        raise ValidationError({'etape': 'Étape inconnue : choisissez parmi %s.'
                               % ', '.join(sorted(PRODUCTEURS_PAR_ETAPE))})
    return Response(controles.agreger(
        self.get_object(),
        PRODUCTEURS_PAR_ETAPE[etape] if etape else PRODUCTEURS, etape=etape))


CalepinageViewSet.pret_a_envoyer = pret_a_envoyer
