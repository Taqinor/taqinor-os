"""Vues du module Innovation (boîte à idées interne).

Palier d'accès : lecture/proposition/vote — tout utilisateur connecté de la
société (``IsAnyRole``) — « logged-in users only » (NTIDE4/NTIDE8).
"""
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsAnyRole
from core.viewsets import CompanyScopedModelViewSet

from . import services
from .models import VoteIdee
from .serializers import VoteIdeeSerializer


class VoteIdeeViewSet(CompanyScopedModelViewSet):
    """Votes sur idées (NTIDE2). Lecture : tout utilisateur connecté.
    Création : tout utilisateur connecté (sauf l'auteur de l'idée, cf.
    ``services.voter``). Suppression : le votant lui-même ou l'admin
    (« créateur/admin », NTIDE2)."""

    queryset = VoteIdee.objects.select_related('votant', 'idee').all()
    serializer_class = VoteIdeeSerializer
    http_method_names = ['get', 'post', 'delete', 'head', 'options']
    permission_classes = [IsAnyRole]

    def perform_create(self, serializer):
        idee = serializer.validated_data['idee']
        if idee.company_id != self.request.user.company_id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Idée hors de votre société.')
        try:
            vote = services.voter(idee, self.request.user)
        except services.VoteInterdit as exc:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'idee': str(exc)}) from exc
        serializer.instance = vote

    def perform_destroy(self, instance):
        user = self.request.user
        if instance.votant_id != user.id and not (
                user.is_superuser or user.is_admin_role):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(
                'Seul l\'auteur du vote ou un administrateur peut le retirer.')
        services.retirer_vote(instance)

    # ── Sélecteurs exposés (NTIDE2) ──────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='recents')
    def recents(self, request):
        """Votes récents de la société (``votes_recents``)."""
        qs = self.get_queryset().order_by('-created_at')[:20]
        return Response(VoteIdeeSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='mes-idees')
    def mes_idees(self, request):
        """Votes reçus sur les idées PROPOSÉES par l'appelant
        (``votes_my_ideas``)."""
        qs = self.get_queryset().filter(idee__auteur=request.user)
        return Response(VoteIdeeSerializer(qs, many=True).data)
