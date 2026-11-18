"""Formes des suggestions venues de l'ERP (reference/api.md §3.2, annexe A `suggestions.json` ; TCH72).

Une SUGGESTION : `id`, `famille`, `titre` (le `titre_propose`, gabarit SANS nom de client, A4), `lien`
(forme LIEN de `formes.lien`) et `created_at`. Le libellé du lien se lit À L'OUVERTURE, avec les droits
du moment, par la porte unique `selectors/liens.libelle_de_cible` (A4) : une cible sortie de la portée
du compte est servie `inaccessible`, sans libellé ni adresse. Contexte : `{'user': <compte>}`.
"""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.taches.choix import LienEtat
from apps.taches.selectors.liens import libelle_de_cible
from apps.taches.serializers.formes import LienSerializer, lien


def lien_de_suggestion(user, suggestion):
    """LIEN de la cible de `suggestion` vue par `user` maintenant (`None` sans cible)."""
    if suggestion.content_type_id is None or suggestion.object_id is None:
        return None
    content_type = suggestion.content_type
    cible = f'{content_type.app_label}.{content_type.model}'
    libelle = libelle_de_cible(user, cible, suggestion.object_id)
    etat = LienEtat.OK if libelle is not None else LienEtat.INACCESSIBLE
    return lien(cible, suggestion.object_id, libelle, etat)


class SuggestionSerializer(serializers.Serializer):
    """Une ligne de `GET suggestions/`."""

    id = serializers.IntegerField()
    famille = serializers.CharField()
    titre = serializers.CharField(source='titre_propose')
    lien = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()

    @extend_schema_field(LienSerializer(allow_null=True))
    def get_lien(self, obj):
        return lien_de_suggestion(self.context['user'], obj)
