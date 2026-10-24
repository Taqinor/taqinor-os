"""ENF11 — champs de sérialiseur qui REFUSENT la coercition silencieuse.

``serializers.CharField`` accepte un entier ou un booléen et le convertit en
chaîne (``0`` → ``"0"``) : l'API acceptait alors une donnée que son schéma
OpenAPI déclare invalide (constat api-fuzz « accepted schema-violating
request »). ``ChaineStricte`` répond 400 tant que la valeur n'est pas déjà une
chaîne ; le comportement d'une requête valide est inchangé.
"""
import re
from datetime import date

from django.db import models
from django.core import validators as _validateurs
from django.core.exceptions import ValidationError as _ErreurDjango
from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from rest_framework import serializers
from rest_framework.fields import SkipField, empty


class ChaineStricte(serializers.CharField):
    """``CharField`` qui n'accepte que de vraies chaînes JSON."""

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail('invalid')
        return super().to_internal_value(data)


#: Motif publié d'une chaîne SANS caractère nul : DRF refuse ``\u0000`` dans
#: tout ``CharField`` (``ProhibitNullCharactersValidator``) alors que le schéma
#: l'autorisait — le fuzz envoyait une chaîne « conforme » et recevait 400.
MOTIF_SANS_NUL = r'^[^\u0000]*$'
#: CI #997 (2) — « non blanc » au sens de DRF (``str.strip``) : le validateur
#: du schéma (regex Rust) ne compte pas ``\u001c``-``\u001f`` dans ``\s``,
#: Python si — ``"\u001c"`` seul était publié conforme puis refusé « vide ».
MOTIF_NON_BLANC_SANS_NUL = r'^[^\u0000]*[^\s\u0000\u001c-\u001f][^\u0000]*$'


def non_blanc(texte):
    """Vrai si la chaîne ``texte`` porte un caractère ni blanc (``str.strip``)
    ni nul — la règle de ``MOTIF_NON_BLANC_SANS_NUL``."""
    return any(not c.isspace() and c != '\u0000' for c in texte)


#: Validateurs dont drf-spectacular publie lui-même le motif/format.
_VALIDATEURS_PUBLIES = (
    _validateurs.RegexValidator, _validateurs.EmailValidator,
    _validateurs.URLValidator, _validateurs.FileExtensionValidator)


#: Sous-ensemble sûr des URL que ``URLValidator`` accepte (http(s), hôte à
#: points, chemin simple) ; vide permis (champ facultatif).
MOTIF_URL_HTTP = r'^(|https?://[a-z]{1,10}\.[a-z]{2,10}(/[A-Za-z0-9._~/-]*)?)$'


#: URL « souple » (IdP SSO : ports, requêtes, hôtes à étiquettes longues) :
#: http(s), puis au moins un signe ni blanc ni de contrôle ; vide permis.
#: C'est LE MÊME prédicat côté serveur (``UrlHttpSouple``) et côté schéma.
MOTIF_URL_HTTP_SOUPLE = r'^(|https?://[^\s\x00-\x1f]+)$'
URL_HTTP_SOUPLE_MAX = 253
_RE_URL_HTTP_SOUPLE = re.compile(MOTIF_URL_HTTP_SOUPLE)


class UrlHttpSouple:
    """Validateur dont l'acceptation égale EXACTEMENT le schéma publié
    (``MOTIF_URL_HTTP_SOUPLE`` + ``maxLength: 253``) : tout ce que le schéma
    refuse, le serveur le refuse, et inversement — plus de 400 sur un corps
    « conforme » (hôte à étiquettes de 63 signes) ni de 2xx sur un corps hors
    schéma. ``fullmatch`` : ``$`` Python tolérerait un ``\\n`` final."""

    code = 'invalid'
    message = 'Saisissez une URL valide.'

    def __call__(self, value):
        if (not isinstance(value, str) or len(value) > URL_HTTP_SOUPLE_MAX
                or not _RE_URL_HTTP_SOUPLE.fullmatch(value)):
            raise _ErreurDjango(self.message, code=self.code)

    def __eq__(self, autre):
        return isinstance(autre, UrlHttpSouple)

    def __hash__(self):
        return hash(UrlHttpSouple)


