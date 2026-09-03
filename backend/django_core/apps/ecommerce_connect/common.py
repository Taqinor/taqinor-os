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
    # QJR413 (a) — COMPARER EN BYTES. ``compare_digest(str, str)`` lève un
    # ``TypeError`` non intercepté dès qu'un opérande porte un caractère
    # non-ASCII : un seul octet hostile dans ``X-Shopify-Hmac-Sha256`` /
    # ``X-WC-Webhook-Signature`` rendait un HTTP 500 NON AUTHENTIFIÉ au lieu
    # d'un refus. Même patron que ``ventes.domain.cycle_vie``.
    return hmac.compare_digest(computed.encode('utf-8'),
                               str(signature_header).encode('utf-8'))


def connexion_par_signature(plateforme, raw_body: bytes, signature_header: str):
    """AUD212 — résout la ``ConnexionEcommerce`` dont le secret PROPRE valide
    cette signature. C'est LE point d'entrée d'un webhook public.

    Avant ce correctif, le secret HMAC était une variable ``.env`` UNIQUE pour
    toute la plateforme et le tenant venait d'un en-tête CLIENT
    (``X-Shopify-Shop-Domain`` / ``X-WC-Webhook-Source``, résolu par un
    ``boutique_url__icontains`` non déterministe) : la société A, qui connaît
    légitimement le secret partagé, pouvait signer un POST et le faire
    atterrir — vraie Facture, vrai Paiement, vraie sortie de stock — dans le
    tenant de B en changeant simplement l'en-tête. Désormais c'est le SECRET
    qui désigne le tenant, et l'en-tête n'est plus lu du tout.

    Fail-closed : ``None`` sans en-tête, sans connexion active, ou si aucun
    secret ne valide. Une connexion sans secret n'accepte JAMAIS de webhook
    (``verify_hmac_base64`` renvoie ``False`` sur secret vide) — la
    comparaison reste en temps constant (``hmac.compare_digest``).
    """
    if not signature_header:
        return None
    connexions = (
        ConnexionEcommerce.objects
        .filter(plateforme=plateforme, actif=True)
        .exclude(webhook_secret='')
        .select_related('company')
        .order_by('id'))
    for connexion in connexions:
        if verify_hmac_base64(
                connexion.webhook_secret, raw_body, signature_header):
            return connexion
    return None


# ── AUD202 — devise : l'ERP facture en MAD, JAMAIS dans la devise du panier ──
# `facturation.Facture.devise` a pour défaut `'MAD'` (models.py, champ FG52) et
# `creer_facture_classique` ne pose aucune devise : toute commande libellée dans
# une AUTRE devise serait donc encaissée comme si ses montants étaient des MAD.
# On REFUSE explicitement au lieu d'accepter en silence.
DEVISE_ERP = 'MAD'

# Repli quand AUCUNE ligne résolue ne porte de taux : c'est le défaut du modèle
# `Facture.taux_tva` (facturation/models.py), pas un chiffre inventé ici. Dès
# qu'un `Produit.tva` est lisible, c'est LUI qui fait foi (DC7).
TAUX_TVA_DEFAUT = Decimal('20.00')

_CENTIME = Decimal('0.01')


def devise_compatible(devise_payload) -> bool:
    """``True`` si la devise annoncée par la plateforme est facturable telle
    quelle par l'ERP (AUD202).

    Une devise ABSENTE du payload n'est pas un mismatch (rien à comparer) :
    on ne refuse que sur une divergence RÉELLEMENT constatée."""
    if not devise_payload:
        return True
    return str(devise_payload).strip().upper() == DEVISE_ERP


