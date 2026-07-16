"""Sérialiseurs du module ``apps.sante``.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
``core.viewsets.CompanyScopedModelViewSet`` (``TenantMixin.perform_create``).
"""
from rest_framework import serializers

from .models import (
    ActeMedical, ActeRealise, Admission, Convention, FactureSante,
    GrilleTarifaire, PaiementSante, Patient, Praticien, PriseEnCharge,
    RendezVous, Salle)


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
            'numero_dossier', 'contact_urgence', 'client', 'convention',
            'numero_affiliation',
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


class AdmissionSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)

    class Meta:
        model = Admission
        fields = [
            'id', 'patient', 'rdv', 'praticien', 'date_admission',
            'date_sortie', 'type', 'type_display', 'statut', 'statut_display',
        ]
        read_only_fields = ['statut', 'date_sortie']


class ConventionSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = Convention
        fields = [
            'id', 'nom', 'type', 'type_display', 'taux_tiers_payant_pct',
            'contact', 'actif',
        ]


class ActeRealiseSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActeRealise
        fields = [
            'id', 'admission', 'patient', 'praticien', 'acte',
            'date_realisation', 'quantite', 'tarif_applique_ttc',
            'facturable', 'prise_en_charge', 'facture_sante',
        ]
        read_only_fields = ['tarif_applique_ttc', 'facture_sante']


class FactureSanteSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    montant_du = serializers.SerializerMethodField()

    class Meta:
        model = FactureSante
        fields = [
            'id', 'patient', 'admission', 'convention', 'sous_total_ttc',
            'remise_ttc', 'taux_tva', 'montant_tva', 'total_ttc',
            'part_tiers_payant_ttc', 'part_patient_ttc', 'statut',
            'statut_display', 'date_emission', 'montant_du',
        ]
        read_only_fields = [
            'sous_total_ttc', 'total_ttc', 'part_tiers_payant_ttc',
            'part_patient_ttc',
        ]

    def get_montant_du(self, obj):
        from .services import montant_du
        return montant_du(obj)


class PaiementSanteSerializer(serializers.ModelSerializer):
    mode_display = serializers.CharField(source='get_mode_display', read_only=True)

    class Meta:
        model = PaiementSante
        fields = [
            'id', 'facture_sante', 'montant', 'mode', 'mode_display',
            'date_paiement', 'encaisse_par',
        ]
        read_only_fields = ['encaisse_par']


class PriseEnChargeSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)

    class Meta:
        model = PriseEnCharge
        fields = [
            'id', 'patient', 'convention', 'admission',
            'numero_dossier_convention', 'date_demande', 'date_reponse',
            'statut', 'statut_display', 'montant_accorde', 'motif_refus',
            'date_expiration',
        ]


class GrilleTarifaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = GrilleTarifaire
        fields = [
            'id', 'convention', 'acte', 'tarif_convention_ttc',
            'taux_prise_charge_pct',
        ]


class ActeMedicalSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActeMedical
        fields = [
            'id', 'code_ngap', 'libelle', 'categorie', 'tarif_base_ttc',
            'cotation_lettre_cle', 'actif',
        ]
        read_only_fields = ['actif']
