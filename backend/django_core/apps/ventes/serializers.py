from django.utils import timezone
from rest_framework import serializers
from .models import Devis, LigneDevis, BonCommande, Facture, LigneFacture


class LigneDevisSerializer(serializers.ModelSerializer):
    total_ht = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = LigneDevis
        fields = '__all__'


class DevisSerializer(serializers.ModelSerializer):
    lignes = LigneDevisSerializer(many=True, read_only=True)
    total_ht = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_tva = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_ttc = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    client_nom = serializers.CharField(source='client.nom', read_only=True)

    class Meta:
        model = Devis
        fields = '__all__'
        read_only_fields = ['reference', 'created_by', 'fichier_pdf', 'date_creation']


class DevisWriteSerializer(serializers.ModelSerializer):
    """Création/modification sans lignes imbriquées."""
    class Meta:
        model = Devis
        exclude = ['reference', 'fichier_pdf']
        read_only_fields = ['created_by', 'date_creation']


class BonCommandeSerializer(serializers.ModelSerializer):
    client_nom      = serializers.CharField(source='client.nom', read_only=True)
    devis_reference = serializers.CharField(source='devis.reference', read_only=True, default=None)
    has_facture     = serializers.SerializerMethodField()

    class Meta:
        model = BonCommande
        fields = '__all__'
        read_only_fields = ['reference', 'date_creation']

    def get_has_facture(self, obj):
        return Facture.objects.filter(bon_commande=obj).exists()


class LigneFactureSerializer(serializers.ModelSerializer):
    total_ht = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = LigneFacture
        fields = '__all__'


class FactureSerializer(serializers.ModelSerializer):
    lignes = LigneFactureSerializer(many=True, read_only=True)
    total_ht = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_tva = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_ttc = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    client_nom = serializers.CharField(source='client.nom', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Facture
        fields = '__all__'
        read_only_fields = ['reference', 'created_by', 'fichier_pdf', 'date_emission']

    def get_is_overdue(self, obj):
        return (
            obj.statut == Facture.Statut.EMISE
            and obj.date_echeance is not None
            and obj.date_echeance < timezone.now().date()
        )


class FactureWriteSerializer(serializers.ModelSerializer):
    """Création/modification sans lignes imbriquées."""
    class Meta:
        model = Facture
        exclude = ['reference', 'fichier_pdf']
        read_only_fields = ['created_by', 'date_emission']
