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

#: Dépôt de FICHIER : multipart seul. ``FormParser`` (urlencoded) faisait
#: publier un second type de média où ``file`` ne peut pas être un fichier :
#: api-fuzz 24/10 envoyait ``file=`` (texte) et recevait « Fichier requis ».
UPLOAD_PARSERS = [MultiPartParser]
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


class CorpsObjetMixin:
    """api-fuzz-full 27/10 (ENF11) — toute ÉCRITURE de la vue lit un corps
    OBJET (``request.data.get``) : un nombre, ``null`` ou un tableau en corps
    faisait lever ``AttributeError`` (500) dans chaque action → 400 FR dès
    ``initial`` (après les permissions). Corps vide et formulaire multipart
    restent des objets."""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if (request.method in ('POST', 'PUT', 'PATCH')
                and getattr(self, 'action', None) is not None):
            corps_objet(request)


def id_entier(valeur, nom):
    """Identifiant entier 1..ID_MAX (``int`` ou chaîne de chiffres), sinon
    400 nommant le champ — évite ``TypeError``/``DataError`` côté ORM."""
    if (isinstance(valeur, bool) or not isinstance(valeur, (int, str))
            or (isinstance(valeur, str) and not (
                valeur.strip().isascii() and valeur.strip().isdigit()))
            or not 1 <= int(valeur) <= ID_MAX):
        raise ValidationError({nom: 'Identifiant entier valide requis.'})
    return int(valeur)


def id_ou_none(valeur):
    """api-fuzz-full 27/10 (ENF11) — l'identifiant de corps transmis au filtre
    ORM : un entier JSON (ou une chaîne de chiffres) 1..``ID_MAX``, sinon
    ``None`` (aucune ligne ne correspond). Une liste ou un objet faisait lever
    ``TypeError`` dans ``filter(id=…)`` (500) ; ``statut_inconnu`` rend ensuite
    le 404 (entier) ou le 400 (corps invalide)."""
    if isinstance(valeur, str) and valeur.isascii() and valeur.isdigit():
        valeur = int(valeur)
    if isinstance(valeur, int) and not isinstance(valeur, bool) and 1 <= valeur <= ID_MAX:
        return valeur
    return None


def id_corps(request, nom):
    """api-fuzz-full 28/10 (ENF11) — identifiant FACULTATIF du champ de corps
    ``nom``, publié entier : ``null``/absent → ``None`` ; un entier hors
    1..``ID_MAX`` ne désigne aucune ligne (``None``) ; tout autre type (liste,
    objet, booléen, texte) → 400 nommant le champ — une liste atteignait
    ``filter(id=…)`` (``TypeError``, 500)."""
    valeur = corps_objet(request).get(nom)
    if valeur is None:
        return None
    if isinstance(valeur, bool) or not isinstance(valeur, int):
        raise ValidationError({nom: 'Identifiant entier attendu.'})
    return valeur if 1 <= valeur <= ID_MAX else None


def champ_requis(request, nom):
    """api-fuzz-full 27/10 (ENF11) — valeur du champ de corps OBLIGATOIRE
    ``nom`` (``null`` compris, s'il est publié nullable) ; absent → 400 nommant
    le champ (le schéma le publie ``required``)."""
    corps = corps_objet(request)
    if nom not in corps:
        raise ValidationError({nom: 'Ce champ est obligatoire.'})
    return corps[nom]


def choix_corps(request, nom, choix, defaut):
    """api-fuzz-full 27/10 (ENF11) — valeur du champ de corps ``nom`` parmi
    ``choix`` (``defaut`` si absent) ; toute autre valeur → 400 nommant le
    champ (une chaîne libre était écrite telle quelle en base)."""
    valeur = corps_objet(request).get(nom, defaut)
    if valeur not in list(choix):
        raise ValidationError({nom: f"Valeur attendue parmi : {', '.join(choix)}."})
    return valeur


def statut_inconnu(valeur, attendu=int):
    """ENF11 — statut d'un identifiant de corps qui ne désigne rien : 404 pour
    une valeur du type publié (``attendu`` : entier JSON, ou chaîne pour une
    clé), bien formée mais absente ; 400 sinon (corps invalide)."""
    from rest_framework import status
    if isinstance(valeur, attendu) and not isinstance(valeur, bool):
        return status.HTTP_404_NOT_FOUND
    return status.HTTP_400_BAD_REQUEST


