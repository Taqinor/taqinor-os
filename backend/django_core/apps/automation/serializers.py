from rest_framework import serializers

from .actions import (
    SET_FIELD_TARGETS, set_field_autorise, set_field_champs_autorises,
)
from .models import (
    ActionType, ApprovalDelegation, ApprovalRequest, ApprovalRequestType,
    AutomationApproval, AutomationRule, AutomationRun,
    IncomingWebhookTrigger, TriggerType, record_state_change_targets,
)


class AutomationRuleSerializer(serializers.ModelSerializer):
    trigger_type_display = serializers.CharField(
        source='get_trigger_type_display', read_only=True)
    action_type_display = serializers.CharField(
        source='get_action_type_display', read_only=True)

    class Meta:
        model = AutomationRule
        # `company` posée côté serveur (TenantMixin) — jamais lue du corps.
        fields = [
            'id', 'nom', 'enabled',
            'trigger_type', 'trigger_type_display', 'trigger_config',
            'action_type', 'action_type_display', 'action_config',
            'requires_approval', 'approval_threshold', 'ordre',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def validate(self, attrs):
        """ARC34 — une règle ``RECORD_STATE_CHANGE`` doit viser un couple
        (modèle, champ) AUTORISÉ par le registre plateforme (surface
        ``automation_state_fields`` des manifestes ``apps/<x>/platform.py`` —
        ``record_state_change_targets()``), et son arbre de ``conditions``
        optionnel doit être structurellement valide
        (``core.rules.validate_condition_group``, FG367). Les autres types de
        déclencheurs sont INCHANGÉS (aucune validation ajoutée).

        AUD821 — la validation ne portait QUE sur ``trigger_config`` : le
        ``action_config`` n'était JAMAIS validé, donc une action ``SET_FIELD``
        pouvait viser ``Devis.statut`` ou ``Facture.montant_ttc`` et écrire
        directement en base (hors machine à états, hors ``core.events``). Le
        champ visé est désormais confronté au registre FERMÉ
        ``actions.SET_FIELD_TARGETS`` — voir ``_valider_set_field``."""
        self._valider_set_field(attrs)
        trigger_type = attrs.get(
            'trigger_type', getattr(self.instance, 'trigger_type', None))
        if trigger_type != TriggerType.RECORD_STATE_CHANGE:
            return attrs
        config = attrs.get(
            'trigger_config',
            getattr(self.instance, 'trigger_config', None)) or {}
        model = (config.get('model') or '').strip().lower()
        field = (config.get('field') or '').strip()
        if not model or not field:
            raise serializers.ValidationError({
                'trigger_config': (
                    "Un déclencheur « changement d'état » exige un modèle et "
                    "un champ (trigger_config['model'] / "
                    "trigger_config['field'])."),
            })
        autorises = record_state_change_targets()
        if field not in autorises.get(model, set()):
            couples = ', '.join(
                f'{m}.{f}' for m in sorted(autorises)
                for f in sorted(autorises[m])) or 'aucun'
            raise serializers.ValidationError({
                'trigger_config': (
                    f'Couple (modèle, champ) non autorisé : '
                    f'« {model}.{field} ». Couples déclarés au registre '
                    f'plateforme : {couples}.'),
            })
        conditions = config.get('conditions')
        if conditions:
            from core.rules import validate_condition_group
            erreurs = validate_condition_group(conditions)
            if erreurs:
                raise serializers.ValidationError(
                    {'trigger_config': erreurs})
        return attrs

    def _valider_set_field(self, attrs):
        """AUD821 — une action ``SET_FIELD`` ne vise qu'un champ DÉCLARÉ.

        ``action_config`` ne porte pas toujours le modèle cible (il est impliqué
        par le déclencheur), donc la création refuse tout champ qui n'est sûr
        sur AUCUN modèle du registre ; l'exécution (``actions._set_field``)
        refait le contrôle STRICT sur le couple réel. Un ``action_config`` qui
        précise ``model`` est validé sur le COUPLE tout de suite.
        """
        action_type = attrs.get(
            'action_type', getattr(self.instance, 'action_type', None))
        if action_type != ActionType.SET_FIELD:
            return
        config = attrs.get(
            'action_config',
            getattr(self.instance, 'action_config', None)) or {}
        field = (config.get('field') or '').strip()
        if not field:
            raise serializers.ValidationError({
                'action_config': (
                    "Une action « Mettre à jour un champ » exige "
                    "action_config['field']."),
            })
        modele = (config.get('model') or '').strip().lower()
        if modele:
            autorise = set_field_autorise(modele, field)
        else:
            autorise = field in set_field_champs_autorises()
        if not autorise:
            couples = ', '.join(
                f'{m}.{f}' for m in sorted(SET_FIELD_TARGETS)
                for f in sorted(SET_FIELD_TARGETS[m])) or 'aucun'
            cible = f'{modele}.{field}' if modele else field
            raise serializers.ValidationError({
                'action_config': (
                    f'Champ non assignable par une automatisation : '
                    f'« {cible} ». Une automatisation n\'écrit jamais un champ '
                    f'de machine à états ni un champ financier — elle doit '
                    f'passer par le service métier. Champs déclarés : '
                    f'{couples}.'),
            })


class AutomationRunSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)
    rule_nom = serializers.CharField(
        source='rule.nom', read_only=True, default=None)

    class Meta:
        model = AutomationRun
        fields = [
            'id', 'rule', 'rule_nom', 'target_model', 'target_id',
            'status', 'status_display', 'message', 'timestamp',
        ]
        read_only_fields = fields


class AutomationApprovalSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)
    rule_nom = serializers.CharField(
        source='rule.nom', read_only=True, default=None)
    requested_by_nom = serializers.CharField(
        source='requested_by.username', read_only=True, default=None)
    decided_by_nom = serializers.CharField(
        source='decided_by.username', read_only=True, default=None)

    class Meta:
        model = AutomationApproval
        fields = [
            'id', 'rule', 'rule_nom', 'target_model', 'target_id',
            'description', 'context', 'status', 'status_display',
            'requested_by', 'requested_by_nom',
            'decided_by', 'decided_by_nom', 'decided_at', 'date_creation',
        ]
        read_only_fields = fields


class ApprovalRequestTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalRequestType
        # `company` posée côté serveur (TenantMixin) — jamais lue du corps.
        fields = [
            'id', 'nom', 'description', 'enabled',
            'champs_requis', 'champs_optionnels', 'palier_approbateur',
            # ZCTR7 — min approbations / PJ obligatoire / config par champ.
            'min_approbations', 'piece_jointe_obligatoire', 'champs_config',
            # ZCTR8 — ordre des approbateurs (séquentiel/parallèle).
            'sequence_approbateurs',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']


class ApprovalRequestSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)
    request_type_nom = serializers.CharField(
        source='request_type.nom', read_only=True, default=None)
    demandeur_nom = serializers.CharField(
        source='demandeur.username', read_only=True, default=None)
    decided_by_nom = serializers.CharField(
        source='decided_by.username', read_only=True, default=None)
    # XKB3 — présent uniquement quand la décision a été prise par un
    # suppléant « au nom de » ce délégant (délégation active à l'instant T).
    decided_on_behalf_of_nom = serializers.CharField(
        source='decided_on_behalf_of.username', read_only=True, default=None)
    # ZCTR7 — nombre de décisions favorables DISTINCTES déjà enregistrées,
    # et seuil requis (pour afficher « 1/2 approbations » côté frontend).
    approvals_count = serializers.SerializerMethodField()
    min_approbations = serializers.IntegerField(
        source='request_type.min_approbations', read_only=True, default=1)

    class Meta:
        model = ApprovalRequest
        fields = [
            'id', 'request_type', 'request_type_nom', 'demandeur',
            'demandeur_nom', 'payload', 'status', 'status_display',
            'decided_by', 'decided_by_nom', 'decided_at', 'decision_note',
            'decided_on_behalf_of', 'decided_on_behalf_of_nom',
            'approvals_count', 'min_approbations',
            'date_creation',
        ]
        # `company` + `demandeur` posés côté serveur ; le statut/décision ne
        # se change QUE via les actions dédiées (approve/reject), jamais par
        # un PATCH direct du champ.
        read_only_fields = [
            'id', 'request_type_nom', 'demandeur', 'demandeur_nom', 'status',
            'status_display', 'decided_by', 'decided_by_nom', 'decided_at',
            'decision_note', 'decided_on_behalf_of',
            'decided_on_behalf_of_nom', 'approvals_count', 'min_approbations',
            'date_creation',
        ]

    def get_approvals_count(self, obj):
        from .models import ApprovalDecision
        return obj.decisions.filter(
            decision=ApprovalDecision.Decision.APPROVE,
        ).values('decided_by_id').distinct().count()


class ApprovalDelegationSerializer(serializers.ModelSerializer):
    delegant_nom = serializers.CharField(
        source='delegant.username', read_only=True, default=None)
    suppleant_nom = serializers.CharField(
        source='suppleant.username', read_only=True, default=None)

    class Meta:
        model = ApprovalDelegation
        # `company` posée côté serveur ; `delegant` par défaut = l'appelant
        # (posé côté vue), mais un admin peut déléguer pour un tiers.
        fields = [
            'id', 'delegant', 'delegant_nom', 'suppleant', 'suppleant_nom',
            'date_debut', 'date_fin', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class IncomingWebhookTriggerSerializer(serializers.ModelSerializer):
    rule_nom = serializers.CharField(source='rule.nom', read_only=True)
    url_path = serializers.SerializerMethodField()

    class Meta:
        model = IncomingWebhookTrigger
        # `company` posée côté serveur ; `token` généré côté serveur (jamais
        # lu du corps) — seule la rotation explicite (action dédiée) change.
        fields = [
            'id', 'rule', 'rule_nom', 'token', 'url_path', 'hmac_secret',
            'enabled', 'date_creation', 'date_modification',
        ]
        read_only_fields = ['id', 'rule_nom', 'token', 'url_path',
                            'date_creation', 'date_modification']

    def get_url_path(self, obj):
        return f'/api/django/public/hooks/{obj.token}/'
