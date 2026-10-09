"""CH3/CH4 — Sérialiseurs recette IEC 62446-1 + pack de remise (installations)."""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.mixins import SameCompanyFKSerializerMixin

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


class CommissioningRecordSerializer(SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    # ACHT53 — FK inscriptibles bornées à la société.
    same_company_fields = ('installation',)
    iv_readings = CommissioningIVReadingSerializer(many=True, read_only=True)
    resultat_display = serializers.CharField(
        source='get_resultat_display', read_only=True)
    passe = serializers.BooleanField(read_only=True)
    # XFSM12 — instrument de mesure (traçabilité d'étalonnage IEC 62446-1).
    instrument_nom = serializers.SerializerMethodField()
    instrument_numero_serie = serializers.SerializerMethodField()
    instrument_etalonnage_expire = serializers.BooleanField(read_only=True)
    # CIQ626 — sections du contrat ``recette_ci.json`` (lecture).
    irradiance = serializers.SerializerMethodField()
    energie = serializers.SerializerMethodField()
    thermographie = serializers.SerializerMethodField()
    limitation_injection = serializers.SerializerMethodField()
    decouplage = serializers.SerializerMethodField()
    echantillon_iv = serializers.SerializerMethodField()
    comparaison = serializers.SerializerMethodField()
    # CIQ628 — réserves du chantier (bloc ``reserves`` du contrat).
    reserves = serializers.SerializerMethodField()
    # CIQ629 — bloc ``reception`` du contrat.
    reception = serializers.SerializerMethodField()

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
            # CIQ626 — sections C&I (saisies à plat ; servies groupées).
            'irradiance_poa_wm2', 'irradiance_source', 'temperature_module_c',
            'irradiation_kwh_m2', 'energie_mesuree_kwh',
            'energie_fenetre_debut', 'energie_fenetre_fin',
            'terre_installation_ohm', 'thermographie_faite',
            'thermographie_constats', 'limitation_injection_etat',
            'limitation_injection_consigne', 'decouplage_etat',
            'decouplage_piece', 'echantillon_iv_chaines',
            'instruments_par_essai',
            'irradiance', 'energie', 'thermographie', 'limitation_injection',
            'decouplage', 'echantillon_iv', 'comparaison', 'reserves',
            'reception',
            # CIQ627 — promesse figée (lecture seule).
            'promesse_figee',
        ]
        read_only_fields = ['promesse_figee']

    def validate(self, attrs):
        """CIQ625 — ``resultat`` est CALCULÉ par le serveur à chaque écriture
        (``core.recette.resultat`` : un essai faux ⇒ non conforme, tous vrais
        ⇒ conforme, sinon en cours) : un ``resultat`` envoyé par le client est
        IGNORÉ, sauf le seul choix humain « conforme avec réserves »
        (``reserves``), admis seulement quand TOUS les essais sont vrais —
        sinon 400 FR nommant ``resultat``."""
        from core.recette.resultat import RESERVES, ReservesRefusees

        from .services import resultat_recette_fiche
        demande = attrs.pop('resultat', None)
        fiche = (self.instance if self.instance is not None
                 else CommissioningRecord())
        try:
            attrs['resultat'] = resultat_recette_fiche(
                fiche, attrs, choix=RESERVES if demande == RESERVES else None)
        except ReservesRefusees as exc:
            raise serializers.ValidationError({'resultat': str(exc)})
        # CIQ628 — « conforme avec réserves » exige au moins une réserve
        # d'origine recette OUVERTE sur le chantier.
        if demande == RESERVES:
            from .services import (
                RAISON_RESERVES_SANS_LISTE, recette_a_reserve_ouverte,
            )
            chantier = getattr(fiche, 'installation', None) \
                if fiche.installation_id else attrs.get('installation')
            if chantier is None or not recette_a_reserve_ouverte(chantier):
                raise serializers.ValidationError(
                    {'resultat': RAISON_RESERVES_SANS_LISTE})
        return attrs

    def validate_instrument_id(self, value):
        """ACHT44 — l'instrument de la fiche appartient à l'outillage de la
        société du demandeur (jamais un id étranger ni inexistant)."""
        if value in (None, ''):
            return value
        from apps.outillage.models import Outillage
        request = self.context.get('request')
        company_id = getattr(getattr(request, 'user', None), 'company_id',
                             None)
        if not Outillage.objects.filter(
                pk=value, company_id=company_id).exists():
            raise serializers.ValidationError('Instrument inconnu.')
        return value

    def validate_instruments_par_essai(self, value):
        """CIQ626 — ``{essai: instrument_id}`` ; chaque instrument doit
        appartenir à l'outillage de la société (jamais une autre société)."""
        from apps.outillage.models import Outillage
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "Format attendu : {essai: identifiant d'instrument}.")
        request = self.context.get('request')
        company_id = getattr(getattr(request, 'user', None), 'company_id',
                             None)
        propre = {}
        for essai, iid in value.items():
            if iid in (None, ''):
                continue
            try:
                iid = int(iid)
            except (TypeError, ValueError):
                raise serializers.ValidationError(
                    f"Instrument invalide pour l'essai « {essai} ».")
            if not Outillage.objects.filter(
                    pk=iid, company_id=company_id).exists():
                raise serializers.ValidationError(
                    f"Instrument inconnu pour l'essai « {essai} ».")
            propre[str(essai)] = iid
        return propre

    def update(self, instance, validated_data):
        """CIQ627 — la promesse du devis est figée à la première écriture
        où elle est disponible (jamais réécrite)."""
        from .services import figer_promesse_recette_ci
        instance = super().update(instance, validated_data)
        figer_promesse_recette_ci(instance)
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        from .services import instruments_par_essai_detail
        data['instruments_par_essai'] = instruments_par_essai_detail(instance)
        return data

    @extend_schema_field(serializers.DictField())
    def get_irradiance(self, obj):
        return {'irradiance_poa_wm2': obj.irradiance_poa_wm2,
                'source': obj.irradiance_source,
                'temperature_module_c': obj.temperature_module_c,
                'irradiation_kwh_m2': obj.irradiation_kwh_m2}

    @extend_schema_field(serializers.DictField())
    def get_energie(self, obj):
        from .services import LIBELLE_PR, pr_mesure_recette
        return {'energie_mesuree_kwh': obj.energie_mesuree_kwh,
                'fenetre_debut': obj.energie_fenetre_debut,
                'fenetre_fin': obj.energie_fenetre_fin,
                'pr_mesure': pr_mesure_recette(obj),
                # CIQ627 — PR modélisé de la promesse FIGÉE du devis.
                'pr_modele_devis': (obj.promesse_figee or {}).get(
                    'pr_modelise'),
                'libelle': LIBELLE_PR}

    @extend_schema_field(serializers.DictField())
    def get_thermographie(self, obj):
        return {'faite': obj.thermographie_faite,
                'constats': obj.thermographie_constats, 'photos': []}

    @extend_schema_field(serializers.DictField())
    def get_limitation_injection(self, obj):
        return {'etat': obj.limitation_injection_etat,
                'consigne': obj.limitation_injection_consigne}

    @extend_schema_field(serializers.DictField())
    def get_decouplage(self, obj):
        return {'etat': obj.decouplage_etat, 'piece': obj.decouplage_piece}

    @extend_schema_field(serializers.DictField())
    def get_echantillon_iv(self, obj):
        return {'essais_realises': obj.iv_readings.count() if obj.pk else 0,
                'chaines': obj.echantillon_iv_chaines}

    @extend_schema_field(serializers.DictField())
    def get_comparaison(self, obj):
        from .services import comparaison_recette_ci
        return comparaison_recette_ci(obj)

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_reserves(self, obj):
        from .services import reserves_contrat
        return reserves_contrat(obj.installation)

    @extend_schema_field(serializers.DictField())
    def get_reception(self, obj):
        from .services import reception_contrat
        return reception_contrat(obj.installation)

    def get_instrument_nom(self, obj):
        instrument = obj.instrument
        return instrument.nom if instrument else None

    def get_instrument_numero_serie(self, obj):
        instrument = obj.instrument
        return instrument.numero_serie if instrument else None


