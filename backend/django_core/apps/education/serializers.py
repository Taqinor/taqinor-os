"""Sérialiseurs DRF de l'app éducation (``apps.education``)."""
from rest_framework import serializers

from .models import (
    AnneeScolaire, Classe, EcheancierScolarite, Eleve, Famille,
    GrilleTarifaire, Inscription, LigneEcheance, Niveau, Remise)


class AnneeScolaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnneeScolaire
        fields = [
            'id', 'libelle', 'date_debut', 'date_fin', 'statut',
            'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class NiveauSerializer(serializers.ModelSerializer):
    class Meta:
        model = Niveau
        fields = ['id', 'nom', 'cycle', 'ordre']
        read_only_fields = ['id']


class ClasseSerializer(serializers.ModelSerializer):
    effectif = serializers.IntegerField(read_only=True)
    niveau_nom = serializers.CharField(source='niveau.nom', read_only=True)

    class Meta:
        model = Classe
        fields = [
            'id', 'annee_scolaire', 'niveau', 'niveau_nom', 'nom',
            'capacite_max', 'enseignant_principal', 'salle', 'effectif']
        read_only_fields = ['id', 'effectif']


class FamilleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Famille
        fields = [
            'id', 'nom', 'parent1_nom', 'parent1_telephone',
            'parent1_whatsapp', 'parent1_email', 'parent2_nom',
            'parent2_telephone', 'parent2_whatsapp', 'parent2_email',
            'adresse']
        read_only_fields = ['id']


class EleveSerializer(serializers.ModelSerializer):
    numero_dossier = serializers.CharField(read_only=True)

    class Meta:
        model = Eleve
        fields = [
            'id', 'famille', 'nom', 'prenom', 'date_naissance', 'sexe',
            'cin', 'photo', 'classe', 'statut', 'numero_dossier']
        read_only_fields = ['id', 'numero_dossier']


class InscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Inscription
        fields = [
            'id', 'eleve', 'annee_scolaire', 'classe_demandee',
            'classe_affectee', 'statut', 'date_demande', 'date_decision',
            'decide_par', 'position_liste_attente']
        read_only_fields = [
            'id', 'date_demande', 'date_decision', 'decide_par',
            'position_liste_attente', 'statut', 'classe_affectee']


class GrilleTarifaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = GrilleTarifaire
        fields = [
            'id', 'annee_scolaire', 'niveau', 'frais_inscription',
            'scolarite_annuelle', 'transport_mensuel', 'cantine_mensuelle',
            'activites_annuelles', 'devise', 'active']
        read_only_fields = ['id']


class RemiseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Remise
        fields = [
            'id', 'famille', 'eleve', 'type', 'mode', 'valeur', 'motif',
            'valable_annee_scolaire', 'justificatif', 'approuve_par',
            'statut']
        read_only_fields = ['id', 'approuve_par']


class LigneEcheanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LigneEcheance
        fields = ['id', 'libelle', 'montant', 'date_echeance', 'statut']
        read_only_fields = ['id']


class EcheancierScolariteSerializer(serializers.ModelSerializer):
    lignes = LigneEcheanceSerializer(many=True, read_only=True)

    class Meta:
        model = EcheancierScolarite
        fields = [
            'id', 'eleve', 'annee_scolaire', 'grille_tarifaire', 'remises',
            'montant_total', 'nombre_echeances', 'lignes']
        read_only_fields = [
            'id', 'grille_tarifaire', 'remises', 'montant_total',
            'nombre_echeances', 'lignes']
