"""Serializers en LECTURE SEULE de l'API publique (N89).

Champs explicitement choisis (jamais `__all__`) pour exposer une vue publique
propre des objets métier. Aucun prix d'achat / marge n'est jamais sérialisé :
les lignes n'exposent que prix_unitaire (prix de VENTE) et totaux, jamais
`Produit.prix_achat`.
"""
from rest_framework import serializers

from apps.crm.models import Lead
from apps.ventes.models import Devis, LigneDevis, Facture, LigneFacture
from apps.installations.models import Installation
from apps.stock.models import Produit

from .models import BulkJob


class PublicLeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = [
            'id', 'nom', 'prenom', 'societe', 'email', 'telephone',
            'ville', 'stage', 'canal', 'priorite', 'type_installation',
            'perdu', 'source', 'date_creation', 'date_modification',
        ]
        read_only_fields = fields


class PublicLigneDevisSerializer(serializers.ModelSerializer):
    total_ht = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = LigneDevis
        # prix_unitaire = prix de VENTE ; jamais de prix d'achat ici.
        fields = [
            'id', 'designation', 'quantite', 'prix_unitaire', 'remise',
            'taux_tva', 'total_ht',
        ]
        read_only_fields = fields


class PublicDevisSerializer(serializers.ModelSerializer):
    lignes = PublicLigneDevisSerializer(many=True, read_only=True)
    total_ht = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    total_tva = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    total_ttc = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    client = serializers.PrimaryKeyRelatedField(read_only=True)
    lead = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Devis
        fields = [
            'id', 'reference', 'client', 'lead', 'statut',
            'date_creation', 'date_validite', 'taux_tva', 'remise_globale',
            'mode_installation', 'total_ht', 'total_tva', 'total_ttc',
            'lignes',
        ]
        read_only_fields = fields


class PublicLigneFactureSerializer(serializers.ModelSerializer):
    class Meta:
        model = LigneFacture
        fields = [
            'id', 'designation', 'quantite', 'prix_unitaire', 'remise',
            'taux_tva',
        ]
        read_only_fields = fields


class PublicFactureSerializer(serializers.ModelSerializer):
    lignes = PublicLigneFactureSerializer(many=True, read_only=True)
    client = serializers.PrimaryKeyRelatedField(read_only=True)
    devis = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Facture
        fields = [
            'id', 'reference', 'client', 'devis', 'statut', 'type_facture',
            'pourcentage', 'libelle', 'montant_ht', 'montant_tva',
            'montant_ttc', 'date_emission', 'date_echeance', 'taux_tva',
            'remise_globale', 'lignes',
        ]
        read_only_fields = fields


class PublicProduitSerializer(serializers.ModelSerializer):
    """XSTK23 — disponibilité produit UNIQUEMENT : SKU/nom/marque/catégorie/
    quantité disponible. JAMAIS `prix_achat` ni `prix_vente` ni aucun coût."""
    categorie = serializers.SlugRelatedField(
        slug_field='nom', read_only=True)
    quantite_disponible = serializers.SerializerMethodField()

    class Meta:
        model = Produit
        fields = [
            'id', 'sku', 'nom', 'marque', 'categorie', 'quantite_disponible',
        ]
        read_only_fields = fields

    def get_quantite_disponible(self, obj):
        from apps.stock.services import available_quantity
        return available_quantity(obj)


class BulkJobSerializer(serializers.ModelSerializer):
    """NTAPI16 — suivi d'un `BulkJob` : statut/progression/compteurs/liens.

    `resultat_url`/`erreurs_url` sont des liens présignés COURTE durée (15 min,
    comme les notifications « export prêt » existantes) — jamais l'URL MinIO
    interne brute, jamais permanents. `resultat_url` n'apparaît qu'une fois
    `termine` ; `erreurs_url` dès qu'au moins une ligne a échoué (même job
    encore `en_cours`, pour un import partiel)."""
    progression_pct = serializers.IntegerField(read_only=True)
    resultat_url = serializers.SerializerMethodField()
    erreurs_url = serializers.SerializerMethodField()

    class Meta:
        model = BulkJob
        fields = [
            'id', 'type', 'entite', 'statut', 'progression_pct',
            'total', 'traites', 'succes', 'erreurs',
            'resultat_url', 'erreurs_url', 'message_erreur',
            'created_at', 'updated_at', 'termine_le',
        ]
        read_only_fields = fields

    def get_resultat_url(self, obj):
        if obj.statut != BulkJob.STATUT_TERMINE or not obj.resultat_file_key:
            return None
        from apps.records.storage import presign_export_result
        return presign_export_result(obj.resultat_file_key, expires=900)

    def get_erreurs_url(self, obj):
        if not obj.erreurs_file_key:
            return None
        from apps.records.storage import presign_export_result
        return presign_export_result(obj.erreurs_file_key, expires=900)


class PublicChantierSerializer(serializers.ModelSerializer):
    """Installation = « Chantier » (verbose_name) côté métier."""
    client = serializers.PrimaryKeyRelatedField(read_only=True)
    devis = serializers.PrimaryKeyRelatedField(read_only=True)
    lead = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Installation
        fields = [
            'id', 'reference', 'client', 'devis', 'lead', 'statut',
            'site_ville', 'puissance_installee_kwc', 'raccordement',
            'type_installation',
            # FG104 — exposé pour la synchro incrémentale (?updated_since=).
            'date_creation', 'date_modification',
        ]
        read_only_fields = fields
