"""Vues du module Innovation (boîte à idées interne).

Palier d'accès :
  * lecture/proposition/vote — tout utilisateur connecté de la société
    (``IsAnyRole``) — « logged-in users only » (NTIDE4/NTIDE8) ;
  * transitions de statut (examiner/retenir/réaliser/fermer) — palier
    Directeur/Responsable (``IsResponsableOrAdmin``, NTIDE5).
"""
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from . import services
from .models import Idee, VoteIdee
from .serializers import IdeeDetailSerializer, IdeeSerializer, VoteIdeeSerializer


class IdeeViewSet(CompanyScopedModelViewSet):
    """Boîte à idées interne : liste/détail/proposition + actions (NTIDE4/5).

    Aucun ``destroy`` : une idée se ferme (action ``fermer``), elle ne se
    supprime jamais (dossier de décision produit, comme les litiges/dossiers
    légaux ailleurs dans le dépôt)."""

    queryset = Idee.objects.select_related('auteur').all()
    serializer_class = IdeeSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    permission_classes = [IsAnyRole]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['votes_count', 'created_at', 'id']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return IdeeDetailSerializer
        return IdeeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        contexte = params.get('contexte')
        if contexte:
            qs = qs.filter(contexte__iexact=contexte)
        created_since = params.get('created_since')
        if created_since:
            qs = qs.filter(created_at__gte=created_since)
        owner = params.get('owner') or params.get('auteur')
        if owner:
            qs = qs.filter(auteur_id=owner)
        return qs

    def perform_create(self, serializer):
        idee = serializer.save(
            company=self.request.user.company, auteur=self.request.user)
        from apps.records.models import Activity
        from apps.records.services import log_activity
        log_activity(
            idee, Activity.Kind.CREATION, user=self.request.user,
            company=idee.company)

    # ── NTIDE5 — machine à états + chatter ──────────────────────────────────
    def _transition(self, request, target):
        idee = self.get_object()
        note = (request.data.get('note') or '').strip()
        try:
            services.transitionner(
                idee, target=target, user=request.user, note=note)
        except services.TransitionInvalide as exc:
            return Response({'statut': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(IdeeSerializer(idee).data)

    @action(detail=True, methods=['post'], url_path='examiner',
            permission_classes=[IsResponsableOrAdmin])
    def examiner(self, request, pk=None):
        """ouvert → examinée."""
        return self._transition(request, Idee.Statut.EXAMINEE)

    @action(detail=True, methods=['post'], url_path='retenir',
            permission_classes=[IsResponsableOrAdmin])
    def retenir(self, request, pk=None):
        """examinée → retenue."""
        return self._transition(request, Idee.Statut.RETENUE)

    @action(detail=True, methods=['post'], url_path='realiser',
            permission_classes=[IsResponsableOrAdmin])
    def realiser(self, request, pk=None):
        """retenue → réalisée."""
        return self._transition(request, Idee.Statut.REALISEE)

    @action(detail=True, methods=['post'], url_path='fermer',
            permission_classes=[IsResponsableOrAdmin])
    def fermer(self, request, pk=None):
        """ouvert|examinée|retenue → fermée. Note de fermeture optionnelle
        (``{"note": "..."}``), journalisée dans le chatter."""
        return self._transition(request, Idee.Statut.FERMEE)

    @action(detail=True, methods=['get'], url_path='historique')
    def historique(self, request, pk=None):
        """Timeline chatter (générique ``records.Activity``, ARC8)."""
        idee = self.get_object()
        from apps.records.serializers import ChatterActivitySerializer
        from apps.records.services import chatter_qs
        qs = chatter_qs(idee, company=idee.company)
        return Response(ChatterActivitySerializer(qs, many=True).data)


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
