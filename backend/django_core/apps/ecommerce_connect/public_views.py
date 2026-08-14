"""Webhooks PUBLICS (sans login DRF) — NTRET18/19.

Shopify/WooCommerce livrent le webhook « commande payée » en POST, signé
HMAC (jamais de session/JWT côté plateforme externe). La signature EST
l'authentification : sans secret configuré (``SHOPIFY_WEBHOOK_SECRET``),
``verify_webhook_hmac`` renvoie toujours ``False`` — 401, jamais un
traitement en clair.
"""
import json

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import shopify


def _company_from_shop_domain(shop_domain):
    """Résout la société propriétaire d'une connexion Shopify par domaine.

    Lecture seule, jamais d'exception — ``None`` si introuvable."""
    from .models import ConnexionEcommerce
    if not shop_domain:
        return None
    connexion = ConnexionEcommerce.objects.filter(
        plateforme=ConnexionEcommerce.Plateforme.SHOPIFY,
        boutique_url__icontains=shop_domain, actif=True,
    ).select_related('company').first()
    return connexion.company if connexion else None


@api_view(['POST'])
@permission_classes([AllowAny])
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
    company = _company_from_shop_domain(shop_domain)
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
