from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from rest_framework import serializers

from core.mixins import SameCompanyFKSerializerMixin
from core.champs_stricts import ChampsStrictsSansDecimalMixin, EntierStrict
from apps.records.champs_stricts import (
    ChampsStrictsBornesMixin, DecimalLitteral, RegexStricte,
)

from .models import (
    Annonce,
    Holiday,
    MessageAccueil,
    Notification,
    NotificationPreference,
    NotificationRoutingRule,
    WhatsAppTemplate,
    WorkingHoursConfig,
)
from .types_evenements import EventType


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
    # ENF8 — ``reason`` vaut '' quand non classée : pas une valeur d'énum.
    reason = serializers.CharField(read_only=True)

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

    @extend_schema_field(OpenApiTypes.STR)
    def get_severity(self, obj):
        from . import severity as severity_module
        return severity_module.severity_of(obj.event_type)

    @extend_schema_field(OpenApiTypes.STR)
    def get_category(self, obj):
        from . import severity as severity_module
        return severity_module.category_of(obj.event_type)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_action(self, obj):
        from . import severity as severity_module
        return severity_module.is_action(obj.event_type)


class NotificationPreferenceSerializer(ChampsStrictsSansDecimalMixin, serializers.ModelSerializer):
    event_label = serializers.CharField(
        source='get_event_type_display', read_only=True)

    class Meta:
        model = NotificationPreference
        # company + user posés côté serveur — jamais lus du corps.
        fields = ['id', 'event_type', 'event_label', 'in_app', 'whatsapp', 'email', 'push']
        read_only_fields = ['id', 'event_label']

    def validate_event_type(self, value):
        if value not in EventType.values:
            raise serializers.ValidationError("Type d'événement inconnu.")
        return value


class NotificationRoutingRuleSerializer(ChampsStrictsBornesMixin,
                                        SameCompanyFKSerializerMixin,
                                        serializers.ModelSerializer):
    """FG4 — Serializer des règles de routage (admin seulement)."""
    # ENF17 — l'utilisateur ciblé d'une AUTRE société = id absent (400).
    same_company_fields = ('target_user',)
    event_label = serializers.CharField(
        source='get_event_type_display', read_only=True)
    # CI #997 fuzz : une règle ciblant un utilisateur n'a pas de rôle — le
    # libellé est ``null`` (publié nullable, plus « string » seul).
    target_role_label = serializers.CharField(
        source='get_target_role_display', read_only=True, allow_null=True)

    class Meta:
        model = NotificationRoutingRule
        # company posée côté serveur (TenantMixin + perform_create).
        fields = [
            'id', 'event_type', 'event_label',
            'target_role', 'target_role_label', 'target_user',
            'enabled', 'created_at',
        ]
        read_only_fields = ['id', 'event_label', 'target_role_label', 'created_at']

    def validate_event_type(self, value):
        # APAR21 — seule la liste UNIQUE des événements routables est
        # acceptée (une règle sur un événement notifié directement à une
        # personne serait sans effet).
        from .services import EVENEMENTS_ROUTABLES
        if value not in EVENEMENTS_ROUTABLES:
            raise serializers.ValidationError(
                f'Événement non routable : « {value} » est notifié '
                'directement à une personne, une règle serait sans effet.')
        return value

    def validate(self, data):
        # ENF11 (nocturne 15/10) — en MODIFICATION, la cible EN PLACE compte (un
        # PATCH ``{}`` d'une règle valide était refusé) ; une règle qui perdrait
        # toute cible est un refus d'état (409).
        instance = self.instance
        role = data.get('target_role', getattr(instance, 'target_role', None))
        cible = data.get('target_user', getattr(instance, 'target_user', None))
        if not role and not cible:
            message = 'Une règle de routage doit cibler soit un rôle, soit un utilisateur.'
            if instance is not None:
                from core.conflit_etat import ConflitEtat
                raise ConflitEtat(message)
            raise serializers.ValidationError(message)
        return data


#: ENF11 (nocturne 15/10, phase stateful) — la forme que ``DecimalLitteral``
#: accepte (``-?[0-9]+(.[0-9]+)?``) bornée par le champ (4 chiffres dont 2
#: décimales) : le motif générique publiait aussi « .0 » / « 8. », refusés
#: en 400 (« conforme refusée »). Même patron que monitoring.
MOTIF_HEURES_PAR_JOUR = r'^-?0*[0-9]{1,2}(\.[0-9]{1,2})?$'