class MotifUrlPublie(_validateurs.RegexValidator):
    """Valide avec ``URLValidator`` (acceptation inchangée) mais PUBLIE un
    ``pattern`` dans le schéma : un champ texte « URL » dont la déclaration ne
    dit rien laisse le fuzz envoyer une chaîne conforme et recevoir un 400.
    Le motif publié est un sous-ensemble de ce que ``URLValidator`` accepte."""

    def __init__(self, message='URL invalide.'):
        super().__init__(regex=MOTIF_URL_HTTP, message=message, code='invalid')

    def __call__(self, value):
        _validateurs.URLValidator(message=self.message, code=self.code)(value)


class _ChaineSansNul(OpenApiSerializerFieldExtension):
    """ENF11 (api-fuzz « rejected schema-compliant request ») — une chaîne
    stricte publie ``pattern`` : aucun caractère nul (seule règle que DRF ajoute
    sans la déclarer). Une chaîne qui porte déjà un motif, un format ou une
    énumération est laissée telle quelle (son propre motif prime)."""
    target_class = 'core.champs_stricts.ChaineStricte'
    match_subclasses = True

    def map_serializer_field(self, auto_schema, direction):
        schema = auto_schema._map_serializer_field(
            self.target, direction, bypass_extensions=True)
        champ = self.target
        if direction != 'request' or schema.get('type') != 'string' or any(
                cle in schema for cle in ('pattern', 'format', 'enum')):
            return schema
        # Un validateur propre au champ (slug, e-mail, URL, extension de
        # fichier) est publié par drf-spectacular APRÈS cette extension et
        # seulement si aucun `pattern`/`format` n'est déjà posé : on lui
        # laisse la place (son motif prime sur la règle générique).
        if any(isinstance(v, _VALIDATEURS_PUBLIES) for v in champ.validators):
            return schema
        schema = dict(schema)
        # Non blanc = rogné ET (blanc interdit OU longueur minimale) : « " " »
        # est rogné en vide puis refusé ; sans rognage, « " " » passe.
        non_blanc = champ.trim_whitespace and (
            not champ.allow_blank or schema.get('minLength', 0) >= 1)
        schema['pattern'] = (
            MOTIF_NON_BLANC_SANS_NUL if non_blanc else MOTIF_SANS_NUL)
        return schema


class _ClePrimaireEntiere(OpenApiSerializerFieldExtension):
    """ENF11 (api-fuzz « rejected schema-compliant request ») — une clé
    primaire entière (série ``AutoField``) vaut au moins 1 : le schéma
    publiait n'importe quel entier et ``0`` répondait 400 « objet inexistant ».
    Le ``minimum`` n'est posé que côté requête, sur une clé de type entier."""
    target_class = 'rest_framework.relations.PrimaryKeyRelatedField'
    match_subclasses = True

    def map_serializer_field(self, auto_schema, direction):
        schema = auto_schema._map_serializer_field(
            self.target, direction, bypass_extensions=True)
        if direction != 'request' or schema.get('type') != 'integer' \
                or 'minimum' in schema:
            return schema
        schema = dict(schema)
        schema['minimum'] = 1
        return schema


def entier_ou_400(valeur, nom, defaut=None, mini=None, maxi=None):
    """Entier de requête STRICT : absent/vide -> ``defaut`` ; illisible ou
    inférieur à ``mini`` -> 400 nommant le paramètre ; supérieur à ``maxi`` ->
    plafonné (comportement historique des paramètres ``limit``)."""
    if valeur is None or str(valeur).strip() == '':
        return defaut
    try:
        n = int(str(valeur).strip())
    except ValueError:
        raise serializers.ValidationError({nom: ['Entier attendu.']})
    if mini is not None and n < mini:
        raise serializers.ValidationError({nom: ['Valeur hors plage.']})
    return n if maxi is None else min(n, maxi)


_DATE_ISO = re.compile(r'^\d{4}-\d{2}-\d{2}\Z')


class DateStricte(serializers.DateField):
    """``DateField`` limité à ``AAAA-MM-JJ`` (``format: date``) : DRF lisait
    aussi ``2026-1-5`` et ``20261005`` (``date.fromisoformat`` de 3.11)."""

    def to_internal_value(self, value):
        if not isinstance(value, str) or not _DATE_ISO.match(value):
            self.fail('invalid', format='AAAA-MM-JJ')
        return super().to_internal_value(value)


def date_ou_400(valeur, nom):
    """Date de requête ``AAAA-MM-JJ`` STRICTE : absent/vide -> ``None`` ;
    toute autre forme (``2026-1-5``, ``abc``, jour inexistant) -> 400 nommant
    le paramètre, comme le schéma ``format: date`` le déclare."""
    if valeur is None or str(valeur).strip() == '':
        return None
    brut = str(valeur).strip()
    if _DATE_ISO.match(brut):
        try:
            return date.fromisoformat(brut)
        except ValueError:
            pass
    raise serializers.ValidationError(
        {nom: ['Date attendue au format AAAA-MM-JJ.']})


