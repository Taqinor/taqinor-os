from rest_framework import serializers

from .models import Territoire, TerritoireMembre, TerritoireRegle


class TerritoireRegleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TerritoireRegle
        fields = ['id', 'territoire', 'ordre', 'condition', 'actif']


class TerritoireMembreSerializer(serializers.ModelSerializer):
    utilisateur_nom = serializers.CharField(
        source='utilisateur.username', read_only=True)

    class Meta:
        model = TerritoireMembre
        fields = [
            'id', 'territoire', 'utilisateur', 'utilisateur_nom', 'quota_pct',
            'nb_assignations', 'dernier_assigne_at', 'actif',
        ]
        read_only_fields = ['nb_assignations', 'dernier_assigne_at']


class TerritoireSerializer(serializers.ModelSerializer):
    type_territoire_display = serializers.CharField(
        source='get_type_territoire_display', read_only=True)
    regles = TerritoireRegleSerializer(many=True, read_only=True)
    membres = TerritoireMembreSerializer(many=True, read_only=True)

    class Meta:
        model = Territoire
        fields = [
            'id', 'nom', 'type_territoire', 'type_territoire_display',
            'criteres', 'actif', 'date_creation', 'regles', 'membres',
        ]
        read_only_fields = ['date_creation']
