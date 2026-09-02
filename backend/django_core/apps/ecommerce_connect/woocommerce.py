"""Connecteur WooCommerce — NTRET19, ``[GATED: WooCommerce REST API]``.

MÊME architecture que ``shopify.py`` (NTRET18) : sans
``WOOCOMMERCE_CONSUMER_KEY``/``WOOCOMMERCE_CONSUMER_SECRET`` en ``.env``,
intégration TOTALEMENT no-op. Le mapping « commande payée → Facture +
Paiement + décrément stock » est FACTORISÉ dans ``common.py`` (partagé avec
Shopify, jamais dupliqué) ; seul le format REST WooCommerce
(authentification Basic Auth consumer key/secret, en-tête de signature
``X-WC-Webhook-Signature``) est spécifique à ce module.
"""
import logging

from django.conf import settings
from django.utils import timezone

from . import common
from .models import ConnexionEcommerce, ProduitSync

logger = logging.getLogger(__name__)

PLATEFORME = ConnexionEcommerce.Plateforme.WOOCOMMERCE


def is_configured():
    """``True`` si une clé API WooCommerce (consumer key + secret) est
    configurée en ``.env``. Lu à CHAQUE appel, jamais mis en cache."""
    return bool(
        getattr(settings, 'WOOCOMMERCE_CONSUMER_KEY', '')
        and getattr(settings, 'WOOCOMMERCE_CONSUMER_SECRET', ''))


def sync_catalogue(company):
    """NTRET19 — pousse le catalogue (prix TTC + stock) vers WooCommerce.

    NO-OP TOTAL sans clé configurée ou sans ``ConnexionEcommerce`` active :
    aucun appel réseau, aucune exception. Renvoie
    ``{'skipped': bool, 'reason': str, ...}``."""
    if not is_configured():
        return {'skipped': True, 'reason': 'no_api_key', 'pushed': 0}
    connexion = common.connexion_active(company, PLATEFORME)
    if connexion is None:
        return {'skipped': True, 'reason': 'no_connexion', 'pushed': 0}

    from apps.stock import selectors as stock_selectors

    import httpx

    consumer_key = getattr(settings, 'WOOCOMMERCE_CONSUMER_KEY', '')
    consumer_secret = getattr(settings, 'WOOCOMMERCE_CONSUMER_SECRET', '')
    base_url = connexion.boutique_url.rstrip('/')
    pushed, errors = 0, 0
    for ligne in ProduitSync.objects.filter(
            connexion=connexion, vendable_en_ligne=True):
        produit = stock_selectors.get_produit_scoped(company, ligne.produit_id)
        if produit is None:
            continue
        payload = {
            'name': getattr(produit, 'nom', ''),
            'regular_price': str(produit.prix_vente),
            'stock_quantity': produit.quantite_stock,
            'manage_stock': True,
        }
        try:
            resp = httpx.put(
                f'{base_url}/wp-json/wc/v3/products/{ligne.external_product_id}',
                json=payload, auth=(consumer_key, consumer_secret), timeout=10.0,
            )
            ok = 200 <= resp.status_code < 300
        except Exception as exc:  # noqa: BLE001 — best-effort, jamais bloquant
            ok = False
            logger.warning('WooCommerce: échec push produit %s: %s',
                           ligne.produit_id, exc)
            resp = None
        ligne.derniere_sync = timezone.now()
        if ok:
            ligne.dernier_statut = ProduitSync.Statut.OK
            ligne.dernier_message = ''
            pushed += 1
        else:
            ligne.dernier_statut = ProduitSync.Statut.ERREUR
            ligne.dernier_message = (
                f'HTTP {resp.status_code}' if resp is not None else 'échec réseau')
            errors += 1
        ligne.save(update_fields=['derniere_sync', 'dernier_statut',
                                  'dernier_message'])

    connexion.derniere_sync_catalogue = timezone.now()
    connexion.save(update_fields=['derniere_sync_catalogue'])
    return {'skipped': False, 'pushed': pushed, 'errors': errors}


def connexion_signataire(raw_body: bytes, signature_header: str):
    """AUD212 — ``ConnexionEcommerce`` WooCommerce dont le secret PROPRE valide
    la signature ``X-WC-Webhook-Signature``, ou ``None``.

    Remplace l'ancien couple « ``verify_webhook_signature`` contre le secret
    `.env` GLOBAL + société déduite de l'en-tête ``X-WC-Webhook-Source`` » :
    le tenant vient maintenant de la connexion dont le secret a validé la
    signature, jamais d'un en-tête client."""
    return common.connexion_par_signature(PLATEFORME, raw_body, signature_header)


# AUD202 — le topic WooCommerce câblé est `order.updated`, qui se déclenche à
# CHAQUE transition de la commande : `pending`, `on-hold`, `cancelled`,
# `refunded`, `failed`… Sans lire `status`, une commande ANNULÉE produisait
# quand même une Facture émise + un Paiement encaissé + une sortie de stock.
# Seuls `processing` (payée, en préparation) et `completed` (payée, livrée)
# sont des encaissements. Statut absent = non payé (fail-closed).
STATUTS_PAYES = frozenset({'processing', 'completed'})


def commande_est_payee(payload) -> bool:
    """``True`` si le payload WooCommerce décrit une commande RÉELLEMENT
    encaissée (``status`` dans ``STATUTS_PAYES``) — AUD202. Fail-closed."""
    statut = str((payload or {}).get('status') or '').strip().lower()
    return statut in STATUTS_PAYES


def traiter_webhook_commande(*, connexion=None, company=None, external_order_id,
                             montant_ttc, email_client='', libelle='',
                             lignes=None, user=None, payload_brut=None):
    """NTRET19 — traite une commande WooCommerce PAYÉE (webhook), IDEMPOTENT.

    Normalise les arguments WooCommerce puis délègue le mapping
    commande→facture à ``common.traiter_commande_payee`` — logique PARTAGÉE
    avec ``shopify.traiter_webhook_commande`` (NTRET18), jamais dupliquée.

    AUD212 — ``connexion`` (celle dont le secret a validé la signature) est la
    SOURCE DE VÉRITÉ du tenant : c'est le seul argument que passe le webhook
    public. ``company`` reste accepté pour les appelants INTERNES déjà scopés.
    """
    if connexion is None:
        connexion = (common.connexion_active(company, PLATEFORME)
                     if company is not None else None)
    if connexion is None:
        return None
    return common.traiter_commande_payee(
        connexion=connexion, external_order_id=external_order_id,
        montant_ttc=montant_ttc, email_client=email_client, libelle=libelle,
        lignes=lignes, user=user, payload_brut=payload_brut)
