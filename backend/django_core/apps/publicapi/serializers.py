"""Serializers de GESTION (écran Paramètres) pour clés API & webhooks (N89).

Authentifiés par session/JWT normaux, palier admin. La clé en clair et le
secret webhook ne sont JAMAIS renvoyés en lecture — uniquement une fois, à la
création, par les vues dédiées.
"""
from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from rest_framework import serializers

from core.champs_stricts import ChaineStricte
from core.mixins import SameCompanyFKSerializerMixin
from core.models import ApiUsagePlan

from .portees import ALL_SCOPES, SCOPE_CHOICES
from .constants import ALL_EVENTS, EVENT_CHOICES, ALL_ENVIRONMENTS, ENV_LIVE
from .schema_fields import champ_choix
from .models import ApiKey, ServiceAccount, Webhook, WebhookDelivery
from .validators import UnsafeWebhookURL, validate_webhook_target_url


class ApiKeySerializer(SameCompanyFKSerializerMixin,
                       serializers.ModelSerializer):
    """Représentation en lecture d'une clé (jamais le secret)."""
    # ENF17 — FK en lecture seule (read_only_fields = fields) ; bornée
    # société si elle redevient inscriptible.
    same_company_fields = ('created_by',)
    created_by_nom = serializers.SerializerMethodField()

    class Meta:
        model = ApiKey
        fields = [
            'id', 'label', 'prefix', 'scopes', 'enabled', 'api_version',
            # NTAPI26 — environnement (test/live). NTAPI23 — grace period de
            # rotation en cours (None = clé permanente).
            'environnement', 'expire_le',
            'created_by', 'created_by_nom', 'created_at', 'last_used_at',
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_created_by_nom(self, obj):
        u = obj.created_by
        if not u:
            return ''
        return (u.get_full_name() or u.username or u.email or '').strip()


class ApiKeyCreateSerializer(serializers.Serializer):
    """Entrée de création : libellé + scopes. Renvoie la clé en clair UNE fois."""
    label = serializers.CharField(max_length=120)
    scopes = serializers.ListField(
        child=serializers.ChoiceField(choices=ALL_SCOPES),
        allow_empty=True, default=list)
    # NTAPI26 — environnement de la clé (défaut `live`, comportement
    # historique inchangé pour tout appelant qui ne l'envoie pas).
    environnement = champ_choix(
        ALL_ENVIRONMENTS, required=False, default=ENV_LIVE)

    def validate_label(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Le libellé est obligatoire.')
        return value


class WebhookSerializer(serializers.ModelSerializer):
    """Représentation en lecture d'un webhook (jamais le secret en clair)."""
    # ENF11 — la règle « https uniquement » est exprimée dans le schéma
    # (``pattern``) ; l'hôte public/résolvable reste contrôlé par
    # ``validate_target_url`` (DNS, anti-SSRF), non exprimable.
    target_url = serializers.RegexField(
        r'^https://\S+$', max_length=500,
        error_messages={'invalid': "L'URL du webhook doit utiliser https."})

    class Meta:
        model = Webhook
        fields = [
            'id', 'label', 'target_url', 'events', 'enabled',
            # NTAPI12 — condition fine par évènement (opt-in, `{}` = aucun
            # filtre, comportement historique).
            'filtres',
            # NTAPI11 — traçabilité d'une désactivation AUTOMATIQUE : l'écran
            # Paramètres distingue « l'admin l'a coupé » (les deux champs sont
            # vides) de « la cible est morte » (raison + horodatage). En
            # LECTURE SEULE : seul le serveur les pose/efface.
            'disabled_reason', 'disabled_at',
            'created_at',
        ]
        read_only_fields = [
            'id', 'created_at', 'disabled_reason', 'disabled_at']

    def validate_events(self, value):
        unknown = [e for e in value if e not in ALL_EVENTS]
        if unknown:
            raise serializers.ValidationError(
                f'Évènements inconnus : {", ".join(unknown)}.')
        return value

    def validate_filtres(self, value):
        """NTAPI12 — une faute de frappe dans une condition doit être signalée
        À L'ENREGISTREMENT, pas six semaines plus tard sous la forme d'une
        intégration muette."""
        from .webhook_filters import erreurs_de_filtres

        erreurs = erreurs_de_filtres(value)
        if erreurs:
            raise serializers.ValidationError(erreurs)
        return value or {}

    def validate_target_url(self, value):
        # ERR46 — refuse https + bloque les hôtes internes (anti-SSRF).
        try:
            return validate_webhook_target_url(value)
        except UnsafeWebhookURL as exc:
            raise serializers.ValidationError(str(exc))


def scope_catalogue():
    """Catalogue scopes/évènements pour peupler l'écran Paramètres."""
    return {
        'scopes': [{'code': c, 'label': lbl} for c, lbl in SCOPE_CHOICES],
        'events': [{'code': c, 'label': lbl} for c, lbl in EVENT_CHOICES],
    }


class WebhookDeliverySerializer(SameCompanyFKSerializerMixin,
                                serializers.ModelSerializer):
    # ENF17 — FK en lecture seule (read_only_fields = fields) ; bornée
    # société si elle redevient inscriptible.
    same_company_fields = ('webhook',)

    class Meta:
        model = WebhookDelivery
        fields = [
            'id', 'webhook', 'event', 'payload', 'status', 'response_status',
            'error', 'created_at',
            # NTAPI10 — clé d'idempotence envoyée au consommateur (visible
            # dans l'historique de livraison de l'écran Paramètres).
            'idempotency_key',
        ]
        read_only_fields = fields


# ENF11 — `core.serializers` porte aussi un `ApiUsagePlanSerializer` : un nom de
# composant distinct evite la collision « identical names » du generateur.
@extend_schema_serializer(component_name='PublicApiUsagePlan')
class ApiUsagePlanSerializer(serializers.ModelSerializer):
    """NTAPI7 — plan d'API nommé de la société (gratuit/pro/entreprise).

    ``company`` n'est JAMAIS acceptée en écriture : la vue la force depuis
    ``request.user.company`` (jamais du corps de requête)."""

    class Meta:
        model = ApiUsagePlan
        fields = [
            'id', 'code', 'quota_par_minute', 'quota_par_jour',
            'quota_par_mois', 'quota_burst', 'retention_livraisons_jours',
            'nb_webhooks_max', 'actif', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ServiceAccountSerializer(serializers.ModelSerializer):
    """NTSEC24 — compte de service (jeton renvoyé UNE fois à la création)."""
    # ENF11 — liste de textes (le JSONField générique laissait passer ``null``
    # et des entiers : schéma « any », refus 400 inattendu sur ``scopes: null``).
    scopes = serializers.ListField(child=ChaineStricte(), required=False)

    class Meta:
        model = ServiceAccount
        fields = [
            'id', 'nom', 'scopes', 'prefix', 'actif', 'expire_le',
            'last_used_at', 'created_at',
        ]
        read_only_fields = [
            'id', 'prefix', 'last_used_at', 'created_at']
