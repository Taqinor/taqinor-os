"""FG96 — API de configuration du tableau de bord par utilisateur / palier de rôle.

Endpoint principal : GET /reporting/dashboard-config/effective/
  Retourne la configuration effective pour l'utilisateur courant :
    1. Sa config per-user (si elle existe)
    2. La config du palier de rôle (menu_tier) de cet utilisateur
    3. Le défaut Python (ROLE_DEFAULT_CARDS / GLOBAL_DEFAULT_CARDS)
  Cela garantit qu'un utilisateur sans config voit EXACTEMENT ce qu'il voit
  aujourd'hui (aucune régression de comportement).

CRUD complet via le router DRF (SavedReportViewSet style) — company forcée serveur.
"""
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from core.champs_stricts import ChampsStrictsMixin, IdInconnu404Mixin
from core.mixins import TenantMixin

from core.mixins import SameCompanyFKSerializerMixin
from core.openapi_erreurs import EXTENSION_CORPS_RESSERRE
from core.parseurs import ListeJSON

from .models import (
    DashboardConfig,
    ROLE_DEFAULT_CARDS,
    GLOBAL_DEFAULT_CARDS,
    ALL_DASHBOARD_CARDS,
)
from drf_spectacular.utils import (
    extend_schema, extend_schema_view, inline_serializer,
)
from rest_framework import serializers as drf_serializers
from rest_framework.parsers import JSONParser


class DashboardConfigSerializer(IdInconnu404Mixin, ChampsStrictsMixin,
                                SameCompanyFKSerializerMixin,
                                serializers.ModelSerializer):
    """Configuration de tableau de bord : per-user XOR palier de rôle."""
    # AANA17 — une config ne peut viser qu'un utilisateur de LA société.
    same_company_fields = ('user',)
    # ERR-ENF11-FUZZ-REPORTING — liste de clés de cartes publiée comme telle
    # (``{}`` ou ``null`` étaient conformes au schéma ``{}`` puis refusés).
    cards = ListeJSON(element=str, required=False, items={
        'type': 'string', 'enum': list(ALL_DASHBOARD_CARDS)})

    class Meta:
        model = DashboardConfig
        fields = [
            'id', 'user', 'menu_tier', 'cards',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_cards(self, value):
        """Les clés doivent appartenir à ALL_DASHBOARD_CARDS."""
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "cards doit être une liste de clés de cartes.")
        unknown = [c for c in value if c not in ALL_DASHBOARD_CARDS]
        if unknown:
            raise serializers.ValidationError(
                f"Clés de cartes inconnues : {unknown}. "
                f"Clés valides : {ALL_DASHBOARD_CARDS}")
        return value

    def validate(self, attrs):
        user = attrs.get('user')
        menu_tier = attrs.get('menu_tier', '')
        if user and menu_tier:
            raise serializers.ValidationError(
                "Fournir user ET menu_tier ensemble est invalide : "
                "une config est soit per-user (user non-null, menu_tier vide) "
                "soit de palier (user null, menu_tier non-vide).")
        if not user and not menu_tier:
            raise serializers.ValidationError(
                "Fournir au moins user ou menu_tier.")
        return attrs


#: CI #997 fuzz — la règle de ``validate`` (une config est PER-USER : ``user``
#: posé et ``menu_tier`` vide, OU de PALIER : ``menu_tier`` non vide et ``user``
#: nul/absent) est publiée à la création et au remplacement : un corps qui
#: porte les deux, ou aucun, n'est plus « conforme au schéma ».
USER_XOR_PALIER = {EXTENSION_CORPS_RESSERRE: {'anyOf': [
    {'required': ['user'], 'properties': {
        'user': {'type': 'integer'},
        'menu_tier': {'type': 'string', 'maxLength': 0}}},
    {'required': ['menu_tier'], 'properties': {
        'user': {'enum': [None]},
        'menu_tier': {'type': 'string', 'minLength': 1, 'pattern': r'\S'}}},
]}}


@extend_schema_view(create=extend_schema(extensions=USER_XOR_PALIER),
                    update=extend_schema(extensions=USER_XOR_PALIER))
class DashboardConfigViewSet(TenantMixin, viewsets.ModelViewSet):
    """CRUD des configurations de tableau de bord, bornées à la société.

    Réservé aux administrateurs / responsables (même portée que les rapports
    sauvegardés). ``company`` est forcée côté serveur par TenantMixin.

    Action supplémentaire :
      GET /dashboard-config/effective/
        Retourne la configuration effective pour l'utilisateur courant.
    """
    serializer_class = DashboardConfigSerializer
    parser_classes = [JSONParser]
    permission_classes = [IsResponsableOrAdmin]
    queryset = DashboardConfig.objects.all()

    def perform_create(self, serializer):
        # company forcée côté serveur, jamais lue du corps de la requête.
        serializer.save(company=self.request.user.company)

    @extend_schema(responses=inline_serializer('DashboardConfigEffective', {
        'source': drf_serializers.CharField(),
        'config_id': drf_serializers.IntegerField(required=False),
        'menu_tier': drf_serializers.CharField(required=False),
        'cards': drf_serializers.JSONField(),
    }))
    @action(detail=False, methods=['get'], url_path='effective',
            permission_classes=[IsAuthenticated])
    def effective(self, request):
        """Retourne la config effective (per-user > palier > défaut Python).

        Aucune config stockée => retourne le jeu complet de cartes du palier
        (comportement identique à aujourd'hui — aucune régression).
        """
        user = request.user
        company = user.company

        if company is None:
            # Superuser sans société : retourne le défaut global.
            return Response({
                'source': 'global_default',
                'cards': GLOBAL_DEFAULT_CARDS,
            })

        # 1. Config per-user.
        per_user = DashboardConfig.objects.filter(
            company=company, user=user).first()
        if per_user is not None:
            return Response({
                'source': 'per_user',
                'config_id': per_user.pk,
                'cards': per_user.cards,
            })

        # 2. Config palier de rôle.
        tier = getattr(user, 'menu_tier', None) or ''
        role_cfg = DashboardConfig.objects.filter(
            company=company, user__isnull=True, menu_tier=tier).first()
        if role_cfg is not None:
            return Response({
                'source': 'role_default',
                'menu_tier': tier,
                'config_id': role_cfg.pk,
                'cards': role_cfg.cards,
            })

        # 3. Défaut Python (aucune config stockée => comportement inchangé).
        default_cards = ROLE_DEFAULT_CARDS.get(tier, GLOBAL_DEFAULT_CARDS)
        return Response({
            'source': 'python_default',
            'menu_tier': tier,
            'cards': default_cards,
        })
