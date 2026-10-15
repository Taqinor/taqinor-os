"""Sérialiseurs de la fondation Identité & accès."""
import re

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.champs_stricts import (
    MOTIF_URL_HTTP_SOUPLE, URL_HTTP_SOUPLE_MAX, ChampsStrictsMixin,
    IdInconnu404Mixin, UrlHttpSouple)
from core.mixins import SameCompanyFKSerializerMixin
from core.parseurs import ObjetJSON

from .models import IdentityProvider, IpAllowRule, NetworkPolicy, TrustedDevice


#: CI #1000 — plage CIDR en notation « adresse[/préfixe] » : IPv4 pointée
#: (octets 0-255 sans zéro de tête, préfixe 0-32) ou IPv6 hexadécimale (préfixe
#: 0-128). C'est LE MÊME prédicat côté serveur (``ValideCidr``) et côté schéma
#: (``pattern``) : le schéma ne disait que « chaîne » alors que ``ip_network``
#: refusait ``"0"`` (400 sur un corps « conforme »). Tout ce que ce motif
#: accepte, ``ipaddress.ip_network(strict=False)`` l'accepte (vérifié par un
#: tirage aléatoire de 500 000 chaînes) : le middleware relit donc la valeur sans
#: surprise. Hors motif : masques décimaux (``/255.0.0.0``), IPv6 à IPv4
#: embarquée, identifiant de zone.
_OCTET = r'(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])'
_H16 = r'[0-9A-Fa-f]{1,4}'
_V4 = rf'{_OCTET}(?:\.{_OCTET}){{3}}(?:/(?:3[0-2]|[12]?[0-9]))?'
_V6 = '(?:' + '|'.join([
    r'(?:H:){7}H', r'(?:H:){1,7}:', r'(?:H:){1,6}:H', r'(?:H:){1,5}(?::H){1,2}',
    r'(?:H:){1,4}(?::H){1,3}', r'(?:H:){1,3}(?::H){1,4}',
    r'(?:H:){1,2}(?::H){1,5}', r'H:(?::H){1,6}', r':(?:(?::H){1,7}|:)',
]).replace('H', _H16) + r')(?:/(?:12[0-8]|1[01][0-9]|[1-9]?[0-9]))?'
MOTIF_CIDR = f'^(?:{_V4}|{_V6})$'
CIDR_MAX = 64
_RE_CIDR = re.compile(MOTIF_CIDR)


class ValideCidr:
    """Validateur dont l'acceptation égale EXACTEMENT ``MOTIF_CIDR`` +
    ``maxLength`` 64 (``fullmatch`` : ``$`` Python tolérerait un ``\\n``)."""

    code = 'invalid'
    message = 'Plage CIDR invalide (ex. 10.0.0.0/8).'

    def __call__(self, value):
        if (not isinstance(value, str) or len(value) > CIDR_MAX
                or not _RE_CIDR.fullmatch(value)):
            raise DjangoValidationError(self.message, code=self.code)

    def __eq__(self, autre):
        return isinstance(autre, ValideCidr)

    def __hash__(self):
        return hash(ValideCidr)


class PlageCidr(serializers.CharField):
    """Plage CIDR : pas de rognage (une plage à blancs de bord est HORS motif,
    pas corrigée) ; validateur et schéma partagent ``MOTIF_CIDR``."""
    default_validators = [ValideCidr()]

    def __init__(self, **kwargs):
        kwargs.setdefault('max_length', CIDR_MAX)
        kwargs.setdefault('trim_whitespace', False)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail('invalid')
        return super().to_internal_value(data)


class _PlageCidr(OpenApiSerializerFieldExtension):
    target_class = 'apps.identity.serializers.PlageCidr'

    def map_serializer_field(self, auto_schema, direction):
        if direction == 'request':
            return {'type': 'string', 'minLength': 1, 'maxLength': CIDR_MAX,
                    'pattern': MOTIF_CIDR}
        return {'type': 'string', 'maxLength': CIDR_MAX}


class IpAllowRuleSerializer(IdInconnu404Mixin, ChampsStrictsMixin,
                            SameCompanyFKSerializerMixin,
                            serializers.ModelSerializer):
    # ENF11 (api-fuzz) : politique inconnue (0 compris) = 404 ; texte strict.
    # ENF15 : la politique référencée naît bornée à la société de l'appelant.
    same_company_fields = ('policy',)
    # CI #1000 : plage au motif publié (sinon « 0 » conforme → 400, et un id de
    # politique inconnu mêlé à ce 400 ne pouvait plus répondre 404).
    cidr = PlageCidr()

    class Meta:
        model = IpAllowRule
        fields = ['id', 'policy', 'cidr', 'label', 'created_at']
        read_only_fields = ['id', 'created_at']


