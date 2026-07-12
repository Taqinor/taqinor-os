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
    PaymentTransaction,
    RegistreTraitement,
    SavedQuery,
    ScheduledExport,
    TenantTheme,
    TenantUsageSnapshot,
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
