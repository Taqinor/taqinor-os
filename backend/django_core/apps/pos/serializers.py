from rest_framework import serializers

from .models import (
    CommandeRetrait,
    ConfigMaterielPOS,
    LigneCommandeRetrait,
    LigneVenteComptoir,
    SessionCaisse,
    VenteComptoir,
)


class LigneVenteComptoirSerializer(serializers.ModelSerializer):
    total_ttc = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True)
    total_ht = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True)
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)

    class Meta:
        model = LigneVenteComptoir
        # `produit.prix_achat` n'est JAMAIS exposé (aucun champ prix_achat
        # sur ce modèle — le prix d'achat n'existe que côté stock.Produit).
        fields = [
            'id', 'vente', 'produit', 'produit_nom', 'designation',
            'quantite', 'prix_unitaire_ttc', 'remise', 'taux_tva',
            'numeros_serie', 'total_ttc', 'total_ht',
        ]


class VenteComptoirSerializer(serializers.ModelSerializer):
    lignes = LigneVenteComptoirSerializer(many=True, read_only=True)
    total_ht = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True)
    total_ttc = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True)
    client_nom = serializers.CharField(source='client.nom', read_only=True)

    class Meta:
        model = VenteComptoir
        fields = [
            'id', 'reference', 'client', 'client_nom', 'statut',
            'session_caisse', 'caissier', 'taux_tva', 'facture', 'note',
            'created_by', 'date_creation', 'date_validation', 'lignes',
            'total_ht', 'total_ttc',
        ]
        read_only_fields = ['reference', 'statut', 'facture', 'created_by']


class SessionCaisseSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionCaisse
        fields = [
            'id', 'caisse_comptable', 'caissier', 'statut',
            'fond_ouverture', 'date_ouverture', 'date_cloture',
            'montant_compte_cloture', 'montant_tpe_compte', 'ecart_tpe',
            'cloture_caisse_comptable', 'commentaire',
        ]
        read_only_fields = [
            'statut', 'date_ouverture', 'date_cloture',
            'montant_compte_cloture', 'ecart_tpe', 'cloture_caisse_comptable',
        ]


class LigneCommandeRetraitSerializer(serializers.ModelSerializer):
    class Meta:
        model = LigneCommandeRetrait
        fields = ['id', 'commande', 'produit', 'quantite']


class CommandeRetraitSerializer(serializers.ModelSerializer):
    lignes = LigneCommandeRetraitSerializer(many=True, read_only=True)
    client_nom = serializers.CharField(source='client.nom', read_only=True)

    class Meta:
        model = CommandeRetrait
        fields = [
            'id', 'reference', 'client', 'client_nom', 'devis', 'statut',
            'code_retrait', 'vente_comptoir', 'date_creation', 'date_pret',
            'date_retrait', 'created_by', 'lignes',
        ]
        read_only_fields = [
            'reference', 'statut', 'code_retrait', 'created_by',
            'date_pret', 'date_retrait',
        ]


class ConfigMaterielPOSSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfigMaterielPOS
        fields = [
            'id', 'imprimante_ip', 'imprimante_port', 'imprimante_active',
        ]
