"""ENF11 — corps de requête VALIDÉS des vues de profil / session / 2FA.

Un corps qui n'est pas un objet JSON (``[null]``, ``-1``…) levait une 500 sur
``request.data.get`` ; un champ de mauvais type était coercé en silence. Ces
sérialiseurs répondent 400 (DRF) et servent aussi de déclaration OpenAPI.
"""
from django.core.validators import RegexValidator
from drf_spectacular.extensions import OpenApiSerializerExtension
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_field, inline_serializer,
)
from rest_framework import serializers, status

from core.champs_stricts import (
    MOTIF_NON_BLANC_SANS_NUL, MOTIF_SANS_NUL, BooleenStrict, ChaineStricte,
)

from .selectors import MOBILE_HOME_ALLOWED_ROUTES


class SwitchCompanyRequete(serializers.Serializer):
    company_id = serializers.IntegerField(min_value=1, max_value=2147483647)


@extend_schema_field({'type': 'string', 'nullable': True,
                      'enum': sorted(MOBILE_HOME_ALLOWED_ROUTES)})
class RouteAccueilChamp(ChaineStricte):
    """api-fuzz full 24/10 — la route d'accueil est une valeur de la
    whitelist (``''`` = tableau de bord) ou ``null`` : l'énumération est
    PUBLIÉE (``"f"`` était « conforme » puis refusé « Route inconnue. »). Le
    contrôle de la vue reste (défense en profondeur)."""


class MobileHomeRouteRequete(serializers.Serializer):
    route = RouteAccueilChamp(required=False, allow_null=True, allow_blank=True)


def nom_requetable(texte):
    """Vrai si ``texte`` (identifiant saisi) peut être cherché en base : non
    vide et SANS caractère nul (PostgreSQL lève dessus — 500). Faux :
    aucune recherche, la validation DRF qui suit répond 400."""
    return bool(texte) and chr(0) not in texte


def role_demande(champ, brut):
    """Le rôle que le PATCH résoudrait (MÊME champ DRF que la mise à jour),
    ou ``None`` si ce champ le refuse — la mise à jour échouera alors en 400.
    api-fuzz full 24/10 : ``Role.objects.filter(pk="abc")`` levait (500)."""
    try:
        return champ.to_internal_value(brut)
    except (serializers.ValidationError, TypeError, ValueError):
        return None


class _SchemaCorpsObligatoire(AutoSchema):
    """Corps de requête publié ``required`` (drf-spectacular ne le fait que
    si le composant porte un champ requis — un schéma brut passait pour
    FACULTATIF, et un PATCH sans corps, refusé en 400, était « conforme »)."""

    def _get_request_body(self, direction='request'):
        corps = super()._get_request_body(direction)
        if corps:
            corps['required'] = True
        return corps


def exiger_corps(methode):
    """api-fuzz full 24/10 — pose ``_SchemaCorpsObligatoire`` SOUS le schéma
    déjà étendu par ``@extend_schema`` de ``methode`` (qui reste la base) ;
    appelé depuis ``urls.py`` (``views.py`` est un fichier-mur, C20)."""
    kwargs = getattr(methode, 'kwargs', None)
    if kwargs is None:
        kwargs = methode.kwargs = {}
    base = kwargs.get('schema') or AutoSchema
    kwargs['schema'] = type(
        'CorpsObligatoire' + base.__name__, (_SchemaCorpsObligatoire, base), {})
    return methode


def _chaines_sans_nul(serialiseur, schema):
    """Publie, sur chaque champ texte d'écriture de ``serialiseur``, le motif
    que DRF applique sans le dire : aucun caractère nul (non blanc quand le
    champ refuse le vide après rognage — règle de ``core.champs_stricts``)."""
    schema = dict(schema)
    proprietes = dict(schema.get('properties', {}))
    for nom, champ in serialiseur.fields.items():
        prop = proprietes.get(nom)
        if (champ.read_only or not isinstance(champ, serializers.CharField)
                or not prop or prop.get('type') != 'string'
                or any(cle in prop for cle in ('pattern', 'format', 'enum'))):
            continue
        non_blanc = champ.trim_whitespace and not champ.allow_blank
        proprietes[nom] = {**prop, 'pattern': (
            MOTIF_NON_BLANC_SANS_NUL if non_blanc else MOTIF_SANS_NUL)}
    schema['properties'] = proprietes
    return schema


class _JetonsSansNul(OpenApiSerializerExtension):
    """api-fuzz full 24/10 (``POST token/verify/``, ``POST token/``) — un
    caractère nul était « conforme » au schéma puis refusé (400) par DRF : le
    motif est publié. Schéma seul ; vérification des jetons inchangée."""
    target_class = 'rest_framework_simplejwt.serializers.TokenVerifySerializer'
    priority = 1

    def map_serializer(self, auto_schema, direction):
        schema = auto_schema._map_serializer(
            self.target, direction, bypass_extensions=True)
        if direction != 'request':
            return schema
        return _chaines_sans_nul(self.target, schema)


class _ConnexionSansNul(_JetonsSansNul):
    target_class = 'authentication.serializers.CustomTokenObtainPairSerializer'


@extend_schema_field({'type': 'string', 'enum': ['fr', 'en', 'ar']})
class LangueChamp(ChaineStricte):
    """Langue d'interface (le contrôle de valeur reste dans la vue)."""


class LangueInterfaceRequete(serializers.Serializer):
    langue_interface = LangueChamp()


class CalendrierHegirienRequete(serializers.Serializer):
    calendrier_hegirien = BooleenStrict()