def nombre_ou_400(valeur, nom, defaut=None, mini=None):
    """Nombre de requête STRICT (``float``) : absent/vide -> ``defaut`` ;
    illisible, ``nan``/``inf`` ou inférieur à ``mini`` -> 400 nommant le
    paramètre (il retombait en silence sur le défaut)."""
    if valeur is None or str(valeur).strip() == '':
        return defaut
    try:
        n = float(str(valeur).strip())
    except ValueError:
        n = None
    if n is None or n != n or n in (float('inf'), float('-inf')) or (
            mini is not None and n < mini):
        raise serializers.ValidationError({nom: ['Nombre attendu.']})
    return n


class DecimalStricte(serializers.DecimalField):
    """Décimal transporté en CHAÎNE (comme le schéma le déclare) : un nombre
    ou un booléen JSON est refusé en 400 ; ``""`` vaut « non renseigné » quand
    le champ accepte ``null``."""

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail('invalid')
        return super().to_internal_value(data)

    def validate_empty_values(self, data):
        if data == '' and self.allow_null:
            return (True, None)
        return super().validate_empty_values(data)


class DecimalBornee(DecimalStricte):
    """CI #997 (2) — ``DecimalStricte`` dont le motif publié suit la borne
    basse : avec ``min_value >= 0`` (prix, coût) il n'a plus de signe ``-``
    (``"-1"`` était « conforme » au schéma puis refusé en 400)."""


def _motif_decimal(champ):
    """Le motif EXACT publié par ``_DecimalChaineNonVide`` pour ``champ``
    (lu comme le validateur du schéma, regex Rust : ``re.fullmatch`` — un
    saut de ligne final n'y passe pas)."""
    entiers, decimales = champ.max_whole_digits, champ.decimal_places
    if not entiers or decimales is None:
        return r'^-?(?:\d+(?:\.\d*)?|\.\d+)$'
    return (fr'^-?(?:\d{{1,{entiers}}}(?:\.\d{{0,{decimales}}})?'
            fr'|\.\d{{1,{decimales}}})$')


class DecimalSouple(serializers.DecimalField):
    """CI #997 api-fuzz (``POST ventes/devis/ {"taux_tva": 0}``) — décimal
    accepté en CHAÎNE **ou** en NOMBRE JSON, et PUBLIÉ ainsi (``anyOf`` motif
    | nombre borné, voir ``_DecimalChaineNonVide``) : des clients envoient des
    nombres (générateur de devis), le serveur ne les refuse pas. Un nombre
    hors bornes ou un booléen → 400 ; un nombre dans les bornes est arrondi
    au demi supérieur à ``decimal_places`` (bruit flottant ``0.1 + 0.2``).

    CI #997 (2) — une CHAÎNE suit le motif publié : ``""``, des blancs autour,
    ``+1``, ``1e2`` ou ``1_0`` (que ``Decimal`` lit) → 400 ; ``""`` ne vaut
    plus ``null`` en silence (``null`` reste le « non renseigné » publié)."""

    def validate_empty_values(self, data):
        return serializers.Field.validate_empty_values(self, data)

    def to_internal_value(self, data):
        if isinstance(data, bool) or (
                isinstance(data, str)
                and not re.fullmatch(_motif_decimal(self), data)):
            self.fail('invalid')
        if isinstance(data, (int, float)):
            from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
            try:
                valeur = Decimal(repr(data))
            except (InvalidOperation, ValueError):
                self.fail('invalid')
            if not valeur.is_finite():
                self.fail('invalid')
            borne = borne_decimal(self)
            if borne is not None and valeur > borne:
                self.fail('max_value', max_value=borne)
            if borne is not None and valeur < -borne:
                self.fail('min_value', min_value=-borne)
            if self.decimal_places is not None:
                try:
                    valeur = valeur.quantize(
                        Decimal(1).scaleb(-self.decimal_places),
                        ROUND_HALF_UP)
                except InvalidOperation:
                    self.fail('invalid')
            data = format(valeur, 'f')
        return super().to_internal_value(data)


