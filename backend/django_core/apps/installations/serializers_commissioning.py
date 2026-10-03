"""CH3/CH4 — Sérialiseurs recette IEC 62446-1 + pack de remise (installations)."""
from rest_framework import serializers

from .models import (
    CommissioningRecord, CommissioningIVReading, HandoverPack, RecettePompage,
)


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


# ── AGR608 — recette POMPAGE (contrat partagé recette_pompage.json) ─────────
PROMESSE_CLES = ('debit_hmt_m3h', 'hmt_m', 'm3_jour', 'heures_pompage',
                 'devis_reference', 'figee_le')


def comparaison_recette_pompage(recette):
    """Bloc ``comparaison`` du contrat. AGR608 ne calcule AUCUN écart : il
    sert la promesse FIGÉE stockée (vide tant que la comparaison AGR609 ne
    l'a pas figée) et dit pourquoi chaque valeur manque. Aucun seuil, aucune
    tolérance, aucune correction d'irradiance."""
    promesse_stockee = recette.promesse or {}
    promesse = {cle: promesse_stockee.get(cle) for cle in PROMESSE_CLES}
    omissions = []
    if not promesse_stockee:
        omissions.append({
            'cle': 'promesse',
            'motif': "promesse du devis non encore figée dans la fiche"})
    omissions.append({
        'cle': 'ecart_debit_pct',
        'motif': "aucun débit attendu : écart non calculable"})
    omissions.append({
        'cle': 'hors_seuil',
        'motif': "seuil d'écart non saisi par la société : aucun verdict"})
    return {
        'promesse': promesse,
        'debit_attendu_a_hmt_mesuree_m3h': None,
        'ecart_debit_pct': None,
        'seuil_ecart_pct': None,
        'hors_seuil': None,
        'commentaire_requis': False,
        'omissions': omissions,
    }


class RecettePompageSerializer(serializers.ModelSerializer):
    """AGR608 — fiche ``record`` du contrat ``recette_pompage.json`` (mêmes
    clés). ``installation``/``company`` jamais lus du corps ; le résultat
    est saisi par le technicien. ``vue_portail`` = liste blanche CLIENT :
    jamais l'instrument, le technicien, un prix ni ``prix_achat``."""
    verrouillee = serializers.BooleanField(read_only=True)
    cadre = serializers.SerializerMethodField()
    comparaison = serializers.SerializerMethodField()
    vue_portail = serializers.SerializerMethodField()

    class Meta:
        model = RecettePompage
        fields = [
            'id', 'date_essai', 'technicien', 'instrument_id',
            'niveau_statique_m', 'niveau_dynamique_m', 'hmt_mesuree_m',
            'debit_mesure_m3h', 'methode_debit', 'index_compteur_m3',
            'courant_plaque_a', 'courant_phase_1_a', 'courant_phase_2_a',
            'courant_phase_3_a', 'tension_v', 'frequence_variateur_hz',
            'irradiance_wm2', 'source_irradiance', 'isolement_moteur_mohm',
            'isolement_ok', 'sens_rotation_ok', 'test_marche_a_sec_ok',
            'resultat', 'observations', 'commentaire_ecart', 'verrouillee',
            'cadre', 'comparaison', 'vue_portail',
        ]

    def validate_technicien(self, value):
        request = self.context.get('request')
        company_id = getattr(getattr(request, 'user', None), 'company_id', None)
        if value is not None and value.company_id != company_id:
            raise serializers.ValidationError('Technicien inconnu.')
        return value

    def get_cadre(self, obj):
        return RecettePompage.CADRE

    def get_comparaison(self, obj):
        return comparaison_recette_pompage(obj)

    def get_vue_portail(self, obj):
        comp = comparaison_recette_pompage(obj)
        return {
            'date_essai': (obj.date_essai.isoformat()
                           if obj.date_essai else None),
            'hmt_mesuree_m': obj.hmt_mesuree_m,
            'debit_mesure_m3h': obj.debit_mesure_m3h,
            'debit_promis_m3h': comp['promesse'].get('debit_hmt_m3h'),
            'ecart_debit_pct': comp['ecart_debit_pct'],
            'commentaire_ecart': obj.commentaire_ecart,
            'resultat': obj.resultat,
        }


def recette_pompage_envelope(installation, recette, context=None):
    """Réponse ``{installation, record}`` du contrat (record null sans
    fiche)."""
    return {
        'installation': installation.id,
        'record': (RecettePompageSerializer(recette, context=context or {})
                   .data if recette is not None else None),
    }
