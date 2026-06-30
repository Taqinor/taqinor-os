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
