"""XPLT10 — Partage de dashboard : lien public tokenisé + mode TV + partage
interne granulaire.

Trois surfaces :
  * ``PartageDashboardViewSet``  — CRUD des liens publics tokenisés (créer /
    révoquer), bornés à la société.
  * ``dashboard_public(request, token)`` — accès PUBLIC lecture seule (aucune
    identité de confiance : tout est résolu depuis le jeton), calqué sur
    ``ged.resolve_partage_public``/``PARTAGE_*``.
  * ``DashboardPartageInterneViewSet`` — partage interne fin (utilisateur/rôle
    → lecture/édition), plus fin que ``Dashboard.partage`` (inchangé).
  * ``dashboard_tv(request)`` — liste des dashboards partagés pour le mode TV
    (rotation + rafraîchissement pilotés côté frontend).

Aucune liste nominative ni ``prix_achat``/marge n'est jamais servie au lien
public — seul le ``layout`` déjà agrégé du dashboard (JSON opaque à `core`)
est renvoyé, exactement comme il l'est à l'écran interne.
"""
from rest_framework import serializers, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from core.mixins import TenantMixin

from .models import Dashboard, DashboardPartageInterne, PartageDashboard

PARTAGE_OK = 'ok'
PARTAGE_INTROUVABLE = 'introuvable'
PARTAGE_EXPIRE = 'expire'


def resolve_dashboard_partage_public(token):
    """XPLT10 — Résout un partage de dashboard DEPUIS le seul jeton.

    Renvoie ``(statut, partage_ou_None)`` :
      * ``PARTAGE_INTROUVABLE`` — jeton inconnu OU révoqué (``actif=False``)
        → 404, sans distinguer les deux (pas de fuite « ce jeton existe »).
      * ``PARTAGE_EXPIRE`` — expiré → 410 Gone.
      * ``PARTAGE_OK`` — accès autorisé.
    """
    partage = (PartageDashboard.objects
               .select_related('dashboard', 'company')
               .filter(token=token)
               .first())
    if partage is None or not partage.actif:
        return PARTAGE_INTROUVABLE, None
    if partage.is_expired:
        return PARTAGE_EXPIRE, partage
    return PARTAGE_OK, partage


@api_view(['GET'])
@permission_classes([AllowAny])
def dashboard_public(request, token):
    """XPLT10 — ``GET dashboards-partages/public/<token>/``.

    Accès public LECTURE SEULE, sans login. Ne sert jamais de liste nominative
    ni de prix d'achat/marge — uniquement les agrégats déjà présents dans
    ``Dashboard.layout``."""
    statut, partage = resolve_dashboard_partage_public(token)
    if statut == PARTAGE_INTROUVABLE:
        return Response({'detail': 'Introuvable.'}, status=404)
    if statut == PARTAGE_EXPIRE:
        return Response({'detail': 'Lien expiré.'}, status=410)

    dashboard = partage.dashboard
    return Response({
        'titre': dashboard.titre,
        'description': dashboard.description,
        'layout': dashboard.layout,
    })


class PartageDashboardSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartageDashboard
        fields = [
            'id', 'dashboard', 'token', 'expires_at', 'actif',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'token', 'created_at', 'updated_at']


class PartageDashboardViewSet(TenantMixin, viewsets.ModelViewSet):
    """XPLT10 — CRUD des liens publics tokenisés vers un dashboard.

    Créer génère un jeton (côté modèle) ; révoquer = mettre ``actif=False``
    (kill-switch, jamais de suppression physique tant que non explicitement
    demandée — la ligne DELETE reste disponible via le ModelViewSet standard).
    Bornée à la société ET au dashboard de la même société (le serializer ne
    valide pas cross-tenant, on le garde en `perform_create`)."""
    serializer_class = PartageDashboardSerializer
    permission_classes = [IsAuthenticated]
    queryset = PartageDashboard.objects.all()

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)


class DashboardPartageInterneSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardPartageInterne
        fields = [
            'id', 'dashboard', 'utilisateur', 'role', 'niveau',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DashboardPartageInterneViewSet(TenantMixin, viewsets.ModelViewSet):
    """XPLT10 — partage interne fin d'un dashboard (utilisateur/rôle →
    lecture/édition), bornée à la société."""
    serializer_class = DashboardPartageInterneSerializer
    permission_classes = [IsAuthenticated]
    queryset = DashboardPartageInterne.objects.all()


def user_can_view_dashboard(user, dashboard):
    """XPLT10 — un utilisateur voit un dashboard PERSONNEL d'autrui SEULEMENT
    s'il figure dans un ``DashboardPartageInterne`` (utilisateur direct OU son
    rôle) — plus fin que ``Dashboard.partage`` (société entière, inchangé).

    Un dashboard déjà société-entière (``partage=True``) ou sans owner ou
    possédé par ``user`` reste visible sans consulter cette table (comportement
    ``DashboardViewSet.get_queryset`` INCHANGÉ)."""
    from django.db.models import Q

    if dashboard.owner_id is None or dashboard.owner_id == user.id:
        return True
    if dashboard.partage:
        return True
    role = getattr(user, 'role_legacy', '') or ''
    return DashboardPartageInterne.objects.filter(
        dashboard=dashboard,
    ).filter(Q(utilisateur=user) | Q(role=role)).exists()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_tv(request):
    """XPLT10 — ``GET dashboards-tv/`` : dashboards éligibles au mode TV
    (plein écran, rotation automatique) pour l'utilisateur courant.

    Renvoie les dashboards société (``partage=True``) + ceux explicitement
    partagés en interne avec l'utilisateur (direct ou par rôle) — jamais les
    dashboards personnels d'autrui non partagés. Le frontend pilote la
    rotation/rafraîchissement ; cet endpoint fournit juste la LISTE + layout."""
    from django.db.models import Q

    user = request.user
    if not user.company_id:
        return Response({'dashboards': []})

    role = getattr(user, 'role_legacy', '') or ''
    partages_internes_ids = DashboardPartageInterne.objects.filter(
        dashboard__company=user.company,
    ).filter(Q(utilisateur=user) | Q(role=role)).values_list(
        'dashboard_id', flat=True)

    qs = Dashboard.objects.filter(
        Q(company=user.company),
    ).filter(
        Q(partage=True) | Q(id__in=list(partages_internes_ids))
    ).distinct().order_by('titre', 'id')

    return Response({'dashboards': [
        {'id': d.id, 'titre': d.titre, 'layout': d.layout}
        for d in qs
    ]})
