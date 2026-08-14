"""Connecteur Shopify — NTRET18, ``[GATED: Shopify API]``.

Sans ``SHOPIFY_ADMIN_TOKEN`` en ``.env`` : intégration TOTALEMENT no-op
(aucun appel réseau, jamais d'exception). C'est le motif du dépôt pour toute
fonctionnalité à clé (OCR, chatbot SQL, email sortant…) — voir CLAUDE.md.

Deux directions :

* ERP → Shopify : ``sync_catalogue`` pousse prix TTC + stock disponible des
  produits marqués ``vendable_en_ligne`` (``ProduitSync``, dans CETTE app —
  jamais un nouveau champ sur ``stock.Produit``, hors périmètre SUPPLY).
* Shopify → ERP : ``traiter_webhook_commande`` vérifie la signature HMAC puis
  délègue le mapping commande→facture à ``common.traiter_commande_payee``
  (NTRET19 — logique PARTAGÉE avec ``woocommerce.py``, jamais dupliquée).

Aucune dépendance externe ajoutée : ``httpx`` (déjà une dépendance du projet,
voir ``apps.publicapi.delivery``) pour les appels sortants.
"""
import logging

from django.conf import settings
from django.utils import timezone

from . import common
from .models import ConnexionEcommerce, ProduitSync

logger = logging.getLogger(__name__)

PLATEFORME = ConnexionEcommerce.Plateforme.SHOPIFY


def is_configured():
    """``True`` si une clé API Shopify est configurée en ``.env``.

    Lu à CHAQUE appel (jamais mis en cache) — le fondateur doit pouvoir
    armer/désarmer sans redéployer, même patron que
    ``apps.veille_ao.tasks.collecte_active``."""
    return bool(getattr(settings, 'SHOPIFY_ADMIN_TOKEN', '') or '')


def sync_catalogue(company):
    """NTRET18 — pousse le catalogue (prix TTC + stock) vers Shopify.

    NO-OP TOTAL sans clé configurée (``is_configured()`` False) ou sans
    ``ConnexionEcommerce`` active pour la société : aucun appel réseau, aucune
    exception. Renvoie un résumé ``{'skipped': bool, 'reason': str, ...}``.
    """
    if not is_configured():
        return {'skipped': True, 'reason': 'no_api_key', 'pushed': 0}
    connexion = common.connexion_active(company, PLATEFORME)
    if connexion is None:
        return {'skipped': True, 'reason': 'no_connexion', 'pushed': 0}

    from apps.stock import selectors as stock_selectors

    import httpx

    token = getattr(settings, 'SHOPIFY_ADMIN_TOKEN', '')
    base_url = connexion.boutique_url.rstrip('/')
    pushed, errors = 0, 0
    for ligne in ProduitSync.objects.filter(
            connexion=connexion, vendable_en_ligne=True):
        produit = stock_selectors.get_produit_scoped(company, ligne.produit_id)
        if produit is None:
            continue
        payload = {
            'product': {
                'id': ligne.external_product_id or None,
                'title': getattr(produit, 'nom', ''),
                'variants': [{
                    'price': str(produit.prix_vente),
                    'inventory_quantity': produit.quantite_stock,
                }],
            }
        }
        try:
            resp = httpx.put(
                f'{base_url}/admin/api/2024-01/products/'
                f'{ligne.external_product_id}.json',
                json=payload,
                headers={'X-Shopify-Access-Token': token},
                timeout=10.0,
            )
            ok = 200 <= resp.status_code < 300
        except Exception as exc:  # noqa: BLE001 — best-effort, jamais bloquant
            ok = False
            logger.warning('Shopify: échec push produit %s: %s',
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


def verify_webhook_hmac(raw_body: bytes, hmac_header: str) -> bool:
    """Vérifie la signature ``X-Shopify-Hmac-Sha256`` (base64, HMAC-SHA256).

    ``False`` sans secret configuré (jamais d'acceptation par défaut) OU sans
    en-tête fourni."""
    secret = getattr(settings, 'SHOPIFY_WEBHOOK_SECRET', '') or ''
    return common.verify_hmac_base64(secret, raw_body, hmac_header)


def traiter_webhook_commande(*, company, external_order_id, montant_ttc,
                             email_client='', libelle='', lignes=None,
                             user=None, payload_brut=None):
    """NTRET18 — traite une commande Shopify PAYÉE (webhook), IDEMPOTENT.

    Normalise les arguments Shopify puis délègue le mapping commande→facture
    (création Facture + Paiement + décrément stock) à
    ``common.traiter_commande_payee`` — logique PARTAGÉE avec
    ``woocommerce.traiter_webhook_commande`` (NTRET19), jamais dupliquée.
    """
    connexion = common.connexion_active(company, PLATEFORME)
    if connexion is None:
        return None
    return common.traiter_commande_payee(
        connexion=connexion, external_order_id=external_order_id,
        montant_ttc=montant_ttc, email_client=email_client, libelle=libelle,
        lignes=lignes, user=user, payload_brut=payload_brut)
