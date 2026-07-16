"""Sérialiseurs du module ``apps.sante``.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
``core.viewsets.CompanyScopedModelViewSet`` (``TenantMixin.perform_create``).
"""
from rest_framework import serializers

from .models import Patient, Praticien, RendezVous, Salle


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


class RendezVousSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    patient_nom = serializers.SerializerMethodField()
    praticien_nom = serializers.SerializerMethodField()

    class Meta:
        model = RendezVous
        fields = [
            'id', 'patient', 'patient_nom', 'praticien', 'praticien_nom',
            'salle', 'date_heure_debut', 'duree_min', 'type_acte', 'statut',
            'statut_display', 'motif_court', 'cree_par',
        ]
        read_only_fields = ['cree_par']

    def get_patient_nom(self, obj):
        return str(obj.patient) if obj.patient_id else None

    def get_praticien_nom(self, obj):
        return obj.praticien.nom if obj.praticien_id else None
