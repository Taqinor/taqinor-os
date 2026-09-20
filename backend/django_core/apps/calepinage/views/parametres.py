"""Les réglages société du module — CAL45 (endpoint posé par CAL16).

``GET /api/django/calepinage/parametres/`` rend les SEPT sections, toujours
toutes présentes (contrat ``contract_samples/parametres_calepinage.json``) :
une société qui n'a jamais rien réglé reçoit sept objets vides, ce qui veut
dire « comportement d'aujourd'hui, strictement inchangé » — jamais une clé
absente que l'écran devrait deviner.

CAL246 — la même réponse porte AUSSI ``kits`` : le catalogue de kits de pose
AO (``apps.ao.selectors.kits_de_pose``, CAL198), LU, jamais STOCKÉ — ce n'est
donc pas une huitième section de ``ParametresCalepinage`` (aucune migration),
et ``PUT`` la refuse comme toute clé inconnue (catalogue en LECTURE SEULE
depuis cet endpoint).

``PUT`` pose les sections fournies (mise à jour PARTIELLE) par le SEUL chemin
d'écriture du domaine, ``services.parametres.enregistrer_parametres`` : une
section inconnue est refusée en la NOMMANT, en français. La société vient
TOUJOURS de ``request.user`` — jamais d'un corps de requête.

Un GET n'écrit rien : le sélecteur est en lecture pure (un GET qui crée une
ligne en base est un GET qui ment).
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import ScopedPermission

from ..permissions import CAL_GERER, CAL_VOIR
from ..selectors import kits_de_pose_disponibles, parametres_de_societe
from ..services.parametres import ReglageInvalide, enregistrer_parametres

__all__ = ['ParametresCalepinageView', 'SuggestionPenteIGNView']


class ParametresCalepinageView(APIView):
    """Les réglages calepinage de la société de l'appelant."""

    permission_classes = [ScopedPermission]
    read_permission = CAL_VOIR
    write_permission = CAL_GERER

    def get(self, request, *args, **kwargs):
        company = getattr(request.user, 'company', None)
        reponse = parametres_de_societe(company)
        # CAL246 — catalogue LU (AO), jamais stocké : ajouté à la réponse,
        # jamais accepté en écriture (PUT ne connaît que les 7 sections).
        reponse['kits'] = kits_de_pose_disponibles(company)
        return Response(reponse)

    def put(self, request, *args, **kwargs):
        donnees = request.data if isinstance(request.data, dict) else None
        if donnees is None:
            return Response(
                {'detail': "Le corps attendu est un objet « section : "
                           "réglages »."},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            reglages = enregistrer_parametres(
                getattr(request.user, 'company', None), donnees)
        except ReglageInvalide as refus:
            return Response({refus.champ or 'detail': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(reglages)


class SuggestionPenteIGNView(APIView):
    """CAL237 — pente et azimut SUGGÉRÉS par pan, depuis l'IGN. France seule.

    La porte vit AVEC les réglages parce que c'est un RÉGLAGE qui la commande :
    le service n'existe que si la société a déclaré ``pays = 'fr'`` dans sa
    section « imagerie » (CAL47). Elle ne sert aucun objet métier — aucun
    identifiant de calepinage n'entre ici — et ne persiste RIEN : elle propose.

    * ``GET`` — le service est-il offert ici ? Réponse LOCALE : aucune requête
      sortante n'est émise, même quand il l'est.
    * ``POST`` — ``{"roof_layout": {…}}`` (ou le document nu) : une suggestion
      par pan exploitable, chacune portant sa SOURCE et son horodatage. Le
      document n'est pas modifié : c'est le dessinateur qui accepte ou jette,
      et une suggestion refusée laisse la pente saisie seule vérité.
    * ``403`` — société hors France : le motif FRANÇAIS nomme le champ
      (« pays »), et aucune requête sortante n'a été émise.
    """

    permission_classes = [ScopedPermission]
    read_permission = CAL_VOIR
    #: Proposer consomme du temps serveur et un quota externe : c'est une
    #: écriture au sens des permissions, comme le moteur (CAL22).
    write_permission = CAL_GERER

    def get(self, request, *args, **kwargs):
        from ..services.lidar_ign import (
            PAYS_COUVERT, SOURCE, URL_SOURCE, service_disponible,
        )

        company = getattr(request.user, 'company', None)
        return Response({
            'disponible': service_disponible(company),
            'pays_couvert': PAYS_COUVERT,
            'source': SOURCE,
            'source_url': URL_SOURCE,
            'suggestions': [],
            'detail': '',
        })

    def post(self, request, *args, **kwargs):
        from ..services.lidar_ign import (
            PAYS_COUVERT, SOURCE, URL_SOURCE, ServiceIndisponible,
            suggerer_pentes,
        )

        donnees = request.data if isinstance(request.data, dict) else None
        document = None
        if isinstance(donnees, dict):
            document = donnees.get('roof_layout')
            if not isinstance(document, dict):
                document = donnees
        if not isinstance(document, dict) or not document.get('zones'):
            return Response(
                {'roof_layout': "Document de conception manquant : aucun pan "
                                "(« zones ») à analyser."},
                status=status.HTTP_400_BAD_REQUEST)

        try:
            suggestions = suggerer_pentes(
                getattr(request.user, 'company', None), document)
        except ServiceIndisponible as refus:
            return Response(
                {refus.champ or 'detail': str(refus),
                 'disponible': False,
                 'pays_couvert': PAYS_COUVERT,
                 'source': SOURCE,
                 'source_url': URL_SOURCE,
                 'suggestions': []},
                status=status.HTTP_403_FORBIDDEN)

        return Response({
            'disponible': True,
            'pays_couvert': PAYS_COUVERT,
            'source': SOURCE,
            'source_url': URL_SOURCE,
            'suggestions': suggestions,
            'detail': '' if suggestions else (
                "Aucun pan ne porte assez de points d'altitude exploitables : "
                "aucune pente n'est suggérée (rien n'est deviné)."),
        })
