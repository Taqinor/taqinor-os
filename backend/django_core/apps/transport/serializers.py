from decimal import Decimal

from rest_framework import serializers

from .models import LigneOrdreTransport, OrdreTransport


class LigneOrdreTransportSerializer(serializers.ModelSerializer):
    """NTLOG2 — marchandise d'un ordre de transport."""

    class Meta:
        model = LigneOrdreTransport
        fields = [
            'id', 'ordre', 'stock_produit_id', 'designation', 'quantite',
            'unite', 'poids_kg', 'volume_m3', 'valeur_declaree',
        ]


class OrdreTransportSerializer(serializers.ModelSerializer):
    """NTLOG1 — ordre de transport. `numero`/`statut`/`created_by` posés
    côté serveur (jamais lus du corps de requête — voir
    `views.OrdreTransportViewSet`). `poids_total_kg`/`volume_total_m3`
    (NTLOG2) sont calculés en lecture sur les lignes liées."""
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    type_flux_display = serializers.CharField(
        source='get_type_flux_display', read_only=True, default=None)
    lignes = LigneOrdreTransportSerializer(many=True, read_only=True)
    poids_total_kg = serializers.SerializerMethodField()
    volume_total_m3 = serializers.SerializerMethodField()

    class Meta:
        model = OrdreTransport
        fields = [
            'id', 'numero', 'type_flux', 'type_flux_display',
            'expediteur_nom', 'expediteur_adresse', 'destinataire_nom',
            'destinataire_adresse', 'date_enlevement_prevue',
            'date_livraison_prevue', 'statut', 'statut_display',
            'instructions_speciales', 'ventes_boncommande_id',
            'ventes_devis_id', 'installations_installation_id', 'lignes',
            'poids_total_kg', 'volume_total_m3', 'created_by', 'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'numero', 'statut', 'created_by', 'created_at', 'updated_at',
        ]

    def get_poids_total_kg(self, obj):
        return sum(
            (ligne.poids_kg for ligne in obj.lignes.all()), Decimal('0'))

    def get_volume_total_m3(self, obj):
        return sum(
            (ligne.volume_m3 for ligne in obj.lignes.all()), Decimal('0'))
