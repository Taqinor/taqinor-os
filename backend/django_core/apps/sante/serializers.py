"""Sérialiseurs du module ``apps.sante``.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
``core.viewsets.CompanyScopedModelViewSet`` (``TenantMixin.perform_create``).
"""
from rest_framework import serializers

from .models import Patient, Praticien, Salle


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


class PatientSerializer(serializers.ModelSerializer):
    sexe_display = serializers.CharField(source='get_sexe_display', read_only=True)

    class Meta:
        model = Patient
        fields = [
            'id', 'nom', 'prenom', 'cin', 'date_naissance', 'sexe',
            'sexe_display', 'telephone', 'whatsapp', 'email', 'adresse',
            'numero_dossier', 'contact_urgence', 'client',
        ]
        read_only_fields = ['numero_dossier']
