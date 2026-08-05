from rest_framework import serializers

from .models import (
    AdminOpsSettings, AnnonceProduit, ConfigPackage, SandboxEnvironment,
    SessionImpersonation,
)


class AnnonceProduitSerializer(serializers.ModelSerializer):
    """NTADM18 — annonce produit + état de lecture du DEMANDEUR.

    `lu` est calculé depuis `context['lues']` (l'ensemble des annonces déjà
    lues par l'utilisateur courant) : jamais une requête par ligne."""

    lu = serializers.SerializerMethodField()
    auteur_nom = serializers.CharField(
        source='auteur.username', read_only=True, default='')

    class Meta:
        model = AnnonceProduit
        fields = [
            'id', 'titre', 'corps', 'date_publication', 'cible_roles',
            'auteur', 'auteur_nom', 'lu', 'created_at',
        ]
        read_only_fields = fields

    def get_lu(self, obj):
        return obj.pk in (self.context.get('lues') or set())


class SessionImpersonationSerializer(serializers.ModelSerializer):
    """NTADM22 — lecture SEULE : une session ne se crée/modifie QUE par les
    endpoints dédiés (consentement obligatoire), jamais par un PATCH générique."""

    statut = serializers.CharField(read_only=True)
    cible_nom = serializers.CharField(
        source='utilisateur_cible.username', read_only=True, default='')
    support_nom = serializers.CharField(
        source='initiee_par.username', read_only=True, default='')
    societe_nom = serializers.CharField(
        source='company.nom', read_only=True, default='')

    class Meta:
        model = SessionImpersonation
        fields = [
            'id', 'company', 'societe_nom', 'utilisateur_cible', 'cible_nom',
            'initiee_par', 'support_nom', 'motif', 'consentement_donne',
            'consentement_le', 'consentement_par', 'refusee', 'refus_le',
            'expire_le', 'demarree_le', 'terminee_le', 'expiree', 'statut',
            'created_at',
        ]
        read_only_fields = fields


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
