from rest_framework import serializers

from .models import OrdreTransport


class OrdreTransportSerializer(serializers.ModelSerializer):
    """NTLOG1 — ordre de transport. `numero`/`statut`/`created_by` posés
    côté serveur (jamais lus du corps de requête — voir
    `views.OrdreTransportViewSet`)."""
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    type_flux_display = serializers.CharField(
        source='get_type_flux_display', read_only=True, default=None)

    class Meta:
        model = OrdreTransport
        fields = [
            'id', 'numero', 'type_flux', 'type_flux_display',
            'expediteur_nom', 'expediteur_adresse', 'destinataire_nom',
            'destinataire_adresse', 'date_enlevement_prevue',
            'date_livraison_prevue', 'statut', 'statut_display',
            'instructions_speciales', 'ventes_boncommande_id',
            'ventes_devis_id', 'installations_installation_id',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'numero', 'statut', 'created_by', 'created_at', 'updated_at',
        ]