@extend_schema_field({'type': 'string', 'pattern': r'^\d{6}$'})
class CodeTotp(ChaineStricte):
    """Code TOTP à 6 chiffres (espaces tolérés à la saisie, comme avant) :
    forme invalide = 400 ; un code bien formé mais faux relève de l'ÉTAT (409,
    dans la vue)."""

    def to_internal_value(self, data):
        code = super().to_internal_value(data).replace(' ', '')
        if not (len(code) == 6 and code.isascii() and code.isdigit()):
            self.fail('invalid')
        return code


class MotDePasseReinit(serializers.CharField):
    """Déclaration (schéma seul) du mot de passe de
    ``users/{id}/reinitialiser-mot-de-passe/`` : ≥ 8 caractères (``min_length``
    → ``minLength`` publié), pas entièrement numérique (``RegexValidator`` →
    ``pattern`` publié). Le serveur reste la vérité (validateurs Django +
    politique de la société) ; la vue n'utilise pas ce champ pour valider."""

    def __init__(self, **kwargs):
        kwargs.setdefault('min_length', 8)
        kwargs.setdefault('trim_whitespace', False)
        kwargs.setdefault('validators', [RegexValidator(
            r'^[\s\S]*\D[\s\S]*$', message='Mot de passe entièrement numérique.')])
        super().__init__(**kwargs)


class TwoFactorEnableRequete(serializers.Serializer):
    code = CodeTotp()


class TwoFactorDisableRequete(serializers.Serializer):
    code = ChaineStricte(required=False, allow_blank=True)
    password = ChaineStricte(required=False, allow_blank=True)


# PATCH : drf-spectacular fabrique un composant « Patched… » sans champ requis
# pour tout sérialiseur de PATCH ; ces deux corps ont un champ OBLIGATOIRE, que
# le schéma dit donc en clair (sinon ``{}`` y passait pour « conforme »).
SCHEMA_PATCH_LANGUE = {'application/json': {
    'type': 'object', 'required': ['langue_interface'],
    'properties': {'langue_interface': {
        'type': 'string', 'enum': ['fr', 'en', 'ar']}}}}
SCHEMA_PATCH_HEGIRIEN = {'application/json': {
    'type': 'object', 'required': ['calendrier_hegirien'],
    'properties': {'calendrier_hegirien': {'type': 'boolean'}}}}

# Refus VOULUS de la création d'un compte (déclarés, non « corrigés ») : nom
# d'utilisateur déjà pris, mot de passe rejeté par la politique de la société
# (FG22/AUD402). Aucune donnée générée par un fuzzeur ne peut l'anticiper.
REPONSE_400_COMPTE = OpenApiResponse(
    description="Refus : nom d'utilisateur déjà pris, ou mot de passe rejeté "
                "par la politique de mot de passe de la société.")


#: ENF11 — ``{id}`` des routes de détail de ``UserViewSet`` : la PK entière du
#: compte (le queryset de la vue dépend de ``request.user`` : drf-spectacular ne
#: peut pas en déduire le modèle sans requête).
ID_COMPTE = [OpenApiParameter(
    'id', OpenApiTypes.INT, OpenApiParameter.PATH,
    description="Identifiant du compte utilisateur de la société.")]


#: ENF11 — schéma de ``POST auth/logout/`` (``LogoutView``), posé dans
#: ``authentication/urls.py`` : ``views.py`` est un fichier-mur (C20). Corps
#: OPTIONNEL — ``refresh`` (repli du cookie ``refresh_token``) et
#: ``push_endpoint`` (APAR57, désabonnement push de cet appareil).
SCHEMA_LOGOUT = extend_schema(
    request=inline_serializer('LogoutRequete', {
        'refresh': serializers.CharField(required=False),
        'push_endpoint': serializers.CharField(required=False),
    }),
    responses=inline_serializer('LogoutReponse', {
        'detail': serializers.CharField(),
    }))


#: ENF11 — avatar : le contenu du fichier (taille, type réel) ne se publie pas
#: dans le schéma → 413 / 415 déclarés, jamais un 400 (constat nocturne).
REQUETE_AVATAR = {'multipart/form-data': inline_serializer(
    'AvatarUpload', {'file': serializers.FileField(
        help_text="Image PNG, JPEG ou WebP (contrôlée sur ses octets), "
                  "2 Mo maximum.")})}
REPONSES_AVATAR_REFUS = {
    413: OpenApiResponse(description="Fichier de plus de 2 Mo."),
    415: OpenApiResponse(
        description="Contenu qui n'est pas un PNG, JPEG ou WebP."),
}


def statut_refus_avatar(err):
    """413 pour la taille, 415 pour le type réel (voir ``avatars.store_avatar``)."""
    return (status.HTTP_413_REQUEST_ENTITY_TOO_LARGE if err.startswith('Fichier trop')
            else status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)


#: ENF11 — réinitialisation : la forme (≥ 8 caractères, pas entièrement
#: numérique) est publiée au schéma → 400 ; ce que le schéma ne peut pas dire
#: (mot de passe trop courant, politique propre à la société) relève de l'état
#: de la société → 409, même corps ``{"password": [...]}``.
REQUETE_REINIT = inline_serializer('ReinitialiserMotDePasseRequete', {
    'password': MotDePasseReinit()})
REPONSES_REINIT = {
    200: inline_serializer('ReinitialiserMotDePasseReponse', {
        'detail': serializers.CharField()}),
    409: OpenApiResponse(
        description="Mot de passe refusé par la politique (trop courant, "
                    "règles de la société) : {\"password\": […]}."),
}


def statut_refus_mot_de_passe(brut):
    forme = not isinstance(brut, str) or len(brut) < 8 or brut.isdigit()
    return status.HTTP_400_BAD_REQUEST if forme else status.HTTP_409_CONFLICT
