"""Vues de la gouvernance des accès (NTSEC19).

Campagnes de revue d'accès : CRUD Directeur-only + génération d'items au
lancement + attestation manager. Tout est scopé société côté serveur.
"""
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from authentication.permissions import IsAdminRole
from core.viewsets import CompanyScopedModelViewSet

from .models import AccessReviewCampaign, AccessReviewItem
from .serializers import (
    AccessReviewCampaignSerializer, AccessReviewItemSerializer,
)
from .services import attester as _attester, generate_items


class AccessReviewCampaignViewSet(CompanyScopedModelViewSet):
    """CRUD des campagnes de revue d'accès (Directeur only)."""

    queryset = AccessReviewCampaign.objects.all().prefetch_related('items')
    serializer_class = AccessReviewCampaignSerializer
    permission_classes = [IsAdminRole]

    def perform_create(self, serializer):
        campaign = serializer.save(company=self.request.user.company)
        # Au lancement, générer un item par compte du périmètre.
        generate_items(campaign)

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
