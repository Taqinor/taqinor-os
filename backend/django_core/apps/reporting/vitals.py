"""VX61 — collecte des Web Vitals RÉELS (POST, un beacon par métrique) +
agrégat p75 par route (GET).

Le frontend capte INP/LCP/CLS/TTFB via `PerformanceObserver` natif
(`frontend/src/lib/vitals.js` — hand-roll, la lib `web-vitals` de Google
reste une dépendance GATÉE) et envoie un `navigator.sendBeacon` par métrique.
`company`/`utilisateur` sont TOUJOURS posés côté serveur depuis
`request.user` — jamais lus du corps de la requête.
"""
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import WebVitalMetric


class WebVitalMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebVitalMetric
        # company/utilisateur : posés côté serveur dans la vue, jamais lus du
        # corps — absents des champs acceptés en écriture.
        fields = ['route', 'metric', 'value', 'rating', 'navigation_id']

    def validate_route(self, value):
        # Le beacon envoie `window.location.pathname` — tronquer défensivement
        # plutôt que rejeter (jamais bloquer un beacon fire-and-forget).
        return (value or '')[:255]


@api_view(['POST'])
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