def ventilation_tva(company, lignes, montant_ttc):
    """Dérive ``(taux_tva, montant_ht, montant_tva)`` d'une commande externe
    depuis le taux de CHAQUE produit (``Produit.tva``) — AUD202.

    Avant ce correctif le taux était figé à 20 %, alors que le catalogue
    solaire porte 10 % sur les panneaux PV (`seed_catalogue`) : une commande
    web de panneaux était facturée au mauvais taux.

    Trois cas, tous explicites :

    * aucune ligne résolue ne porte de taux → repli ``TAUX_TVA_DEFAUT``
      (défaut du modèle `Facture`, comportement historique) ;
    * un seul taux distinct → c'est LUI (le cas nominal) ;
    * plusieurs taux → ventilation ligne par ligne à partir des montants TTC
      de ligne fournis par la plateforme ; sans ces montants, on lève
      ``ValueError`` plutôt que d'imprimer un taux de tête arbitraire sur un
      document client (règle « aucun chiffre inventé »).
    """
    from apps.stock import selectors as stock_selectors

    montant = Decimal(str(montant_ttc))
    resolues = []
    for ligne in (lignes or []):
        produit_id = ligne.get('produit_id')
        if not produit_id:
            continue
        produit = stock_selectors.get_produit_scoped(company, produit_id)
        if produit is None or produit.tva is None:
            continue
        brut = ligne.get('montant_ttc')
        resolues.append((
            Decimal(str(produit.tva)),
            None if brut in (None, '') else Decimal(str(brut)),
        ))

    taux_distincts = {taux for taux, _ in resolues}

    if len(taux_distincts) <= 1:
        taux = taux_distincts.pop() if taux_distincts else TAUX_TVA_DEFAUT
        ht = (montant / (Decimal('1') + taux / Decimal('100'))).quantize(_CENTIME)
        return taux, ht, (montant - ht).quantize(_CENTIME)

    if any(brut is None for _, brut in resolues):
        raise ValueError(
            'Taux de TVA mixtes sur la commande sans montant de ligne '
            'fourni par la plateforme — rapprochement manuel requis '
            '(aucun taux de tête ne serait exact).')
    total_lignes = sum((brut for _, brut in resolues), Decimal('0'))
    if abs(total_lignes - montant) > _CENTIME:
        raise ValueError(
            f'Taux de TVA mixtes et montants de ligne incohérents '
            f'({total_lignes} ≠ {montant}) — rapprochement manuel requis.')

    ht = sum(
        ((brut / (Decimal('1') + taux / Decimal('100'))).quantize(_CENTIME)
         for taux, brut in resolues),
        Decimal('0'))
    tva = (montant - ht).quantize(_CENTIME)
    taux_effectif = (
        (tva / ht * Decimal('100')).quantize(_CENTIME)
        if ht else TAUX_TVA_DEFAUT)
    return taux_effectif, ht, tva


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

    # AUD202 — un échec métier (TVA indérivable, stock insuffisant) ne doit
    # produire NI facture NI paiement NI mouvement : la transaction est
    # entièrement annulée, puis la commande est tracée en ERREUR pour
    # rapprochement manuel (jamais une 500, jamais un traitement partiel).
    try:
        with transaction.atomic():
            taux_tva, montant_ht, montant_tva = ventilation_tva(
                company, lignes, montant)
            facture = ventes_services.creer_facture_classique(
                company=company, client=client, user=user, taux_tva=taux_tva,
                montant_ht=montant_ht, montant_tva=montant_tva,
                montant_ttc=montant,
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
                # AUD202 — plus de `max(..., 0)` : une commande web qui
                # dépasse le stock disponible est REFUSÉE (sauf société en
                # stock négatif autorisé), au lieu d'écrire un mouvement
                # tronqué où `quantite ≠ avant − apres`.
                apres = avant - quantite
                stock_services.check_negative_stock_guard(company, avant, apres)
                stock_services.record_stock_movement(
                    company=company, produit=produit, type_mouvement='sortie',
                    quantite=quantite, quantite_avant=avant,
                    quantite_apres=apres,
                    reference=f'ECOM-{external_order_id}',
                    note=f'Vente {connexion.get_plateforme_display()}',
                    created_by=user)

            commande = CommandeSync.objects.create(
                company=company, connexion=connexion,
                external_order_id=external_order_id, facture_id=facture.id,
                statut=CommandeSync.Statut.TRAITEE,
                payload_brut=payload_brut or {})
    except ValueError as exc:
        return CommandeSync.objects.create(
            company=company, connexion=connexion,
            external_order_id=external_order_id,
            statut=CommandeSync.Statut.ERREUR, message=str(exc),
            payload_brut=payload_brut or {})
    return commande
