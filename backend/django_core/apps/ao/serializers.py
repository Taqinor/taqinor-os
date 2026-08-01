"""Serializers du module Appels d'offres (``apps.ao``).

AOF3 — le CORPS des 8 serializers AO vit désormais ICI (il vivait encore
interleavé dans ``apps.compta.serializers``, où toute évolution du domaine AO
aurait forcé la lane à écrire hors de son périmètre). ``company`` n'est JAMAIS
un champ exposé : elle est posée côté serveur par le socle
``CompanyScopedModelViewSet``.
"""
from rest_framework import serializers

from .models import (
    AppelOffre,
    BordereauPrix,
    CautionSoumission,
    DossierSoumission,
    EcheanceAO,
    LigneBordereau,
    PieceSoumission,
    ResultatAO,
)


# ── FG222 — Appels d'offres ────────────────────────────────────────────────

class AppelOffreSerializer(serializers.ModelSerializer):
    type_marche_display = serializers.CharField(
        source='get_type_marche_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = AppelOffre
        fields = [
            'id', 'reference', 'objet', 'acheteur', 'type_marche',
            'type_marche_display', 'lot', 'date_limite', 'montant_estime',
            'caution_provisoire', 'statut', 'statut_display', 'lead_id',
            'date_creation',
        ]
        read_only_fields = ['date_creation']


# ── FG223 — Bordereaux des prix (BOQ) ──────────────────────────────────────

class LigneBordereauSerializer(serializers.ModelSerializer):
    montant_ht = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True)

    class Meta:
        model = LigneBordereau
        fields = [
            'id', 'bordereau', 'numero', 'designation', 'unite', 'quantite',
            'prix_unitaire', 'montant_ht',
        ]


class BordereauPrixSerializer(serializers.ModelSerializer):
    lignes = LigneBordereauSerializer(many=True, read_only=True)
    total_ht = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True)
    appel_offre_reference = serializers.CharField(
        source='appel_offre.reference', read_only=True)

    class Meta:
        model = BordereauPrix
        fields = [
            'id', 'appel_offre', 'appel_offre_reference', 'intitule',
            'lignes', 'total_ht', 'date_creation',
        ]
        read_only_fields = ['date_creation']


# ── FG224 — Cautions de soumission ─────────────────────────────────────────

class CautionSoumissionSerializer(serializers.ModelSerializer):
    type_caution_display = serializers.CharField(
        source='get_type_caution_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = CautionSoumission
        fields = [
            'id', 'appel_offre', 'type_caution', 'type_caution_display',
            'montant', 'banque', 'date_emission', 'date_echeance',
            'date_restitution', 'statut', 'statut_display', 'date_creation',
        ]
        read_only_fields = ['date_creation']


# ── FG225 — Dossiers et pièces de soumission ───────────────────────────────

class PieceSoumissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PieceSoumission
        fields = [
            'id', 'dossier', 'libelle', 'obligatoire', 'fournie', 'fichier',
            'date_depot',
        ]


class DossierSoumissionSerializer(serializers.ModelSerializer):
    pieces = PieceSoumissionSerializer(many=True, read_only=True)
    complet = serializers.BooleanField(read_only=True)
    appel_offre_reference = serializers.CharField(
        source='appel_offre.reference', read_only=True)

    class Meta:
        model = DossierSoumission
        fields = [
            'id', 'appel_offre', 'appel_offre_reference', 'pieces', 'complet',
            'date_creation',
        ]
        read_only_fields = ['date_creation']


# ── FG226 — Échéances d'AO ─────────────────────────────────────────────────

class EcheanceAOSerializer(serializers.ModelSerializer):
    type_echeance_display = serializers.CharField(
        source='get_type_echeance_display', read_only=True)

    class Meta:
        model = EcheanceAO
        fields = [
            'id', 'appel_offre', 'type_echeance', 'type_echeance_display',
            'libelle', 'date_echeance', 'rappel_jours', 'traitee',
            'date_creation',
        ]
        read_only_fields = ['date_creation']


# ── FG227 — Résultats d'AO ─────────────────────────────────────────────────

class ResultatAOSerializer(serializers.ModelSerializer):
    issue_display = serializers.CharField(
        source='get_issue_display', read_only=True)
    ecart_prix = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True, allow_null=True)
    appel_offre_reference = serializers.CharField(
        source='appel_offre.reference', read_only=True)

    class Meta:
        model = ResultatAO
        fields = [
            'id', 'appel_offre', 'appel_offre_reference', 'issue',
            'issue_display', 'attributaire', 'notre_prix', 'prix_gagnant',
            'ecart_prix', 'motif', 'date_resultat', 'date_creation',
        ]
        read_only_fields = ['date_creation']
