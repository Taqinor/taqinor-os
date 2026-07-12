from rest_framework import serializers

from .models import (
    Annonce, AnnonceLecture, EventType, Holiday, Notification,
    NotificationPreference, NotificationRoutingRule, WhatsAppTemplate,
    WorkingHoursConfig,
)


class NotificationSerializer(serializers.ModelSerializer):
    event_label = serializers.CharField(
        source='get_event_type_display', read_only=True)
    # VX208 — taxonomie STATIQUE (`severity.py`, aucune migration) exposée en
    # lecture : sévérité (tri/liseré critique), catégorie (groupement
    # frontend) et `is_action` (compteur ACTIONS rouge vs INFOS point gris —
    # un `DIGEST` n'est JAMAIS une action).
    severity = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    is_action = serializers.SerializerMethodField()
    # VX212(a) — « pourquoi je reçois ça » : raison courte + libellé FR,
    # vide si non classée (comportement historique).
    reason_label = serializers.CharField(
        source='get_reason_display', read_only=True, default='')

    class Meta:
        model = Notification
        # company + recipient posés côté serveur — jamais lus du corps.
        fields = [
            'id', 'event_type', 'event_label', 'title', 'body', 'link',
            'read', 'read_at', 'created_at',
            'severity', 'category', 'is_action', 'reason', 'reason_label',
        ]
        read_only_fields = [
            'id', 'event_type', 'event_label', 'title', 'body', 'link',
            'read_at', 'created_at', 'severity', 'category', 'is_action',
            'reason', 'reason_label',
        ]

    def get_severity(self, obj):
        from . import severity as severity_module
        return severity_module.severity_of(obj.event_type)

    def get_category(self, obj):
        from . import severity as severity_module
        return severity_module.category_of(obj.event_type)

    def get_is_action(self, obj):
        from . import severity as severity_module
        return severity_module.is_action(obj.event_type)


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    event_label = serializers.CharField(
        source='get_event_type_display', read_only=True)

    class Meta:
        model = NotificationPreference
        # company + user posés côté serveur — jamais lus du corps.
        fields = ['id', 'event_type', 'event_label', 'in_app', 'whatsapp', 'email']
        read_only_fields = ['id', 'event_label']

    def validate_event_type(self, value):
        if value not in EventType.values:
            raise serializers.ValidationError("Type d'événement inconnu.")
        return value


class NotificationRoutingRuleSerializer(serializers.ModelSerializer):
    """FG4 — Serializer des règles de routage (admin seulement)."""
    event_label = serializers.CharField(
        source='get_event_type_display', read_only=True)
    target_role_label = serializers.CharField(
        source='get_target_role_display', read_only=True)

    class Meta:
        model = NotificationRoutingRule
        # company posée côté serveur (TenantMixin + perform_create).
        fields = [
            'id', 'event_type', 'event_label',
            'target_role', 'target_role_label', 'target_user',
            'enabled', 'created_at',
        ]
        read_only_fields = ['id', 'event_label', 'target_role_label', 'created_at']

    def validate(self, data):
        if not data.get('target_role') and not data.get('target_user'):
            raise serializers.ValidationError(
                'Une règle de routage doit cibler soit un rôle, soit un utilisateur.')
        return data


class WorkingHoursConfigSerializer(serializers.ModelSerializer):
    """FG5 — Sérializer de la configuration des jours ouvrés (singleton société)."""

    class Meta:
        model = WorkingHoursConfig
        # company posée côté serveur — jamais acceptée du corps.
        fields = ['id', 'working_days', 'hours_per_day', 'updated_at']
        read_only_fields = ['id', 'updated_at']


class HolidaySerializer(serializers.ModelSerializer):
    """FG5 — Sérializer des jours fériés."""

    class Meta:
        model = Holiday
        # company posée côté serveur — jamais acceptée du corps.
        fields = ['id', 'date', 'nom', 'recurrent_annuel', 'created_at']
        read_only_fields = ['id', 'created_at']


class WhatsAppTemplateSerializer(serializers.ModelSerializer):
    """XMKT25 — Registre des gabarits BSP + cycle d'approbation Meta."""
    statut_approbation_label = serializers.CharField(
        source='get_statut_approbation_display', read_only=True)
    categorie_label = serializers.CharField(
        source='get_categorie_display', read_only=True)

    class Meta:
        model = WhatsAppTemplate
        # company posée côté serveur — jamais acceptée du corps.
        fields = [
            'id', 'name', 'body_fr', 'language', 'active',
            'statut_approbation', 'statut_approbation_label', 'motif_rejet',
            'categorie', 'categorie_label', 'groupe',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'statut_approbation', 'statut_approbation_label',
            'motif_rejet', 'categorie_label', 'created_at', 'updated_at',
        ]


class AnnonceSerializer(serializers.ModelSerializer):
    """XKB5 — Annonces internes ciblées et programmées."""
    cible_type_label = serializers.CharField(
        source='get_cible_type_display', read_only=True)
    auteur_username = serializers.CharField(
        source='auteur.username', read_only=True, default='')
    is_expiree = serializers.SerializerMethodField()
    lus_count = serializers.SerializerMethodField()

    class Meta:
        model = Annonce
        # company + auteur posés côté serveur — jamais acceptés du corps.
        fields = [
            'id', 'titre', 'corps', 'auteur', 'auteur_username',
            'cible_type', 'cible_type_label', 'cible_role',
            'cible_departement_nom', 'date_publication', 'date_expiration',
            'publiee', 'date_publication_effective', 'epinglee',
            'lecture_obligatoire', 'is_expiree', 'lus_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'auteur', 'auteur_username', 'publiee',
            'date_publication_effective', 'is_expiree', 'lus_count',
            'created_at', 'updated_at',
        ]

    def get_is_expiree(self, obj):
        return obj.is_expiree()

    def get_lus_count(self, obj):
        return obj.lectures.count()


class AnnonceLectureSerializer(serializers.ModelSerializer):
    """XKB6 — Accusé de lecture obligatoire."""
    utilisateur_username = serializers.CharField(
        source='utilisateur.username', read_only=True)

    class Meta:
        model = AnnonceLecture
        fields = [
            'id', 'annonce', 'utilisateur', 'utilisateur_username',
            'date_lecture', 'relances_envoyees', 'derniere_relance_le',
        ]
        read_only_fields = [
            'id', 'utilisateur', 'utilisateur_username', 'date_lecture',
            'relances_envoyees', 'derniere_relance_le',
        ]
