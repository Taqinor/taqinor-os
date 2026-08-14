"""Webhooks PUBLICS (sans login DRF) — NTRET18/19.

Shopify/WooCommerce livrent le webhook « commande payée » en POST, signé
HMAC (jamais de session/JWT côté plateforme externe). La signature EST
l'authentification : sans secret configuré, ``verify_webhook_hmac``/
``verify_webhook_signature`` renvoient toujours ``False`` — 401, jamais un
traitement en clair.
"""
import json

from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from . import shopify, woocommerce


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


def _company_from_boutique_url(plateforme, url_fragment):
    """Résout la société propriétaire d'une connexion (Shopify/WooCommerce)
    par fragment d'URL de boutique. Lecture seule, jamais d'exception —
    ``None`` si introuvable."""
    from .models import ConnexionEcommerce
    if not url_fragment:
        return None
    connexion = ConnexionEcommerce.objects.filter(
        plateforme=plateforme, boutique_url__icontains=url_fragment, actif=True,
    ).select_related('company').first()
    return connexion.company if connexion else None


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
    if not shopify.verify_webhook_hmac(raw_body, hmac_header):
        return Response({'detail': 'Signature invalide.'},
                        status=status.HTTP_401_UNAUTHORIZED)

    try:
        payload = json.loads(raw_body or b'{}')
    except (ValueError, TypeError):
        return Response({'detail': 'Payload JSON invalide.'},
                        status=status.HTTP_400_BAD_REQUEST)

    shop_domain = request.META.get('HTTP_X_SHOPIFY_SHOP_DOMAIN', '')
    company = _company_from_boutique_url(shopify.PLATEFORME, shop_domain)
    if company is None:
        # Boutique inconnue de ce dépôt : rien à faire, jamais une 500.
        return Response({'detail': 'Boutique inconnue.'},
                        status=status.HTTP_404_NOT_FOUND)

    # NOTE — mapping ligne minimal : un déploiement réel avec clé API
    # résoudrait chaque `line_items[].sku`/`variant_id` vers
    # `ProduitSync.external_product_id` (mapping inverse). Ce lot pose la
    # structure ; le mapping fin se règle avec le fondateur à l'armement de
    # la clé (voir shopify.is_configured()).
    lignes = [
        {'produit_id': li.get('produit_id'), 'quantite': li.get('quantity')}
        for li in payload.get('line_items', [])
        if isinstance(li, dict)
    ]
    commande = shopify.traiter_webhook_commande(
        company=company,
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
    if not woocommerce.verify_webhook_signature(raw_body, signature_header):
        return Response({'detail': 'Signature invalide.'},
                        status=status.HTTP_401_UNAUTHORIZED)

    try:
        payload = json.loads(raw_body or b'{}')
    except (ValueError, TypeError):
        return Response({'detail': 'Payload JSON invalide.'},
                        status=status.HTTP_400_BAD_REQUEST)

    source_url = request.META.get('HTTP_X_WC_WEBHOOK_SOURCE', '')
    company = _company_from_boutique_url(woocommerce.PLATEFORME, source_url)
    if company is None:
        return Response({'detail': 'Boutique inconnue.'},
                        status=status.HTTP_404_NOT_FOUND)

    # NOTE — même simplification que Shopify (voir ci-dessus) : mapping fin
    # `line_items[].sku` → `ProduitSync.external_product_id` à l'armement.
    lignes = [
        {'produit_id': li.get('produit_id'), 'quantite': li.get('quantity')}
        for li in payload.get('line_items', [])
        if isinstance(li, dict)
    ]
    billing = payload.get('billing') or {}
    commande = woocommerce.traiter_webhook_commande(
        company=company,
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
