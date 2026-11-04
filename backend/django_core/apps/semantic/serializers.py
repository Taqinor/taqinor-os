"""NTDATA10 — sérialiseur du CRUD des métriques nommées.

La société n'est JAMAIS un champ : elle est posée côté serveur
(``TenantMixin.perform_create``). La validation de la MESURE est celle du
modèle (``MetricDefinition.clean``) — une seule règle, jamais une seconde qui
dériverait : on la rejoue ici sur une instance non enregistrée et on remonte
ses messages FRANÇAIS champ par champ.
"""
import re

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from core.champs_stricts import ChampsStrictsMixin
from core.unicite import UniciteEn409Mixin

from .models import MetricDefinition

#: Forme d'une clé de métrique (celle des 8 métriques cœur : ``ca_ht``, ``dso``).
_CLE_VALIDE = re.compile(r'^[a-z][a-z0-9_]{0,79}$')


class MetricDefinitionSerializer(UniciteEn409Mixin, ChampsStrictsMixin,
                                 serializers.ModelSerializer):
    """Une métrique nommée : clé, dataset, mesure, unité, filtres."""

    class Meta:
        model = MetricDefinition
        fields = [
            'id', 'cle', 'libelle', 'description', 'dataset', 'mesure',
            'unite', 'format', 'dimensions_par_defaut', 'filtres', 'actif',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_cle(self, value):
        # La clé voyage dans les URL (`metriques/<cle>/valeur/`) et dans les
        # layouts de tableaux de bord : un identifiant simple, jamais une
        # phrase.
        if not _CLE_VALIDE.match(value or ''):
            raise serializers.ValidationError(
                'La clé ne contient que des lettres minuscules, des chiffres '
                'et « _ » (ex. « marge_brute »), et commence par une lettre.')
        return value

    def validate_mesure(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'La mesure doit être un objet JSON.')
        return value

    def validate_filtres(self, value):
        if value in (None, ''):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'Les filtres doivent être un objet JSON.')
        return value

    def validate_dimensions_par_defaut(self, value):
        if value in (None, ''):
            return []
        if (not isinstance(value, list)
                or not all(isinstance(v, str) and v for v in value)):
            raise serializers.ValidationError(
                'Les dimensions par défaut doivent être une liste de noms de '
                'champs.')
        return value

    def validate(self, attrs):
        """Rejoue ``MetricDefinition.clean`` sur l'état FINAL de la ligne."""
        attrs = super().validate(attrs)
        etat = {}
        if self.instance is not None:
            for champ in ('cle', 'dataset', 'mesure'):
                etat[champ] = getattr(self.instance, champ)
        etat.update({k: v for k, v in attrs.items()
                     if k in ('cle', 'dataset', 'mesure')})
        try:
            MetricDefinition(**etat).clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                getattr(exc, 'message_dict', None) or {'mesure': exc.messages})
        return attrs