def borne_decimal(champ):
    """Plus grande valeur absolue qu'un ``DecimalField`` accepte (``None`` si
    le champ ne la borne pas) : ``999.99`` pour ``max_digits=5, places=2``."""
    from decimal import Decimal
    if not champ.max_whole_digits or champ.decimal_places is None:
        return None
    return Decimal(10) ** champ.max_whole_digits - Decimal(1).scaleb(
        -champ.decimal_places)


class DecimalSoupleMixin:
    """Mixin de ``ModelSerializer`` : les décimaux de modèle deviennent des
    ``DecimalSouple`` (chaîne ou nombre, publiés comme tels). À placer AVANT
    ``serializers.ModelSerializer`` dans les bases."""

    serializer_field_mapping = {
        **serializers.ModelSerializer.serializer_field_mapping,
        models.DecimalField: DecimalSouple,
    }


class _DecimalChaineNonVide(OpenApiSerializerFieldExtension):
    r"""ENF11 (api-fuzz « rejected schema-compliant request ») — le motif que
    drf-spectacular publie pour un décimal-chaîne (``^-?\d{0,N}(?:\.\d{0,M})?$``)
    accepte la chaîne VIDE, que ``DecimalField`` refuse (400). Le schéma exige
    désormais au moins un chiffre ; ``""`` n'est publié que pour une
    ``DecimalStricte`` nullable, qui la lit comme « non renseigné »."""
    target_class = 'rest_framework.fields.DecimalField'
    match_subclasses = True

    def map_serializer_field(self, auto_schema, direction):
        champ = self.target
        schema = auto_schema._map_serializer_field(
            champ, direction, bypass_extensions=True)
        if 'pattern' not in schema or not champ.max_whole_digits:
            return schema
        schema = dict(schema)
        schema['pattern'] = _motif_decimal(champ)
        if (isinstance(champ, DecimalBornee) and champ.min_value is not None
                and champ.min_value >= 0):
            schema['pattern'] = schema['pattern'].replace('^-?', '^', 1)
        if isinstance(champ, DecimalStricte) and champ.allow_null:
            motif = schema.pop('pattern')
            schema['anyOf'] = [{'pattern': motif}, {'maxLength': 0}]
        if isinstance(champ, DecimalSouple) and direction == 'request':
            schema = _chaine_ou_nombre(schema, champ)
        return schema


def _chaine_ou_nombre(schema, champ):
    """``anyOf`` [décimal-chaîne au motif, nombre JSON borné] d'une
    ``DecimalSouple`` (``nullable`` porté par chaque branche, OpenAPI 3.0)."""
    from decimal import Decimal
    branche = {k: schema.pop(k) for k in ('type', 'format', 'pattern')
               if k in schema}
    nombre = {'type': 'number'}
    borne = borne_decimal(champ)
    bornes = {'minimum': [champ.min_value], 'maximum': [champ.max_value]}
    if borne is not None:
        bornes['minimum'].append(-borne)
        bornes['maximum'].append(borne)
    for cle, choix in (('minimum', max), ('maximum', min)):
        valeurs = [Decimal(str(v)) for v in bornes[cle] if v is not None]
        if valeurs:
            nombre[cle] = float(choix(valeurs))
    if schema.pop('nullable', False):
        branche['nullable'] = nombre['nullable'] = True
    schema['anyOf'] = [branche, nombre]
    return schema


class TexteLie(serializers.CharField):
    """Texte d'un objet lié TOUJOURS servi (api-fuzz « Response violates
    schema »). DRF SAUTE un champ lu via ``source='lien.attr'`` dont le lien est
    vide dès que le sérialiseur est ``partial`` (PATCH) : la clé disparaissait
    de la réponse alors que le schéma la déclare obligatoire. Ici la clé est
    rendue avec son ``default`` (``None``/``''``) comme sur un GET."""

    def get_attribute(self, instance):
        try:
            return super().get_attribute(instance)
        except SkipField:
            return None if self.default is empty else self.default


#: Heure telle que DRF la REND (``time.isoformat()`` d'une heure naïve) :
#: ``HH:MM:SS`` avec microsecondes éventuelles, jamais de décalage.
MOTIF_HEURE_RENDUE = r'^\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?$'


