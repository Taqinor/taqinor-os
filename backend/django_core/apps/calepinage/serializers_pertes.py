"""CAL139 — les formes DÉCLARÉES des postes de pertes (schéma OpenAPI).

Ces sérialiseurs ne VALIDENT rien : la validation métier vit dans
``services/pertes.py`` (elle doit nommer le poste fautif en français, ce qu'un
message DRF générique ne fait pas). Ils existent pour que le schéma publié
décrive la forme réelle des deux actions ``pertes`` /
``enregistrer-pertes`` — un client généré depuis le schéma doit voir les mêmes
clés que le serveur rend.

Fichier À PART de ``serializers.py`` : d'autres lanes ``backend/calepinage-*``
y écrivent (lanes réellement file-disjointes).
"""
from __future__ import annotations

from rest_framework import serializers

__all__ = ['PertesCalepinageSerializer', 'PosteDePerteSerializer',
           'PostesDePertesSerializer', 'PosteDuCatalogueSerializer']


class PosteDePerteSerializer(serializers.Serializer):
    """UN poste : sa valeur, sa source, et ses douze mois s'il est saisonnier."""

    poste = serializers.CharField()
    libelle = serializers.CharField(required=False, allow_blank=True)
    pct = serializers.FloatField(required=False)
    #: ``null`` = poste NON sourcé — publié comme tel, jamais masqué.
    source = serializers.CharField(required=False, allow_null=True)
    reference = serializers.CharField(required=False, allow_blank=True)
    #: 12 valeurs (salissure) ; ``pct`` est alors leur MOYENNE, calculée
    #: côté serveur — jamais saisie à côté.
    mensuel = serializers.ListField(child=serializers.FloatField(),
                                    required=False, allow_null=True)


class PostesDePertesSerializer(serializers.Serializer):
    """Le CORPS de ``POST enregistrer-pertes/`` : la liste complète."""

    pertes = PosteDePerteSerializer(many=True)


class PosteDuCatalogueSerializer(serializers.Serializer):
    """Un poste du catalogue de référence — un NOM, jamais une valeur."""

    poste = serializers.CharField()
    libelle = serializers.CharField()
    reference = serializers.CharField()
    mensuel = serializers.BooleanField()


class PertesCalepinageSerializer(serializers.Serializer):
    """La RÉPONSE des deux actions : postes, somme et catalogue."""

    calepinage = serializers.IntegerField()
    pertes = PosteDePerteSerializer(many=True)
    #: ``null`` quand aucun poste n'est renseigné : une somme de rien n'est
    #: pas ``0 %``, c'est une absence de politique.
    total_pct = serializers.FloatField(allow_null=True)
    postes_non_sources = serializers.ListField(
        child=serializers.CharField())
    simulable = serializers.BooleanField()
    motif_non_simulable = serializers.CharField(allow_blank=True)
    catalogue = PosteDuCatalogueSerializer(many=True)
