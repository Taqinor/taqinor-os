"""ZSTK1 — Action planifiée : recompute réappro + alertes de rupture (cron).

Les sélecteurs de réappro existent (`produits_a_reapprovisionner` FG54,
`previsions_reappro` FG65, réappro multi-dépôts FG326) mais AUCUN cron ne les
faisait tourner — Odoo lance une action nocturne « reordering rules run ».
Aujourd'hui personne n'est notifié tant qu'un humain n'ouvre pas l'écran.

Autodécouvert par ``erp_agentique.celery`` (``autodiscover_tasks()``), comme
``apps.rh.tasks``/``apps.installations.tasks``. Boucle PAR société active
(jamais une company lue d'une requête) ; une exception sur l'une n'empêche
jamais les suivantes (best-effort, journalisé). Aucun BCF n'est créé
automatiquement ici — SUGGESTION seulement (réutilise `produits_a_reapprovisionner`,
jamais de logique dupliquée).

Idempotence (« une seule notification par jour par société ») : avant
d'émettre, on vérifie qu'aucune ``Notification`` du même ``event_type``
portant le même ``link`` stable (encodant la société) n'a déjà été créée
AUJOURD'HUI (Africa/Casablanca).
"""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


def _deja_notifie_aujourdhui(event_type, link):
    """Vrai si une notification portant CE lien a déjà été créée aujourd'hui
    (Africa/Casablanca) — quel que soit le destinataire (idempotence PAR
    société, pas par destinataire)."""
    from apps.notifications.models import Notification
    today = timezone.localdate()
    try:
        return Notification.objects.filter(
            event_type=event_type, link=link,
            created_at__date=today).exists()
    except Exception:  # pragma: no cover - défensif
        return False


def _recipients_reappro(company):
    """Responsables/admins actifs de la société (destinataires de l'alerte).
    À défaut (aucun rôle taggé), tous les utilisateurs actifs."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    qs = User.objects.filter(
        company=company, is_active=True,
        role_legacy__in=['responsable', 'admin'])
    if qs.exists():
        return list(qs)
    return list(User.objects.filter(company=company, is_active=True))


@shared_task(name='stock.recompute_reordering')
def recompute_reordering_task():
    """ZSTK1 — pour CHAQUE société, calcule les produits sous seuil effectif
    (réutilise `apps.stock.selectors.a_reapprovisionner`/
    `apps.stock.services.produits_a_reapprovisionner` — jamais de logique
    dupliquée) et notifie best-effort (« N références à réapprovisionner »).
    Idempotent : une seule notification par jour par société. Renvoie un dict
    {company_id: nb_produits_notifies} (0 = aucun produit sous seuil, ou déjà
    notifié aujourd'hui)."""
    from authentication.models import Company
    from apps.stock.services import produits_a_reapprovisionner
    from apps.notifications.services import notify_many
    from apps.notifications.models import EventType

    today = timezone.localdate()
    result = {}
    for company in Company.objects.all():
        try:
            besoins = produits_a_reapprovisionner(company)
        except Exception:  # noqa: BLE001 — une société en échec n'arrête pas
            logger.warning(
                'stock.recompute_reordering: échec calcul société %s',
                company.id, exc_info=True)
            continue
        if not besoins:
            result[company.id] = 0
            continue
        link = f'stock-reappro-{company.id}-{today.isoformat()}'
        if _deja_notifie_aujourdhui(EventType.STOCK_LOW, link):
            result[company.id] = 0
            continue
        recipients = _recipients_reappro(company)
        noms = ', '.join(b['nom'] for b in besoins[:10])
        suffixe = '…' if len(besoins) > 10 else ''
        try:
            notify_many(
                recipients, EventType.STOCK_LOW,
                title=f'{len(besoins)} référence(s) à réapprovisionner',
                body=f'Sous le seuil effectif : {noms}{suffixe}.',
                link=link, company=company)
            result[company.id] = len(besoins)
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning(
                'stock.recompute_reordering: notification échouée société %s',
                company.id, exc_info=True)
            result[company.id] = 0
    return result
