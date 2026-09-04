"""Webhooks PUBLICS (sans login DRF) — NTRET18/19.

Shopify/WooCommerce livrent le webhook « commande payée » en POST, signé
HMAC (jamais de session/JWT côté plateforme externe). La signature EST
l'authentification ET (AUD212) la DÉSIGNATION DU TENANT : chaque
``ConnexionEcommerce`` porte son propre secret, et seule celle dont le secret
valide le corps brut traite la commande. Aucune connexion signataire — secret
absent, secret faux, en-tête absent — ⇒ 401, jamais un traitement en clair et
jamais une société déduite d'un en-tête fourni par l'appelant.
"""
import json

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from . import common, shopify, woocommerce

# Réponse d'erreur PARTAGÉE des deux webhooks (400/401/404/503, toujours
# `{"detail": ...}`) — une SEULE instance `inline_serializer` réutilisée :
# en fabriquer une par site d'appel produirait deux classes Python de même
# nom (« identical names, different identities ») pour drf-spectacular, cf.
# authentication/views_demo_wizard.py.
_WEBHOOK_ERREUR = inline_serializer('EcommerceWebhookErreur', {
    'detail': serializers.CharField(),
})
# Même motif : forme de succès IDENTIQUE des deux webhooks (Shopify et
# WooCommerce renvoient tous deux `{id, statut}`), une SEULE instance.
_WEBHOOK_COMMANDE_RESULTAT = inline_serializer('EcommerceWebhookCommandeResultat', {
    'id': serializers.IntegerField(),
    'statut': serializers.CharField(),
})


class EcommerceWebhookThrottle(SimpleRateThrottle):
    """YRBAC9 — débit des webhooks e-commerce ENTRANTS, par IP.

    Même patron que les autres throttles publics du dépôt
    (``stock.public_views.QuaiCheckinThrottle``,
    ``sav.public_views.SavPublicThrottle``,
    ``compta.views._MarketingPublicThrottle`` qui couvre déjà les webhooks
    entrants Brevo/SMS) : ``rate`` câblé EN DUR et ``get_rate`` qui le renvoie,
    donc AUCUNE entrée ``DEFAULT_THROTTLE_RATES`` n'est requise (sinon DRF lève
    ``ImproperlyConfigured``). Une classe par app car importer le throttle
    d'une AUTRE app passerait par ses ``views`` — interdit par la frontière
    inter-apps (CLAUDE.md / import-linter).

    Budget 60/min : c'est celui du seul autre webhook ENTRANT du dépôt
    (``automation_webhook``). Volontairement plus large que les 30/min des
    liens tokenisés lus par un humain — une plateforme livre ses commandes en
    rafale et en at-least-once ; un budget trop serré ferait perdre des
    commandes PAYÉES. Il reste une borne anti-inondation : la signature HMAC,
    elle, est l'authentification (cf. docstring du module)."""

    scope = 'ecommerce_webhook'
    rate = '60/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope, 'ident': self.get_ident(request),
        }


# AUD212 — `_company_from_boutique_url` a été SUPPRIMÉE. Elle résolvait le
# tenant depuis un en-tête CLIENT (`X-Shopify-Shop-Domain` /
# `X-WC-Webhook-Source`) par un `boutique_url__icontains` + `.first()` sans
# ordre déterministe, alors que le secret HMAC était une variable `.env`
# UNIQUE pour toute la plateforme : la société A pouvait signer un POST avec
# le secret qu'elle connaît légitimement et le faire atterrir chez B en
# changeant l'en-tête. Le tenant vient désormais EXCLUSIVEMENT de la
# `ConnexionEcommerce` dont le secret PROPRE a validé la signature
# (`common.connexion_par_signature`) — l'en-tête de boutique n'est plus lu.


