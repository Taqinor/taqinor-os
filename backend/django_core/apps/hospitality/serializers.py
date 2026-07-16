"""Sérialiseurs du module Hôtellerie & restauration.

``company`` n'est JAMAIS exposée en écriture : posée côté serveur par le
``TenantMixin`` (``perform_create``/``perform_update``).
"""
from rest_framework import serializers

from .models import Chambre, TypeChambre


class TypeChambreSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeChambre
        fields = ['id', 'libelle', 'capacite_max', 'description']


class ChambreSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    type_chambre_libelle = serializers.CharField(
        source='type_chambre.libelle', read_only=True)

    class Meta:
        model = Chambre
        fields = [
            'id', 'type_chambre', 'type_chambre_libelle', 'numero', 'nom',
            'etage', 'statut', 'statut_display', 'vue',
        ]
        # NTHOT1 — une chambre créée sans statut explicite obtient LIBRE par
        # défaut (valeur du modèle) ; le statut évolue ensuite via les
        # actions du cycle de vie (check-in/check-out/housekeeping).
        extra_kwargs = {'statut': {'required': False}}
