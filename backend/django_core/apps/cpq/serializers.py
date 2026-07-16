"""Sérialiseurs de l'app CPQ.

``company`` n'est jamais exposée en écriture : posée côté serveur par le
``TenantMixin`` (``perform_create``)."""
from rest_framework import serializers

from core.rules import validate_condition_group
from .models import OptionProduit, ContrainteCompatibilite, RegleProduitCPQ


class OptionProduitSerializer(serializers.ModelSerializer):
    class Meta:
        model = OptionProduit
        fields = ['id', 'produit', 'groupe_option', 'obligatoire']


class ContrainteCompatibiliteSerializer(serializers.ModelSerializer):
    bloquante = serializers.BooleanField(read_only=True)

    class Meta:
        model = ContrainteCompatibilite
        fields = ['id', 'produit_a', 'produit_b', 'type',
                  'message_utilisateur', 'bloquante']


class RegleProduitCPQSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegleProduitCPQ
        fields = ['id', 'nom', 'condition_group', 'actions', 'actif',
                  'date_creation']
        read_only_fields = ['date_creation']

    def validate_condition_group(self, value):
        """Valide la STRUCTURE de l'arbre via le moteur générique (core.rules)
        avant persistance — jamais un nouveau moteur."""
        errors = validate_condition_group(value)
        if errors:
            raise serializers.ValidationError(errors)
        return value

    def validate_actions(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                'actions doit être une liste.')
        return value
