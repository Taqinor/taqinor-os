"""L'iPhone (reference/api.md §3.4 ; conception/spec-6b-iphone.md) : jetons d'accès, notification
de test, tuile Scriptable, calendrier abonné.

`jetons/` (session, jamais sous l'en-tête assistant : 403) : la liste ne sert jamais d'empreinte ; la
création rend le clair UNE fois et révoque l'ancien du même usage. La tuile et le flux sont
authentifiés par `JetonAccesAuthentication` de LEUR usage (`auth_jeton.py`) ; le flux sert du
`text/calendar`, son jeton est dans l'adresse (aucun en-tête d'authentification au schéma) : son
chemin est masqué pour les journaux et ses réponses d'erreur ne sont jamais réécrites par
`django.request`. Une route pas encore construite lève
`PasEncore` (501).
"""
import re

from django.db.models import F
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView

from apps.taches.auth_jeton import JetonFlux, JetonTuile, emettre_jeton, revoquer_jeton
from apps.taches.selectors.base import jetons_de
from apps.taches.serializers.presence import JetonEntreeSerializer, JetonSerializer, forme_jeton_cree
from apps.taches.throttles import ThrottleFlux, ThrottleTuile
from apps.taches.views.base import (
    ERREUR_DETAIL, PERMISSIONS, MethodeAvantJeton, PasEncore, corps, est_assistant, forme_echantillon,
    reponses,
)

#: `jetons/` rend au plus 20 lignes (api.md §0), actives d'abord puis les plus récentes.
PLAFOND_JETONS = 20
DETAIL_INTROUVABLE = 'Introuvable.'
DEBITS = list(api_settings.DEFAULT_THROTTLE_CLASSES)
#: Le segment du flux qui porte le jeton, et ce qu'en voient les journaux.
MOTIF_CHEMIN_FLUX = re.compile(r'/flux/[^/]+\.ics$')
CHEMIN_FLUX_MASQUE = '/flux/<jeton>.ics'


class HorsAssistant(BasePermission):
    """403 sous l'en-tête assistant (api.md §0 : `jetons/` ne sert jamais le relais du Copilote)."""

    message = "L'assistant ne gère pas les jetons."

    def has_permission(self, request, view):
        return not est_assistant(request)


class JetonsVue(APIView):
    """GET jetons/ (sans empreinte) · POST jetons/ `{usage}` (clair rendu UNE fois)."""

    permission_classes = [*PERMISSIONS, HorsAssistant]

    @extend_schema(responses=reponses(forme_echantillon('jetons_liste')))
    def get(self, request):
        jetons = (jetons_de(request.user)
                  .order_by(F('revoque_le').desc(nulls_first=True), '-created_at', '-pk')[:PLAFOND_JETONS])
        return Response({'results': JetonSerializer(jetons, many=True).data})

    @extend_schema(request=corps('Jeton', {'usage': 'flux', 'libelle': ''}, requis=('usage',)),
                   responses=reponses(forme_echantillon('jeton'), statut=201, erreurs=(400,)))
    def post(self, request):
        entree = JetonEntreeSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        jeton, clair = emettre_jeton(request.user, entree.validated_data['usage'],
                                     entree.validated_data['libelle'])
        reponse = Response(forme_jeton_cree(request, jeton, clair), status=status.HTTP_201_CREATED)
        reponse['Cache-Control'] = 'no-store'
        return reponse


class JetonRevoquerVue(APIView):
    """POST jetons/{id}/revoquer/ — l'id d'un autre compte répond comme un id inconnu (404)."""

    permission_classes = [*PERMISSIONS, HorsAssistant]

    @extend_schema(request=None, responses=reponses(None, statut=204, erreurs=(404,)))
    def post(self, request, id):
        jeton = jetons_de(request.user).filter(pk=id).first()
        if jeton is None:
            raise NotFound(DETAIL_INTROUVABLE)
        revoquer_jeton(jeton)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TestNotificationVue(APIView):
    """POST mon-iphone/test-notification/ — push `TACHES_RAPPEL`, hors plafond."""

    permission_classes = PERMISSIONS

    @extend_schema(request=None, responses=reponses(None, statut=204))
    def post(self, request):
        raise PasEncore()


class TuileVue(MethodeAvantJeton, APIView):
    """GET tuile/ — tuile Scriptable, jeton `tuile` (J:tuile)."""

    authentication_classes = [JetonTuile]
    permission_classes = PERMISSIONS
    throttle_classes = [*DEBITS, ThrottleTuile]

    @extend_schema(responses={200: forme_echantillon('tuile'), 401: ERREUR_DETAIL, 429: ERREUR_DETAIL})
    def get(self, request):
        raise PasEncore()


class FluxVue(MethodeAvantJeton, APIView):
    """GET flux/{jeton}.ics — calendrier abonné, jeton `flux` dans l'adresse (J:flux)."""

    authentication_classes = [JetonFlux]
    permission_classes = PERMISSIONS
    throttle_classes = [*DEBITS, ThrottleFlux]

    def initialize_request(self, request, *args, **kwargs):
        """Le chemin porte le jeton : `request.path` (lu par les journaux, dont celui d'un 500) est
        masqué dès l'entrée de la vue ; le jeton reste lu dans les `kwargs` de l'adresse résolue."""
        request.path = MOTIF_CHEMIN_FLUX.sub(CHEMIN_FLUX_MASQUE, request.path)
        return super().initialize_request(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        """Le chemin porte le jeton : une réponse d'erreur n'est jamais écrite par `django.request`
        (« Not Found: /…/flux/<jeton>.ics ») ; `Cache-Control: no-store` partout."""
        response = super().finalize_response(request, response, *args, **kwargs)
        if response.status_code >= 400:
            response._has_been_logged = True
        response['Cache-Control'] = 'no-store'
        return response

    @extend_schema(auth=[], responses={
        (200, 'text/calendar'): OpenApiTypes.STR,
        (404, 'application/json'): ERREUR_DETAIL,
        (429, 'application/json'): ERREUR_DETAIL,
    })
    def get(self, request, jeton):
        raise PasEncore()
