"""CAL149 — les formes DÉCLARÉES des profils types (schéma OpenAPI).

Ces sérialiseurs ne VALIDENT rien : la validation métier vit sur le modèle
``ProfilTypeConsommation`` (provenance obligatoire, courbe 24 h par saison) et
dans ``services/profils_types.py``, qui nomment le champ fautif en français —
ce qu'un message DRF générique ne fait pas. Ils existent pour que le schéma
publié décrive la forme réelle de l'endpoint.

Fichier À PART de ``serializers.py`` : d'autres lanes ``backend/calepinage-*``
y écrivent (lanes réellement file-disjointes).
"""
from __future__ import annotations

from rest_framework import serializers

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


class ProfilTypeEcritureSerializer(serializers.Serializer):
    """Un profil SAISI — la courbe est donnée en poids par saison."""

    cle = serializers.CharField()
    libelle = serializers.CharField(required=False, allow_blank=True)
    famille = serializers.CharField(required=False)
    courbe = serializers.DictField(
        child=serializers.ListField(child=serializers.FloatField()))
    provenance = serializers.CharField()
    actif = serializers.BooleanField(required=False)


class ProfilsTypesEcritureSerializer(serializers.Serializer):
    """Le CORPS du ``PUT`` : la liste COMPLÈTE des profils de la société."""

    profils = ProfilTypeEcritureSerializer(many=True)
