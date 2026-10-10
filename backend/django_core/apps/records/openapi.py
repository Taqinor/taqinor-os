"""ENF7 — briques de schéma OpenAPI partagées de ``records`` (et de ``ged``).

* ``CibleModelField`` : « app.modele » parmi ``ALLOWED_TARGETS``. L'énumération
  est résolue PARESSEUSEMENT, au moment de la génération du schéma (le registre
  de cibles ARC30 n'est pas prêt à l'import des vues) via l'extension
  ci-dessous.
* ``CibleQuerySerializer`` : paramètres de requête ``model`` + ``id`` lus par les
  listes filtrées par cible.
* ``CibleBodySerializer`` : corps ``{model, id}`` des créations rattachées à une
  cible.
"""
from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from rest_framework import serializers


def cibles_autorisees():
    """Libellés « app.modele » triés des cibles autorisées (registre ARC30)."""
    from .models import ALLOWED_TARGETS
    return sorted(f'{app}.{model}' for app, model in ALLOWED_TARGETS)


class ParsersParActionMixin:
    """D2 (fondateur 09/10) — JSON seul par défaut, multipart réservé aux actions
    qui reçoivent un fichier (``parsers_par_action = {'create': [...]}``).

    DRF résout les parseurs AVANT de poser ``self.action`` : on le pose donc
    plus tôt (même valeur que ``ViewSetMixin.initialize_request``). Le schéma
    OpenAPI (qui renseigne ``view.action`` lui-même) lit les mêmes parseurs."""
    parsers_par_action = {}

    def initialize_request(self, request, *args, **kwargs):
        if getattr(self, 'action_map', None) is not None:
            methode = request.method.lower()
            self.action = ('metadata' if methode == 'options'
                           else self.action_map.get(methode))
        return super().initialize_request(request, *args, **kwargs)

    def get_parsers(self):
        classes = self.parsers_par_action.get(getattr(self, 'action', None))
        if classes is None:
            return super().get_parsers()
        return [parser() for parser in classes]


class CibleModelField(serializers.CharField):
    """« app.modele » d'une cible autorisée (enum résolu à la génération)."""


class CibleModelFieldExtension(OpenApiSerializerFieldExtension):
    target_class = 'apps.records.openapi.CibleModelField'

    def map_serializer_field(self, auto_schema, direction):
        return {'type': 'string', 'enum': cibles_autorisees()}


class CibleQuerySerializer(serializers.Serializer):
    """Filtre de liste par cible : les deux paramètres vont ensemble."""
    model = CibleModelField(
        required=False,
        help_text="Cible « app.modele » (avec ``id``).")
    id = serializers.IntegerField(
        required=False, help_text="Identifiant de la cible (avec ``model``).")


class CibleBodySerializer(serializers.Serializer):
    """Corps de création rattaché à une cible."""
    model = CibleModelField(help_text="Cible « app.modele ».")
    id = serializers.IntegerField(help_text="Identifiant de la cible.")


class SourceApprobationField(serializers.CharField):
    """Source d'approbation de « Ma file » (enum résolu à la génération)."""


class SourceApprobationFieldExtension(OpenApiSerializerFieldExtension):
    target_class = 'apps.records.openapi.SourceApprobationField'

    def map_serializer_field(self, auto_schema, direction):
        from apps.reporting import approbations as appro
        return {'type': 'string', 'enum': sorted(appro._SOURCE_LOADERS)}


def paginee(nom, serializer):
    """Enveloppe de pagination ``count/next/previous/results`` (vues
    fonctionnelles, que drf-spectacular ne pagine pas automatiquement)."""
    from drf_spectacular.utils import inline_serializer
    return inline_serializer(nom, {
        'count': serializers.IntegerField(),
        'next': serializers.URLField(allow_null=True),
        'previous': serializers.URLField(allow_null=True),
        'results': serializer(many=True),
    })