class HandoverPackSerializer(SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    # ACHT53 — FK inscriptibles bornées à la société.
    same_company_fields = ('installation',)

    class Meta:
        model = HandoverPack
        fields = [
            'id', 'installation', 'titre', 'pieces', 'monitoring_acces',
            'complet', 'date_generation', 'notes',
        ]
        # Les pièces et « complet » sont assemblés côté serveur.
        read_only_fields = ['pieces', 'complet', 'date_generation']


# ── AGR608 — recette POMPAGE (contrat partagé recette_pompage.json) ─────────
def comparaison_recette_pompage(recette):
    """Bloc ``comparaison`` du contrat — AGR609 : calculé par LE service
    ``services.comparer_recette_pompage`` (promesse FIGÉE, débit attendu à la
    HMT mesurée, écart, seuil société sans défaut). Aucune correction
    d'irradiance, aucun verdict sans seuil."""
    from .services import comparer_recette_pompage
    return comparer_recette_pompage(recette)


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

    def validate(self, attrs):
        """AGR609 (d) — un écart AU-DELÀ du seuil SAISI par la société exige
        ``commentaire_ecart`` (400 FR). Jugé sur l'état APRÈS l'écriture
        (fiche + champs reçus) ; seuil non saisi ⇒ aucun verdict, rien
        d'exigé."""
        import copy

        from .services import (
            comparer_recette_pompage, message_commentaire_requis,
        )
        if self.instance is None:
            return attrs
        apres = copy.copy(self.instance)
        for champ, valeur in attrs.items():
            setattr(apres, champ, valeur)
        comparaison = comparer_recette_pompage(apres)
        if (comparaison['commentaire_requis']
                and not (apres.commentaire_ecart or '').strip()):
            raise serializers.ValidationError({
                'commentaire_ecart': message_commentaire_requis(
                    comparaison['ecart_debit_pct'])})
        return attrs

    @extend_schema_field(serializers.CharField())
    def get_cadre(self, obj):
        return RecettePompage.CADRE

    @extend_schema_field(serializers.DictField())
    def get_comparaison(self, obj):
        return comparaison_recette_pompage(obj)

    @extend_schema_field(serializers.DictField())
    def get_vue_portail(self, obj):
        # AGR612 — UNE liste blanche, partagée avec le portail client.
        from .services import vue_portail_recette_pompage
        return vue_portail_recette_pompage(obj)


def recette_pompage_envelope(installation, recette, context=None):
    """Réponse ``{installation, record}`` du contrat (record null sans
    fiche)."""
    return {
        'installation': installation.id,
        'record': (RecettePompageSerializer(recette, context=context or {})
                   .data if recette is not None else None),
    }
