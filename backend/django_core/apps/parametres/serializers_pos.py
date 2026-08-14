"""NTRET8 — sérialiseurs des Paramètres POS (Paramètres → Point de vente)."""
from rest_framework import serializers

from .models_pos import BoutiquePos, ParametresPos


class ParametresPosSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParametresPos
        fields = ['id', 'taux_horaire_comptoir']


class BoutiquePosSerializer(serializers.ModelSerializer):
    emplacement_nom = serializers.CharField(
        source='emplacement.nom', read_only=True)

    class Meta:
        model = BoutiquePos
        fields = [
            'id', 'emplacement', 'emplacement_nom', 'actif', 'adresse',
            'horaires', 'surface_m2',
        ]
