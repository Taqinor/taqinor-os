"""API du moteur d'automatisations (N72 / N73).

- ``AutomationRuleViewSet`` : CRUD des règles + enable/disable (palier admin).
- ``AutomationRunViewSet`` : journal lecture seule des exécutions.
- ``AutomationApprovalViewSet`` : liste des approbations + approve/reject
  (palier propriétaire admin/responsable) ; approuver relance l'action différée.

Tout est scopé à la société (TenantMixin) ; la société et l'acteur sont posés
côté serveur, jamais lus du corps de requête.
"""
from django.utils import timezone

from rest_framework import filters, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import (
    IsAdminOrResponsableTier, IsAdminRole, IsAnyRole,
)

from . import engine, services
from .models import (
    ApprovalDelegation, ApprovalRequest, ApprovalRequestType,
    AutomationApproval, AutomationRule, AutomationRun,
    IncomingWebhookTrigger,
)
from .serializers import (
    ApprovalDelegationSerializer, ApprovalRequestSerializer,
    ApprovalRequestTypeSerializer, AutomationApprovalSerializer,
    AutomationRuleSerializer, AutomationRunSerializer,
    IncomingWebhookTriggerSerializer,
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

    def _audit_rule(self, field, label, old, new):
        """FG18 — journalise une écriture de règle d'automatisation au Journal
        d'audit des Paramètres (section='automatisations'). Best-effort : ne
        casse jamais l'écriture de la règle. Acteur + société côté serveur."""
        try:
            from apps.parametres.models import SettingsAuditLog
            actor = self.request.user
            SettingsAuditLog.log_change(
                company=getattr(actor, 'company', None), user=actor,
                section='automatisations', field=field, field_label=label,
                old=old, new=new,
            )
        except Exception:
            pass

    def perform_create(self, serializer):
        # TenantMixin force la société côté serveur (jamais depuis la requête).
        super().perform_create(serializer)
        instance = serializer.instance
        self._audit_rule(
            field=f'rule:{instance.nom}', label='Règle créée', old=None,
            new=f'{instance.nom} '
                f'({"activée" if instance.enabled else "désactivée"})')

    def perform_update(self, serializer):
        old_enabled = serializer.instance.enabled
        old_nom = serializer.instance.nom
        super().perform_update(serializer)
        instance = serializer.instance
        if instance.enabled != old_enabled or instance.nom != old_nom:
            self._audit_rule(
                field=f'rule:{instance.nom}', label='Règle modifiée',
                old=f'{old_nom} '
                    f'({"activée" if old_enabled else "désactivée"})',
                new=f'{instance.nom} '
                    f'({"activée" if instance.enabled else "désactivée"})')

    def perform_destroy(self, instance):
        nom = instance.nom
        super().perform_destroy(instance)
        self._audit_rule(
            field=f'rule:{nom}', label='Règle supprimée', old=nom, new=None)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminRole])
    def toggle(self, request, pk=None):
        """Bascule l'état activé/désactivé de la règle."""
        rule = self.get_object()
        old = rule.enabled
        rule.enabled = not rule.enabled
        rule.save(update_fields=['enabled', 'date_modification'])
        self._audit_rule(
            field=f'rule:{rule.nom}', label='Règle (bascule)',
            old='activée' if old else 'désactivée',
            new='activée' if rule.enabled else 'désactivée')
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
        # YEVNT11 — SOD : le demandeur ne peut pas approuver sa propre
        # demande (override admin audité).
        try:
            engine.enforce_requester_not_approver(
                requester=approval.requested_by, approver=request.user,
                company=approval.company, label=f'approval#{approval.pk}')
        except engine.SodViolation as exc:
            return Response({'detail': str(exc)}, status=403)
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
# XKB2 — Types de demandes d'approbation ad-hoc + soumission/décision.

class ApprovalRequestTypeViewSet(TenantMixin, viewsets.ModelViewSet):
    """CRUD des types de demande (admin) ; lecture tout rôle (pour le picker
    de soumission)."""
    queryset = ApprovalRequestType.objects.all()
    serializer_class = ApprovalRequestTypeSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['nom', 'date_creation']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        enabled = self.request.query_params.get('enabled')
        if enabled in ('0', '1', 'true', 'false'):
            qs = qs.filter(enabled=enabled in ('1', 'true'))
        return qs


