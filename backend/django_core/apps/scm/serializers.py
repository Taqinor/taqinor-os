"""Sérialiseurs de planification supply chain (Groupe NTSCM).

``company`` n'est jamais exposée en écriture : posée côté serveur par
``core.viewsets.CompanyScopedModelViewSet``.
"""
from rest_framework import serializers

from .models import PrevisionDemande


class PrevisionDemandeSerializer(serializers.ModelSerializer):
    methode_display = serializers.CharField(
        source='get_methode_display', read_only=True)
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True)
    genere_par_nom = serializers.CharField(
        source='genere_par.username', read_only=True, default=None)

    class Meta:
        model = PrevisionDemande
        fields = [
            'id', 'produit', 'produit_nom', 'segment', 'periode',
            'quantite_prevue', 'methode', 'methode_display',
            'genere_le', 'genere_par', 'genere_par_nom',
        ]
        read_only_fields = ['id', 'genere_le', 'genere_par']
