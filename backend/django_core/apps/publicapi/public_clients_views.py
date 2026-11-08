"""NTI18N42 — langue documentaire RÉSOLUE d'un client, en lecture seule.

``GET /api/public/v1/clients/<id>/langue/`` : pour une intégration tierce qui
génère ses propres communications (courriers, SMS, e-mails) et veut les écrire
dans la langue que la société utiliserait pour les documents de ce client.

Authentifiée par clé d'API (scope dédié ``read:clients``), société TOUJOURS
prise sur la clé. Le client est lu par le ``selectors.py`` de l'app ``crm``
(jamais ``apps.crm.models``) ; un client d'une autre société est un 404, jamais
un 403 (on ne révèle pas son existence).

CE QUI EST SERVI — trois clés, rien d'autre : ``client_id``,
``langue_document`` (la préférence STOCKÉE sur la fiche) et ``langue_sortie``
(la langue RÉSOLUE par ``i18n_resolver.resolve_langue_sortie`` : préférence
client si elle diffère du défaut, sinon repli société, sinon ``fr``). Ni nom,
ni coordonnées, ni aucun champ de la fiche : le scope ouvre une langue, pas un
annuaire.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.crm.selectors import get_company_client
from apps.parametres.i18n_resolver import resolve_langue_sortie

from .auth import PUBLIC_AUTHENTICATION_CLASSES, ApiKeyRateThrottle, HasApiScope
from .portees import SCOPE_READ_CLIENTS
from .public_response import PublicApiResponseMixin


class PublicClientLangueView(PublicApiResponseMixin, APIView):
    """``GET /api/public/v1/clients/<id>/langue/``."""

    authentication_classes = PUBLIC_AUTHENTICATION_CLASSES
    permission_classes = [HasApiScope]
    throttle_classes = [ApiKeyRateThrottle]
    required_scope = SCOPE_READ_CLIENTS

    @extend_schema(responses=inline_serializer('ClientLanguePublic', {
        'client_id': drf_serializers.IntegerField(),
        'langue_document': drf_serializers.CharField(),
        'langue_sortie': drf_serializers.CharField(),
    }))
    def get(self, request, pk):
        company = request.auth.company
        client = get_company_client(company, pk)
        if client is None:
            raise NotFound()
        return Response({
            'client_id': client.pk,
            'langue_document': client.langue_document,
            'langue_sortie': resolve_langue_sortie(
                client=client, company=company),
        })
