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
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from core.champs_stricts import BooleenStrict, ChaineStricte, EntierStrict, date_ou_400

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


#: ERR-ENF11-FUZZ-INSTALLATIONS — décimal tel que les vues le LISENT
#: (``Decimal(str(x))``) : un nombre JSON ou une chaîne décimale.
DECIMAL_SOUPLE = {'oneOf': [
    {'type': 'number'}, {'type': 'string', 'pattern': r'^-?\d+(\.\d+)?$'}]}


@extend_schema_field(DECIMAL_SOUPLE)
class DecimalSouple(serializers.CharField):
    """Champ de DÉCLARATION (corps lus à la main) : nombre ou chaîne décimale."""


def dec(required=False, null=False, **kw):
    # Décimal accepté en nombre OU en chaîne par le code (Decimal(str(x))) :
    # le schéma le dit (il annonçait une chaîne libre, nombre exclu).
    return DecimalSouple(
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


# ── ERR-ENF11-FUZZ-INSTALLATIONS : paramètres de requête publiés = lus ──────
#: Identifiant de requête : ses bornes RÉELLES (``0`` n'est pas un id).
ID_SCHEMA = {'type': 'integer', 'minimum': 1, 'maximum': ID_MAX}
#: Filtre d'identifiant : un id, ou la chaîne vide (= filtre non posé).
ID_OU_VIDE = {'oneOf': [ID_SCHEMA, {'type': 'string', 'enum': ['']}]}
#: Date ISO, ou la chaîne vide (= borne non posée, défaut de la vue).
DATE_OU_VIDE = {'oneOf': [
    {'type': 'string', 'format': 'date'}, {'type': 'string', 'enum': ['']}]}


def qid(name, **kw):
    return q(name, ID_SCHEMA, **kw)


#: Nombre, ou la chaîne vide (= valeur par défaut de la vue).
NOMBRE_OU_VIDE = {'oneOf': [{'type': 'number'}, {'type': 'string', 'enum': ['']}]}


def qfv(name, **kw):
    return q(name, NOMBRE_OU_VIDE, **kw)


def qidv(name, **kw):
    return q(name, ID_OU_VIDE, **kw)


def qdv(name, **kw):
    return q(name, DATE_OU_VIDE, **kw)


def id_requete(request, nom, requis=False):
    """Identifiant du paramètre ``nom`` : absent ou vide → ``None`` (400 si
    ``requis``) ; toute autre forme qu'un entier 1..ID_MAX → 400 nommant le
    paramètre (``abc`` faisait un 500 ORM, ``null`` était ignoré)."""
    brut = request.query_params.get(nom)
    if brut is None or brut == '':
        if requis:
            raise ValidationError({nom: 'Paramètre requis.'})
        return None
    return id_entier(brut, nom)


def _valider_filtres(request, entiers, dates):
    for nom in entiers:
        id_requete(request, nom)
    for nom in dates:
        date_ou_400(request.query_params.get(nom), nom)


def listing(*args, **kw):
    """``extend_schema_view`` pour la liste : déclare les paramètres lus par
    ``get_queryset``.

    ERR-ENF11-FUZZ-INSTALLATIONS — un filtre entier (``qi``) est publié
    « id 1..ID_MAX ou vide » et une date (``qd``) « date ISO ou vide », puis
    VALIDÉ à l'entrée de la liste (400 nommant le paramètre) : avant, ``abc``
    finissait en 500 ORM et ``null`` était ignoré (200)."""
    params = list(args) + list(kw.values())
    entiers = [p.name for p in params if p.type == OpenApiTypes.INT]
    dates = [p.name for p in params if p.type == OpenApiTypes.DATE]
    for p in params:
        if p.name in entiers:
            p.type = ID_OU_VIDE
        elif p.name in dates:
            p.type = DATE_OU_VIDE
    decorer = extend_schema_view(list=extend_schema(parameters=params))

    def appliquer(cls):
        cls = decorer(cls)
        if entiers or dates:
            initial_parent = cls.initial

            def initial(self, request, *a, **k):
                initial_parent(self, request, *a, **k)
                if getattr(self, 'action', None) == 'list':
                    _valider_filtres(request, entiers, dates)
            cls.initial = initial
        return cls
    return appliquer


# ── ERR-ENF11-FUZZ-INSTALLATIONS : corps VALIDÉS des actions lues à la main ──
# Le sérialiseur est À LA FOIS la déclaration OpenAPI (nom du composant
# inchangé) et la validation : un champ mal typé → 400 le nommant.
def corps_valide(classe, request):
    """Valide ``request.data`` par ``classe`` (400 sinon) et rend ses données."""
    serialiseur = classe(data=request.data)
    serialiseur.is_valid(raise_exception=True)
    return serialiseur.validated_data


def _id_strict(**kw):
    return EntierStrict(min_value=1, max_value=ID_MAX, **kw)


class ReplanifierEnMasseRequete(serializers.Serializer):
    """XFSM3 — {jour, [technicien], [intervention_ids], [simuler], [motif]}."""
    jour = serializers.DateField()
    technicien = _id_strict(required=False, allow_null=True)
    intervention_ids = serializers.ListField(
        child=_id_strict(), required=False, max_length=500)
    simuler = BooleenStrict(required=False, default=False)
    motif = ChaineStricte(required=False, allow_blank=True)


class SuggererCreneauRequete(serializers.Serializer):
    """XFSM2 — {chantier, [type_intervention], [duree_jours], [date_cible]}."""
    chantier = _id_strict()
    type_intervention = ChaineStricte(required=False, allow_blank=True, default='')
    duree_jours = EntierStrict(required=False, min_value=1, max_value=365, default=1)
    date_cible = serializers.DateField(required=False, allow_null=True)


#: Drapeau de requête publié booléen : ces valeurs, rien d'autre.
_DRAPEAUX = {'true': True, '1': True, 'false': False, '0': False}


def drapeau_requete(request, nom):
    """Booléen du paramètre ``nom`` : absent → ``False`` ; ``true``/``1``/
    ``false``/``0`` → sa valeur ; autre forme → 400 nommant le paramètre
    (``null`` était lu « non » en silence)."""
    brut = request.query_params.get(nom)
    if brut is None:
        return False
    if brut.lower() not in _DRAPEAUX:
        raise ValidationError({nom: 'Booléen attendu (true/false).'})
    return _DRAPEAUX[brut.lower()]
