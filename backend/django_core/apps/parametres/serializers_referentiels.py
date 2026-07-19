"""WIR66 — sérialiseurs des référentiels société (TVA / conditions / unités).

Les trois modèles maîtres (``models_taxes``/``models_payment_terms``/
``models_units``) sont seedés à la création de société mais n'avaient aucune
API. Ces sérialiseurs les exposent en CRUD ; ``company`` est TOUJOURS forcée
côté serveur (jamais lue du corps), la clé technique (``code``) d'une entrée
existante ne peut pas migrer.
"""
from rest_framework import serializers

from .models_payment_terms import ConditionPaiement
from .models_taxes import TauxTVA
from .models_units import UniteMesure


class TauxTVASerializer(serializers.ModelSerializer):
    class Meta:
        model = TauxTVA
        fields = ['id', 'code', 'libelle', 'taux', 'defaut', 'actif']

    def validate_code(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Le code est requis.')
        return value

    def validate(self, attrs):
        # La clé technique ancre le seed/miroir : elle ne migre pas une fois
        # posée (on modifie un taux existant, on n'en renomme jamais le code).
        if self.instance is not None:
            new_code = attrs.get('code')
            if new_code and new_code != self.instance.code:
                raise serializers.ValidationError(
                    {'code': "Le code d'un taux existant ne peut pas changer."})
        return attrs


class ConditionPaiementSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConditionPaiement
        fields = [
            'id', 'libelle', 'delai_jours', 'fin_de_mois', 'escompte_pct',
            'actif',
        ]

    def validate_libelle(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Le libellé est requis.')
        return value


class UniteMesureSerializer(serializers.ModelSerializer):
    class Meta:
        model = UniteMesure
        fields = ['id', 'code', 'libelle', 'actif']

    def validate_code(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Le code est requis.')
        return value

    def validate(self, attrs):
        # Le code = valeur portée par ``Produit.unite_stock`` (clé de miroir) :
        # on ne le renomme jamais sur une unité existante.
        if self.instance is not None:
            new_code = attrs.get('code')
            if new_code and new_code != self.instance.code:
                raise serializers.ValidationError(
                    {'code': "Le code d'une unité existante ne peut pas "
                             'changer.'})
        return attrs