class ApprovalRequestViewSet(TenantMixin, viewsets.ModelViewSet):
    """Demandes d'approbation ad-hoc (XKB2) : soumission par tout employé,
    décision réservée au palier propriétaire (admin/responsable), et
    alimente la même boîte que ``AutomationApprovalViewSet`` (XKB1).

    Un employé ne voit que ses propres demandes ; un approbateur (admin ou
    responsable) voit tout ce qui est scopé à sa société."""
    queryset = ApprovalRequest.objects.select_related(
        'request_type', 'demandeur', 'decided_by').all()
    serializer_class = ApprovalRequestSerializer
    parser_classes = [JSONParser, MultiPartParser]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'status']

    def get_permissions(self):
        if self.action in ('approve', 'reject'):
            return [IsAdminOrResponsableTier()]
        return [IsAnyRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        req_status = params.get('status')
        if req_status:
            qs = qs.filter(status=req_status)
        mine_only = params.get('mine')
        if mine_only in ('1', 'true'):
            qs = qs.filter(demandeur=self.request.user)
        elif getattr(
                self.request.user, 'menu_tier', None) not in (
                    'admin', 'responsable'):
            # Palier limité : ne voit QUE ses propres demandes soumises, PLUS
            # celles de tout délégant pour qui il est suppléant actif (XKB3).
            qs = qs.filter(
                demandeur_id__in=services.visible_demandeur_ids_for(
                    self.request.user))
        return qs

    def create(self, request, *args, **kwargs):
        company = request.user.company
        type_id = request.data.get('request_type')
        try:
            req_type = ApprovalRequestType.objects.get(
                pk=type_id, company=company, enabled=True)
        except (ApprovalRequestType.DoesNotExist, ValueError, TypeError):
            return Response(
                {'detail': 'Type de demande introuvable.'},
                status=status.HTTP_400_BAD_REQUEST)

        payload = request.data.get('payload') or {}
        if hasattr(payload, 'dict'):  # QueryDict (multipart) -> dict
            payload = payload.dict()
        file = request.FILES.get('file')
        try:
            req = services.submit_request(
                request_type=req_type, demandeur=request.user,
                company=company, payload=payload,
                has_attachment=bool(file))
        except services.ApprovalError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if file:
            try:
                services.attach_file(
                    req, file, user=request.user, company=company)
            except services.ApprovalError as exc:
                return Response(
                    {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            self.get_serializer(req).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        req = self.get_object()
        try:
            services.decide_request(
                req, decider=request.user, approve=True,
                note=request.data.get('note', '') or '')
        except engine.SodViolation as exc:
            return Response({'detail': str(exc)}, status=403)
        except services.ApprovalError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(self.get_serializer(req).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        req = self.get_object()
        try:
            services.decide_request(
                req, decider=request.user, approve=False,
                note=request.data.get('note', '') or '')
        except engine.SodViolation as exc:
            return Response({'detail': str(exc)}, status=403)
        except services.ApprovalError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(self.get_serializer(req).data)


class ApprovalDelegationViewSet(TenantMixin, viewsets.ModelViewSet):
    """Délégations d'approbation (XKB3). Un employé gère ses propres
    délégations (délégant = lui-même) ; un admin/responsable peut en créer
    pour un tiers."""
    queryset = ApprovalDelegation.objects.select_related(
        'delegant', 'suppleant').all()
    serializer_class = ApprovalDelegationSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_debut', 'date_fin']

    def get_permissions(self):
        return [IsAnyRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if getattr(user, 'menu_tier', None) not in ('admin', 'responsable'):
            # Palier limité : ne gère que SES délégations (émises ou reçues).
            from django.db.models import Q
            qs = qs.filter(Q(delegant=user) | Q(suppleant=user))
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        # Un palier limité ne peut déléguer que POUR LUI-MÊME (jamais au nom
        # d'un tiers) ; l'admin/responsable peut poser `delegant` librement.
        if getattr(user, 'menu_tier', None) not in ('admin', 'responsable'):
            serializer.save(company=user.company, delegant=user)
        else:
            serializer.save(company=user.company)


# ─────────────────────────────────────────────────────────────────────────────
# XPLT4 — Webhook entrant générique par règle (gestion admin : créer,
# rotation, activer/désactiver). Le POST externe lui-même est traité par
# ``public_views.incoming_webhook`` (aucune session).

class IncomingWebhookTriggerViewSet(TenantMixin, viewsets.ModelViewSet):
    """Gestion (admin) des webhooks entrants tokenisés (XPLT4)."""
    queryset = IncomingWebhookTrigger.objects.select_related('rule').all()
    serializer_class = IncomingWebhookTriggerSerializer
    permission_classes = [IsAdminRole]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation']

    def create(self, request, *args, **kwargs):
        company = request.user.company
        rule_id = request.data.get('rule')
        rule = AutomationRule.objects.filter(
            pk=rule_id, company=company).first()
        if rule is None:
            return Response(
                {'detail': 'Règle introuvable.'}, status=400)
        trigger, _ = IncomingWebhookTrigger.objects.get_or_create(
            rule=rule, defaults={
                'company': company,
                'hmac_secret': request.data.get('hmac_secret', '') or '',
            })
        return Response(
            self.get_serializer(trigger).data, status=201)

    @action(detail=True, methods=['post'])
    def rotate(self, request, pk=None):
        """Régénère le token : l'ancien devient immédiatement invalide."""
        trigger = self.get_object()
        trigger.rotate_token()
        return Response(self.get_serializer(trigger).data)


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
