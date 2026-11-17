"""L'iPhone (reference/api.md §3.4 ; conception/spec-6b-iphone.md) : jetons d'accès, notification
de test, tuile Scriptable, calendrier abonné.

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction ; la
tuile et le flux sont authentifiés par le BOUCHON `JetonPasEncoreLivre` (401 neutre) tant que
`JetonAccesAuthentication` n'est pas livrée. Le flux sert du `text/calendar` ; son jeton est dans
l'adresse (aucun en-tête d'authentification au schéma).
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from apps.taches.views.base import (
    AUTH_JETON, ERREUR_DETAIL, PERMISSIONS, MethodeAvantJeton, PasEncore, corps, forme_echantillon,
    reponses,
)


class JetonsVue(APIView):
    """GET jetons/ (sans empreinte) · POST jetons/ `{usage}` (clair rendu UNE fois)."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(forme_echantillon('jetons_liste')))
    def get(self, request):
        raise PasEncore()

    @extend_schema(request=corps('Jeton', {'usage': 'flux', 'libelle': ''}, requis=('usage',)),
                   responses=reponses(forme_echantillon('jeton'), statut=201, erreurs=(400,)))
    def post(self, request):
        raise PasEncore()


class JetonRevoquerVue(APIView):
    """POST jetons/{id}/revoquer/."""

    permission_classes = PERMISSIONS

    @extend_schema(request=None, responses=reponses(None, statut=204, erreurs=(404,)))
    def post(self, request, id):
        raise PasEncore()


class TestNotificationVue(APIView):
    """POST mon-iphone/test-notification/ — push `TACHES_RAPPEL`, hors plafond."""

    permission_classes = PERMISSIONS

    @extend_schema(request=None, responses=reponses(None, statut=204))
    def post(self, request):
        raise PasEncore()


class TuileVue(MethodeAvantJeton, APIView):
    """GET tuile/ — tuile Scriptable, jeton `tuile` (J:tuile)."""

    authentication_classes = AUTH_JETON
    permission_classes = PERMISSIONS

    @extend_schema(responses={200: forme_echantillon('tuile'), 401: ERREUR_DETAIL, 429: ERREUR_DETAIL})
    def get(self, request):
        raise PasEncore()


class FluxVue(MethodeAvantJeton, APIView):
    """GET flux/{jeton}.ics — calendrier abonné, jeton `flux` dans l'adresse (J:flux)."""

    authentication_classes = AUTH_JETON
    permission_classes = PERMISSIONS

    @extend_schema(auth=[], responses={
        (200, 'text/calendar'): OpenApiTypes.STR,
        (401, 'application/json'): ERREUR_DETAIL,
        (404, 'application/json'): ERREUR_DETAIL,
        (429, 'application/json'): ERREUR_DETAIL,
    })
    def get(self, request, jeton):
        raise PasEncore()
