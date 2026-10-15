"""Sérialiseurs de la fondation Identité & accès."""
import ipaddress

from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.champs_stricts import (
    MOTIF_URL_HTTP_SOUPLE, URL_HTTP_SOUPLE_MAX, ChampsStrictsMixin,
    IdInconnu404Mixin, UrlHttpSouple)
from core.mixins import SameCompanyFKSerializerMixin
from core.parseurs import ObjetJSON

from .models import IdentityProvider, IpAllowRule, NetworkPolicy, TrustedDevice


class IpAllowRuleSerializer(IdInconnu404Mixin, ChampsStrictsMixin,
                            SameCompanyFKSerializerMixin,
                            serializers.ModelSerializer):
    # ENF11 (api-fuzz) : politique inconnue (0 compris) = 404 ; texte strict.
    # ENF15 : la politique référencée naît bornée à la société de l'appelant.
    same_company_fields = ('policy',)

    class Meta:
        model = IpAllowRule
        fields = ['id', 'policy', 'cidr', 'label', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_cidr(self, value):
        # Valider ICI (DRF → 400) et non seulement dans ``IpAllowRule.clean()``
        # (django ValidationError au save → 500). Normalise aussi la saisie.
        cidr = (value or '').strip()
        try:
            ipaddress.ip_network(cidr, strict=False)
        except (ValueError, AttributeError):
            raise serializers.ValidationError(
                'Plage CIDR invalide (ex. 10.0.0.0/8).')
        return cidr


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
