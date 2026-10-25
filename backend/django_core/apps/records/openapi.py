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
    """« app.modele » d'une cible autorisée (enum résolu à la génération).

    ERR-ENF11-FUZZ-RECORDS (2e passe) — à la LECTURE d'un paramètre de requête
    la valeur doit appartenir à l'énumération publiée (``resolve_target``
    tolérait la casse et rendait une liste vide pour le reste : 200 sur un
    paramètre que le schéma déclare invalide)."""
    default_error_messages = {
        'invalid_choice': "« {input} » n'est pas une cible autorisée."}

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail('invalid')
        valeur = super().to_internal_value(data)
        if valeur not in cibles_autorisees():
            self.fail('invalid_choice', input=valeur)
        return valeur


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


def cible_requete_ou_400(request):
    """``(model, id)`` du filtre de cible d'une liste, VALIDÉS selon le schéma
    (``model`` ∈ cibles autorisées, ``id`` entier) : 400 nommant le paramètre
    sinon. Chaque moitié est facultative (comme le schéma) ; sans les deux, le
    filtre n'est pas appliqué."""
    params = request.query_params
    # CI #997 — un paramètre PRÉSENT mais vide (``?model=``, ``?id=``) n'est
    # pas « absent » : 400 nommant le paramètre (le schéma ne publie pas le
    # vide ; DRF lirait ``''`` comme non fourni et servirait la liste entière).
    vides = [nom for nom in ('model', 'id')
             if nom in params and str(params.get(nom, '')).strip() == '']
    if vides:
        raise serializers.ValidationError(
            {nom: ['Ce paramètre ne peut être vide.'] for nom in vides})
    ser = CibleQuerySerializer(data=params)
    ser.is_valid(raise_exception=True)
    return ser.validated_data.get('model'), ser.validated_data.get('id')


def cible_corps_ou_400(data):
    """``(model, id)`` d'un corps de création rattaché à une cible, typés selon
    le schéma : ``model`` chaîne, ``id`` entier (un entier écrit en chaîne reste
    toléré — clients d'écran qui lisent l'id dans l'URL ; un multipart ne
    porte que des chaînes). Booléen, flottant, liste, objet ou chaîne non
    numérique → 400 nommant le champ (ils étaient lus en silence)."""
    model, oid = data.get('model'), data.get('id')
    if model is not None and not isinstance(model, str):
        raise serializers.ValidationError({'model': ['Chaîne attendue.']})
    if model == '':
        # api-fuzz-full 25/10 — ``""`` passait pour « sans cible » (à-faire
        # personnel créé, 201) alors que le schéma n'accepte qu'une cible.
        raise serializers.ValidationError({'model': ['Cible « app.modele » attendue.']})
    if oid is not None:
        if isinstance(oid, str) and oid.isascii() and oid.isdigit():
            oid = int(oid)
        if isinstance(oid, bool) or not isinstance(oid, int):
            raise serializers.ValidationError({'id': ['Entier attendu.']})
    return model, oid


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
