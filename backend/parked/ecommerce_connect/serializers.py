from rest_framework import serializers

from .models import CommandeSync, ConnexionEcommerce, ProduitSync


class ConnexionEcommerceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConnexionEcommerce
        fields = ['id', 'plateforme', 'boutique_url', 'actif',
                  'derniere_sync_catalogue', 'derniere_sync_commandes']
        read_only_fields = ['id', 'derniere_sync_catalogue',
                            'derniere_sync_commandes']


class ProduitSyncSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProduitSync
        fields = ['id', 'connexion', 'produit_id', 'vendable_en_ligne',
                  'external_product_id', 'derniere_sync', 'dernier_statut',
                  'dernier_message']
        read_only_fields = ['id', 'derniere_sync', 'dernier_statut',
                            'dernier_message']

    def validate_connexion(self, value):
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        company_id = getattr(user, 'company_id', None)
        if company_id is not None and value.company_id != company_id:
            raise serializers.ValidationError(
                'Connexion introuvable pour cette société.')
        return value


class CommandeSyncSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommandeSync
        fields = ['id', 'connexion', 'external_order_id', 'facture_id',
                  'statut', 'message', 'created_at']
        read_only_fields = fields
