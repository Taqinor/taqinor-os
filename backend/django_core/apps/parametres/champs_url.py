"""ENF11 (api-fuzz « rejected schema-compliant request ») — URL http(s) d'un réglage
de Paramètres, dont le schéma de REQUÊTE et le serveur partagent LE MÊME
prédicat.

Le ``URLField`` DRF publie ``format: uri`` : le fuzz envoyait un hôte à
étiquettes de 63 signes, « conforme », que ``URLValidator`` refusait (400). Ici
l'acceptation est exactement ``MOTIF_URL_HTTP_SOUPLE`` (``core.champs_stricts``,
le motif d'``identity``) : http(s) puis au moins un signe ni blanc ni de contrôle
— ``""`` en plus quand le champ est facultatif — et la longueur est ``max_length``
(publiée ``maxLength``). Pas de rognage : une URL à blancs de bord est HORS motif.
"""
import re

from django.core.exceptions import ValidationError as _ErreurDjango
from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from rest_framework import serializers

from core.champs_stricts import MOTIF_URL_HTTP_SOUPLE

#: ``MOTIF_URL_HTTP_SOUPLE`` sans sa branche vide (champ obligatoire).
MOTIF_URL_HTTP_NON_VIDE = r'^https?://[^\s\x00-\x1f]+$'
_RE_URL_HTTP = re.compile(MOTIF_URL_HTTP_SOUPLE)


class ValidateurUrlHttp:
    """Vrai prédicat du motif publié (``fullmatch`` : ``$`` Python tolérerait un
    ``\\n`` final)."""

    code = 'invalid'
    message = 'Saisissez une URL valide.'

    def __call__(self, value):
        if not isinstance(value, str) or not _RE_URL_HTTP.fullmatch(value):
            raise _ErreurDjango(self.message, code=self.code)

    def __eq__(self, autre):
        return isinstance(autre, ValidateurUrlHttp)

    def __hash__(self):
        return hash(ValidateurUrlHttp)


class UrlHttp(serializers.CharField):
    """URL http(s) d'un réglage (voir le docstring du module). ``allow_blank``
    pour un lien facultatif ; ``max_length`` : borne de la colonne."""

    default_validators = [ValidateurUrlHttp()]

    def __init__(self, **kwargs):
        kwargs.setdefault('trim_whitespace', False)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail('invalid')
        return super().to_internal_value(data)


class _UrlHttp(OpenApiSerializerFieldExtension):
    target_class = 'apps.parametres.champs_url.UrlHttp'

    def map_serializer_field(self, auto_schema, direction):
        schema = auto_schema._map_serializer_field(
            self.target, direction, bypass_extensions=True)
        if direction != 'request':
            return schema
        schema = dict(schema)
        schema.pop('format', None)
        schema['pattern'] = (MOTIF_URL_HTTP_SOUPLE if self.target.allow_blank
                             else MOTIF_URL_HTTP_NON_VIDE)
        return schema
