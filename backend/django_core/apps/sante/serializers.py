"""Sérialiseurs du module ``apps.sante``.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
``core.viewsets.CompanyScopedModelViewSet`` (``TenantMixin.perform_create``).
"""
from rest_framework import serializers

from .models import Praticien, Salle


class PraticienSerializer(serializers.ModelSerializer):
    class Meta:
        model = Praticien
        fields = [
            'id', 'user', 'nom', 'specialite', 'numero_ordre',
            'couleur_agenda', 'actif',
        ]


class SalleSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = Salle
        fields = [
            'id', 'nom', 'type', 'type_display', 'capacite', 'equipements',
        ]
