"""N58 — sérialiseur de la configuration des statuts métier (StatutConfig)."""
from rest_framework import serializers

from .models_statuses import StatutConfig
from .statuses_defaults import VALID_DOMAINES, default_keys


class StatutConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatutConfig
        fields = [
            'id', 'domaine', 'cle', 'libelle', 'ordre', 'actif',
            'date_modification',
        ]
        # company posée côté serveur — jamais depuis le corps. La clé
        # canonique (domaine/cle) ne peut pas migrer une fois posée : on ne
        # configure que des statuts existants, on n'en renomme jamais la clé.
        read_only_fields = ['date_modification']

    def validate_domaine(self, value):
        if value not in VALID_DOMAINES:
            raise serializers.ValidationError('Domaine inconnu.')
        return value

    def validate(self, attrs):
        # La clé doit être un statut CANONIQUE existant du domaine — on ne crée
        # jamais de nouveau statut via cette couche d'affichage.
        domaine = attrs.get('domaine') or getattr(
            self.instance, 'domaine', None)
        cle = attrs.get('cle') or getattr(self.instance, 'cle', None)
        if domaine and cle and cle not in default_keys(domaine):
            raise serializers.ValidationError(
                {'cle': "Cette clé n'est pas un statut connu de ce domaine."})
        # La clé d'une surcharge existante ne peut pas être réaffectée (elle
        # référence la machine à états).
        if self.instance is not None:
            new_cle = attrs.get('cle')
            new_dom = attrs.get('domaine')
            if (new_cle and new_cle != self.instance.cle) or (
                    new_dom and new_dom != self.instance.domaine):
                raise serializers.ValidationError(
                    "Le domaine et la clé d'une surcharge ne peuvent pas "
                    "changer — créez-en une autre.")
        return attrs
