"""Service d'ÉMISSION appelé PAR d'autres apps (XSTK23).

`stock`/`installations` n'importent JAMAIS les models/signals de `publicapi` :
ils appellent ces fonctions (best-effort, jamais bloquant pour l'appelant).
Ceci est le point d'entrée « service » attendu par la règle de frontière
inter-app (jamais d'import de models cross-app dans l'autre sens non plus —
`publicapi` ne référence ici que ses propres modèles).
"""
import logging

from . import delivery
from .constants import EVENT_STOCK_SEUIL_ATTEINT, EVENT_LIVRAISON_LIVREE

logger = logging.getLogger(__name__)


def _safe_dispatch(company_id, event, payload):
    try:
        delivery.dispatch_event(company_id, event, payload)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.exception('Webhook dispatch failed for %s', event)


def notify_stock_seuil_atteint(
        *, company_id, produit_id, sku, nom, quantite_disponible, seuil):
    """XSTK23 — franchissement du seuil effectif À LA BAISSE.

    L'appelant (apps.stock.services) est seul responsable de ne déclencher
    ceci qu'UNE FOIS par franchissement (compare l'état avant/après autour du
    mouvement qui fait passer le disponible sous le seuil). Best-effort :
    n'importe jamais Produit ici, ne reçoit que des scalaires — jamais de
    prix d'achat/vente dans la charge utile.
    """
    _safe_dispatch(company_id, EVENT_STOCK_SEUIL_ATTEINT, {
        'event': EVENT_STOCK_SEUIL_ATTEINT,
        'produit_id': produit_id,
        'sku': sku,
        'nom': nom,
        'quantite_disponible': quantite_disponible,
        'seuil': seuil,
    })


def notify_livraison_livree(
        *, company_id, livraison_id, reference, installation_id,
        numero_suivi=None):
    """XSTK23 — livraison passée au statut « livrée ».

    Appelée depuis `apps.installations` (action `livrer`), jamais deux fois
    pour la même livraison (l'appelant garde l'idempotence — même contrat
    que la notification client XSTK22)."""
    _safe_dispatch(company_id, EVENT_LIVRAISON_LIVREE, {
        'event': EVENT_LIVRAISON_LIVREE,
        'livraison_id': livraison_id,
        'reference': reference,
        'installation_id': installation_id,
        'numero_suivi': numero_suivi,
    })


# ─────────────────────────────────────────────────────────────────────────────
# YOPSB11 — Archivage par lots de `WebhookDelivery` (journal à forte croissance)
#
# Le journal des livraisons est append-only et grossit sans borne (une ligne par
# tentative). La politique YOPSB11 (registre partagé YOPSB10) déplace les
# livraisons plus vieilles que `jours` vers `WebhookDeliveryArchive` (par lots,
# un commit par lot) puis les supprime de la table vive. Fenêtre par défaut
# 0 = OFF (comportement inchangé) ; réglage via `WEBHOOK_DELIVERY_ARCHIVE_DAYS`.

DEFAULT_WEBHOOK_DELIVERY_ARCHIVE_DAYS = 0


def _webhook_delivery_to_archive(row):
    return {
        'original_id': row.pk,
        'company_id': row.company_id,
        'webhook_id': row.webhook_id,
        'event': row.event,
        'event_id': row.event_id,
        'payload': row.payload,
        'status': row.status,
        'response_status': row.response_status,
        'error': row.error,
        'created_at': row.created_at,
    }


def archiver_anciens(now, jours, apply_=True):
    """YOPSB11 — archive les `WebhookDelivery` plus vieilles que `jours` (par
    lots de 5 000, un commit par lot). `jours <= 0` (défaut OFF) → 0 ;
    `apply_=False` (dry-run) compte sans déplacer. Renvoie le nombre archivé."""
    from core.retention import archive_old_rows
    from .models import WebhookDelivery, WebhookDeliveryArchive

    return archive_old_rows(
        WebhookDelivery, WebhookDeliveryArchive, _webhook_delivery_to_archive,
        cutoff_field='created_at', now=now, jours=jours, apply_=apply_,
    )


