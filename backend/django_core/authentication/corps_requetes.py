"""ENF11 — corps de requête VALIDÉS des vues de profil / session / 2FA.

Un corps qui n'est pas un objet JSON (``[null]``, ``-1``…) levait une 500 sur
``request.data.get`` ; un champ de mauvais type était coercé en silence. Ces
sérialiseurs répondent 400 (DRF) et servent aussi de déclaration OpenAPI.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_field, inline_serializer,
)
from rest_framework import serializers

from core.champs_stricts import BooleenStrict, ChaineStricte


class SwitchCompanyRequete(serializers.Serializer):
    company_id = serializers.IntegerField(min_value=1, max_value=2147483647)


class MobileHomeRouteRequete(serializers.Serializer):
    route = ChaineStricte(required=False, allow_null=True, allow_blank=True)


@extend_schema_field({'type': 'string', 'enum': ['fr', 'en', 'ar']})
class LangueChamp(ChaineStricte):
    """Langue d'interface (le contrôle de valeur reste dans la vue)."""


class LangueInterfaceRequete(serializers.Serializer):
    langue_interface = LangueChamp()


class CalendrierHegirienRequete(serializers.Serializer):
    calendrier_hegirien = BooleenStrict()


class TwoFactorEnableRequete(serializers.Serializer):
    code = ChaineStricte(required=False, allow_blank=True)


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
