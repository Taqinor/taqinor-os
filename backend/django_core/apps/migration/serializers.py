"""Serializers DRF du groupe NTMIG.

``company`` n'est JAMAIS exposé en écriture (elle est forcée côté serveur par
``CompanyScopedModelViewSet``) ; les compteurs, statuts et champs de
dérogation sont en lecture seule — ils ne se posent que par les services
(garde NTMIG5), jamais par le corps d'une requête.
"""
from rest_framework import serializers

from .models import LotMigration, ProjetMigration, RapportReconciliation


class RapportReconciliationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RapportReconciliation
        fields = [
            'id', 'lot', 'nb_source', 'nb_cible_crees', 'nb_cible_existants',
            'nb_erreurs', 'total_financier_source', 'total_financier_cible',
            'ecart_financier', 'ecarts', 'conforme', 'created_at',
        ]
        read_only_fields = fields


class LotMigrationSerializer(serializers.ModelSerializer):
    dernier_rapport = serializers.SerializerMethodField()
    derogation_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = LotMigration
        fields = [
            'id', 'projet', 'entite', 'ordre', 'statut', 'import_job',
            'source_lignes', 'crees', 'maj', 'erreurs', 'source_montant',
            'derogation_reconcile', 'derogation_motif', 'derogation_par_nom',
            'derogation_at', 'dernier_rapport', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'statut', 'import_job', 'source_lignes', 'crees', 'maj',
            'erreurs', 'source_montant', 'derogation_reconcile',
            'derogation_motif', 'derogation_par_nom', 'derogation_at',
            'dernier_rapport', 'created_at', 'updated_at',
        ]

    def get_dernier_rapport(self, obj):
        rapport = obj.rapports.order_by('-created_at').first()
        if rapport is None:
            return None
        return RapportReconciliationSerializer(rapport).data

    def get_derogation_par_nom(self, obj):
        return getattr(obj.derogation_par, 'username', '') or ''


class ProjetMigrationSerializer(serializers.ModelSerializer):
    lots_total = serializers.SerializerMethodField()
    lots_reconcilies = serializers.SerializerMethodField()

    class Meta:
        model = ProjetMigration
        fields = [
            'id', 'nom', 'source', 'statut', 'cree_par', 'date_debut',
            'date_fin', 'notes', 'lots_total', 'lots_reconcilies',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'statut', 'cree_par', 'date_fin', 'lots_total',
            'lots_reconcilies', 'created_at', 'updated_at',
        ]

    def get_lots_total(self, obj):
        return obj.lots.count()

    def get_lots_reconcilies(self, obj):
        return obj.lots.filter(
            statut=LotMigration.Statut.RECONCILIE).count()
