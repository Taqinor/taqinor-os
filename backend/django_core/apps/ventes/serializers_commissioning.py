"""FG274-FG275 — sérialiseurs de la mise en service & recette IEC 62446.

``company`` et ``created_by`` sont forcés côté serveur. ``resultat`` (recette) et
``ecart_pmax_pct``/``defaut_detecte`` (I-V) sont calculés côté serveur, jamais
acceptés du corps. Aucun prix exposé.
"""
from rest_framework import serializers

from .models import (
    CommissioningTest, IVCurveCapture, AsBuiltPack, AttestationConformite,
    TestPerformanceReception, AttestationRE)


class IVCurveCaptureSerializer(serializers.ModelSerializer):
    """FG275 — mesure I-V par string ; écart & défaut calculés serveur."""

    class Meta:
        model = IVCurveCapture
        fields = [
            'id', 'recette', 'string_label', 'n_modules_serie',
            'voc_mesure_v', 'isc_mesure_a', 'vmp_mesure_v', 'imp_mesure_a',
            'pmax_mesure_w', 'voc_attendu_v', 'isc_attendu_a',
            'pmax_attendu_w', 'ecart_pmax_pct', 'defaut_detecte',
            'observations', 'created_at',
        ]
        # Écart & défaut TOUJOURS recalculés serveur (jamais du corps).
        read_only_fields = [
            'id', 'ecart_pmax_pct', 'defaut_detecte', 'created_at',
        ]


class CommissioningTestSerializer(serializers.ModelSerializer):
    """FG274 — fiche de recette IEC 62446 ; ``resultat`` calculé serveur."""
    iv_curves = IVCurveCaptureSerializer(many=True, read_only=True)
    resultat_label = serializers.CharField(
        source='get_resultat_display', read_only=True)

    class Meta:
        model = CommissioningTest
        fields = [
            'id', 'chantier', 'devis', 'date_essai',
            'isolement_mohm', 'isolement_ok', 'polarite_ok',
            'continuite_terre_ohm', 'continuite_terre_ok',
            'controle_onduleur_ok', 'resultat', 'resultat_label',
            'technicien', 'observations', 'iv_curves',
            'created_at', 'updated_at',
        ]
        # ``resultat`` est dérivé des essais côté serveur ; jamais du corps.
        read_only_fields = [
            'id', 'resultat', 'resultat_label', 'iv_curves',
            'created_at', 'updated_at',
        ]


class AsBuiltPackSerializer(serializers.ModelSerializer):
    """FG276 — pack documentaire as-built ; ``company`` forcée serveur."""

    class Meta:
        model = AsBuiltPack
        fields = [
            'id', 'chantier', 'devis', 'recette', 'titre', 'pieces',
            'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AttestationConformiteSerializer(serializers.ModelSerializer):
    """FG277 — attestation de conformité électrique."""
    statut_label = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = AttestationConformite
        fields = [
            'id', 'chantier', 'recette', 'reference', 'referentiel',
            'mesures', 'signataire_nom', 'signataire_qualite',
            'signataire_habilitation', 'date_emission', 'statut',
            'statut_label', 'observations', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'statut_label', 'created_at', 'updated_at',
        ]


class TestPerformanceReceptionSerializer(serializers.ModelSerializer):
    """FG278 — PR de réception ; pr_mesure/ecart/verdict dérivés serveur."""
    verdict_label = serializers.CharField(
        source='get_verdict_display', read_only=True)

    class Meta:
        model = TestPerformanceReception
        fields = [
            'id', 'chantier', 'recette', 'date_mesure',
            'energie_mesuree_kwh', 'energie_attendue_kwh',
            'pr_mesure', 'pr_attendu', 'pr_seuil_acceptation',
            'ecart_pct', 'verdict', 'verdict_label', 'observations',
            'created_at', 'updated_at',
        ]
        # pr_mesure (si dérivé), ecart_pct et verdict TOUJOURS calculés serveur.
        read_only_fields = [
            'id', 'ecart_pct', 'verdict', 'verdict_label',
            'created_at', 'updated_at',
        ]


class AttestationRESerializer(serializers.ModelSerializer):
    """FG287 — attestation d'énergie renouvelable ; CO₂ dérivé serveur."""
    statut_label = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = AttestationRE
        fields = [
            'id', 'chantier', 'reference', 'periode_debut', 'periode_fin',
            'energie_kwh', 'facteur_co2_kg_kwh', 'co2_evite_t',
            'signataire_nom', 'date_emission', 'statut', 'statut_label',
            'observations', 'created_at', 'updated_at',
        ]
        # facteur & co2_evite_t TOUJOURS recalculés serveur (jamais du corps).
        read_only_fields = [
            'id', 'facteur_co2_kg_kwh', 'co2_evite_t', 'statut_label',
            'created_at', 'updated_at',
        ]