def statut_ligne_non_supprimable(ligne, valeur):
    """api-fuzz-full 27/10 (ENF11) — ``supprimer-ligne-consommation`` : une
    ligne INCONNUE suit ``statut_inconnu`` (404 pour un id entier) ; une ligne
    de la NOMENCLATURE (elle existe, l'état stocké s'oppose) = 409."""
    from rest_framework import status
    if ligne is None:
        return statut_inconnu(valeur)
    return status.HTTP_409_CONFLICT


def statut_refus_releve(refus):
    """api-fuzz-full 27/10 (ENF11) — statut d'un refus de
    ``field_capture.champs_releve_serie`` : « ni produit ni désignation » est
    une règle d'ENSEMBLE (l'un OU l'autre de deux champs facultatifs, que le
    schéma OpenAPI 3.0 du corps ne porte pas) → 409 ; des caractéristiques
    illisibles restent un 400 (forme du champ)."""
    from rest_framework import status
    if 'designation' in refus:
        return status.HTTP_409_CONFLICT
    return status.HTTP_400_BAD_REQUEST


def texte_corps(request, nom, *autres):
    """api-fuzz-full 27/10 (ENF11) — valeur TEXTE du champ de corps ``nom``
    (``''`` si absent ou nul), sans espaces de bord. ``nom`` et ``autres``
    (lus ensuite par la vue) sont publiés chaînes : un nombre JSON, ou une
    PARTIE FICHIER multipart sous ce nom, faisait lever ``.strip()`` (500) →
    400 nommant le champ. Le caractère nul (refusé par PostgreSQL, motif publié
    par ``ChaineStricte``) aussi : 400, plus un 500 à l'écriture."""
    corps = corps_objet(request)
    for cle in (nom, *autres):
        valeur = corps.get(cle)
        if valeur is not None and (not isinstance(valeur, str) or chr(0) in valeur):
            raise ValidationError({cle: 'Texte attendu (sans caractère nul).'})
    return (corps.get(nom) or '').strip()


#: Plus grand pourcentage qu'une colonne ``DecimalField(5, 2)`` sait garder.
PCT_MAX = 999.99


def seuil_pct(valeur, nom, defaut=20):
    """Pourcentage 0..``PCT_MAX`` (nombre JSON), ``defaut`` si absent ; sinon
    400 nommant le champ — au-delà, la colonne (5, 2) débordait (500)."""
    if valeur is None:
        return defaut
    if (isinstance(valeur, bool) or not isinstance(valeur, (int, float))
            or not 0 <= valeur <= PCT_MAX):
        raise ValidationError({nom: f'Pourcentage entre 0 et {PCT_MAX} attendu.'})
    return float(valeur)


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


#: api-fuzz-full 27/10 (ENF11) — quantité d'une colonne ``DecimalField(12, 2)``
#: (lignes de consommation) : au plus 10 chiffres entiers et 2 décimales. La
#: borne est PUBLIÉE et APPLIQUÉE à l'identique (``quantite_bornee``) — une
#: quantité de 1e15 débordait la colonne (``DataError`` → 500).
QTE_MAX_TEXTE = '9999999999.99'
MOTIF_QUANTITE = r'^-?\d{1,10}(\.\d{1,2})?$'
QUANTITE_BORNEE = {'oneOf': [
    {'type': 'number', 'minimum': -float(QTE_MAX_TEXTE), 'maximum': float(QTE_MAX_TEXTE)},
    {'type': 'string', 'pattern': MOTIF_QUANTITE}]}


@extend_schema_field(QUANTITE_BORNEE)
class QuantiteBornee(serializers.CharField):
    """Champ de DÉCLARATION : quantité bornée (nombre ou chaîne décimale)."""


def qte(required=False, null=False, **kw):
    return QuantiteBornee(
        required=required, allow_null=null, allow_blank=False, **kw)


def quantite_bornee(request, nom, defaut='0'):
    """``Decimal`` du champ de corps ``nom`` (``defaut`` si absent ou nul),
    accepté EXACTEMENT comme ``QUANTITE_BORNEE`` le publie ; sinon 400 nommant
    le champ."""
    from decimal import Decimal, InvalidOperation
    valeur = corps_objet(request).get(nom)
    if valeur is None:
        return Decimal(defaut)
    quantite = None
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
        try:
            quantite = Decimal(str(valeur))
        except InvalidOperation:
            quantite = None
    elif isinstance(valeur, str) and re.fullmatch(MOTIF_QUANTITE, valeur):
        quantite = Decimal(valeur)
    if (quantite is None or not quantite.is_finite()
            or abs(quantite) > Decimal(QTE_MAX_TEXTE)):
        raise ValidationError({nom: f'Quantité décimale attendue (au plus {QTE_MAX_TEXTE}).'})
    return quantite


