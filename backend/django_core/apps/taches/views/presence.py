"""L'iPhone (reference/api.md §3.4 ; conception/spec-6b-iphone.md) : jetons d'accès, notification
de test, tuile Scriptable, calendrier abonné.

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction ; la
tuile et le flux sont authentifiés par le BOUCHON `JetonPasEncoreLivre` (401 neutre) tant que
`JetonAccesAuthentication` n'est pas livrée.
"""
from rest_framework.views import APIView

from apps.taches.views.base import AUTH_JETON, PERMISSIONS, PasEncore


class JetonsVue(APIView):
    """GET jetons/ (sans empreinte) · POST jetons/ `{usage}` (clair rendu UNE fois)."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()

    def post(self, request):
        raise PasEncore()


class JetonRevoquerVue(APIView):
    """POST jetons/{id}/revoquer/."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class TestNotificationVue(APIView):
    """POST mon-iphone/test-notification/ — push `TACHES_RAPPEL`, hors plafond."""

    permission_classes = PERMISSIONS

    def post(self, request):
        raise PasEncore()


class TuileVue(APIView):
    """GET tuile/ — tuile Scriptable, jeton `tuile` (J:tuile)."""

    authentication_classes = AUTH_JETON
    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()


class FluxVue(APIView):
    """GET flux/{jeton}.ics — calendrier abonné, jeton `flux` dans l'adresse (J:flux)."""

    authentication_classes = AUTH_JETON
    permission_classes = PERMISSIONS

    def get(self, request, jeton):
        raise PasEncore()
