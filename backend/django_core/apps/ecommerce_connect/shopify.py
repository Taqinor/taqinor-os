"""Connecteur Shopify — NTRET18, ``[GATED: Shopify API]``.

Sans ``SHOPIFY_API_KEY``/``SHOPIFY_ADMIN_TOKEN`` en ``.env`` : intégration
TOTALEMENT no-op (aucun appel réseau, jamais d'exception). C'est le motif du
dépôt pour toute fonctionnalité à clé (OCR, chatbot SQL, email sortant…) —
voir CLAUDE.md.

Deux directions :

* ERP → Shopify : ``sync_catalogue`` pousse prix TTC + stock disponible des
  produits marqués ``vendable_en_ligne`` (``ProduitSync``, dans CETTE app —
  jamais un nouveau champ sur ``stock.Produit``, hors périmètre SUPPLY).
* Shopify → ERP : ``traiter_webhook_commande`` vérifie la signature HMAC puis
  crée Facture + Paiement + décrémente le stock via ``ventes.services``/
  ``stock.services`` (jamais un import direct de leurs ``models``).

Aucune dépendance externe ajoutée : ``httpx`` (déjà une dépendance du projet,
voir ``apps.publicapi.delivery``) pour les appels sortants, ``hmac``/
``hashlib``/``base64`` (stdlib) pour la vérification de signature.
"""
import base64
import hashlib
import hmac
import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import CommandeSync, ConnexionEcommerce, ProduitSync

logger = logging.getLogger(__name__)

PLATEFORME = ConnexionEcommerce.Plateforme.SHOPIFY


def is_configured():
    """``True`` si une clé API Shopify est configurée en ``.env``.

    Lu à CHAQUE appel (jamais mis en cache) — le fondateur doit pouvoir
    armer/désarmer sans redéployer, même patron que
    ``apps.veille_ao.tasks.collecte_active``."""
    return bool(getattr(settings, 'SHOPIFY_ADMIN_TOKEN', '') or '')


def _connexion_active(company):
    return ConnexionEcommerce.objects.filter(
        company=company, plateforme=PLATEFORME, actif=True).first()


def sync_catalogue(company):
    """NTRET18 — pousse le catalogue (prix TTC + stock) vers Shopify.

    NO-OP TOTAL sans clé configurée (``is_configured()`` False) ou sans
    ``ConnexionEcommerce`` active pour la société : aucun appel réseau, aucune
    exception. Renvoie un résumé ``{'skipped': bool, 'reason': str, ...}``.
    """
    if not is_configured():
        return {'skipped': True, 'reason': 'no_api_key', 'pushed': 0}
    connexion = _connexion_active(company)
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
    if not secret or not hmac_header:
        return False
    digest = hmac.new(secret.encode('utf-8'), raw_body, hashlib.sha256).digest()
    computed = base64.b64encode(digest).decode('utf-8')
    return hmac.compare_digest(computed, hmac_header)


def traiter_webhook_commande(*, company, external_order_id, montant_ttc,
                             email_client='', libelle='', lignes=None,
                             user=None, payload_brut=None):
    """NTRET18 — traite une commande Shopify PAYÉE (webhook), IDEMPOTENT.

    Clé d'idempotence : (connexion, external_order_id) — un webhook rejoué
    (Shopify livre AU MOINS une fois) ne crée jamais deux fois la facture.
    Résout le client par email via ``crm.selectors.find_client_by_email``
    (LECTURE SEULE — cette app ne crée JAMAIS de ``crm.Client``, hors
    périmètre SUPPLY) : un email inconnu produit une ``CommandeSync`` en
    ERREUR, en attente de rapprochement manuel, jamais un crash du webhook.
    """
    connexion = _connexion_active(company)
    if connexion is None:
        return None

    external_order_id = str(external_order_id)
    existing = CommandeSync.objects.filter(
        connexion=connexion, external_order_id=external_order_id).first()
    if existing is not None:
        return existing  # idempotent : déjà traitée

    from apps.crm import selectors as crm_selectors

    client = (
        crm_selectors.find_client_by_email(email_client, company=company)
        if email_client else None)
    if client is None:
        return CommandeSync.objects.create(
            company=company, connexion=connexion,
            external_order_id=external_order_id,
            statut=CommandeSync.Statut.ERREUR,
            message=(
                f"Client introuvable pour l'email '{email_client}' — "
                'rapprochement manuel requis (ecommerce_connect ne crée '
                'jamais de crm.Client).'),
            payload_brut=payload_brut or {})

    from apps.stock import selectors as stock_selectors
    from apps.stock import services as stock_services
    from apps.ventes import services as ventes_services

    montant = Decimal(str(montant_ttc))
    taux_tva = Decimal('20.00')
    montant_ht = (montant / (Decimal('1') + taux_tva / Decimal('100'))).quantize(
        Decimal('0.01'))
    montant_tva = (montant - montant_ht).quantize(Decimal('0.01'))

    with transaction.atomic():
        facture = ventes_services.creer_facture_classique(
            company=company, client=client, user=user, taux_tva=taux_tva,
            montant_ht=montant_ht, montant_tva=montant_tva,
            montant_ttc=montant,
            libelle=libelle or f'Commande {connexion.get_plateforme_display()} '
                               f'#{external_order_id}')
        ventes_services.enregistrer_paiement(
            facture=facture, montant=montant, mode='carte',
            date_paiement=timezone.now().date(), user=user,
            reference=external_order_id,
            note='Paiement en ligne (webhook e-commerce, NTRET18).')

        for ligne in (lignes or []):
            produit_id = ligne.get('produit_id')
            quantite = int(ligne.get('quantite') or 0)
            if not produit_id or quantite <= 0:
                continue
            produit = stock_selectors.get_produit_scoped(company, produit_id)
            if produit is None:
                continue
            avant = produit.quantite_stock
            apres = max(avant - quantite, 0)
            stock_services.record_stock_movement(
                company=company, produit=produit, type_mouvement='sortie',
                quantite=quantite, quantite_avant=avant, quantite_apres=apres,
                reference=f'ECOM-{external_order_id}',
                note=f'Vente {connexion.get_plateforme_display()}',
                created_by=user)

        commande = CommandeSync.objects.create(
            company=company, connexion=connexion,
            external_order_id=external_order_id, facture_id=facture.id,
            statut=CommandeSync.Statut.TRAITEE, payload_brut=payload_brut or {})
    return commande
