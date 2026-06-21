"""API du moteur d'automatisations (N72 / N73).

- ``AutomationRuleViewSet`` : CRUD des règles + enable/disable (palier admin).
- ``AutomationRunViewSet`` : journal lecture seule des exécutions.
- ``AutomationApprovalViewSet`` : liste des approbations + approve/reject
  (palier propriétaire admin/responsable) ; approuver relance l'action différée.

Tout est scopé à la société (TenantMixin) ; la société et l'acteur sont posés
côté serveur, jamais lus du corps de requête.
"""
from django.utils import timezone

from rest_framework import filters, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import (
    IsAdminOrResponsableTier, IsAdminRole, IsAnyRole,
)

from . import engine
from .models import AutomationApproval, AutomationRule, AutomationRun
from .serializers import (
    AutomationApprovalSerializer, AutomationRuleSerializer,
    AutomationRunSerializer,
)

READ_ACTIONS = ['list', 'retrieve']


class AutomationRuleViewSet(TenantMixin, viewsets.ModelViewSet):
    """Règles d'automatisation (N72). Lecture tout rôle ; écriture admin.
    Tout est opt-in : sans règle activée, aucun comportement ne change."""
    queryset = AutomationRule.objects.all()
    serializer_class = AutomationRuleSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['ordre', 'nom', 'date_creation']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        trigger = params.get('trigger_type')
        if trigger:
            qs = qs.filter(trigger_type=trigger)
        enabled = params.get('enabled')
        if enabled in ('0', '1', 'true', 'false'):
            qs = qs.filter(enabled=enabled in ('1', 'true'))
        return qs

    @action(detail=True, methods=['post'], permission_classes=[IsAdminRole])
    def toggle(self, request, pk=None):
        """Bascule l'état activé/désactivé de la règle."""
        rule = self.get_object()
        rule.enabled = not rule.enabled
        rule.save(update_fields=['enabled', 'date_modification'])
        return Response(self.get_serializer(rule).data)


class AutomationRunViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """Journal des exécutions (N72). Lecture seule, tout rôle, scopé société."""
    queryset = AutomationRun.objects.select_related('rule').all()
    serializer_class = AutomationRunSerializer
    permission_classes = [IsAnyRole]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['timestamp', 'status']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        rule = params.get('rule')
        if rule:
            qs = qs.filter(rule_id=rule)
        status = params.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs


class AutomationApprovalViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """Approbations (N73). Liste lecture seule (tout rôle) ; approve/reject
    réservés au palier propriétaire (admin/responsable). Approuver relance
    l'action différée."""
    queryset = AutomationApproval.objects.select_related('rule').all()
    serializer_class = AutomationApprovalSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'status']

    def get_permissions(self):
        if self.action in ('approve', 'reject'):
            return [IsAdminOrResponsableTier()]
        return [IsAnyRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        status = self.request.query_params.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approuve une approbation en attente et relance l'action différée."""
        approval = self.get_object()
        if approval.status != AutomationApproval.Status.PENDING:
            return Response(
                {'detail': 'Décision déjà prise.'}, status=400)
        approval.status = AutomationApproval.Status.APPROVED
        approval.decided_by = request.user
        approval.decided_at = timezone.now()
        approval.save(update_fields=['status', 'decided_by', 'decided_at'])
        engine.run_approved(approval, user=request.user)
        return Response(self.get_serializer(approval).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Rejette une approbation en attente : l'action n'est jamais lancée."""
        approval = self.get_object()
        if approval.status != AutomationApproval.Status.PENDING:
            return Response(
                {'detail': 'Décision déjà prise.'}, status=400)
        approval.status = AutomationApproval.Status.REJECTED
        approval.decided_by = request.user
        approval.decided_at = timezone.now()
        approval.save(update_fields=['status', 'decided_by', 'decided_at'])
        return Response(self.get_serializer(approval).data)


# ─────────────────────────────────────────────────────────────────────────────
# FG3 — Bibliothèque de modèles d'automatisation (presets sans-code).
# GET uniquement ; lecture tout rôle ; pas de modification.

@api_view(['GET'])
@permission_classes([IsAnyRole])
def automation_templates(request):
    """Liste les modèles d'automatisation prédéfinis (presets pour le UI).

    Retourne une liste statique de presets. Le frontend peut s'en servir pour
    préremplir le formulaire de création de règle (« Créer depuis un modèle »).
    Aucune règle n'est créée ici : c'est une aide à la saisie, pas une action
    automatique. Lecture seule, tout rôle authentifié."""
    from .templates import AUTOMATION_TEMPLATES
    return Response(AUTOMATION_TEMPLATES)
