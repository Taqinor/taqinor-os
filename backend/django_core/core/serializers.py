"""Sérialiseurs de la couche fondation ``core``.

FG368 — forme de sortie des jobs planifiés (lecture seule, infra globale).
FG369 — forme de sortie des modèles de workflow installables (catalogue).
"""
from rest_framework import serializers

from .models import (
    ApiUsagePlan,
    BackgroundJob,
    BackupRun,
    BrandedTemplate,
    ChangelogEntry,
    ConsentRecord,
    Dashboard,
    DataSubjectRequest,
    DeletionRecord,
    ModuleToggle,
    OutboxEvent,
    PaymentTransaction,
    RegistreTraitement,
    SavedQuery,
    ScheduledExport,
    TenantTheme,
    TenantUsageSnapshot,
    WorkflowDefinition,
    WorkflowStepDefinition,
)


class ScheduledJobSerializer(serializers.Serializer):
    """Job planifié normalisé (cf. ``core.jobs.list_jobs``)."""
    name = serializers.CharField()
    task = serializers.CharField()
    schedule = serializers.CharField(allow_blank=True)
    enabled = serializers.BooleanField()
    source = serializers.CharField()
    last_run = serializers.CharField(allow_null=True, required=False)


class WorkflowTemplateStepSerializer(serializers.Serializer):
    """Étape d'un modèle de workflow (FG369, lecture seule)."""
    ordre = serializers.IntegerField()
    nom = serializers.CharField()
    type_approbation = serializers.CharField()
    sla_heures = serializers.IntegerField(allow_null=True)
    role_requis = serializers.CharField(allow_blank=True)
    escalade_vers = serializers.CharField(allow_blank=True)


class WorkflowTemplateSerializer(serializers.Serializer):
    """Modèle de workflow installable (FG369, catalogue — lecture seule)."""
    code = serializers.CharField()
    nom = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    nb_etapes = serializers.IntegerField()
    steps = WorkflowTemplateStepSerializer(many=True)


class WorkflowStepDefinitionSerializer(serializers.ModelSerializer):
    """WIR51 — étape (modèle) d'un ``WorkflowDefinition``.

    Utilisée à la fois IMBRIQUÉE dans ``WorkflowDefinitionSerializer``
    (``definition`` alors imposée par le parent, jamais lue du corps) et en
    AUTONOME via ``WorkflowStepDefinitionViewSet`` (``definition`` fournie et
    validée company-scope pour interdire l'accroche à une définition d'un
    autre tenant)."""

    class Meta:
        model = WorkflowStepDefinition
        fields = [
            'id', 'definition', 'ordre', 'nom', 'type_approbation',
            'sla_heures', 'role_requis', 'escalade_vers',
        ]
        read_only_fields = ['id']
        extra_kwargs = {'definition': {'required': False}}

    def validate_definition(self, value):
        request = self.context.get('request')
        if (value is not None and request is not None
                and getattr(request.user, 'company_id', None)
                and value.company_id != request.user.company_id):
            raise serializers.ValidationError(
                'Définition hors de votre société.')
        return value

    def validate(self, attrs):
        # En autonome (viewset des étapes), la définition est obligatoire à la
        # création (une étape sans définition n'a pas de rattachement) ;
        # imbriquée, elle est imposée par le parent (`_sync_steps`). Le viewset
        # autonome pose `require_definition` dans le contexte : signal fiable,
        # contrairement à `self.parent` qui n'est pas toujours lié lors d'une
        # validation imbriquée `many=True`.
        if (self.context.get('require_definition') and self.instance is None
                and not attrs.get('definition')):
            raise serializers.ValidationError(
                {'definition': 'Ce champ est obligatoire.'})
        return attrs


class WorkflowDefinitionSerializer(serializers.ModelSerializer):
    """WIR51 — définition de workflow (chaîne d'approbation multi-étapes) +
    ses étapes imbriquées.

    ``company`` n'est JAMAIS lue du corps (imposée côté serveur via
    ``TenantMixin``). ``code`` (identifiant stable, unique par société) est
    DÉRIVÉ du ``nom`` côté serveur et reste en lecture seule. Les étapes sont
    créées / remplacées intégralement depuis la liste imbriquée ``steps``
    (renumérotées 1..n dans l'ordre du tableau)."""

    steps = WorkflowStepDefinitionSerializer(many=True, required=False)

    class Meta:
        model = WorkflowDefinition
        fields = [
            'id', 'code', 'nom', 'description', 'actif', 'steps',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'code', 'created_at', 'updated_at']

    def create(self, validated_data):
        steps_data = validated_data.pop('steps', [])
        validated_data['code'] = self._derive_code(
            validated_data.get('company'), validated_data.get('nom', ''))
        definition = WorkflowDefinition.objects.create(**validated_data)
        self._sync_steps(definition, steps_data)
        return definition

    def update(self, instance, validated_data):
        steps_data = validated_data.pop('steps', None)
        for attr in ('nom', 'description', 'actif'):
            if attr in validated_data:
                setattr(instance, attr, validated_data[attr])
        instance.save()
        # Remplacement intégral des étapes UNIQUEMENT si `steps` est fourni.
        if steps_data is not None:
            instance.steps.all().delete()
            self._sync_steps(instance, steps_data)
        return instance

    @staticmethod
    def _sync_steps(definition, steps_data):
        for i, step in enumerate(steps_data):
            step = dict(step)
            step.pop('definition', None)  # imposée par le parent, jamais du corps
            step.pop('ordre', None)       # renumérotée 1..n (unicité garantie)
            WorkflowStepDefinition.objects.create(
                definition=definition, ordre=i + 1, **step)

    @staticmethod
    def _derive_code(company, nom):
        from django.utils.text import slugify
        base = (slugify(nom) or 'workflow').replace('-', '_')[:60]
        code = base
        n = 2
        while WorkflowDefinition.objects.filter(
                company=company, code=code).exists():
            code = ('%s_%d' % (base, n))[:64]
            n += 1
        return code