class _HeureRendueSansFuseau(OpenApiSerializerFieldExtension):
    """CI #956 (api-fuzz « Response violates schema », parametres/delete-logo) —
    drf-spectacular publie un ``TimeField`` en ``format: time``, que le
    validateur lit comme une « full-time » RFC 3339 (décalage obligatoire,
    ``09:00:00Z``) ; DRF rend ``"09:00:00"``. Côté RÉPONSE le schéma dit le
    motif réellement rendu ; côté requête rien ne change (``format: time``)."""
    target_class = 'rest_framework.fields.TimeField'
    match_subclasses = True

    def map_serializer_field(self, auto_schema, direction):
        schema = auto_schema._map_serializer_field(
            self.target, direction, bypass_extensions=True)
        if direction != 'response' or schema.get('format') != 'time':
            return schema
        schema = dict(schema)
        schema.pop('format')
        schema['pattern'] = MOTIF_HEURE_RENDUE
        return schema


def installer_dates_rfc3339():
    """api-fuzz-full du 24/10/2026 (« Response violates schema », POST
    ``core/dashboards-partages/`` et ``ged/partages/``, ``expires_at`` en
    1263 / 0907) — pour une date antérieure à 1913, le fuseau local
    (Africa/Casablanca) rend le décalage « LMT » ``-00:30:20`` : à secondes,
    ce n'est pas une date-heure RFC 3339 (``format: date-time``). Plusieurs
    apps le corrigeaient champ par champ ; ici UNE fois pour tout
    ``DateTimeField`` DRF : un décalage à secondes est ramené en UTC (``Z``),
    même instant. Aucune date postérieure à 1913 ne change. Idempotent."""
    import datetime

    origine = serializers.DateTimeField.enforce_timezone
    if getattr(origine, '_rfc3339', False):
        return

    def enforce_timezone(self, value):
        value = origine(self, value)
        decalage = value.utcoffset() if getattr(value, 'tzinfo', None) else None
        if decalage is not None and int(decalage.total_seconds()) % 60:
            return value.astimezone(datetime.timezone.utc)
        return value

    enforce_timezone._rfc3339 = True
    serializers.DateTimeField.enforce_timezone = enforce_timezone


def drapeau_ou_400(valeur, nom):
    """Drapeau de requête déclaré ``enum=['1']`` : absent → ``False`` ;
    ``'1'`` → ``True`` ; toute autre valeur → 400 nommant le paramètre (elle
    était lue en silence comme « non »)."""
    if valeur is None:
        return False
    if valeur == '1':
        return True
    raise serializers.ValidationError(
        {nom: ['Seule la valeur « 1 » est acceptée.']})


class BooleenStrict(serializers.BooleanField):
    """``BooleanField`` qui n'accepte que de vrais booléens JSON (``0``/``1``
    ou ``"true"`` étaient convertis en silence)."""

    def to_internal_value(self, data):
        if not isinstance(data, bool):
            self.fail('invalid', input=data)
        return data


#: CI #997 fuzz (3) — plafond MÉTIER d'une quantité de stock saisie en une
#: fois (mouvement libre, scan) : publié en ``maximum`` et appliqué AVANT tout
#: calcul. Le schéma annonçait tout l'entier 32 bits : ``2147483646`` en entrée
#: faisait déborder ``quantite_stock`` (ou le casier) au save — 500.
QUANTITE_MAX = 1_000_000


class EntierNullableEnLecture(serializers.IntegerField):
    """Entier écrit SANS ``null`` mais lu avec ``null`` (CI #997 api-fuzz
    « Response violates schema », portail/documents-client-portail : ``lead_id``
    d'un dépôt sans lead). Le formulaire multipart ne sait pas écrire un
    ``null`` (il part en texte « None » → 400), donc la REQUÊTE ne publie pas
    ``nullable`` ; la RÉPONSE, elle, le publie : la clé revient ``null``."""

    def __init__(self, **kwargs):
        kwargs.setdefault('required', False)
        super().__init__(**kwargs)


class _EntierNullableEnLecture(OpenApiSerializerFieldExtension):
    target_class = 'core.champs_stricts.EntierNullableEnLecture'

    def map_serializer_field(self, auto_schema, direction):
        schema = auto_schema._map_serializer_field(
            self.target, direction, bypass_extensions=True)
        if direction != 'response':
            return schema
        schema = dict(schema)
        schema['nullable'] = True
        return schema


class EntierStrict(serializers.IntegerField):
    """Entier JSON réel : ``"5"``, ``5.0`` et ``true`` sont refusés (400)."""

    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, int):
            self.fail('invalid')
        return super().to_internal_value(data)


