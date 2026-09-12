"""NTOBS1 — endpoints publics de la page de statut.

Aucune authentification, aucune donnée société : ne renvoie QUE les
composants/incidents SYSTÈME (``company=None``) — un enregistrement
société-spécifique (si un jour construit) ne doit JAMAIS fuiter ici.
Throttlé par IP (best-effort, sans dépendance externe, même patron que
``apps.sav.public_views.SavPublicThrottle``).
"""
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .models import ComponentStatus, IncidentPublic
from .serializers import ComponentStatusPublicSerializer, IncidentPublicSerializer

PUBLIC_STATUS_CACHE_KEY = 'statuspage:public:status'
PUBLIC_STATUS_CACHE_SECONDS = 60
UPTIME_HISTORY_DAYS = 90


class StatuspagePublicThrottle(SimpleRateThrottle):
    """Limite le débit des endpoints publics par IP (sans dépendance externe)."""

    scope = 'statuspage_public'
    rate = '60/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


def _statut_global(composants):
    """Agrège le pire statut des composants système visibles publiquement."""
    ordre = {
        ComponentStatus.Statut.MAJOR_OUTAGE: 3,
        ComponentStatus.Statut.PARTIAL_OUTAGE: 2,
        ComponentStatus.Statut.DEGRADED: 1,
        ComponentStatus.Statut.OPERATIONAL: 0,
    }
    pire = ComponentStatus.Statut.OPERATIONAL
    for comp in composants:
        if ordre.get(comp['statut'], 0) > ordre.get(pire, 0):
            pire = comp['statut']
    return pire


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([StatuspagePublicThrottle])
def public_status(request):
    """GET /api/django/statuspage/public/ — statut courant des composants système.

    Cache 60 s (mémoire partagée Django) : jamais plus d'une requête DB par
    minute pour ce endpoint, quel que soit le trafic public.
    """
    cached = cache.get(PUBLIC_STATUS_CACHE_KEY)
    if cached is not None:
        return Response(cached)

    composants_qs = ComponentStatus.objects.filter(company__isnull=True)
    composants = ComponentStatusPublicSerializer(composants_qs, many=True).data
    payload = {
        'overall_status': _statut_global(composants),
        'composants': composants,
        'generated_at': timezone.now().isoformat(),
    }
    cache.set(PUBLIC_STATUS_CACHE_KEY, payload, PUBLIC_STATUS_CACHE_SECONDS)
    return Response(payload)


class PublicIncidentsView(generics.ListAPIView):
    """GET /api/django/statuspage/public/incidents/ — historique 90 jours.

    Système uniquement (``company=None``), paginé (pagination DRF par défaut
    du projet), jamais un incident société-spécifique.
    """

    serializer_class = IncidentPublicSerializer
    permission_classes = [AllowAny]
    throttle_classes = [StatuspagePublicThrottle]

    def get_queryset(self):
        depuis = timezone.now() - timedelta(days=UPTIME_HISTORY_DAYS)
        return (
            IncidentPublic.objects
            .filter(company__isnull=True, debute_le__gte=depuis)
            .prefetch_related('updates', 'composants')
            .order_by('-debute_le')
        )
