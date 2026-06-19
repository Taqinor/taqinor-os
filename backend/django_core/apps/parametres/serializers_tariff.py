"""N64/N65 — Sérialiseur de la Tarification & ROI éditable.

Expose le barème ONEE, le modèle de facturation et les hypothèses ROI/productible.
``company``, ``version`` et ``date_modification`` sont posés/gérés CÔTÉ SERVEUR —
jamais lus du corps de la requête. Tout champ non renseigné garde son défaut
(barème ONEE courant, hypothèses conservatrices)."""
from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from .models_tariff import TariffSettings


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
        ]
        # version/date posés serveur ; company jamais exposée ni acceptée.
        read_only_fields = ['version', 'date_modification']

    def validate_residential_tiers(self, value):
        """Liste de paliers {max_kwh: int|null, prix_kwh_ttc} ou NULL.

        NULL/[] → repli sur le barème ONEE par défaut côté service. Tout autre
        type, ou un palier mal formé, est refusé (jamais de barème incohérent)."""
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
        return cleaned
