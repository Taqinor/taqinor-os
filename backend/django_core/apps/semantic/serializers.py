"""NTDATA10 — sérialiseur du CRUD des métriques nommées.

La société n'est JAMAIS un champ : elle est posée côté serveur
(``TenantMixin.perform_create``). La validation de la MESURE est celle du
modèle (``MetricDefinition.clean``) — une seule règle, jamais une seconde qui
dériverait : on la rejoue ici sur une instance non enregistrée et on remonte
ses messages FRANÇAIS champ par champ.
"""
import re

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import RegexValidator
from rest_framework import serializers

from core.champs_stricts import BooleenStrict, ChampsStrictsMixin
from core.unicite import UniciteEn409Mixin

from .models import MetricDefinition
from .portabilite import FORMAT, MAX_METRIQUES_IMPORT

#: Forme d'une clé de métrique (celle des 8 métriques cœur : ``ca_ht``, ``dso``).
_CLE_VALIDE = re.compile(r'^[a-z][a-z0-9_]{0,79}$')
_MESSAGE_CLE = ('La clé ne contient que des lettres minuscules, des chiffres '
                'et « _ » (ex. « marge_brute »), et commence par une lettre.')


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
        # ENF11 (nocturne 41958593088, dCl2lo) : la forme de la clé est PUBLIÉE
        # (motif au schéma via RegexValidator) — « 0 » était conforme puis 400.
        # ENF45 d : sans ``mesure`` (défaut ``{}``) ``MetricDefinition.clean``
        # refusait un corps que le schéma disait complet — elle est REQUISE à
        # la création (et au PUT) ; PATCH la garde facultative.
        extra_kwargs = {'cle': {'validators': [
            RegexValidator(_CLE_VALIDE, message=_MESSAGE_CLE)]},
            'mesure': {'required': True}}

    def validate_cle(self, value):
        # La clé voyage dans les URL (`metriques/<cle>/valeur/`) et dans les
        # layouts de tableaux de bord : un identifiant simple, jamais une
        # phrase.
        if not _CLE_VALIDE.match(value or ''):
            raise serializers.ValidationError(_MESSAGE_CLE)
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


class ImportMetriquesSerializer(serializers.Serializer):
    """NTDATA48 — corps de ``POST semantic/metriques/import/``.

    ``metriques`` : les entrées du document d'export (chacune revalidée par
    ``MetricDefinitionSerializer`` + la liste blanche de ``portabilite``) ;
    ``commit`` : ``false`` (défaut) = dry-run, ``true`` = appliquer.
    """

    # ENF11 (nocturne 41958593088, VKjai2) : le SEUL format lisible est
    # publié (motif exact, sans composant d'énumération qui renommerait le
    # ``FormatEnum`` voisin) — un texte quelconque était conforme puis 400.
    format = serializers.RegexField(
        r'^(?:%s)?$' % re.escape(FORMAT), required=False, allow_blank=True,
        error_messages={'invalid': (
            'Document étranger : format « %s » attendu.' % FORMAT)})
    version = serializers.IntegerField(required=False, min_value=1)
    metriques = serializers.ListField(
        # Toute valeur JSON (``null`` compris) : une entrée qui n'est pas un
        # objet est REFUSÉE ligne à ligne par ``portabilite`` (rapport), comme
        # le schéma publié l'annonce — jamais un 400 global (api-fuzz).
        child=serializers.JSONField(allow_null=True), allow_empty=True,
        max_length=MAX_METRIQUES_IMPORT)
    commit = BooleenStrict(required=False, default=False)
