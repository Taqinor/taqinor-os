"""N79 — API CRUD des rapports sauvegardés (SavedReport).

Multi-tenant strict via `TenantMixin` : le queryset est borné à la société de
l'utilisateur, `company` est FORCÉE côté serveur (jamais lue du corps), `owner`
est posé sur l'utilisateur courant. Aucun prix d'achat / marge n'apparaît ici
(rien que des métadonnées de rapport).
"""
from rest_framework import serializers, viewsets

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from .models import SavedReport


class SavedReportSerializer(serializers.ModelSerializer):
    target_kind_label = serializers.CharField(
        source='get_target_kind_display', read_only=True)
    schedule_label = serializers.CharField(
        source='get_schedule_display', read_only=True)

    class Meta:
        model = SavedReport
        # company + owner posés côté serveur — jamais lus du corps.
        fields = [
            'id', 'name', 'definition', 'target_kind', 'target_kind_label',
            'schedule', 'schedule_label', 'recipients', 'pinned',
            'last_sent_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'target_kind_label', 'schedule_label', 'last_sent_at',
            'created_at', 'updated_at',
        ]


class SavedReportViewSet(TenantMixin, viewsets.ModelViewSet):
    """CRUD des rapports sauvegardés, bornés à la société de l'utilisateur.

    Gestion réservée aux responsables/admins (mêmes rapports qu'ils consultent).
    `company` est forcée par `TenantMixin.perform_create/update` ; `owner` est
    fixé sur l'utilisateur courant à la création."""
    serializer_class = SavedReportSerializer
    permission_classes = [IsResponsableOrAdmin]
    queryset = SavedReport.objects.all()

    def perform_create(self, serializer):
        # company forcée par TenantMixin ; owner = utilisateur courant.
        serializer.save(company=self.request.user.company,
                        owner=self.request.user)
