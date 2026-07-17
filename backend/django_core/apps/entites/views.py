from rest_framework.decorators import action
from rest_framework.response import Response

from core.viewsets import CompanyScopedModelViewSet

from . import selectors, services
from .models import Entite
from .permissions import IsAdministrateur
from .serializers import EntiteSerializer


class EntiteViewSet(CompanyScopedModelViewSet):
    """NTADM1 — CRUD `Entite` (Administrateur only) + arbre (`?tree=1`) +
    chatter générique (NTADM47) via `records`."""

    serializer_class = EntiteSerializer
    permission_classes = [IsAdministrateur]
    queryset = Entite.objects.all()

    def get_queryset(self):
        return Entite.objects.filter(
            company=self.request.user.company).select_related('parent')

    def list(self, request, *args, **kwargs):
        if request.query_params.get('tree') == '1':
            return Response(selectors.entite_tree(request.user.company))
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        entite = services.creer_entite(
            self.request.user.company,
            nom=serializer.validated_data['nom'],
            code=serializer.validated_data['code'],
            parent=serializer.validated_data.get('parent'),
            user=self.request.user)
        serializer.instance = entite

    def perform_update(self, serializer):
        entite = serializer.instance
        ancien_nom = entite.nom
        ancien_parent = entite.parent

        nouveau_parent = serializer.validated_data.get('parent', ancien_parent)
        if nouveau_parent != ancien_parent:
            services.valider_non_cycle(entite, nouveau_parent)

        instance = serializer.save()

        from apps.records.services import log_field_change
        if instance.nom != ancien_nom:
            log_field_change(
                instance, 'nom', ancien_nom, instance.nom,
                user=self.request.user, field_label='Nom')
        if instance.parent_id != (ancien_parent.id if ancien_parent else None):
            log_field_change(
                instance, 'parent',
                ancien_parent.nom if ancien_parent else '',
                instance.parent.nom if instance.parent else '',
                user=self.request.user, field_label='Entité parente')

    def perform_destroy(self, instance):
        # NTADM1/11 — jamais de suppression dure : DELETE == désactivation.
        services.desactiver_entite(instance, user=self.request.user)

    @action(detail=True, methods=['post'])
    def desactiver(self, request, pk=None):
        entite = self.get_object()
        services.desactiver_entite(entite, user=request.user)
        return Response(EntiteSerializer(entite).data)

    @action(detail=True, methods=['get'])
    def historique(self, request, pk=None):
        """NTADM47 — fil d'activité (chatter générique `records`)."""
        entite = self.get_object()
        from apps.records.services import chatter_qs
        activites = chatter_qs(entite, company=request.user.company)
        data = [{
            'id': a.id,
            'kind': a.kind,
            'field_label': a.field_label,
            'old_value': a.old_value,
            'new_value': a.new_value,
            'body': a.body,
            'created_by': getattr(a.created_by, 'username', None),
            'created_at': a.created_at,
        } for a in activites]
        return Response(data)

    @action(detail=True, methods=['post'])
    def noter(self, request, pk=None):
        """NTADM47 — note manuelle de chatter."""
        entite = self.get_object()
        body = request.data.get('body', '')
        from apps.records.services import log_note
        log_note(entite, request.user, body)
        return Response({'ok': True})