@extend_schema_field({'type': 'string', 'format': 'decimal',
                      'pattern': MOTIF_HEURES_PAR_JOUR})
class _HeuresParJourLitteral(DecimalLitteral):
    """``DecimalLitteral`` dont le motif publié est celui qu'il accepte."""


# ERR-ENF11-FUZZ-NOTIFICATIONS — ``list`` sert UN objet (singleton société) :
# sans ``many=False`` drf-spectacular publiait un tableau pour le GET.
@extend_schema_serializer(many=False)
class WorkingHoursConfigSerializer(ChampsStrictsSansDecimalMixin, serializers.ModelSerializer):
    """FG5 — Sérializer de la configuration des jours ouvrés (singleton société)."""
    # ERR-ENF11-FUZZ-NOTIFICATIONS — sans ligne en base, GET renvoie les défauts
    # avec ``id``/``updated_at`` à ``null`` : le schéma doit le dire. Entier et
    # décimal STRICTS (le schéma déclare integer / string décimale).
    id = serializers.IntegerField(read_only=True, allow_null=True)
    updated_at = serializers.DateTimeField(read_only=True, allow_null=True)
    working_days = EntierStrict(min_value=0, max_value=32767, required=False)
    hours_per_day = _HeuresParJourLitteral(
        max_digits=4, decimal_places=2, required=False)

    class Meta:
        model = WorkingHoursConfig
        # company posée côté serveur — jamais acceptée du corps.
        fields = ['id', 'working_days', 'hours_per_day', 'updated_at']
        read_only_fields = ['id', 'updated_at']


class HolidaySerializer(ChampsStrictsBornesMixin, serializers.ModelSerializer):
    """FG5 — Sérializer des jours fériés."""

    class Meta:
        model = Holiday
        # company posée côté serveur — jamais acceptée du corps.
        fields = ['id', 'date', 'nom', 'recurrent_annuel', 'created_at']
        read_only_fields = ['id', 'created_at']


class WhatsAppTemplateSerializer(ChampsStrictsBornesMixin, serializers.ModelSerializer):
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


class AnnonceSerializer(ChampsStrictsBornesMixin, serializers.ModelSerializer):
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

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_expiree(self, obj):
        return obj.is_expiree()

    @extend_schema_field(OpenApiTypes.INT)
    def get_lus_count(self, obj):
        return obj.lectures.count()


class MessageAccueilSerializer(ChampsStrictsBornesMixin, serializers.ModelSerializer):
    """MSGACC1 — message d'accueil (PAS une notification, cf. models.py).

    ``company``/``auteur`` posés côté serveur (perform_create) — jamais
    acceptés du corps. ``destinataire`` validé par champ : actif ET de la
    MÊME société que l'auteur (règle fondateur multi-tenant)."""
    # Motif publié au schéma : un corps fait de blancs est refusé (400) — le
    # schéma l'annonçait valide (``minLength: 1``).
    corps = RegexStricte(r'\S')
    auteur_nom = serializers.CharField(
        source='auteur.username', read_only=True, default='')
    destinataire_nom = serializers.CharField(
        source='destinataire.username', read_only=True, default='')

    class Meta:
        model = MessageAccueil
        fields = [
            'id', 'destinataire', 'destinataire_nom', 'auteur', 'auteur_nom',
            'visible_a_partir_de', 'corps', 'lu_le', 'created_at',
        ]
        read_only_fields = [
            'id', 'auteur', 'auteur_nom', 'destinataire_nom', 'lu_le', 'created_at',
        ]

    def validate_destinataire(self, value):
        if not value.is_active:
            raise serializers.ValidationError(
                "Ce destinataire n'est pas actif.")
        request = self.context.get('request')
        company_id = getattr(getattr(request, 'user', None), 'company_id', None)
        if company_id is not None and value.company_id != company_id:
            raise serializers.ValidationError(
                "Ce destinataire n'appartient pas à votre société.")
        return value

    def validate_corps(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('Le corps du message est requis.')
        return value