class ChampsStrictsMixin:
    """Mixin de ``ModelSerializer`` : les champs de modèle texte, booléens et
    décimaux sont générés en version STRICTE (un ``0`` pour un booléen ou un
    nombre JSON pour un décimal-chaîne → 400, comme le schéma le déclare).
    À placer AVANT ``serializers.ModelSerializer`` dans les bases."""

    serializer_field_mapping = {
        **serializers.ModelSerializer.serializer_field_mapping,
        models.CharField: ChaineStricte,
        models.TextField: ChaineStricte,
        models.BooleanField: BooleenStrict,
        models.DecimalField: DecimalStricte,
    }


class ChampsStrictsEntiersMixin:
    """``ChampsStrictsMixin`` + ENTIERS stricts (api-fuzz « accepted
    schema-violating request » sur ``PATCH installations/chantiers/{id}/``) :
    texte, booléen, décimal-chaîne et entier de modèle n'acceptent que leur
    type JSON déclaré (``0`` pour un texte, ``"5"`` pour un entier → 400)."""

    serializer_field_mapping = {
        **ChampsStrictsMixin.serializer_field_mapping,
        models.IntegerField: EntierStrict,
        models.PositiveIntegerField: EntierStrict,
        models.SmallIntegerField: EntierStrict,
        models.PositiveSmallIntegerField: EntierStrict,
    }


class ChampsStrictsBornesMixin:
    """``ChampsStrictsEntiersMixin`` avec des décimaux ``DecimalBornee`` (motif
    publié sans signe quand le champ est borné à 0 ou plus)."""

    serializer_field_mapping = {
        **ChampsStrictsEntiersMixin.serializer_field_mapping,
        models.DecimalField: DecimalBornee,
    }


class ChampsStrictsSansDecimalMixin:
    """Variante de ``ChampsStrictsMixin`` SANS les décimaux (lane GED/records/
    notifications : leurs clients envoient encore des nombres JSON pour
    ``x``/``y``/``largeur``…) — texte et booléens stricts seulement."""

    serializer_field_mapping = {
        **serializers.ModelSerializer.serializer_field_mapping,
        models.CharField: ChaineStricte,
        models.TextField: ChaineStricte,
        models.BooleanField: BooleenStrict,
    }


class TypageStrictMixin:
    """Variante (lane parametres/sav) : champs modèle texte / booléen / ENTIER
    générés en version stricte (``"5"`` pour un entier → 400) ; ``TextField``
    et décimaux inchangés. À poser en premier sur un ``ModelSerializer``."""

    serializer_field_mapping = {
        **serializers.ModelSerializer.serializer_field_mapping,
        models.CharField: ChaineStricte,
        models.BooleanField: BooleenStrict,
        models.IntegerField: EntierStrict,
        models.PositiveIntegerField: EntierStrict,
        models.SmallIntegerField: EntierStrict,
        models.PositiveSmallIntegerField: EntierStrict,
    }


class ListesStrictesMixin:
    """CI #997 api-fuzz — un champ M2M (``ManyRelatedField``) accepte tout
    itérable : ``{}`` passait pour une liste vide alors que le schéma déclare
    un tableau. Toute valeur non nulle qui n'est pas une liste → 400 nommé.
    À placer en TÊTE des bases du sérialiseur."""

    def to_internal_value(self, data):
        if hasattr(data, 'get') and not hasattr(data, 'getlist'):
            for nom, champ in self.fields.items():
                valeur = data.get(nom)
                if (isinstance(champ, serializers.ManyRelatedField)
                        and not champ.read_only and valeur is not None
                        and not isinstance(valeur, list)):
                    raise serializers.ValidationError(
                        {nom: ["Une liste d'identifiants est attendue."]})
        return super().to_internal_value(data)


def _ids_inconnus_imbriques(champ, details):
    """api-fuzz-full 24/10 (``POST core/workflow-definitions/``, ``steps[]``
    à ``formulaire``/``definition`` inexistants) — erreurs d'un sérialiseur
    IMBRIQUÉ : ``None`` si ``champ`` n'en est pas un ; sinon vrai ssi ses
    erreurs ne sont QUE des ids inconnus (même règle, récursive ; un élément
    ``{}`` d'une liste est un élément valide). OPT-IN : seul un sérialiseur
    qui pose ``ids_inconnus_imbriques = True`` l'active (les autres gardent le
    400 d'une clé imbriquée, que leurs tests figent)."""
    if isinstance(champ, serializers.ListSerializer):
        if not isinstance(details, list):
            return False
        fautifs = [d for d in details if d]
        return bool(fautifs) and all(
            _ids_inconnus_seulement(d, champ.child.fields, imbriques=True)
            for d in fautifs)
    if isinstance(champ, serializers.Serializer):
        return _ids_inconnus_seulement(details, champ.fields, imbriques=True)
    return None


