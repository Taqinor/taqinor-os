"""Groupe NTWMS — sérialiseurs de la couche entrepôt.

``company`` n'est JAMAIS exposé ni accepté : il est posé côté serveur par
``CompanyScopedModelViewSet`` (règle multi-tenant).
"""
from rest_framework import serializers

from .models_wms import LignePicking, VaguePicking


class LignePickingSerializer(serializers.ModelSerializer):
    """NTWMS4 — ligne d'une vague de prélèvement (lecture)."""

    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    produit_sku = serializers.CharField(source='produit.sku', read_only=True)
    bin_code = serializers.CharField(
        source='bin.code', read_only=True, default='')
    numero_lot = serializers.CharField(
        source='lot.numero_lot', read_only=True, default='')
    reste_a_prelever = serializers.IntegerField(read_only=True)

    class Meta:
        model = LignePicking
        fields = [
            'id', 'vague', 'produit', 'produit_nom', 'produit_sku',
            'quantite_demandee', 'quantite_prelevee', 'reste_a_prelever',
            'bin', 'bin_code', 'lot', 'numero_lot', 'installation',
            'bon_commande', 'ordre_parcours',
        ]
        read_only_fields = [
            'vague', 'quantite_prelevee', 'ordre_parcours',
        ]


class VaguePickingSerializer(serializers.ModelSerializer):
    """NTWMS4 — vague de prélèvement multi-source. La référence est posée
    côté serveur (`core.numbering`), jamais acceptée du client."""

    lignes = LignePickingSerializer(many=True, read_only=True)
    cree_par_username = serializers.CharField(
        source='cree_par.username', read_only=True, default='')
    nb_lignes = serializers.SerializerMethodField()

    class Meta:
        model = VaguePicking
        fields = [
            'id', 'reference', 'statut', 'note', 'date_lancement',
            'date_cloture', 'cree_par', 'cree_par_username', 'nb_lignes',
            'lignes', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'reference', 'statut', 'date_lancement', 'date_cloture',
            'cree_par', 'created_at', 'updated_at',
        ]

    def get_nb_lignes(self, obj):
        return obj.lignes.count()
