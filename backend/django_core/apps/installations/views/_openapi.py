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
import re
from collections.abc import Mapping
from datetime import date, timedelta

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter, extend_schema, extend_schema_view, inline_serializer,
)
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from core.champs_stricts import (
    MOTIF_SANS_NUL, BooleenStrict, ChaineStricte, DateStricte, EntierStrict,
    date_ou_400)
from core.conflit_etat import ConflitEtat

from ..signature_validation import (
    SignatureDataUrl,
)

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
            or (isinstance(valeur, str) and not (
                valeur.strip().isascii() and valeur.strip().isdigit()))
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
#: Lecture sur fenêtre ``debut``/``fin`` : 409 si la fin précède le début
#: (``fenetre_semaine`` — règle d'ensemble, pas un 400).
OBJ_FENETRE = {200: OBJ, 409: OBJ}


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


_NOMBRE = re.compile(r'^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?\Z', re.ASCII)


def nombre_requete(request, nom, defaut=None, mini=None, maxi=None,
                   strict_mini=False):
    """Nombre (``float``) du paramètre ``nom`` : absent ou vide -> ``defaut`` ;
    toute forme qui n'est pas un nombre décimal (``false``, ``nan``, ``1_0``),
    ou hors bornes, -> 400 nommant le paramètre. ``strict_mini`` : ``> mini``."""
    brut = request.query_params.get(nom)
    if brut is None or brut == '':
        return defaut
    valeur = float(brut) if _NOMBRE.match(brut) else None
    if valeur is None or valeur in (float('inf'), float('-inf')):
        raise ValidationError({nom: 'Nombre attendu.'})
    if ((mini is not None and (valeur <= mini if strict_mini else valeur < mini))
            or (maxi is not None and valeur > maxi)):
        raise ValidationError({nom: 'Valeur hors plage.'})
    return valeur


def qnombre(name, mini=None, maxi=None, strict_mini=False, **kw):
    """Paramètre nombre publié AVEC ses bornes réelles (ou la chaîne vide)."""
    nombre = {'type': 'number'}
    if mini is not None:
        nombre['minimum'] = mini
        if strict_mini:
            nombre['exclusiveMinimum'] = True
    if maxi is not None:
        nombre['maximum'] = maxi
    return q(name, {'oneOf': [nombre, {'type': 'string', 'enum': ['']}]}, **kw)


def choix_requete(request, nom, valeurs):
    """Valeur du paramètre ``nom`` parmi ``valeurs`` : absent ou vide ->
    ``None`` ; toute autre valeur -> 400 nommant le paramètre (elle était
    acceptée en silence alors que le schéma publie l'énumération)."""
    brut = request.query_params.get(nom)
    if brut is None or brut == '':
        return None
    if brut not in valeurs:
        raise ValidationError({nom: 'Valeur inconnue.'})
    return brut


def texte_requete(request, nom):
    """Valeur texte du paramètre ``nom`` (``None`` si absent) ; un caractère
    nul fait lever le pilote Postgres (500) -> 400 nommant le paramètre."""
    brut = request.query_params.get(nom)
    if brut is not None and '\x00' in brut:
        raise ValidationError({nom: 'Caractère nul interdit.'})
    return brut


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


#: Longueur maximale (en jours) d'une fenêtre ``debut``/``fin`` de lecture.
FENETRE_MAX_JOURS = 366


def fenetre_semaine(request):
    """``(debut, fin)`` des paramètres ``debut``/``fin`` (ISO) ; défaut = la
    semaine en cours (lundi → dimanche). Une fenêtre inversée (``fin`` avant
    ``debut``) est une règle d'ENSEMBLE que le schéma ne peut pas exprimer :
    409 (conflit), jamais un 400 sur une requête conforme."""
    debut = date_ou_400(request.query_params.get('debut'), 'debut')
    fin = date_ou_400(request.query_params.get('fin'), 'fin')
    if debut is None:
        debut = date.today() - timedelta(days=date.today().weekday())
    if fin is None:
        fin = debut + timedelta(days=6)
    if fin < debut:
        raise ConflitEtat('La fin de fenêtre précède le début.')
    # api-fuzz full : une fenêtre de plusieurs siècles faisait boucler les
    # agrégats (jour par jour) puis déborder (500) : règle d'ensemble, 409.
    if (fin - debut).days > FENETRE_MAX_JOURS:
        raise ConflitEtat(
            f'La fenêtre ne peut pas dépasser {FENETRE_MAX_JOURS} jours.')
    return debut, fin