#: api-fuzz-full 27/10 (ENF11) — ``caracteristiques`` publiées comme
#: ``field_capture.valider_caracteristiques`` les accepte : objet plat d'au
#: plus 10 clés, valeurs texte (sans NUL) ou nombre — le DictField libre
#: annonçait toute valeur (une liste « conforme » était refusée 400).
CARACTERISTIQUES = {
    'type': 'object', 'nullable': True, 'maxProperties': 10,
    'additionalProperties': {'oneOf': [
        {'type': 'string', 'pattern': MOTIF_SANS_NUL}, {'type': 'number'}]}}


@extend_schema_field(CARACTERISTIQUES)
class Caracteristiques(serializers.DictField):
    """Champ de DÉCLARATION : caractéristiques de plaque."""


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
    """N13 — {[fournisseur], [fournisseurs], [produits]} (revue chantier
    26/10/2026) : ``fournisseur`` id imposé aux lignes sans surcharge (sinon
    le moins cher / le catalogue) ; ``fournisseurs`` = ``{"<produit_id>":
    <fournisseur_id>}`` ; ``produits`` = ids à commander (défaut : tous)."""
    fournisseur = serializers.IntegerField(
        min_value=1, max_value=ID_MAX, required=False)
    fournisseurs = serializers.DictField(
        child=serializers.IntegerField(min_value=1, max_value=ID_MAX),
        required=False)
    produits = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=ID_MAX),
        required=False, max_length=500)

    def validate(self, attrs):
        """api-fuzz-full 27/10 (ENF11) : la forme des CLÉS de ``fournisseurs``
        (identifiant de produit) est inexprimable au schéma OpenAPI 3.0 (pas
        de ``propertyNames``) — refus 409 (même corps), APRÈS les refus de
        forme 400 des champs (``validate`` ne court que sur un corps valide)."""
        for cle in attrs.get('fournisseurs') or {}:
            try:
                ok = 1 <= int(str(cle)) <= ID_MAX
            except (TypeError, ValueError):
                ok = False
            if not ok:
                raise ConflitEtat({'fournisseurs': [
                    f"Clé « {cle} » : identifiant de produit attendu."]})
        return attrs


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


def signature_publiee():
    """api-fuzz-full 27/10 (ENF11) — ``signature_client`` d'une intervention
    (FG69) : la data-URL que ``erreur_signature_client`` accepte, PUBLIÉE par
    le même motif que le chantier (une chaîne libre était « conforme » puis
    refusée 400). Le serveur ne décode pas l'image : motif = acceptation."""
    return ChaineStricte(validators=[SignatureDataUrl()])


def designation_ligne():
    """api-fuzz-full 27/10 (ENF11) — ``designation`` d'une ligne de
    consommation hors nomenclature (F11) : obligatoire, non blanche, sans NUL,
    255 caractères au plus (la colonne). Un corps ``{}`` était « conforme »
    (champ facultatif au schéma) puis refusé « Désignation requise » (400)."""
    return ChaineStricte(max_length=255)


class DesignationLigneRequete(serializers.Serializer):
    """F11 — la validation de ``designation`` : le MÊME champ que la
    déclaration du corps d'``ajouter-ligne-consommation``."""
    designation = designation_ligne()


class NombreStrict(serializers.FloatField):
    """Nombre JSON réel : ``"33.5"`` et ``true`` sont refusés (400), comme le
    type ``number`` publié."""

    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, (int, float)):
            self.fail('invalid')
        return super().to_internal_value(data)


class PositionRequete(serializers.Serializer):
    """F6/XFSM7 — ``{lat, lng}`` du départ dépôt et du check-in : la
    déclaration OpenAPI ET la validation. api-fuzz-full 27/10 (ENF11) : bornes
    géographiques PUBLIÉES (−90..90, −180..180) — ``lat = 1e142`` débordait la
    colonne ``numeric(9, 6)`` (``DataError`` → 500)."""
    lat = NombreStrict(required=False, allow_null=True,
                       min_value=-90, max_value=90)
    lng = NombreStrict(required=False, allow_null=True,
                       min_value=-180, max_value=180)


def position(request):
    """``(lat, lng)`` validés par ``PositionRequete`` (400 nommant le champ)."""
    corps = corps_valide(PositionRequete, request)
    return corps.get('lat'), corps.get('lng')


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
