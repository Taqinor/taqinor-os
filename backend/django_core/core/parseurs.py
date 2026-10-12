"""ENFP (décision fondateur D2 du 09/10/2026) — les vues SANS fichier
n'acceptent que du JSON ; le multipart reste réservé aux vues d'upload.

Constat (api-fuzz du 09/10, cluster D2, 51 constats) : le défaut DRF
(``JSONParser`` + ``FormParser`` + ``MultiPartParser``) fait accepter à TOUTE
vue un corps ``multipart/form-data`` dont les booléens arrivent en chaînes
(``"false"`` coercé selon des règles de formulaire HTML), alors que le schéma
OpenAPI ne publie que ``application/json`` pour elle.

Pourquoi le DÉFAUT GLOBAL n'est PAS basculé en JSON seul (ENFP, 09/10) : au
moins 16 modules lisent ``request.FILES`` sans déclarer leurs parseurs (ils
s'appuient sur le défaut DRF) — les basculer en JSON seul casserait leurs
uploads. La liste est dans le rapport ENFP ; une fois que chaque vue d'upload
déclare ``parser_classes = PARSEURS_UPLOAD`` (ou ``ParseursUploadMixin``), le
défaut ``REST_FRAMEWORK['DEFAULT_PARSER_CLASSES']`` pourra passer à
``PARSEURS_JSON``.

Usage (lanes par app) :

* vue sans fichier : ``parser_classes = PARSEURS_JSON`` ou hériter de
  ``JsonSeulementMixin`` ; un corps multipart reçoit alors un 415
  ``unsupported_media_type`` (enveloppe ``core.exceptions``) ;
* vue d'upload : ``parser_classes = PARSEURS_UPLOAD`` ou hériter de
  ``ParseursUploadMixin`` (comportement actuel, rendu EXPLICITE) ;
* ``@action`` : ``@action(..., parser_classes=PARSEURS_UPLOAD)``.

Tuples (immuables) : une sous-classe ne peut pas muter la liste partagée.
"""
from __future__ import annotations

from rest_framework import serializers
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

PARSEURS_JSON = (JSONParser,)
PARSEURS_UPLOAD = (JSONParser, MultiPartParser, FormParser)


class JsonSeulementMixin:
    """Vue sans fichier : corps JSON uniquement (D2)."""

    parser_classes = PARSEURS_JSON


class ParseursUploadMixin:
    """Vue d'upload : JSON + multipart + formulaire, déclarés explicitement."""

    parser_classes = PARSEURS_UPLOAD


def corps_valide(request, schema, **contexte):
    """ERR-ENF11-FUZZ-CORE — corps validé par le serializer DÉCLARÉ au schéma.

    Constat api-fuzz du 11/10 : des vues sans serializer de requête lisaient
    ``(request.data or {}).get(…)`` — un corps tableau (``[null, null]``)
    levait ``AttributeError`` (500) et un champ de mauvais type passait
    jusqu'au moteur. ``schema`` est l'objet passé à ``@extend_schema(
    request=…)`` (``inline_serializer`` ou serializer) : la vue valide
    exactement ce qu'elle publie (documenté == accepté) et répond 400
    ``validation_error`` par champ sinon. Renvoie ``validated_data``.
    """
    classe = schema if isinstance(schema, type) else type(schema)
    serializer = classe(data=request.data, context={'request': request,
                                                    **contexte})
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


class ChoixDocumente(serializers.ChoiceField):
    """ERR-ENF11-FUZZ-CORE — ``ChoiceField`` dont l'énumération est publiée
    SANS composant d'énum partagé (``allOf: [{enum: …}]``).

    Un ``ChoiceField`` ordinaire devient un composant ``<Prop>Enum`` : quand le
    même nom de propriété porte déjà un autre jeu (``code``, ``trigger_type``…),
    ``postprocess_schema_enums`` renomme TOUS les composants concernés et lève
    un avertissement de collision. Ici l'énum reste en ligne : le schéma dit
    exactement les valeurs acceptées sans toucher aux noms existants.
    L'annotation est posée dans ``__init__`` : elle survit au ``deepcopy`` des
    champs déclarés (DRF ré-instancie le champ avec ses arguments).
    """

    def __init__(self, choices, **kwargs):
        from drf_spectacular.drainage import set_override

        valeurs = list(choices)
        super().__init__(choices=valeurs, **kwargs)
        set_override(self, 'field', {
            'type': 'string', 'allOf': [{'enum': valeurs}]})


class ObjetJSON(serializers.JSONField):
    """ERR-ENF11-FUZZ-CORE — ``JSONField`` limité à un OBJET JSON.

    drf-spectacular publie un ``JSONField`` en schéma vide ``{}`` : ``null``
    y est conforme, alors qu'un champ de modèle non nul le refuse (« Ce champ
    ne peut être nul. ») — requête conforme refusée. Ce champ publie
    ``type: object`` (``nullable`` seulement si ``allow_null``) et refuse en
    400 tout ce qui n'est pas un objet (liste, nombre…).
    """

    def __init__(self, **kwargs):
        from drf_spectacular.drainage import set_override

        super().__init__(**kwargs)
        schema = {'type': 'object', 'additionalProperties': True}
        if self.allow_null:
            schema['nullable'] = True
        set_override(self, 'field', schema)

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError('Un objet JSON est attendu.')
        return super().to_internal_value(data)
