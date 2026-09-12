"""NTAPI17 — `GET /api/public/v1/events/` : flux d'évènements par curseur.

Pagination par CURSEUR, jamais par numéro de page : ``?after=<sequence>``
renvoie les évènements strictement postérieurs, dans l'ordre. Un consommateur
mémorise la dernière ``sequence`` reçue et repolle avec — il ne re-scanne
jamais ce qu'il a déjà lu, et aucune insertion concurrente ne peut lui faire
« sauter » une ligne (contrairement à ``?page=2``, où une insertion décale tout
le contenu des pages suivantes).
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import ApiKeyAuthentication, ApiKeyRateThrottle, HasApiScope
from .constants import SCOPE_READ_EVENTS
from .events_feed import LIMITE_MAX, LIMITE_PAR_DEFAUT, lire, serialiser
from .public_response import PublicApiResponseMixin


def _entier(params, nom, defaut):
    brut = params.get(nom)
    if brut in (None, ''):
        return defaut
    try:
        return int(brut)
    except (TypeError, ValueError):
        raise ValidationError(
            {nom: f'Entier attendu pour « {nom} ».'})


@extend_schema(
    summary="Flux d'évènements consommable par curseur (NTAPI17).",
    responses=inline_serializer('PublicEventFeed', {
        'results': inline_serializer('PublicEventFeedEntry', {
            'sequence': serializers.IntegerField(),
            'type': serializers.CharField(),
            'event_id': serializers.CharField(),
            'payload': serializers.JSONField(),
            'created_at': serializers.CharField(),
        }, many=True),
        'next_after': serializers.IntegerField(allow_null=True),
        'limit': serializers.IntegerField(),
    }),
)
class PublicEventFeedView(PublicApiResponseMixin, APIView):
    """``GET /api/public/v1/events/?after=<sequence>&limit=<n>``.

    ``permission_classes = [HasApiScope]`` avec ``required_scope`` : le scope
    ``read:events`` ouvre le CANAL. Chaque évènement reste ensuite filtré, dans
    ``events_feed.lire``, par le scope de lecture de SA famille — une clé qui
    ne porterait que ``read:events`` lit un flux vide. Le flux n'est jamais un
    contournement des scopes de lecture."""

    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [HasApiScope]
    throttle_classes = [ApiKeyRateThrottle]
    required_scope = SCOPE_READ_EVENTS

    def get(self, request):
        after = _entier(request.query_params, 'after', 0)
        limit = _entier(request.query_params, 'limit', LIMITE_PAR_DEFAUT)
        if after < 0:
            raise ValidationError({'after': '« after » ne peut pas être négatif.'})
        if limit < 1:
            raise ValidationError({'limit': '« limit » doit valoir au moins 1.'})
        evenements, limite_effective = lire(
            request.auth, after=after, limit=min(limit, LIMITE_MAX))
        resultats = [serialiser(e) for e in evenements]
        return Response({
            'results': resultats,
            # Curseur à repasser tel quel au prochain appel. `None` quand la
            # page est vide : le client garde SON dernier curseur plutôt que de
            # repartir de zéro (un `0` ici lui ferait tout relire).
            'next_after': resultats[-1]['sequence'] if resultats else None,
            'limit': limite_effective,
        })
