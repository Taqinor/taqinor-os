"""Sérialiseurs de l'app CPQ.

``company`` n'est jamais exposée en écriture : posée côté serveur par le
``TenantMixin`` (``perform_create``)."""
from rest_framework import serializers

from .models import OptionProduit, ContrainteCompatibilite


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
