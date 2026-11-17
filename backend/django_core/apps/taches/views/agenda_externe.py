"""Agendas externes (reference/api.md §3.4, §4 ; A18-M4) : au plus 3 adresses ICS, lues côté serveur.

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction ; leur
schéma OpenAPI est celui de leur échantillon de `contract_samples/`. Aucune écriture ici ne rend
de `geste_id` (api.md §0).
"""
from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from apps.taches.views.base import PERMISSIONS, PasEncore, corps, forme_echantillon, reponses
from core.idempotency import IdempotentCreateMixin

AGENDA_EXTERNE = forme_echantillon('agenda_externe')


class AgendasExternesVue(IdempotentCreateMixin, APIView):
    """GET agendas-externes/ (`{"results":[…]}`, ≤ 3) · POST (une adresse ICS, lue aussitôt)."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(forme_echantillon('agendas_externes')))
    def get(self, request):
        raise PasEncore()

    @extend_schema(request=corps('AgendaExterne', {
        'url': 'https://outlook.office365.com/owa/calendar/abc/reachcalendar.ics', 'libelle': 'Microsoft 365',
    }, requis=('url',)), responses=reponses(AGENDA_EXTERNE, statut=201, erreurs=(400,)))
    def post(self, request):
        raise PasEncore()


class AgendaExterneVue(APIView):
    """PATCH (libellé, actif, rang) · DELETE agendas-externes/{id}/."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('AgendaExternePatch', {'libelle': 'Bureau', 'actif': False, 'rang': 2048}),
                   responses=reponses(AGENDA_EXTERNE, erreurs=(400, 404)))
    def patch(self, request, id):
        raise PasEncore()

    @extend_schema(request=None, responses=reponses(None, statut=204, erreurs=(404,)))
    def delete(self, request, id):
        raise PasEncore()


class AgendaExterneRafraichirVue(APIView):
    """POST agendas-externes/{id}/rafraichir/ — relire maintenant (ignore le cache)."""

    permission_classes = PERMISSIONS

    @extend_schema(request=None, responses=reponses(AGENDA_EXTERNE, erreurs=(404,)))
    def post(self, request, id):
        raise PasEncore()