#: Filtre texte publié SANS caractère nul (``\u0000`` fait lever le pilote
#: Postgres -> 500 : le schéma le disait libre, la liste le refuse en 400).
TEXTE_SANS_NUL = {'type': 'string', 'pattern': MOTIF_SANS_NUL}


def _valider_filtres(request, entiers, dates, textes=()):
    for nom in entiers:
        id_requete(request, nom)
    for nom in dates:
        date_ou_400(request.query_params.get(nom), nom)
    for nom in textes:
        if any('\x00' in v for v in request.query_params.getlist(nom)):
            raise ValidationError({nom: 'Caractère nul interdit.'})


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
    textes = [p.name for p in params if p.type == OpenApiTypes.STR]
    for p in params:
        if p.name in entiers:
            p.type = ID_OU_VIDE
        elif p.name in dates:
            p.type = DATE_OU_VIDE
        elif p.name in textes and not p.enum:
            p.type = TEXTE_SANS_NUL
    decorer = extend_schema_view(list=extend_schema(parameters=params))

    def appliquer(cls):
        cls = decorer(cls)
        if entiers or dates or textes:
            initial_parent = cls.initial

            def initial(self, request, *a, **k):
                initial_parent(self, request, *a, **k)
                if getattr(self, 'action', None) == 'list':
                    _valider_filtres(request, entiers, dates, textes)
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
    jour = DateStricte()
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


class AjouterReserveRequete(serializers.Serializer):
    """F16 — {description, [client_op_id], [assignee], [photo], [memo],
    [creer_suivi], [creer_ticket]} : la déclaration OpenAPI ET la validation
    (corps vide ou mal typé → 400, ``description`` exigée)."""
    client_op_id = ChaineStricte(required=False, allow_blank=True, max_length=64)
    description = ChaineStricte()
    assignee = _id_strict(required=False, allow_null=True)
    photo = _id_strict(required=False, allow_null=True)
    memo = _id_strict(required=False, allow_null=True)
    creer_suivi = BooleenStrict(required=False)
    creer_ticket = BooleenStrict(required=False)


# ── api-fuzz full : corps validés des actions de chantier lues à la main ──
class NoterRequete(serializers.Serializer):
    """Note libre du chatter (chantier, intervention, ordre d'assemblage) :
    texte non blanc, sans caractère nul (il faisait lever la base -> 500)."""
    body = ChaineStricte()


class AnnulerChantierRequete(serializers.Serializer):
    """Annulation d'un chantier : ``motif`` facultatif (un chantier non clôturé
    s'annule sans motif), texte seulement (un nombre faisait lever ``strip``)."""
    motif = ChaineStricte(required=False, allow_blank=True)


class LigneEquipementRequete(serializers.Serializer):
    """Ligne de série d'une checklist : une ligne sans ``produit`` est ignorée.
    ``numero_serie`` <= 120 signes (colonne ``Equipement.numero_serie``)."""
    produit = serializers.IntegerField(
        min_value=1, max_value=ID_MAX, required=False)
    numero_serie = ChaineStricte(
        required=False, allow_blank=True, max_length=120)


class CocherChecklistRequete(serializers.Serializer):
    """N4/N9 — {cle, [fait], [equipements]} : déclaration ET validation."""
    cle = ChaineStricte()
    fait = BooleenStrict(required=False)
    equipements = serializers.ListField(
        child=LigneEquipementRequete(), required=False, max_length=500)


class LigneSerieRequete(serializers.Serializer):
    """CIQ633 — une ligne de l'import en lot des séries."""
    produit = serializers.IntegerField(
        min_value=1, max_value=ID_MAX, required=False)
    numero_serie = ChaineStricte(
        required=False, allow_blank=True, max_length=120)
    chaine = ChaineStricte(required=False, allow_blank=True)


class NonReleveRequete(serializers.Serializer):
    """CIQ633 — produit « non relevé » + motif (un motif vide retire l'entrée)."""
    produit = serializers.IntegerField(
        min_value=1, max_value=ID_MAX, required=False)
    motif = ChaineStricte(required=False, allow_blank=True)


