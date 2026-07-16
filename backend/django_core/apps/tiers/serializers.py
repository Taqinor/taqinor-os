"""Sérialiseur du répertoire ``Tiers`` (ARC17).

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). Le tenant ne peut donc pas être
usurpé depuis le corps de requête.
"""
from rest_framework import serializers

from .models import Tiers


class TiersSerializer(serializers.ModelSerializer):
    type_tiers_display = serializers.CharField(
        source='get_type_tiers_display', read_only=True)
    nom_complet = serializers.CharField(read_only=True)

    class Meta:
        model = Tiers
        fields = [
            'id', 'type_tiers', 'type_tiers_display',
            'nom', 'prenom', 'raison_sociale', 'nom_complet',
            'telephone', 'whatsapp', 'email', 'adresse', 'ville',
            'gps_lat', 'gps_lng',
            'ice', 'rc', 'identifiant_fiscal', 'cin', 'rib',
            'is_client', 'is_fournisseur', 'is_partenaire', 'is_soustraitant',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'id', 'date_creation', 'date_modification',
        ]
