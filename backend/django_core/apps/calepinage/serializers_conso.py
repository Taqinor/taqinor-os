"""CAL149 — les formes DÉCLARÉES des profils types (schéma OpenAPI).

Ces sérialiseurs ne VALIDENT rien à l'exécution : la validation vit dans
``services/profils_types.py`` (``valider_forme_profils`` pour la FORME, le
modèle ``ProfilTypeConsommation`` pour la journée nulle), qui nomment le champ
fautif en français — ce qu'un message DRF générique ne fait pas. Ils existent
pour que le schéma publié décrive la forme réelle de l'endpoint : ERR-ENF11-
FUZZ-CALEPINAGE (w4) — c'est LE MÊME prédicat que ``valider_forme_profils``
applique (un test l'affirme), les bornes viennent du modèle.

Fichier À PART de ``serializers.py`` : d'autres lanes ``backend/calepinage-*``
y écrivent (lanes réellement file-disjointes).
"""
from __future__ import annotations

from drf_spectacular.extensions import OpenApiSerializerExtension
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.champs_stricts import BooleenStrict, ChaineStricte

from .models import ProfilTypeConsommation as _Profil

__all__ = ['ProfilTypeSerializer', 'ProfilsTypesEcritureSerializer',
           'ProfilsTypesSerializer']


class ProfilTypeSerializer(serializers.Serializer):
    """Un profil type — saisi par la société, ou repli ÉTIQUETÉ."""

    #: ``null`` pour un profil de REPLI : il n'existe pas en base.
    id = serializers.IntegerField(allow_null=True, required=False)
    cle = serializers.CharField()
    libelle = serializers.CharField()
    famille = serializers.CharField()
    #: ``societe`` ou ``hypothese_interne`` — jamais autre chose.
    source = serializers.CharField()
    #: Obligatoire pour un profil saisi ; pour un repli, la mention qui dit
    #: que c'est une hypothèse interne.
    provenance = serializers.CharField(allow_blank=True)
    #: ``{saison: [24 fractions]}`` — des POIDS normalisés, pas des kWh.
    courbes = serializers.DictField(
        child=serializers.ListField(child=serializers.FloatField()))
    saisons = serializers.ListField(child=serializers.CharField())


class ProfilsTypesSerializer(serializers.Serializer):
    """La RÉPONSE : la liste complète, saisis puis replis."""

    profils = ProfilTypeSerializer(many=True)


_COURBE_24 = {'type': 'array', 'minItems': _Profil.HEURES,
              'maxItems': _Profil.HEURES,
              'items': {'type': 'number', 'minimum': 0}}

#: La courbe d'un profil SAISI telle que ``valider_forme_profils`` la juge :
#: au moins une saison connue ; chacune, soit 24 poids >= 0, soit — par type de
#: jour connu, au moins un — les mêmes 24 poids. « Entièrement nulle » est un
#: fait de la valeur, que ce schéma ne dit pas (409).
COURBE_PROFIL_SCHEMA = {
    'type': 'object', 'minProperties': 1, 'additionalProperties': False,
    'properties': {
        saison: {'oneOf': [
            _COURBE_24,
            {'type': 'object', 'minProperties': 1,
             'additionalProperties': False,
             'properties': {jour: _COURBE_24 for jour in _Profil.JOURS_TYPES}},
        ]} for saison in _Profil.SAISONS},
}


@extend_schema_field(COURBE_PROFIL_SCHEMA)
class CourbeProfilField(serializers.JSONField):
    pass


# Un profil SAISI — la courbe est donnée en poids par saison. (Commentaire et
# non docstring : une docstring fuiterait dans la description OpenAPI.)
class ProfilTypeEcritureSerializer(serializers.Serializer):
    cle = serializers.SlugField(
        max_length=_Profil._meta.get_field('cle').max_length)
    libelle = ChaineStricte(
        required=False, allow_blank=True, trim_whitespace=False,
        max_length=_Profil._meta.get_field('libelle').max_length)
    famille = serializers.ChoiceField(choices=_Profil.Famille.choices,
                                      required=False)
    courbe = CourbeProfilField()
    provenance = ChaineStricte()
    actif = BooleenStrict(required=False)


#: Les sources d'une proposition de consommation et le sous-document que
#: CHACUNE exige (``lead`` n'en exige aucun : il lit le lead du calepinage).
SOURCES_CONSOMMATION = ('lead', 'factures', 'appareils', 'csv')
DOCUMENT_DE_LA_SOURCE = {'factures': 'factures', 'appareils': 'appareils',
                         'csv': 'csv'}


def classes_tarifaires():
    """Les classes tarifaires SAISISSABLES : celles de l'inversion du barème
    (``apps.parametres.tariff``) et l'alias « domestique » du contrat."""
    from apps.parametres.tariff import CLASSES_INVERSION

    from .services.consommation import ALIAS_CLASSES

    return (*CLASSES_INVERSION, *ALIAS_CLASSES)


# ERR-ENF11-FUZZ-CALEPINAGE (w4) — le corps de ``consommation/proposer``, UN
# prédicat publié ET appliqué par la vue : une source connue, sa classe
# tarifaire dans l'énumération, chaque sous-document du bon TYPE (objet, liste
# d'objets), et le sous-document de la source choisie PRÉSENT (``oneOf`` publié
# par l'extension ci-dessous). Le CONTENU de ces sous-documents — montants,
# appareils, paramètres de charge, CSV — est jugé par le service : son refus est
# un 409 (la classe non résolue du lead aussi), un lead absent un 404.
# (Commentaire et non docstring : une docstring fuiterait dans l'OpenAPI.)
class ConsommationProposerCorpsSerializer(serializers.Serializer):
    source = serializers.ChoiceField(choices=SOURCES_CONSOMMATION)
    classe = serializers.ChoiceField(choices=classes_tarifaires(),
                                     required=False)
    factures = serializers.DictField(required=False)
    appareils = serializers.ListField(child=serializers.DictField(),
                                      required=False)
    charges = serializers.DictField(required=False)
    csv = serializers.DictField(required=False)
    ramadan = serializers.DictField(required=False)

    def validate(self, attrs):
        document = DOCUMENT_DE_LA_SOURCE.get(attrs['source'])
        if document is not None and document not in attrs:
            raise serializers.ValidationError({
                document: [f"La source « {attrs['source']} » exige le "
                           f"document « {document} »."]})
        return attrs


class _SourceExigeSonDocumentPublie(OpenApiSerializerExtension):
    target_class = ConsommationProposerCorpsSerializer

    def map_serializer(self, auto_schema, direction):
        schema = auto_schema._map_serializer(
            self.target, direction, bypass_extensions=True)
        if direction != 'request':
            return schema
        branches = []
        for source in SOURCES_CONSOMMATION:
            branche = {'properties': {'source': {'anyOf': [
                {'enum': [source]}]}}}
            if source in DOCUMENT_DE_LA_SOURCE:
                branche['required'] = [DOCUMENT_DE_LA_SOURCE[source]]
            branches.append(branche)
        return {**schema, 'oneOf': branches}


class ProfilsTypesEcritureSerializer(serializers.Serializer):
    """Le CORPS du ``PUT`` : la liste COMPLÈTE des profils de la société."""

    profils = ProfilTypeEcritureSerializer(many=True)