# ─────────────────────────────────────────────────────────────────────────────
# NTAPI27 — Bac à sable API : société-jumelle isolée + jeu de données de démo.
#
# Une clé `environnement='test'` (NTAPI26) est émise directement sur la
# société-jumelle (`SandboxTenant.sandbox_company`) : AUCUN code spécial
# n'est nécessaire dans les viewsets publics pour garantir l'isolation — le
# scoping `company_id` habituel suffit. Les écritures de démo passent
# EXCLUSIVEMENT par les points d'entrée cross-app déjà sanctionnés (XPLT5 —
# `crm.services.create_lead_from_public_api`, le même que celui qu'un vrai
# appelant `leads:write` utilise), jamais par un import direct de
# `apps.crm.models` — la frontière inter-app reste intacte y compris pour du
# code purement interne.

DEMO_LEADS = [
    {'nom': 'Ferme Solaire Atlas (démo)', 'email': 'demo.atlas@sandbox.taqinor.ma',
     'telephone': '+212600000001', 'ville': 'Marrakech', 'canal': 'site_web'},
    {'nom': 'Villa Zenata (démo)', 'email': 'demo.zenata@sandbox.taqinor.ma',
     'telephone': '+212600000002', 'ville': 'Casablanca', 'canal': 'recommandation'},
    {'nom': 'Coopérative Agricole Souss (démo)', 'email': 'demo.souss@sandbox.taqinor.ma',
     'telephone': '+212600000003', 'ville': 'Agadir', 'canal': 'salon'},
]


def get_or_create_sandbox(company):
    """NTAPI27 — renvoie le `SandboxTenant` de `company` (le crée + seed au
    besoin). Idempotent : un appel répété réutilise le même sandbox."""
    from authentication.models import Company
    from .models import SandboxTenant

    tenant = SandboxTenant.objects.filter(company=company).first()
    if tenant:
        return tenant

    sandbox_company = Company.objects.create(
        nom=f'{company.nom} — Bac à sable API',
        actif=True,
    )
    tenant = SandboxTenant.objects.create(
        company=company, sandbox_company=sandbox_company)
    seed_sandbox_for_company(tenant)
    return tenant


def seed_sandbox_for_company(tenant):
    """NTAPI27 — seed IDEMPOTENT/ADDITIF le sandbox de `tenant` : ne recrée
    jamais un lead de démo déjà présent (dédup sur l'email, via le
    sélecteur `crm.selectors.existing_lead_emails` — jamais d'import direct
    de `apps.crm.models`). Renvoie le nombre de leads créés."""
    from apps.crm.services import create_lead_from_public_api
    from apps.crm.selectors import existing_lead_emails

    already = existing_lead_emails(
        tenant.sandbox_company, [d['email'] for d in DEMO_LEADS])
    created = 0
    for demo in DEMO_LEADS:
        if demo['email'] in already:
            continue
        create_lead_from_public_api(company=tenant.sandbox_company, fields=demo)
        created += 1
    return created


def reset_sandbox(tenant):
    """NTAPI27 — remet le sandbox de `tenant` à son état initial : supprime
    TOUTES les données de la société-jumelle (jamais celles de la société
    réelle — `sandbox_company` est un id distinct), via le service
    d'ÉCRITURE cross-app sanctionné `crm.services.delete_leads_for_company`,
    puis reseed le jeu de démo. Renvoie le nombre de leads recréés."""
    from django.utils import timezone
    from apps.crm.services import delete_leads_for_company

    delete_leads_for_company(tenant.sandbox_company)
    created = seed_sandbox_for_company(tenant)
    tenant.reset_at = timezone.now()
    tenant.save(update_fields=['reset_at'])
    return created
