"""FG25 — vues des politiques d'approbation (Paramètres → Approbations).

Surface déclarative : un Administrateur/Responsable promu déclare, par société,
quelles actions à fort impact exigent une approbation (type + seuil + palier
approbateur). Lecture tout rôle. ``company`` filtrée/forcée côté serveur
(TenantMixin). Chaque écriture est tracée au Journal d'audit (section
'approbations').
"""
from rest_framework import viewsets

from authentication.mixins import TenantMixin
from authentication.permissions import IsAdminOrResponsableTier, IsAnyRole

from .models import SettingsAuditLog
from .models_approvals import ApprovalPolicy
from .serializers_approvals import ApprovalPolicySerializer

READ_ACTIONS = ['list', 'retrieve']


class ApprovalPolicyViewSet(TenantMixin, viewsets.ModelViewSet):
    """Politiques d'approbation configurables (FG25).

    Lecture tout rôle ; écriture Administrateur/Responsable promu. Tout est
    opt-in : sans politique activée, aucun comportement d'approbation ne change.
    """
    queryset = ApprovalPolicy.objects.all()
    serializer_class = ApprovalPolicySerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminOrResponsableTier()]

    def get_queryset(self):
        qs = super().get_queryset()
        action_type = self.request.query_params.get('action_type')
        if action_type:
            qs = qs.filter(action_type=action_type)
        return qs

    def _audit(self, field, label, old, new):
        company = self.request.user.company if (
            self.request.user.company_id) else None
        SettingsAuditLog.log_change(
            company=company, user=self.request.user, section='approbations',
            field=field, field_label=label, old=old, new=new)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        inst = serializer.instance
        self._audit(
            field=f'policy:{inst.action_type}', label='Politique créée',
            old=None,
            new=f'{inst.get_action_type_display()} '
                f'(seuil {inst.seuil}, {inst.get_approver_tier_display()})')

    def perform_update(self, serializer):
        before = serializer.instance
        old_repr = (f'{before.get_action_type_display()} '
                    f'(seuil {before.seuil}, '
                    f'{"activée" if before.enabled else "désactivée"})')
        super().perform_update(serializer)
        inst = serializer.instance
        self._audit(
            field=f'policy:{inst.action_type}', label='Politique modifiée',
            old=old_repr,
            new=f'{inst.get_action_type_display()} '
                f'(seuil {inst.seuil}, '
                f'{"activée" if inst.enabled else "désactivée"})')

    def perform_destroy(self, instance):
        label = instance.get_action_type_display()
        atype = instance.action_type
        super().perform_destroy(instance)
        self._audit(
            field=f'policy:{atype}', label='Politique supprimée',
            old=label, new=None)