class NetworkPolicySerializer(serializers.ModelSerializer):
    # AUD406 — défense en profondeur : n'exposer que les règles de la société
    # propriétaire de la politique. Une règle étrangère rattachée par erreur
    # (le trou refermé côté ``IpAllowRuleViewSet.perform_update``) ne doit ni
    # s'afficher chez le voisin ni laisser croire qu'elle le protège.
    rules = serializers.SerializerMethodField()

    @extend_schema_field(IpAllowRuleSerializer(many=True))
    def get_rules(self, obj):
        # Filtré EN PYTHON pour ne pas casser le ``prefetch_related('rules')``
        # du viewset (une requête de plus par politique sinon).
        propres = [r for r in obj.rules.all()
                   if r.company_id == obj.company_id]
        return IpAllowRuleSerializer(propres, many=True).data

    class Meta:
        model = NetworkPolicy
        fields = ['id', 'mode', 'applies_to', 'rules', 'created_at',
                  'updated_at']
        read_only_fields = ['id', 'rules', 'created_at', 'updated_at']


class TrustedDeviceSerializer(serializers.ModelSerializer):
    """NTSEC14 — lecture seule : liste des appareils de confiance de l'utilisateur
    (jamais l'empreinte complète, qui vaut un jeton de contournement MFA)."""

    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = TrustedDevice
        fields = ['id', 'label', 'approuve_le', 'expire_le', 'revoque_le',
                  'is_active']
        read_only_fields = fields


class UrlFacultative(serializers.CharField):
    """ENF11 — URL http(s) ou chaîne vide, moins de 254 signes.

    CI #997 (api-fuzz « rejected schema-compliant request ») : ``format: uri``
    admettait un hôte de 7 étiquettes de 63 signes que ``URLValidator`` refusait
    (400). Le schéma de REQUÊTE et le serveur partagent désormais LE MÊME
    prédicat (``core.champs_stricts.UrlHttpSouple`` / ``MOTIF_URL_HTTP_SOUPLE``,
    ``maxLength`` 253) : ce que l'un accepte, l'autre aussi — ports, requêtes et
    hôtes d'un vrai IdP compris. La RÉPONSE reste une chaîne libre (``""`` tant
    que l'IdP n'est pas configuré)."""
    default_validators = [UrlHttpSouple()]

    def __init__(self, **kwargs):
        kwargs.setdefault('max_length', URL_HTTP_SOUPLE_MAX)
        # Pas de rognage : une URL à blancs de bord est HORS motif, pas corrigée.
        kwargs.setdefault('trim_whitespace', False)
        super().__init__(**kwargs)


class _UrlFacultative(OpenApiSerializerFieldExtension):
    target_class = 'apps.identity.serializers.UrlFacultative'

    def map_serializer_field(self, auto_schema, direction):
        if direction == 'request':
            return {'type': 'string', 'maxLength': URL_HTTP_SOUPLE_MAX,
                    'pattern': MOTIF_URL_HTTP_SOUPLE}
        return {'type': 'string', 'maxLength': 500}


class IdentityProviderSerializer(ChampsStrictsMixin, serializers.ModelSerializer):
    """CRUD d'un IdP SSO (NTSEC1). ``company`` forcée côté serveur.

    CI #997 (3) — textes et booléens STRICTS : ``enforce_sso: 0`` (le schéma
    déclare un booléen) était lu ``False`` et le POST répondait 201."""
    metadata_url = UrlFacultative(required=False, allow_blank=True)
    sso_url = UrlFacultative(required=False, allow_blank=True)
    # CI #997 fuzz : OBJET JSON non nul publié comme tel (``null`` était conforme
    # au schéma ``{}`` puis refusé par le champ de modèle : 400).
    attribute_map = ObjetJSON(required=False)

    class Meta:
        model = IdentityProvider
        fields = [
            'id', 'protocol', 'nom', 'actif', 'metadata_url', 'metadata_xml',
            'entity_id', 'sso_url', 'x509_cert', 'attribute_map',
            'auto_provision', 'default_role_id', 'enforce_sso',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_attribute_map(self, value):
        if value in (None, ''):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'Le mapping d\'attributs doit être un objet JSON.')
        return value