@extend_schema(request=None, responses={
    200: _WEBHOOK_COMMANDE_RESULTAT,
    400: _WEBHOOK_ERREUR, 401: _WEBHOOK_ERREUR,
    404: _WEBHOOK_ERREUR, 503: _WEBHOOK_ERREUR,
})
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([EcommerceWebhookThrottle])
def webhook_commande_shopify(request):
    """``POST /api/django/ecommerce-connect/shopify/webhook/commande/``.

    Corps JSON Shopify « orders/paid ». Vérifie la signature HMAC AVANT tout
    traitement — un secret absent/incorrect répond 401 sans avoir touché la
    base. Sans clé Shopify configurée du tout, ``shopify.is_configured()``
    est False et l'appel est un no-op (503) : ce webhook ne fait jamais
    d'appel réseau sortant, seulement du traitement local best-effort.
    """
    if not shopify.is_configured():
        return Response(
            {'detail': 'Connecteur Shopify non configuré (no-op).'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE)

    raw_body = request.body
    hmac_header = request.META.get('HTTP_X_SHOPIFY_HMAC_SHA256', '')
    # AUD212 — la signature DÉSIGNE le tenant : seule la connexion dont le
    # secret PROPRE valide ce corps brut est retenue. Aucun en-tête client
    # n'entre dans cette résolution.
    connexion = shopify.connexion_signataire(raw_body, hmac_header)
    if connexion is None:
        return Response({'detail': 'Signature invalide.'},
                        status=status.HTTP_401_UNAUTHORIZED)

    try:
        payload = json.loads(raw_body or b'{}')
    except (ValueError, TypeError):
        return Response({'detail': 'Payload JSON invalide.'},
                        status=status.HTTP_400_BAD_REQUEST)

    # AUD202 — statut RÉEL avant tout traitement « payé » : une commande non
    # encaissée (pending/authorized) ou remboursée/annulée ne doit produire ni
    # facture, ni paiement, ni sortie de stock.
    if not shopify.commande_est_payee(payload):
        return Response(
            {'detail': 'Commande non encaissée (financial_status '
                       f"« {payload.get('financial_status') or '—'} ») — "
                       'aucun traitement.'},
            status=status.HTTP_400_BAD_REQUEST)

    # AUD202 — devise : l'ERP facture en MAD, jamais dans la devise du panier.
    if not common.devise_compatible(payload.get('currency')):
        return Response(
            {'detail': f"Devise « {payload.get('currency')} » non facturable "
                       f'par l\'ERP ({common.DEVISE_ERP}).'},
            status=status.HTTP_400_BAD_REQUEST)

    # NOTE — mapping ligne minimal : un déploiement réel avec clé API
    # résoudrait chaque `line_items[].sku`/`variant_id` vers
    # `ProduitSync.external_product_id` (mapping inverse). Ce lot pose la
    # structure ; le mapping fin se règle avec le fondateur à l'armement de
    # la clé (voir shopify.is_configured()).
    lignes = [
        {'produit_id': li.get('produit_id'), 'quantite': li.get('quantity'),
         # AUD202 — montant TTC de la ligne, utilisé UNIQUEMENT quand la
         # commande mêle plusieurs taux de TVA (sinon le taux produit suffit).
         'montant_ttc': li.get('montant_ttc')}
        for li in payload.get('line_items', [])
        if isinstance(li, dict)
    ]
    commande = shopify.traiter_webhook_commande(
        connexion=connexion,
        external_order_id=payload.get('id') or payload.get('order_number'),
        montant_ttc=payload.get('total_price') or '0',
        email_client=payload.get('email') or payload.get('contact_email') or '',
        libelle=f"Commande Shopify #{payload.get('order_number', '')}",
        lignes=lignes,
        payload_brut=payload,
    )
    if commande is None:
        return Response({'detail': 'Aucune connexion Shopify active.'},
                        status=status.HTTP_404_NOT_FOUND)
    return Response({'id': commande.id, 'statut': commande.statut})


@extend_schema(request=None, responses={
    200: _WEBHOOK_COMMANDE_RESULTAT,
    400: _WEBHOOK_ERREUR, 401: _WEBHOOK_ERREUR,
    404: _WEBHOOK_ERREUR, 503: _WEBHOOK_ERREUR,
})
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([EcommerceWebhookThrottle])
def webhook_commande_woocommerce(request):
    """``POST /api/django/ecommerce-connect/woocommerce/webhook/commande/``.

    Corps JSON WooCommerce « order.updated » (statut payé). Même contrat que
    ``webhook_commande_shopify`` : signature HMAC vérifiée AVANT tout
    traitement, 503 no-op sans clé configurée, 404 sur boutique inconnue.
    """
    if not woocommerce.is_configured():
        return Response(
            {'detail': 'Connecteur WooCommerce non configuré (no-op).'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE)

    raw_body = request.body
    signature_header = request.META.get('HTTP_X_WC_WEBHOOK_SIGNATURE', '')
    # AUD212 — même règle que Shopify : le secret PROPRE de la connexion
    # désigne le tenant, l'en-tête `X-WC-Webhook-Source` n'est plus lu.
    connexion = woocommerce.connexion_signataire(raw_body, signature_header)
    if connexion is None:
        return Response({'detail': 'Signature invalide.'},
                        status=status.HTTP_401_UNAUTHORIZED)

    try:
        payload = json.loads(raw_body or b'{}')
    except (ValueError, TypeError):
        return Response({'detail': 'Payload JSON invalide.'},
                        status=status.HTTP_400_BAD_REQUEST)

    # AUD202 — `order.updated` se déclenche à CHAQUE transition (y compris
    # `cancelled`/`refunded`) : sans ce test, une commande annulée créait une
    # facture émise, un paiement encaissé et une sortie de stock.
    if not woocommerce.commande_est_payee(payload):
        return Response(
            {'detail': 'Commande non encaissée (status '
                       f"« {payload.get('status') or '—'} ») — "
                       'aucun traitement.'},
            status=status.HTTP_400_BAD_REQUEST)

    # AUD202 — devise : l'ERP facture en MAD, jamais dans la devise du panier.
    if not common.devise_compatible(payload.get('currency')):
        return Response(
            {'detail': f"Devise « {payload.get('currency')} » non facturable "
                       f'par l\'ERP ({common.DEVISE_ERP}).'},
            status=status.HTTP_400_BAD_REQUEST)

    # NOTE — même simplification que Shopify (voir ci-dessus) : mapping fin
    # `line_items[].sku` → `ProduitSync.external_product_id` à l'armement.
    lignes = [
        {'produit_id': li.get('produit_id'), 'quantite': li.get('quantity'),
         'montant_ttc': li.get('montant_ttc')}
        for li in payload.get('line_items', [])
        if isinstance(li, dict)
    ]
    billing = payload.get('billing') or {}
    commande = woocommerce.traiter_webhook_commande(
        connexion=connexion,
        external_order_id=payload.get('id') or payload.get('number'),
        montant_ttc=payload.get('total') or '0',
        email_client=billing.get('email') or '',
        libelle=f"Commande WooCommerce #{payload.get('number', '')}",
        lignes=lignes,
        payload_brut=payload,
    )
    if commande is None:
        return Response({'detail': 'Aucune connexion WooCommerce active.'},
                        status=status.HTTP_404_NOT_FOUND)
    return Response({'id': commande.id, 'statut': commande.statut})