def _ids_inconnus_seulement(erreurs, champs, imbriques=False):
    """Vrai si TOUTES les erreurs sont « objet inexistant » (``does_not_exist``)
    sur des champs de relation par clé primaire — ou le refus d'unicité
    (``unique``) d'une telle relation (``OneToOne``), deux refus d'ÉTAT qu'un
    schéma ne peut pas exprimer : un id inconnu l'emporte (404) sur le doublon,
    y compris celui d'un champ ordinaire (``code_parrainage`` d'un client)."""
    if not isinstance(erreurs, dict) or not erreurs:
        return False
    inconnu = False
    for nom, details in erreurs.items():
        champ = champs.get(nom)
        imbrique = (_ids_inconnus_imbriques(champ, details) if imbriques
                    else None)
        if imbrique is not None:
            if not imbrique:
                return False
            inconnu = True
            continue
        relation = getattr(champ, 'child_relation', champ)
        codes = {getattr(d, 'code', None) for d in details} if isinstance(details, list) else set()
        if not isinstance(relation, serializers.PrimaryKeyRelatedField):
            # Doublon d'un champ ordinaire (``unique``) : refus d'ÉTAT lui aussi,
            # toléré seulement À CÔTÉ d'un id inconnu (seul, c'est un 409).
            if codes == {'unique'}:
                continue
            return False
        if not codes or not codes <= {'does_not_exist', 'unique'}:
            return False
        inconnu = inconnu or 'does_not_exist' in codes
    return inconnu


class IdInconnu404Mixin:
    """ERR-ENF11-FUZZ-CRM/GED — un identifiant BIEN FORMÉ (``0`` compris) qui
    ne désigne aucune ligne de la société répond 404, plus 400 : la requête est
    conforme au schéma, c'est la ressource qui manque. Le corps reste celui de
    DRF (``{champ: ["Clé primaire « n » non valide…"]}``), IDENTIQUE pour un id
    inexistant et un id d'une autre société (aucun oracle). Toute autre erreur,
    seule ou mêlée, garde le 400. À placer en tête des bases du sérialiseur."""

    def is_valid(self, *, raise_exception=False):
        valide = super().is_valid(raise_exception=False)
        if not valide and raise_exception:
            from rest_framework.exceptions import NotFound
            if _ids_inconnus_seulement(
                    self.errors, self.fields,
                    imbriques=getattr(self, 'ids_inconnus_imbriques', False)):
                raise NotFound(self.errors)
            raise serializers.ValidationError(self.errors)
        return valide


#: Profondeur de l'arbre ``core.rules`` publié au schéma (groupes imbriqués) ;
#: la feuille est le niveau 0. Un arbre plus profond est HORS schéma ET refusé.
PROFONDEUR_ARBRE_CONDITIONS = 3
#: Un ``op`` de feuille ne doit pas se lire comme un opérateur de GROUPE, casse
#: comprise (``core.rules._is_group`` passe ``op`` en minuscules).
_MOTIF_OP_GROUPE = '^(?:[Aa][Nn][Dd]|[Oo][Rr]|[Nn][Oo][Tt])$'
_RE_OP_GROUPE = re.compile(_MOTIF_OP_GROUPE)


def schema_arbre_conditions(profondeur=PROFONDEUR_ARBRE_CONDITIONS):
    """CI #1000 — l'arbre ``core.rules`` tel que le serveur l'accepte
    (``arbre_conditions_valide``, son jumeau Python), publié en REQUÊTE : le
    schéma d'un ``JSONField`` est ``{}`` (« tout JSON ») alors que ``{}`` ou
    ``true`` étaient refusés (400 sur un corps conforme). Groupe ET/OU, groupe
    NON (une seule condition) ou feuille (``field`` non blanc + opérateur
    connu), déplié sur ``profondeur`` niveaux sans référence récursive."""
    from core.rules import GROUP_OPERATORS, LEAF_OPERATORS
    feuille = {'type': 'object', 'required': ['field', 'operator'],
               'properties': {
                   'field': {'type': 'string', 'minLength': 1,
                             'pattern': MOTIF_NON_BLANC_SANS_NUL},
                   'operator': {'type': 'string',
                                'enum': list(LEAF_OPERATORS)},
                   'op': {'not': {'type': 'string',
                                  'pattern': _MOTIF_OP_GROUPE}}}}
    if profondeur <= 0:
        return feuille
    enfants = schema_arbre_conditions(profondeur - 1)
    et_ou = {'type': 'object', 'required': ['conditions'],
             'anyOf': [{'required': ['op']},
                       {'not': {'required': ['operator']}}],
             'properties': {
                 'op': {'type': 'string',
                        'enum': [o for o in GROUP_OPERATORS if o != 'not']},
                 'conditions': {'type': 'array', 'minItems': 1,
                                'items': enfants}}}
    non = {'type': 'object', 'required': ['op', 'conditions'], 'properties': {
        'op': {'type': 'string', 'enum': ['not']},
        'conditions': {'type': 'array', 'minItems': 1, 'maxItems': 1,
                       'items': enfants}}}
    return {'anyOf': [et_ou, non, feuille]}


