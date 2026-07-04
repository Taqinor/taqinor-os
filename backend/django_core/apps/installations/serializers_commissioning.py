"""CH3/CH4 — Sérialiseurs recette IEC 62446-1 + pack de remise (installations)."""
from rest_framework import serializers

from .models import CommissioningRecord, CommissioningIVReading, HandoverPack


class CommissioningIVReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommissioningIVReading
        fields = [
            'id', 'record', 'string_label', 'n_modules_serie',
            'voc_mesure_v', 'isc_mesure_a', 'pmax_mesure_w',
            'voc_attendu_v', 'isc_attendu_a', 'pmax_attendu_w',
            'ecart_pmax_pct', 'defaut_detecte', 'observations',
        ]
        # `record` est posé côté serveur depuis l'URL (jamais du corps) ; l'écart
        # et le drapeau de défaut sont calculés côté serveur.
        read_only_fields = ['record', 'ecart_pmax_pct', 'defaut_detecte']


class CommissioningRecordSerializer(serializers.ModelSerializer):
    iv_readings = CommissioningIVReadingSerializer(many=True, read_only=True)
    resultat_display = serializers.CharField(
        source='get_resultat_display', read_only=True)
    passe = serializers.BooleanField(read_only=True)
    # XFSM12 — instrument de mesure (traçabilité d'étalonnage IEC 62446-1).
    instrument_nom = serializers.SerializerMethodField()
    instrument_numero_serie = serializers.SerializerMethodField()
    instrument_etalonnage_expire = serializers.BooleanField(read_only=True)

    class Meta:
        model = CommissioningRecord
        fields = [
            'id', 'installation', 'date_essai', 'technicien',
            'instrument_id', 'instrument_nom', 'instrument_numero_serie',
            'instrument_etalonnage_expire',
            'doc_dossier_ok', 'doc_schema_ok', 'doc_datasheets_ok',
            'visuel_structure_ok', 'visuel_cablage_ok', 'visuel_terre_ok',
            'continuite_terre_ok', 'continuite_terre_ohm', 'polarite_ok',
            'isolement_mohm', 'isolement_ok',
            'production_test_kw', 'production_attendue_kw', 'performance_ok',
            'securite_coupure_ok', 'securite_signalisation_ok',
            'resultat', 'resultat_display', 'passe', 'observations',
            'ventes_recette_id', 'iv_readings',
        ]

    def get_instrument_nom(self, obj):
        instrument = obj.instrument
        return instrument.nom if instrument else None

    def get_instrument_numero_serie(self, obj):
        instrument = obj.instrument
        return instrument.numero_serie if instrument else None


class HandoverPackSerializer(serializers.ModelSerializer):
    class Meta:
        model = HandoverPack
        fields = [
            'id', 'installation', 'titre', 'pieces', 'monitoring_acces',
            'complet', 'date_generation', 'notes',
        ]
        # Les pièces et « complet » sont assemblés côté serveur.
        read_only_fields = ['pieces', 'complet', 'date_generation']
