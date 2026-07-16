"""Sérialiseurs de l'app CPQ.

``company`` n'est jamais exposée en écriture : posée côté serveur par le
``TenantMixin`` (``perform_create``)."""
from rest_framework import serializers

from django.db import transaction

from core.rules import validate_condition_group
from .models import (
    OptionProduit, ContrainteCompatibilite, RegleProduitCPQ,
    OffreGroupee, LigneOffreGroupee,
)


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


class LigneOffreGroupeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LigneOffreGroupee
        fields = ['id', 'produit', 'quantite', 'mode_prix', 'valeur']


class OffreGroupeeSerializer(serializers.ModelSerializer):
    lignes = LigneOffreGroupeeSerializer(many=True, required=False)

    class Meta:
        model = OffreGroupee
        fields = ['id', 'nom', 'prix_total', 'actif', 'date_creation',
                  'lignes']
        read_only_fields = ['date_creation']

    @transaction.atomic
    def create(self, validated_data):
        lignes = validated_data.pop('lignes', [])
        offre = OffreGroupee.objects.create(**validated_data)
        for ligne in lignes:
            LigneOffreGroupee.objects.create(offre=offre, **ligne)
        return offre

    @transaction.atomic
    def update(self, instance, validated_data):
        lignes = validated_data.pop('lignes', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if lignes is not None:
            instance.lignes.all().delete()
            for ligne in lignes:
                LigneOffreGroupee.objects.create(offre=instance, **ligne)
        return instance
