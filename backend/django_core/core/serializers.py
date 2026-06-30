"""Sérialiseurs de la couche fondation ``core``.

FG368 — forme de sortie des jobs planifiés (lecture seule, infra globale).
FG369 — forme de sortie des modèles de workflow installables (catalogue).
"""
from rest_framework import serializers

from .models import (
    Dashboard,
    DeletionRecord,
    PaymentTransaction,
    SavedQuery,
    ScheduledExport,
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
