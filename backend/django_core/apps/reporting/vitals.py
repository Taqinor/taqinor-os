"""VX61 — collecte des Web Vitals RÉELS (POST, un beacon par métrique) +
agrégat p75 par route (GET).

Le frontend capte INP/LCP/CLS/TTFB via `PerformanceObserver` natif
(`frontend/src/lib/vitals.js` — hand-roll, la lib `web-vitals` de Google
reste une dépendance GATÉE) et envoie un `navigator.sendBeacon` par métrique.
`company`/`utilisateur` sont TOUJOURS posés côté serveur depuis
`request.user` — jamais lus du corps de la requête.
"""
from rest_framework import serializers
from rest_framework.decorators import (
    api_view, parser_classes, permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.champs_stricts import ChaineStricte, ChampsStrictsSansDecimalMixin
from core.parseurs import PARSEURS_JSON

from .models import WebVitalMetric
from .schema_fields import champ_choix
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers as drf_serializers
from drf_spectacular.utils import inline_serializer


class NombreVitalStrict(serializers.FloatField):
    """CI #997 fuzz (2) — la valeur mesurée est un NOMBRE JSON réel : ``false``
    (lu 0.0), ``"12"`` ou un entier hors flottant répondent 400 au lieu
    d'être convertis en silence (le schéma publie ``number``)."""

    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, (int, float)):
            self.fail('invalid')
        try:
            return super().to_internal_value(data)
        except OverflowError:  # entier JSON > 1e308 : ``float()`` déborde
            self.fail('invalid')


class WebVitalMetricSerializer(ChampsStrictsSansDecimalMixin,
                               serializers.ModelSerializer):
    # ``route`` : le beacon n'est jamais rejeté pour une URL trop longue (elle
    # est tronquée par ``validate_route``) — le schéma ne publie donc PAS de
    # ``maxLength`` (sinon 256 caractères « hors schéma » répondraient 201).
    route = ChaineStricte(required=False, allow_blank=True)
    value = NombreVitalStrict()

    class Meta:
        model = WebVitalMetric
        # company/utilisateur : posés côté serveur dans la vue, jamais lus du
        # corps — absents des champs acceptés en écriture.
        fields = ['route', 'metric', 'value', 'rating', 'navigation_id']

    def validate_route(self, value):
        # Le beacon envoie `window.location.pathname` — tronquer défensivement
        # plutôt que rejeter (jamais bloquer un beacon fire-and-forget).
        return (value or '')[:255]


class WebVitalRequeteSerializer(WebVitalMetricSerializer):
    metric = champ_choix(WebVitalMetric.Metric.values)


@extend_schema(
    request=WebVitalRequeteSerializer,
    responses={201: None})
@api_view(['POST'])
# CI #997 fuzz (2) : le beacon est du JSON (valeur = nombre) — un formulaire n'en porte que des chaînes
@parser_classes(PARSEURS_JSON)
@permission_classes([IsAuthenticated])
def collect_vital(request):
    """Beacon POST — une ligne par métrique. `sendBeacon`/`fetch keepalive`
    n'attendent jamais le corps de la réponse : 201 minimal suffit."""
    serializer = WebVitalMetricSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(company=request.user.company, utilisateur=request.user)
    return Response(status=201)


def _percentile_75(values):
    """p75 par tri simple — volumes modestes par route/société, pas besoin
    d'un calcul streaming. `None` si aucune valeur."""
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(0.75 * (len(ordered) - 1))))
    return ordered[idx]


_VITALS_VITALS_P75_REPONSE = inline_serializer('VitalsVitalsP75Reponse', {
    'route': drf_serializers.JSONField(allow_null=True),
    'metrics': drf_serializers.JSONField(allow_null=True),
})


@extend_schema(
    parameters=[
        OpenApiParameter('route', OpenApiTypes.STR, required=False),
    ],
    responses={200: _VITALS_VITALS_P75_REPONSE})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vitals_p75(request):
    """Agrégat p75 par métrique (INP/LCP/CLS/TTFB), borné à la société de
    l'utilisateur ; `?route=` filtre en plus sur une route précise."""
    co = request.user.company
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    qs = WebVitalMetric.objects.filter(company=co)
    route = request.query_params.get('route')
    if route:
        qs = qs.filter(route=route)

    metrics = {}
    for metric in WebVitalMetric.Metric.values:
        values = list(
            qs.filter(metric=metric).values_list('value', flat=True))
        metrics[metric] = {'p75': _percentile_75(values), 'count': len(values)}

    return Response({'route': route or None, 'metrics': metrics})