def arbre_conditions_valide(noeud, profondeur=PROFONDEUR_ARBRE_CONDITIONS):
    """Jumeau Python EXACT de ``schema_arbre_conditions`` : vrai ssi
    l'instance est valide au sens du schéma publié (même prédicat des deux
    côtés — un test le compare à ``jsonschema``)."""
    from core.rules import GROUP_OPERATORS, LEAF_OPERATORS
    if not isinstance(noeud, dict):
        return False
    champ = noeud.get('field')
    op = noeud.get('op')
    feuille = (
        isinstance(champ, str) and bool(champ) and '\u0000' not in champ
        and non_blanc(champ)
        and isinstance(noeud.get('operator'), str)
        and noeud['operator'] in LEAF_OPERATORS
        and not (isinstance(op, str) and _RE_OP_GROUPE.search(op)))
    if profondeur <= 0:
        return feuille
    conditions = noeud.get('conditions')
    enfants = (isinstance(conditions, list) and bool(conditions) and all(
        arbre_conditions_valide(c, profondeur - 1) for c in conditions))
    et_ou = (
        enfants and (('op' in noeud) or ('operator' not in noeud))
        and ('op' not in noeud
             or (isinstance(op, str)
                 and op in [o for o in GROUP_OPERATORS if o != 'not'])))
    non = (enfants and isinstance(op, str) and op == 'not'
           and len(conditions) == 1)
    return bool(feuille or et_ou or non)


class ArbreConditionsField(serializers.JSONField):
    """Arbre de conditions ``core.rules`` (NTEXT21…) validé AU CHAMP : les
    messages de ``validate_condition_group`` d'abord, puis le prédicat exact du
    schéma publié (``arbre_conditions_valide``). ``null`` passe par
    ``allow_null`` du champ."""

    def to_internal_value(self, data):
        from core.rules import validate_condition_group
        valeur = super().to_internal_value(data)
        erreurs = validate_condition_group(valeur)
        if erreurs:
            raise serializers.ValidationError('; '.join(erreurs))
        if not arbre_conditions_valide(valeur):
            raise serializers.ValidationError(
                "Arbre de conditions non conforme au schéma publié.")
        return arbre_conditions_canonique(valeur)


def arbre_conditions_canonique(noeud):
    """api-fuzz-full 24/10 (``POST core/ui-onglets/``, 500) — l'arbre réduit
    aux clés que ``core.rules`` lit (``op``/``conditions`` d'un groupe,
    ``field``/``operator``/``value`` d'une feuille) : une clé inconnue — à
    ``\\x00`` comprise, que le jsonb PostgreSQL refuse — n'est jamais stockée.
    Arbre déjà validé (``arbre_conditions_valide``)."""
    from core.rules import _is_group
    if _is_group(noeud):
        sortie = {'conditions': [
            arbre_conditions_canonique(c) for c in noeud['conditions']]}
        if 'op' in noeud:
            sortie['op'] = noeud['op']
        return sortie
    sortie = {'field': noeud['field'], 'operator': noeud['operator']}
    if 'value' in noeud:
        sortie['value'] = noeud['value']
    return sortie


class _ArbreConditionsSchema(OpenApiSerializerFieldExtension):
    target_class = 'core.champs_stricts.ArbreConditionsField'

    def map_serializer_field(self, auto_schema, direction):
        schema = auto_schema._map_serializer_field(
            self.target, direction, bypass_extensions=True)
        if direction != 'request':
            return schema
        schema = schema_arbre_conditions()
        if self.target.allow_null:
            schema['nullable'] = True
        return schema