class DashboardSerializer(serializers.ModelSerializer):
    """FG381 — dashboard sans-code sauvegardé.

    ``company`` et ``owner`` ne sont JAMAIS lus du corps : ``company`` est
    imposée côté serveur (TenantMixin) et ``owner`` est positionné à
    l'utilisateur courant à la création (voir la vue).
    """
    class Meta:
        model = Dashboard
        fields = [
            'id', 'titre', 'description', 'layout', 'partage', 'owner',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']


class PaymentTransactionSerializer(serializers.ModelSerializer):
    """FG370 — transaction de paiement carte en ligne (CMI / Payzone).

    ``company`` n'est JAMAIS lu du corps (imposée côté serveur). Le statut, la
    référence PSP et l'URL de redirection sont en lecture seule : ils ne
    bougent que via le flux de paiement (``core.payment``), jamais par PATCH
    direct. La cible (facture) est désignée de façon générique par
    ``content_type``/``object_id``.
    """
    class Meta:
        model = PaymentTransaction
        fields = [
            'id', 'provider', 'montant', 'devise', 'statut', 'external_ref',
            'redirect_url', 'payeur_email', 'content_type', 'object_id',
            'paye_le', 'detail', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'statut', 'external_ref', 'redirect_url', 'paye_le',
            'detail', 'created_at', 'updated_at',
        ]


class SavedQuerySerializer(serializers.ModelSerializer):
    """FG382 — requête d'analyse ad-hoc sauvegardée.

    ``company`` et ``owner`` ne sont JAMAIS lus du corps (imposés côté serveur).
    """
    class Meta:
        model = SavedQuery
        fields = [
            'id', 'titre', 'dataset', 'spec', 'partage', 'owner',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']


class ScheduledExportSerializer(serializers.ModelSerializer):
    """FG383 — extrait planifié vers SFTP/S3.

    ``company`` n'est JAMAIS lu du corps (imposée côté serveur). Le résultat de
    la dernière exécution est en lecture seule.
    """
    class Meta:
        model = ScheduledExport
        fields = [
            'id', 'titre', 'dataset', 'spec', 'format', 'destination', 'cron',
            'actif', 'derniere_execution_le', 'dernier_statut',
            'dernier_detail', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'derniere_execution_le', 'dernier_statut', 'dernier_detail',
            'created_at', 'updated_at',
        ]


class DeletionRecordSerializer(serializers.ModelSerializer):
    """FG388 — entrée de corbeille (lecture seule + restauration via action).

    ``model_label`` expose le type de la cible (app.modele) sans révéler de
    modèle métier côté core.
    """
    model_label = serializers.SerializerMethodField()

    class Meta:
        model = DeletionRecord
        fields = [
            'id', 'label', 'model_label', 'object_id', 'deleted_by',
            'restored_at', 'created_at',
        ]
        read_only_fields = fields

    def get_model_label(self, obj):
        ct = obj.content_type
        return f'{ct.app_label}.{ct.model}' if ct else ''


class ModuleToggleSerializer(serializers.ModelSerializer):
    """FG391 — activation/désactivation d'un module par société.

    ``company`` n'est JAMAIS lu du corps (imposée côté serveur).
    """
    class Meta:
        model = ModuleToggle
        fields = ['id', 'module', 'actif', 'raison',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class TenantThemeSerializer(serializers.ModelSerializer):
    """FG392 — thème white-label par société.

    ``company`` n'est JAMAIS lu du corps (imposée côté serveur, OneToOne).
    """
    class Meta:
        model = TenantTheme
        fields = [
            'id', 'logo_url', 'couleur_primaire', 'couleur_secondaire',
            'domaine', 'nom_affichage', 'extra', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class BrandedTemplateSerializer(serializers.ModelSerializer):
    """FG393 — modèle brandé éditable (PDF/email/WhatsApp).

    ``company`` n'est JAMAIS lu du corps (imposée côté serveur). ``variables``
    expose les placeholders détectés dans le corps (aide à l'éditeur).
    """
    variables = serializers.SerializerMethodField()

    class Meta:
        model = BrandedTemplate
        fields = [
            'id', 'kind', 'code', 'nom', 'sujet', 'corps', 'actif',
            'variables', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'variables', 'created_at', 'updated_at']

    def get_variables(self, obj):
        from .templating import variables_utilisees
        return variables_utilisees(f'{obj.sujet}\n{obj.corps}')


class ConsentRecordSerializer(serializers.ModelSerializer):
    """FG394 — entrée du registre de consentement.

    ``company`` n'est JAMAIS lu du corps (imposée côté serveur).
    """
    class Meta:
        model = ConsentRecord
        fields = [
            'id', 'subject_identifier', 'purpose', 'granted', 'source',
            'occurred_at', 'version_texte', 'ip_confirmation',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DataSubjectRequestSerializer(serializers.ModelSerializer):
    """FG394 — demande de personne concernée (accès / effacement).

    ``company`` n'est JAMAIS lu du corps. Le statut et le résultat sont en
    lecture seule : ils ne bougent que via le traitement (``core.dsr``).
    """
    class Meta:
        model = DataSubjectRequest
        fields = [
            'id', 'subject_identifier', 'kind', 'statut', 'resultat',
            'traitee_le', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'statut', 'resultat', 'traitee_le',
            'created_at', 'updated_at',
        ]


class RegistreTraitementSerializer(serializers.ModelSerializer):
    """XPLT23 — registre des traitements CNDP (loi 09-08).

    ``company`` n'est JAMAIS lu du corps (imposée côté serveur).
    """
    class Meta:
        model = RegistreTraitement
        fields = [
            'id', 'code', 'finalite', 'base_legale', 'categories_donnees',
            'categories_personnes', 'destinataires', 'duree_conservation',
            'numero_recepisse', 'date_recepisse', 'actif',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class BackupRunSerializer(serializers.ModelSerializer):
    """FG395 — opération de sauvegarde/restauration (libre-service).

    ``company`` et ``declenche_par`` ne sont JAMAIS lus du corps (imposés côté
    serveur). Le statut, le manifeste, l'horodatage de fin et le détail sont en
    lecture seule : ils ne bougent que via le runner (``core.backup``).
    """
    class Meta:
        model = BackupRun
        fields = [
            'id', 'kind', 'mode', 'statut', 'datasets', 'cron', 'artifact_ref',
            'object_key', 'bytes_taille',
            'manifest', 'declenche_par', 'termine_le', 'detail',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'statut', 'manifest', 'declenche_par', 'termine_le', 'detail',
            'object_key', 'bytes_taille',
            'created_at', 'updated_at',
        ]


class ApiUsagePlanSerializer(serializers.ModelSerializer):
    """FG398 — plan de tarif/quota API d'une société.

    ``company`` n'est JAMAIS lu du corps (imposée côté serveur, OneToOne).
    """
    class Meta:
        model = ApiUsagePlan
        fields = [
            'id', 'code', 'quota_par_minute', 'quota_par_jour',
            'quota_par_mois', 'actif', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ChangelogEntrySerializer(serializers.ModelSerializer):
    """FG399 — note de version (journal des nouveautés).

    Modèle GLOBAL au produit (pas de portée société). ``lu`` indique si
    l'utilisateur courant a accusé lecture de la note (calculé en contexte).
    """
    lu = serializers.SerializerMethodField()

    class Meta:
        model = ChangelogEntry
        fields = [
            'id', 'titre', 'corps', 'version', 'categorie', 'publie',
            'publie_le', 'lu', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'lu', 'created_at', 'updated_at']

    def get_lu(self, obj):
        lus = (self.context or {}).get('entries_lues')
        if lus is None:
            return False
        return obj.pk in lus


class TenantUsageSnapshotSerializer(serializers.ModelSerializer):
    """NTPLT6 — sortie lecture seule d'un instantané d'usage par tenant."""

    company_nom = serializers.CharField(
        source='company.nom', read_only=True, default=None)

    class Meta:
        model = TenantUsageSnapshot
        fields = [
            'id', 'company', 'company_nom', 'jour', 'lignes_par_table',
            'octets_minio', 'nb_requetes_api', 'nb_taches_celery',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class BackgroundJobSerializer(serializers.ModelSerializer):
    """NTPLT29 — sortie lecture seule d'un job de fond avec progression."""

    class Meta:
        model = BackgroundJob
        fields = [
            'id', 'kind', 'statut', 'progress_pct', 'result_file_key',
            'message_erreur', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class OutboxEventSerializer(serializers.ModelSerializer):
    """NTPLT9/10 — sortie lecture seule d'un événement outbox (superviseur)."""

    class Meta:
        model = OutboxEvent
        fields = [
            'id', 'company', 'event_name', 'event_id', 'payload', 'statut',
            'tentatives', 'prochaine_tentative', 'occurred_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields
