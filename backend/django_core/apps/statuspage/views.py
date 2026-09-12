"""NTOBS1 — endpoints publics de la page de statut.

Aucune authentification, aucune donnée société : ne renvoie QUE les
composants/incidents SYSTÈME (``company=None``) — un enregistrement
société-spécifique (si un jour construit) ne doit JAMAIS fuiter ici.
Throttlé par IP (best-effort, sans dépendance externe, même patron que
``apps.sav.public_views.SavPublicThrottle``).
"""
from datetime import timedelta

from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .models import ComponentStatus, IncidentPublic, UptimeDayBucket
from .serializers import (
    ComponentStatusPublicSerializer, IncidentPublicSerializer,
    UptimeDayBucketSerializer,
)

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


class PublicIncidentDetailView(generics.RetrieveAPIView):
    """NTOBS2 — GET /api/django/statuspage/public/incidents/<pk>/ : détail
    d'UN incident système (utilisé par la page de détail/post-mortem)."""

    serializer_class = IncidentPublicSerializer
    permission_classes = [AllowAny]
    throttle_classes = [StatuspagePublicThrottle]

    def get_queryset(self):
        return (
            IncidentPublic.objects
            .filter(company__isnull=True)
            .prefetch_related('updates', 'composants')
        )


class IsDirecteurOrAdmin(BasePermission):
    """NTOBS2 — action réservée Directeur/Administrateur (même patron que
    ``apps.credit.views.IsDirecteurOrAdmin``, dupliqué localement : chaque
    app définit sa propre garde, jamais un import cross-app d'une classe de
    permission d'une autre app satellite)."""

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if getattr(u, 'is_superuser', False) or getattr(u, 'is_admin_role', False):
            return True
        role = getattr(u, 'role', None)
        return bool(role and role.nom in ('Directeur', 'Administrateur'))


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsDirecteurOrAdmin])
def publier_postmortem(request, pk):
    """NTOBS2 — POST statuspage/incidents/<pk>/publier-postmortem/.

    Publie le post-mortem d'un incident RÉSOLU (``statut=resolved``). Le
    texte (``postmortem_markdown``) est rédigé par le fondateur — texte libre,
    aucune génération automatique. Idempotent : republier ne fait
    qu'actualiser ``postmortem_publie_le``.
    """
    incident = get_object_or_404(IncidentPublic, pk=pk)
    if incident.statut != IncidentPublic.Statut.RESOLVED:
        return Response(
            {'detail': "L'incident doit être résolu avant de publier un post-mortem."},
            status=status.HTTP_400_BAD_REQUEST)
    if not incident.postmortem_markdown.strip():
        return Response(
            {'detail': 'Le contenu du post-mortem est vide.'},
            status=status.HTTP_400_BAD_REQUEST)
    incident.postmortem_publie_le = timezone.now()
    incident.save(update_fields=['postmortem_publie_le', 'updated_at'])
    return Response(IncidentPublicSerializer(incident).data)


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([StatuspagePublicThrottle])
def public_uptime_90j(request):
    """GET /api/django/statuspage/public/uptime-90j/ — frise 90 jours.

    Système uniquement (``company=None``), agrégats PRÉ-CALCULÉS (jamais un
    recalcul depuis des logs bruts à chaque requête) : renvoie
    ``{composant: [{date, statut, pct}, ...]}``."""
    depuis = timezone.now().date() - timedelta(days=UPTIME_HISTORY_DAYS)
    buckets = (
        UptimeDayBucket.objects
        .filter(company__isnull=True, date__gte=depuis)
        .order_by('composant', 'date')
    )
    data = UptimeDayBucketSerializer(buckets, many=True).data
    par_composant = {}
    for row in data:
        par_composant.setdefault(row['composant'], []).append({
            'date': row['date'],
            'statut': row['statut_pire_du_jour'],
            'pct': row['pct_disponible_jour'],
        })
    return Response(par_composant)
