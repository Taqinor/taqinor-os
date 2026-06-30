"""FG274-FG275 — sérialiseurs de la mise en service & recette IEC 62446.

``company`` et ``created_by`` sont forcés côté serveur. ``resultat`` (recette) et
``ecart_pmax_pct``/``defaut_detecte`` (I-V) sont calculés côté serveur, jamais
acceptés du corps. Aucun prix exposé.
"""
from rest_framework import serializers

from .models import CommissioningTest, IVCurveCapture


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
