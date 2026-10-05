"""N64/N65 — Sérialiseur de la Tarification & ROI éditable.

Expose le barème ONEE, le modèle de facturation et les hypothèses ROI/productible.
``company``, ``version`` et ``date_modification`` sont posés/gérés CÔTÉ SERVEUR —
jamais lus du corps de la requête. Tout champ non renseigné garde son défaut
(barème ONEE courant, hypothèses conservatrices)."""
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from rest_framework import serializers

from .models_tariff import TariffSettings
from .tariff import erreurs_reglages_tarif

# CALX72 — les réglages SAISIS du lot 5 (CALX274 → CALX284), dans l'ordre de
# l'écran Réglages → Tarification. Tous vides par défaut côté modèle : aucun
# défaut n'est suggéré, tout se saisit avec sa source.
CHAMPS_LOT5 = [
    # CALX274/275 — tranches horaires (par saison) et leurs tarifs
    'tou_heures', 'tou_tarifs', 'tou_source', 'tou_date_source',
    # CALX276 — mécanisme de compensation du surplus
    'mecanisme_compensation', 'report_periode', 'plafond_annuel_kwh',
    'ratio_compensation',
    # CALX277 — structure de la grille
    'structure_tarif', 'pays_tarif', 'prix_unique_kwh', 'poste_haut',
    'poste_bas',
    # CALX278 — taxes et charge minimale
    'prix_incluent_taxes', 'taxes', 'charge_minimale_mad_jour',
    # CALX279 — indexation
    'indexation_tarif_pct_an', 'indexation_source',
    # CALX284 — fiscalité et amortissement
    'taux_imposition_pct', 'amortissement_mode', 'amortissement_duree_ans',
    'amortissement_coefficient', 'fiscalite_source',
]

# AGR207 (Groupe AGR) — pompage agricole, calcul INTERNE : barème des charges
# solaires de la société + règle FDA datée. Vides par défaut ([] / {}).
CHAMPS_POMPAGE = ['charges_pompage_solaire', 'regle_fda_pompage']

# CIQ211 (Groupe CIQ) — sensibilités C&I saisies par Reda (liste vide par
# défaut) et mention « crédit-bail » (fausse tant qu'aucun avis juridique).
CHAMPS_CI = ['sensibilites_ci', 'mention_credit_bail_autorisee',
             'mention_credit_bail_source']


class TariffSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TariffSettings
        fields = [
            'residential_tiers',
            'tolerance_kwh',
            'selective_threshold_kwh',
            'force_motrice_prix_kwh_ttc',
            'surplus_injecte_compense',
            'surplus_prix_kwh_ttc',
            'autoconsommation_pct_defaut',
            'pertes_systeme_pct',
            'pvgis_actif',
            'productible_manuel_kwh_kwc',
            'inclinaison_defaut_deg',
            'azimut_defaut_deg',
            'version',
            'date_modification',
        ] + CHAMPS_LOT5 + CHAMPS_POMPAGE + CHAMPS_CI
        # version/date posés serveur ; company jamais exposée ni acceptée.
        read_only_fields = ['version', 'date_modification']

    def validate(self, attrs):
        """CALX72 — la porte de saisie relaie ``erreurs_reglages_tarif``.

        L'état VALIDÉ est celui qui sera enregistré : les valeurs en base,
        recouvertes par celles de la requête (un PATCH partiel ne peut donc
        pas laisser une grille horaire sans sa source). Chaque refus est rangé
        sous le NOM du champ fautif — l'écran l'affiche sous ce champ.
        """
        attrs = super().validate(attrs)
        base = self.instance if self.instance is not None else TariffSettings()
        etat = SimpleNamespace(**{
            champ: attrs.get(champ, getattr(base, champ, None))
            for champ in CHAMPS_LOT5 + CHAMPS_POMPAGE + CHAMPS_CI
            + ['residential_tiers']})
        erreurs = erreurs_reglages_tarif(etat)
        if erreurs:
            raise serializers.ValidationError(erreurs)
        return attrs

    def to_representation(self, instance):
        # AGR207 — la lecture rend TOUJOURS une liste / un objet (jamais
        # ``null``) : aucun défaut, aucune valeur suggérée.
        data = super().to_representation(instance)
        if data.get('charges_pompage_solaire') is None:
            data['charges_pompage_solaire'] = []
        if data.get('regle_fda_pompage') is None:
            data['regle_fda_pompage'] = {}
        if data.get('sensibilites_ci') is None:
            data['sensibilites_ci'] = []
        return data

    def validate_sensibilites_ci(self, value):
        return [] if value is None else value

    def validate_charges_pompage_solaire(self, value):
        return [] if value is None else value

    def validate_regle_fda_pompage(self, value):
        return {} if value is None else value

    def validate_residential_tiers(self, value):
        """Liste de paliers {max_kwh: int|null, prix_kwh_ttc} ou NULL.

        NULL/[] → repli sur le barème ONEE par défaut côté service. Tout autre
        type, ou un palier mal formé, est refusé (jamais de barème incohérent).

        QJR156 (audit QJR79) — UN BARÈME DOIT AVOIR UN PALIER OUVERT. Rien
        n'interdisait jusqu'ici une grille dont TOUS les paliers portent un
        plafond fini : au-delà du dernier plafond, plus aucun palier ne tarife,
        et ``quote_engine.pricing._monthly_bill_from_kwh`` retombait sur le
        ``_FALLBACK_KWH_PRICE`` codé en dur (1,20) — présenté au client comme
        SON barème, sans la moindre mention d'estimation. On refuse la grille à
        la saisie plutôt que de laisser ce forfait se faire passer pour un
        tarif relevé."""
        if value in (None, '', []):
            return None
        if not isinstance(value, list):
            raise serializers.ValidationError(
                'Le barème doit être une liste de paliers.')
        cleaned = []
        for t in value:
            if not isinstance(t, dict):
                raise serializers.ValidationError(
                    'Chaque palier doit être un objet '
                    '{max_kwh, prix_kwh_ttc}.')
            mk = t.get('max_kwh', None)
            if mk not in (None, '', 0):
                try:
                    mk = int(mk)
                except (TypeError, ValueError):
                    raise serializers.ValidationError(
                        'max_kwh doit être un entier ou null.')
                if mk < 0:
                    raise serializers.ValidationError(
                        'max_kwh ne peut pas être négatif.')
            else:
                mk = None
            try:
                prix = Decimal(str(t.get('prix_kwh_ttc', '0')))
            except (InvalidOperation, TypeError):
                raise serializers.ValidationError(
                    'prix_kwh_ttc doit être un nombre.')
            if prix < 0:
                raise serializers.ValidationError(
                    'prix_kwh_ttc ne peut pas être négatif.')
            cleaned.append({'max_kwh': mk, 'prix_kwh_ttc': str(prix)})

        # QJR156 — le DERNIER palier doit être OUVERT (``max_kwh`` absent), et
        # lui seul : un palier fermé placé après un palier ouvert ne tarifierait
        # jamais rien, et une grille entièrement fermée laisse la consommation
        # au-delà du dernier plafond sans tarif.
        ouverts = [i for i, t in enumerate(cleaned) if t['max_kwh'] is None]
        if not ouverts:
            raise serializers.ValidationError(
                'Le dernier palier doit être OUVERT (max_kwh vide) : sans lui, '
                'la consommation au-delà du dernier plafond ne serait tarifée '
                'par aucun palier de votre barème.')
        if len(ouverts) > 1 or ouverts[0] != len(cleaned) - 1:
            raise serializers.ValidationError(
                'Un seul palier peut être ouvert (max_kwh vide), et il doit '
                'être le DERNIER : un palier placé après lui ne tarifierait '
                'jamais rien.')
        return cleaned
