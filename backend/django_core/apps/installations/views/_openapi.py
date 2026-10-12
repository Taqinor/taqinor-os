"""ENF3 — aides de description OpenAPI de l'app installations.

Aucune logique métier : uniquement des fabriques de champs/paramètres pour
que chaque vue décrive EXACTEMENT ce qu'elle lit et renvoie (corps, paramètres
de requête, statuts, binaires).

* ``JsonOnlyMixin`` (décision fondateur D2) : une vue SANS dépôt de fichier
  n'accepte et ne documente que le JSON ; les actions d'upload repassent en
  multipart via ``parser_classes`` sur l'``@action``.
* Les corps/réponses libres sont typés au plus juste : un champ optionnel
  n'est jamais déclaré obligatoire (sinon ACC), un champ réellement exigé par
  le code l'est (sinon REJ).
"""
from collections.abc import Mapping

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (  # noqa: F401  (ré-exportés)
    OpenApiParameter, extend_schema, extend_schema_view, inline_serializer,
)
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

UPLOAD_PARSERS = [MultiPartParser, FormParser]
JSON_AND_UPLOAD_PARSERS = [JSONParser, MultiPartParser, FormParser]


class JsonOnlyMixin:
    """D2 — JSON seulement (les actions d'upload surchargent ``parser_classes``)."""
    parser_classes = [JSONParser]


# ── lecture défensive d'un corps libre (ENF11 : jamais de 500 sur entrée absurde)
ID_MAX = 2147483647  # borne d'une clé primaire entière PostgreSQL


def corps_objet(request):
    """Corps JSON de type objet, sinon 400 FR (un tableau/une chaîne en corps
    faisait lever ``AttributeError`` sur ``.get``)."""
    if not isinstance(request.data, Mapping):
        raise ValidationError({'detail': 'Corps JSON de type objet attendu.'})
    return request.data


def id_entier(valeur, nom):
    """Identifiant entier 1..ID_MAX (``int`` ou chaîne de chiffres), sinon
    400 nommant le champ — évite ``TypeError``/``DataError`` côté ORM."""
    if (isinstance(valeur, bool) or not isinstance(valeur, (int, str))
            or (isinstance(valeur, str) and not valeur.strip().isdigit())
            or not 1 <= int(valeur) <= ID_MAX):
        raise ValidationError({nom: 'Identifiant entier valide requis.'})
    return int(valeur)


def ids_entiers(valeur, nom, maxi=500):
    """Liste NON vide d'identifiants entiers valides, sinon 400."""
    if not isinstance(valeur, list) or not 1 <= len(valeur) <= maxi:
        raise ValidationError(
            {nom: f'Liste de 1 à {maxi} identifiants entiers attendue.'})
    return [id_entier(v, nom) for v in valeur]


# ── champs de corps / de réponse ──────────────────────────────────────────────
def i(required=False, null=False, **kw):
    return serializers.IntegerField(
        required=required, allow_null=null, **kw)


def s(required=False, null=False, **kw):
    return serializers.CharField(
        required=required, allow_null=null, allow_blank=not required, **kw)


def b(required=False, **kw):
    return serializers.BooleanField(required=required, **kw)


def f(required=False, null=False, **kw):
    return serializers.FloatField(required=required, allow_null=null, **kw)


def d(required=False, null=False, **kw):
    return serializers.DateField(required=required, allow_null=null, **kw)


def dt(required=False, null=False, **kw):
    return serializers.DateTimeField(required=required, allow_null=null, **kw)


def dec(required=False, null=False, **kw):
    # Décimal accepté en nombre OU en chaîne par le code (Decimal(str(x))).
    return serializers.CharField(
        required=required, allow_null=null, allow_blank=False, **kw)


def obj(required=False, null=False, **kw):
    return serializers.DictField(required=required, allow_null=null, **kw)


def lst(child=None, required=False, null=False, **kw):
    return serializers.ListField(
        child=child or serializers.DictField(), required=required,
        allow_null=null, **kw)


def ints(required=False, **kw):
    return serializers.ListField(
        child=serializers.IntegerField(), required=required, **kw)


def ids(required=False, **kw):
    """Liste non vide d'identifiants entiers 1..ID_MAX (exactement ce que
    ``ids_entiers`` accepte)."""
    return serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=ID_MAX),
        min_length=1, max_length=500, required=required, **kw)


def idf(required=False, **kw):
    """Identifiant entier 1..ID_MAX (exactement ce que ``id_entier`` accepte)."""
    return serializers.IntegerField(
        min_value=1, max_value=ID_MAX, required=required, **kw)


def choice(values, required=False, **kw):
    return serializers.ChoiceField(
        choices=list(values), required=required, **kw)


_BODIES = {}


def body(name, **fields):
    """Sérialiseur de corps/réponse nommé (composant OpenAPI stable). Un même
    nom renvoie TOUJOURS la même classe (sinon collision de composants)."""
    if name not in _BODIES:
        _BODIES[name] = inline_serializer(name, fields=fields)
    return _BODIES[name]


# ── paramètres de requête ─────────────────────────────────────────────────────
def q(name, typ=OpenApiTypes.STR, required=False, enum=None, desc=None,
      **kw):
    extra = {}
    if enum is not None:
        extra['enum'] = list(enum)
    if desc:
        extra['description'] = desc
    return OpenApiParameter(
        name, typ, OpenApiParameter.QUERY, required=required, **extra, **kw)


def qi(name, **kw):
    return q(name, OpenApiTypes.INT, **kw)


def qs(name, **kw):
    return q(name, OpenApiTypes.STR, **kw)


def qd(name, **kw):
    return q(name, OpenApiTypes.DATE, **kw)


def qb(name, **kw):
    return q(name, OpenApiTypes.BOOL, **kw)


def qf(name, **kw):
    return q(name, OpenApiTypes.FLOAT, **kw)


# ── réponses non-JSON ─────────────────────────────────────────────────────────
PDF = {(200, 'application/pdf'): OpenApiTypes.BINARY}
HTML = {(200, 'text/html'): OpenApiTypes.STR}
OBJ = OpenApiTypes.OBJECT
NO_CONTENT = {204: None}


LIST = type(inline_serializer('ObjetLibre', fields={}))(many=True)


def listing(*args, **kw):
    """``extend_schema_view`` pour la liste : déclare les paramètres lus par
    ``get_queryset``."""
    return extend_schema_view(
        list=extend_schema(parameters=list(args) + list(kw.values())))
