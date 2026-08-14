from decimal import Decimal

from rest_framework import serializers

from .models import (
    CoutFretReel, EtapeTransport, LigneOrdreTransport, LitigeTransport,
    OrdreTransport,
)


class LigneOrdreTransportSerializer(serializers.ModelSerializer):
    """NTLOG2 — marchandise d'un ordre de transport."""

    class Meta:
        model = LigneOrdreTransport
        fields = [
            'id', 'ordre', 'stock_produit_id', 'designation', 'quantite',
            'unite', 'poids_kg', 'volume_m3', 'valeur_declaree',
        ]


class EtapeTransportSerializer(serializers.ModelSerializer):
    """NTLOG3 — étape enlèvement/transit/livraison. `statut_etape` avance
    via `views.EtapeTransportViewSet` (auto-progression
    `services.apres_changement_statut_etape`)."""
    type_etape_display = serializers.CharField(
        source='get_type_etape_display', read_only=True, default=None)
    statut_etape_display = serializers.CharField(
        source='get_statut_etape_display', read_only=True, default=None)

    class Meta:
        model = EtapeTransport
        fields = [
            'id', 'ordre', 'sequence', 'type_etape', 'type_etape_display',
            'lieu', 'date_prevue', 'date_reelle', 'statut_etape',
            'statut_etape_display',
        ]


class CoutFretReelSerializer(serializers.ModelSerializer):
    """NTLOG16 — coût de fret réel (INTERNE, jamais client-facing)."""

    class Meta:
        model = CoutFretReel
        fields = [
            'id', 'ordre_transport', 'montant_ht', 'devise', 'type_cout',
            'stock_boncommandefournisseur_id', 'note', 'created_at',
        ]
        read_only_fields = ['created_at']


class LitigeTransportSerializer(serializers.ModelSerializer):
    """NTLOG17 — litige transport. `statut` avance via les actions
    `prendre-en-charge`/`resoudre`/`rejeter` (jamais un PATCH direct)."""
    type_litige_display = serializers.CharField(
        source='get_type_litige_display', read_only=True, default=None)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)

    class Meta:
        model = LitigeTransport
        fields = [
            'id', 'ordre_transport', 'type_litige', 'type_litige_display',
            'statut', 'statut_display', 'montant_conteste', 'description',
            'created_by', 'created_at',
        ]
        read_only_fields = ['statut', 'created_by', 'created_at']


class OrdreTransportSerializer(serializers.ModelSerializer):
    """NTLOG1 — ordre de transport. `numero`/`statut`/`created_by` posés
    côté serveur (jamais lus du corps de requête — voir
    `views.OrdreTransportViewSet`). `poids_total_kg`/`volume_total_m3`
    (NTLOG2) sont calculés en lecture sur les lignes liées."""
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    type_flux_display = serializers.CharField(
        source='get_type_flux_display', read_only=True, default=None)
    mode_transport_display = serializers.CharField(
        source='get_mode_transport_display', read_only=True, default=None)
    lignes = LigneOrdreTransportSerializer(many=True, read_only=True)
    etapes = EtapeTransportSerializer(many=True, read_only=True)
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
            'ventes_devis_id', 'installations_installation_id',
            'mode_transport', 'mode_transport_display', 'flotte_actif_id',
            'conducteur', 'installations_transporteur_id', 'lignes',
            'etapes', 'poids_total_kg', 'volume_total_m3', 'created_by',
            'created_at', 'updated_at',
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
