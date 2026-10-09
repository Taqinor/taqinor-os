"""Vues de la gouvernance des accès (NTSEC19).

Campagnes de revue d'accès : CRUD Directeur-only + génération d'items au
lancement + attestation manager. Tout est scopé société côté serveur.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from authentication.permissions import IsAdminRole
from core.viewsets import CompanyScopedModelViewSet

from .models import AccessReviewCampaign, AccessReviewItem
from .serializers import (
    AccessReviewCampaignSerializer, AccessReviewItemSerializer,
    SodRuleSerializer,
)
from .schema_fields import champ_choix
from .services import attester as _attester, generate_items


class AttesterSerializer(serializers.Serializer):
    item = serializers.IntegerField()
    decision = champ_choix(c.value for c in AccessReviewItem.Decision)
    commentaire = serializers.CharField(required=False, allow_blank=True)


class AccessReviewCampaignViewSet(CompanyScopedModelViewSet):
    """CRUD des campagnes de revue d'accès (Directeur only)."""

    queryset = AccessReviewCampaign.objects.all().prefetch_related('items')
    serializer_class = AccessReviewCampaignSerializer
    permission_classes = [IsAdminRole]
    parser_classes = [JSONParser]

    def perform_create(self, serializer):
        campaign = serializer.save(company=self.request.user.company)
        # Au lancement, générer un item par compte du périmètre.
        generate_items(campaign)

    @extend_schema(request=AttesterSerializer,
                   responses=AccessReviewItemSerializer)
    @action(detail=True, methods=['post'])
    def attester(self, request, pk=None):
        """Attestation d'un item : ``{item, decision, commentaire}``.

        ``decision=revoque`` retire le rôle du compte concerné. L'item doit
        appartenir à la campagne ET à la société de l'appelant."""
        campaign = self.get_object()
        item_id = request.data.get('item')
        decision = request.data.get('decision')
        commentaire = request.data.get('commentaire', '')
        valid = {c.value for c in AccessReviewItem.Decision}
        if decision not in valid:
            raise DRFValidationError({'decision': 'Décision invalide.'})
        item = AccessReviewItem.objects.filter(
            pk=item_id, campagne=campaign,
            company=request.user.company).first()
        if item is None:
            raise DRFValidationError({'item': 'Item inconnu pour cette campagne.'})
        _attester(item, decision=decision, reviewer=request.user,
                  commentaire=commentaire)
        return Response(AccessReviewItemSerializer(item).data)


class SodRuleViewSet(CompanyScopedModelViewSet):
    """CRUD des règles SoD + rapport de violations (Directeur only)."""

    serializer_class = SodRuleSerializer
    permission_classes = [IsAdminRole]
    parser_classes = [JSONParser]

    def get_queryset(self):
        from .models import SodRule
        return SodRule.objects.filter(company=self.request.user.company)

    @extend_schema(responses=inline_serializer('SodViolationsListe', {
        'results': inline_serializer('SodViolation', {
            'user_id': serializers.IntegerField(),
            'username': serializers.CharField(),
            'permission_a': serializers.CharField(),
            'permission_b': serializers.CharField(),
            'severite': serializers.CharField(),
            'libelle': serializers.CharField(allow_blank=True),
        }, many=True),
    }))
    @action(detail=False, methods=['get'])
    def violations(self, request):
        """Rapport des cumuls SoD de la société (scopé société)."""
        from .sod import sod_violations
        return Response({'results': sod_violations(request.user.company)})

    @extend_schema(request=None, responses=inline_serializer(
        'SodSeedResultat', {'created': serializers.IntegerField()}))
    @action(detail=False, methods=['post'])
    def seed_standard(self, request):
        """Sème le jeu SoD standard finance/achats (idempotent)."""
        from .sod import seed_standard_sod_rules
        created = seed_standard_sod_rules(request.user.company)
        return Response({'created': created})
