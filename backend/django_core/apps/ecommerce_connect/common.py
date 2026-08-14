"""Logique PARTAGÉE Shopify (NTRET18) / WooCommerce (NTRET19) — NTRET19.

Extrait de ``shopify.py`` (NTRET18, seul connecteur à l'époque) : le mapping
« commande externe payée → Facture + Paiement + décrément stock » est
IDENTIQUE entre les deux plateformes — seul le FORMAT du webhook entrant
change. ``shopify.py``/``woocommerce.py`` normalisent chacun leur payload
plateforme puis appellent ``traiter_commande_payee`` ici, UNE SEULE fois —
jamais dupliquée.

Frontière inter-app (CLAUDE.md) : ``ventes.services``/``stock.selectors``/
``stock.services``/``crm.selectors`` sont les seuls points d'entrée —
jamais un import direct de leurs ``models``.
"""
import base64
import hashlib
import hmac
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import CommandeSync, ConnexionEcommerce


def connexion_active(company, plateforme):
    """``ConnexionEcommerce`` ACTIVE de la société pour cette plateforme, ou
    None. Lecture seule."""
    return ConnexionEcommerce.objects.filter(
        company=company, plateforme=plateforme, actif=True).first()


def verify_hmac_base64(secret, raw_body: bytes, signature_header: str) -> bool:
    """Vérifie une signature webhook base64(HMAC-SHA256) — format PARTAGÉ par
    Shopify (``X-Shopify-Hmac-Sha256``) ET WooCommerce
    (``X-WC-Webhook-Signature``). ``False`` sans secret configuré (JAMAIS
    d'acceptation par défaut) ou sans en-tête fourni."""
    if not secret or not signature_header:
        return False
    digest = hmac.new(
        secret.encode('utf-8'), raw_body, hashlib.sha256).digest()
    computed = base64.b64encode(digest).decode('utf-8')
    return hmac.compare_digest(computed, signature_header)


def traiter_commande_payee(*, connexion, external_order_id, montant_ttc,
                           email_client='', libelle='', lignes=None,
                           user=None, payload_brut=None):
    """Traite UNE commande plateforme (Shopify OU WooCommerce) PAYÉE —
    IDEMPOTENT (clé = ``connexion`` + ``external_order_id`` : un webhook
    rejoué, at-least-once comme tout webhook e-commerce, ne crée JAMAIS deux
    fois la facture).

    Résout le client par email via ``crm.selectors.find_client_by_email``
    (LECTURE SEULE — cette app ne crée JAMAIS de ``crm.Client``, hors
    périmètre SUPPLY) : un email inconnu produit une ``CommandeSync`` en
    ERREUR, en attente de rapprochement manuel, JAMAIS un crash du webhook.

    ``lignes`` — liste de ``{'produit_id': int, 'quantite': int}`` (mapping
    externe→interne déjà résolu par l'appelant plateforme).
    """
    company = connexion.company
    external_order_id = str(external_order_id)

    existing = CommandeSync.objects.filter(
        connexion=connexion, external_order_id=external_order_id).first()
    if existing is not None:
        return existing  # idempotent : déjà traitée (webhook rejoué)

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
            montant_ht=montant_ht, montant_tva=montant_tva, montant_ttc=montant,
            libelle=libelle or (
                f'Commande {connexion.get_plateforme_display()} '
                f'#{external_order_id}'))
        ventes_services.enregistrer_paiement(
            facture=facture, montant=montant, mode='carte',
            date_paiement=timezone.now().date(), user=user,
            reference=external_order_id,
            note='Paiement en ligne (webhook e-commerce, NTRET18/19).')

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
