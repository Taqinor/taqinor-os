from rest_framework import serializers

from .models import AdminOpsSettings, ConfigPackage, SandboxEnvironment


class SandboxEnvironmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SandboxEnvironment
        fields = [
            'id', 'sandbox_company', 'statut', 'date_expiration',
            'cree_par', 'prolongations_count', 'erreur', 'date_creation',
        ]
        read_only_fields = fields


class ConfigPackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfigPackage
        fields = [
            'id', 'nom', 'version', 'contenu', 'contenu_purge',
            'cree_par', 'date_creation',
        ]
        read_only_fields = ['id', 'version', 'contenu', 'contenu_purge',
                            'cree_par', 'date_creation']


class AdminOpsSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminOpsSettings
        fields = [
            'sandbox_duree_defaut_jours', 'sandbox_grace_purge_jours',
            'seuil_alerte_sieges_pct', 'retention_evenements_usage_jours',
            'sandbox_autorise', 'date_modification',
        ]
        read_only_fields = ['date_modification']

    def validate_sandbox_duree_defaut_jours(self, v):
        if not (7 <= v <= 30):
            raise serializers.ValidationError('Doit être entre 7 et 30 jours.')
        return v

    def validate_retention_evenements_usage_jours(self, v):
        if not (30 <= v <= 365):
            raise serializers.ValidationError('Doit être entre 30 et 365 jours.')
        return v
