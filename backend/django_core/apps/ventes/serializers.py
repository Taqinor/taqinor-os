from django.utils import timezone
from rest_framework import serializers
from .models import Devis, LigneDevis, BonCommande, Facture, LigneFacture


class LigneDevisSerializer(serializers.ModelSerializer):
    total_ht = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = LigneDevis
        fields = '__all__'

    def create(self, validated_data):
        # Réforme TVA 2024–2026 : toute NOUVELLE ligne porte son propre taux,
        # copié du produit (10 % panneaux PV, 20 % le reste) quand il n'est pas
        # fourni. Les lignes historiques (taux NULL) restent rendues au taux
        # global de leur devis — jamais réécrites.
        if validated_data.get('taux_tva') is None:
            from decimal import Decimal
            produit = validated_data.get('produit')
            produit_tva = getattr(produit, 'tva', None)
            validated_data['taux_tva'] = (
                produit_tva if produit_tva is not None else Decimal('20.00'))
        return super().create(validated_data)


class DevisSerializer(serializers.ModelSerializer):
    lignes = LigneDevisSerializer(many=True, read_only=True)
    total_ht = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_tva = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_ttc = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    client_nom = serializers.CharField(source='client.nom', read_only=True)
    lead_nom = serializers.SerializerMethodField()

    def get_lead_nom(self, obj):
        if not obj.lead_id:
            return None
        return f"{obj.lead.nom} {obj.lead.prenom or ''}".strip()

    class Meta:
        model = Devis
        fields = '__all__'
        read_only_fields = ['reference', 'created_by', 'fichier_pdf', 'date_creation']


class DevisWriteSerializer(serializers.ModelSerializer):
    """Création/modification sans lignes imbriquées.

    Le client devient optionnel À LA CRÉATION quand un lead est fourni : il est
    alors résolu côté serveur depuis le lead (apps.crm.services), jamais déduit
    côté navigateur. La vue garantit qu'au moins l'un des deux est présent et
    que lead/client appartiennent à la société de l'utilisateur.
    """
    class Meta:
        model = Devis
        exclude = ['reference', 'fichier_pdf']
        # company is force-assigned in perform_create — never accept it from the body.
        read_only_fields = ['created_by', 'date_creation', 'company']
        extra_kwargs = {'client': {'required': False}}


class BonCommandeSerializer(serializers.ModelSerializer):
    client_nom = serializers.CharField(source='client.nom', read_only=True)
    devis_reference = serializers.CharField(source='devis.reference', read_only=True, default=None)
    has_facture = serializers.SerializerMethodField()

    class Meta:
        model = BonCommande
        fields = '__all__'
        # company is force-assigned in perform_create — never accept it from the body.
        read_only_fields = ['reference', 'date_creation', 'company']

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
        # company is force-assigned in perform_create — never accept it from the body.
        read_only_fields = ['created_by', 'date_emission', 'company']