class SeriesLotCorpsJson(serializers.Serializer):
    """CIQ633 — import en lot des numéros de série, corps JSON."""
    lignes = serializers.ListField(
        child=LigneSerieRequete(), required=False, max_length=500)
    texte = ChaineStricte(required=False, allow_blank=True)
    produit = serializers.IntegerField(
        min_value=1, max_value=ID_MAX, required=False, allow_null=True)
    non_releves = serializers.ListField(
        child=NonReleveRequete(), required=False, max_length=500)


class SeriesLotRequete(SeriesLotCorpsJson):
    """CIQ633 — import en lot (JSON ou fichier) : la validation serveur."""
    fichier = serializers.FileField(required=False, allow_empty_file=True)


class SeriesLotCorpsFichier(serializers.Serializer):
    """CIQ633 — import en lot par FICHIER (multipart) : ``fichier`` porte le
    CSV ; ``lignes``/``non_releves`` (listes d'objets) ne s'envoient qu'en
    JSON. Un ``fichier`` en JSON est refusé (400 « pas un fichier »)."""
    fichier = serializers.FileField()
    produit = serializers.IntegerField(
        min_value=1, max_value=ID_MAX, required=False)


class CommanderBesoinRequete(serializers.Serializer):
    """N13 — {[fournisseur]} : id entier 1..ID_MAX (sinon fournisseur par défaut)."""
    fournisseur = serializers.IntegerField(
        min_value=1, max_value=ID_MAX, required=False)


def _origines_reserve():
    from ..models import Reserve
    return list(Reserve.Origine.values)


class ReserveChantierRequete(serializers.Serializer):
    """CIQ628 — réserve posée sur le chantier : déclaration ET validation."""
    description = ChaineStricte()
    origine = serializers.ChoiceField(
        choices=_origines_reserve(), required=False)
    bloquante = BooleenStrict(required=False)
    date_echeance = DateStricte(required=False, allow_null=True)
    responsable = ChaineStricte(required=False, allow_blank=True)


#: Réponse de ``tool-return`` (GET et POST) : la LISTE des lignes de retour,
#: ou — quand un outil est déjà sorti sur une autre intervention — l'objet
#: ``{tool_returns, conflits}``. Deux formes, ``oneOf`` (le schéma annonçait
#: un objet seul alors que la liste est la forme ordinaire).
_LIGNES_RETOUR = {'type': 'array',
                  'items': {'$ref': '#/components/schemas/ToolReturn'}}
RETOUR_OUTILLAGE = {200: {'oneOf': [_LIGNES_RETOUR, {
    'type': 'object',
    'properties': {
        'tool_returns': _LIGNES_RETOUR,
        'conflits': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'outil': {'type': 'integer'},
                           'intervention': {'type': 'integer', 'nullable': True}},
            'required': ['outil', 'intervention']}}},
    'required': ['tool_returns', 'conflits']}]}}


class CocherToolReturnRequete(serializers.Serializer):
    """F17 — {ligne, [rendu], [emplacement]} : la déclaration OpenAPI ET la
    validation (``ligne`` mal typée faisait un 500 ORM)."""
    ligne = _id_strict()
    rendu = BooleenStrict(required=False, default=True)
    emplacement = _id_strict(required=False, allow_null=True)


def _texte_facultatif():
    return ChaineStricte(required=False, allow_blank=True, allow_null=True)


class SignerChantierRequete(serializers.Serializer):
    """NTMOB16/CIQ631 — signature client du bon de livraison : la data-URL
    acceptée est PUBLIÉE (motif + longueur), les autres champs sont des textes
    facultatifs (``null`` toléré = vide, comme le lisait la vue)."""
    signature_client = ChaineStricte(validators=[SignatureDataUrl()])
    signataire_nom = _texte_facultatif()
    motif_override_signature = _texte_facultatif()
    motif_override = _texte_facultatif()
    signataire_fonction = _texte_facultatif()
    signataire_societe = _texte_facultatif()
    cosignataire_nom = _texte_facultatif()
    cosignataire_fonction = _texte_facultatif()
    cosignataire_organisme = _texte_facultatif()


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
