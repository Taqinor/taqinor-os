"""Les réglages société du module — CAL45 (endpoint posé par CAL16).

``GET /api/django/calepinage/parametres/`` rend les SEPT sections, toujours
toutes présentes (contrat ``contract_samples/parametres_calepinage.json``) :
une société qui n'a jamais rien réglé reçoit sept objets vides, ce qui veut
dire « comportement d'aujourd'hui, strictement inchangé » — jamais une clé
absente que l'écran devrait deviner.

``PUT`` pose les sections fournies (mise à jour PARTIELLE) par le SEUL chemin
d'écriture du domaine, ``services.parametres.enregistrer_parametres`` : une
section inconnue est refusée en la NOMMANT, en français. La société vient
TOUJOURS de ``request.user`` — jamais d'un corps de requête.

Un GET n'écrit rien : le sélecteur est en lecture pure (un GET qui crée une
ligne en base est un GET qui ment).
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import ScopedPermission

from ..permissions import CAL_GERER, CAL_VOIR
from ..selectors import parametres_de_societe
from ..services.parametres import ReglageInvalide, enregistrer_parametres

__all__ = ['ParametresCalepinageView']


def _forme_reglages(nom):
    """YAPIC6/PACT7 — la forme DÉCLARÉE des réglages, tirée du contrat.

    Les sept sections sont celles de `contract_samples/
    parametres_calepinage.json` : ce sont des documents de réglage libres
    (chaque section a son propre vocabulaire, versionné dans le contrat),
    donc un `DictField` par section — pas un `dict` nu, que la garde
    `scripts/check_openapi_shapes.py` interdit à juste titre : une forme qui
    valide tout ne protège rien.
    """
    return inline_serializer(nom, {
        'imagerie': serializers.DictField(),
        'degagements': serializers.DictField(),
        'zones_types': serializers.DictField(),
        'gabarits_disposition': serializers.DictField(),
        'presets': serializers.DictField(),
        'favoris_materiel': serializers.DictField(),
        'gabarits_dossier': serializers.DictField(),
    })


class ParametresCalepinageView(APIView):
    """Les réglages calepinage de la société de l'appelant."""

    permission_classes = [ScopedPermission]
    read_permission = CAL_VOIR
    write_permission = CAL_GERER

    @extend_schema(responses={200: _forme_reglages(
        'CalepinageParametresReponse')})
    def get(self, request, *args, **kwargs):
        return Response(parametres_de_societe(
            getattr(request.user, 'company', None)))

    @extend_schema(request=_forme_reglages('CalepinageParametresRequete'),
                   responses={200: _forme_reglages(
                       'CalepinageParametresEcrite')})
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
