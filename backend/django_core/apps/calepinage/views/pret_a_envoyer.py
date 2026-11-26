"""ACAL860 — ``GET /calepinages/<pk>/pret-a-envoyer/`` : « prêt à envoyer ? ».

Lecture seule, recalculée à chaque lecture (``services/pret_a_envoyer.py``) :
ni statut, ni version, ni devis touché (D-ACAL-1) ; seule la lecture complète
range son verdict pour la liste (ACAL1333, ``dernier_verdict``). Greffée sur
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

from ..permissions import PeutGererCalepinage, PeutVoirCalepinage
from ..serializers import forme_du_contrat
from ..services import pret_a_envoyer as controles
from ..services.lecture_liste import ranger_verdict
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
    calepinage = self.get_object()
    reponse = controles.agreger(
        calepinage,
        PRODUCTEURS_PAR_ETAPE[etape] if etape else PRODUCTEURS, etape=etape)
    if etape is None:
        # ACAL1333 — seule la lecture COMPLÈTE range le verdict que lit la liste.
        ranger_verdict(calepinage, reponse)
    return Response(reponse)


CalepinageViewSet.pret_a_envoyer = pret_a_envoyer


# Lane E9 (T4-X5-010) — ``GET calepinages/<pk>/apercu-devis/`` : AVANT « Générer le devis », le module et
# l'onduleur que chaque option du devis PORTERA (dry-run de LA composition, rien d'écrit) et les
# désignations de l'étape Électrique qu'il ne portera pas. Société bornée par ``get_object()`` (404).
# Contrat ``contract_samples/calepinage_apercu_devis.json``.
_SURFACES = OpenApiParameter(
    'surfaces', str, required=False,
    description="Clés des surfaces cochées (séparées par des virgules), comme ``surfaces_chiffrees`` de "
                "« Générer le devis » ; absent = tout le document.")


@extend_schema(parameters=[_SURFACES],
               responses=forme_du_contrat('CalepinageApercuDevis', 'calepinage_apercu_devis.json'))
@action(detail=True, methods=['get'], url_path='apercu-devis', permission_classes=[PeutVoirCalepinage])
def apercu_devis(self, request, pk=None):
    """Le matériel que « Générer le devis » portera, par option, et les écarts aux désignations."""
    from ..services.devis import lit_les_devis
    from ..services.devis_apercu import apercu_materiel_du_devis

    calepinage = self.get_object()
    # Lane E9b — les surfaces COCHÉES que « Générer » enverra (``surfaces_chiffrees``), séparées par
    # des virgules ; absent = tout le document, comme la génération.
    brut = request.query_params.get('surfaces')
    surfaces = None if brut is None else [cle.strip() for cle in brut.split(',') if cle.strip()]
    # Lot 8 (D-ACAL-106) — un devis n'est jamais NOMMÉ à qui ne peut pas le lire (garde de lecture
    # des devis, ``DevisViewSet`` list/retrieve, via ``ventes.selectors_assistant.lit_les_devis``).
    return Response(apercu_materiel_du_devis(calepinage, surfaces=surfaces,
                                             lit_les_devis=lit_les_devis(request.user)))


CalepinageViewSet.apercu_devis = apercu_devis


# ACAL1320 (D-ACAL-73) — ``GET calepinages/<pk>/apercu-resync/`` : AVANT « Resynchroniser le devis », ce
# que la resynchronisation CHANGERA au devis lié (jouée puis annulée par ventes : rien d'écrit) ; mêmes
# droits que ``sync-devis`` ; mêmes refus (409 de statut, 400 sans devis lié). Contrat
# ``contract_samples/calepinage_apercu_resync.json``.
_DEVIS_VARIANTE = OpenApiParameter(
    'devis', int, required=False,
    description="Le devis porté par une variante de ce calepinage (comme ``devis`` de « Resynchroniser le "
                "devis ») ; absent = le devis du calepinage.")


@extend_schema(parameters=[_SURFACES, _DEVIS_VARIANTE],
               responses={200: forme_du_contrat('CalepinageApercuResync', 'calepinage_apercu_resync.json'),
                          409: OpenApiResponse(description="Refus de statut de ventes (``detail``, "
                                                           "``revision_possible``), tel quel.")})
@action(detail=True, methods=['get'], url_path='apercu-resync', permission_classes=[PeutGererCalepinage])
def apercu_resync(self, request, pk=None):
    """Ce que « Resynchroniser le devis » changerait au devis lié, sans rien écrire."""
    from ..services.devis import DevisRefuse, lit_les_devis  # porte de ventes (cliquet des imports croisés)
    from ..services.devis_resync_apercu import apercu_resynchronisation
    from .calepinages import _entier_ou_none, _refus_devis, _statut_refus_devis

    calepinage = self.get_object()
    brut = request.query_params.get('surfaces')
    surfaces = None if brut is None else [cle.strip() for cle in brut.split(',') if cle.strip()]
    try:
        reponse = apercu_resynchronisation(
            calepinage, user=request.user, devis_id=_entier_ou_none(request.query_params.get('devis')),
            surfaces_chiffrees=surfaces, lit_les_devis=lit_les_devis(request.user))
    except DevisRefuse as refus:
        return Response(_refus_devis(refus), status=_statut_refus_devis(refus))
    return Response(reponse)


CalepinageViewSet.apercu_resync = apercu_resync
