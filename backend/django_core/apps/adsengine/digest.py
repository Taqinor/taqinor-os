"""ADSDEEP62 — Digest QUOTIDIEN FR (dépense/conversations/leads/signatures/
alertes actives/meilleure ad de la VEILLE), émis via le moteur de
notifications UNIFIÉ (``notifications.services.notify``) — in-app + email
best-effort, opt-out PAR UTILISATEUR respecté. Réutilise l'infra EXISTANTE
(``EventType.DIGEST`` + ``NotificationPreference``) — le MÊME toggle que le
récapitulatif N76 quotidien/hebdo (``notifications/digests.py``) : jamais un
nouveau type d'événement, jamais une table de préférence dédiée. WhatsApp
reste GATÉ (BSP) — aucun template WhatsApp construit ici (dossier
adsdeep-existing-map, gated ADSENG19/34).

Défensif comme ``brief.py`` : chaque section (dépense/conversations/leads,
signatures Odoo, alertes actives, top ad) est calculée dans son propre
try/except — une section en échec ne casse jamais le digest ni les sociétés
suivantes (best-effort par société, comme ``generate_weekly_brief``). Sans
clé email configurée, ``notify()`` dégrade proprement (ligne in-app seule,
jamais d'exception) — comportement du moteur de notifications déjà éprouvé.
"""
from __future__ import annotations

import datetime
import logging

from django.contrib.contenttypes.models import ContentType
from django.db.models import Sum

from .models import AdCampaignMirror, AdMirror, EngineAlert, InsightSnapshot

logger = logging.getLogger(__name__)


def yesterday(now=None):
    """Date de la VEILLE par rapport à ``now`` (date, défaut aujourd'hui)."""
    today = now if isinstance(now, datetime.date) else datetime.date.today()
    return today - datetime.timedelta(days=1)


def _companies_with_campaigns():
    """Sociétés actives ayant au moins une campagne synchronisée (rien à
    résumer sinon — même garde que ``tasks.generate_weekly_brief``)."""
    from authentication.selectors import active_companies

    return [c for c in active_companies()
            if AdCampaignMirror.objects.filter(company=c).exists()]


def _recipients(company):
    """Gérants/staff destinataires du digest (même patron de sélection que
    ``notifications.digests._recipients`` : priorité admin/responsable, repli
    tous les actifs de la société — jamais un utilisateur d'une autre)."""
    try:
        from authentication.models import CustomUser
        base = CustomUser.objects.filter(company=company, is_active=True)
        managers = [
            u for u in base
            if getattr(u, 'is_admin_role', False)
            or getattr(u, 'role_tier', None) in ('admin', 'responsable')
        ]
        return managers or list(base)
    except Exception:  # pragma: no cover - défensif
        logger.warning(
            'adsdeep62: destinataires introuvables pour la société %s',
            getattr(company, 'pk', None), exc_info=True)
        return []


def _spend_conversations_for_day(company, day):
    """Dépense + conversations agrégées niveau CAMPAGNE pour ``day`` (déjà
    synchronisées quotidiennement par ENG6 ``sync_insights_daily``)."""
    ct = ContentType.objects.get_for_model(AdCampaignMirror)
    agg = (InsightSnapshot.objects
           .filter(company=company, content_type=ct, date=day)
           .aggregate(spend=Sum('spend'), conversations=Sum('conversations')))
    return agg['spend'] or 0, agg['conversations'] or 0


def _leads_for_day(company, day):
    """Leads RÉELS capturés le jour ``day`` (``MetaLeadMirror.created_time`` —
    l'horodatage Meta réel, pas notre heure d'insertion DB, pour ne jamais
    compter un backfill historique comme un lead « d'hier »)."""
    from .models import MetaLeadMirror

    return MetaLeadMirror.objects.filter(
        company=company, created_time__date=day).count()


def _signatures_for_day(company, day):
    """Nombre de signatures Odoo (deals signés) DATÉES du jour ``day``.
    Dégrade proprement comme ``metrics._signed_ca_daily`` : ``None`` si Odoo
    n'est pas configuré ou en échec (jamais un 0 fabriqué sur un connecteur
    éteint — distinct d'un vrai zéro signature)."""
    from .odoo_client import is_configured

    if not is_configured():
        return None
    try:
        from .odoo_selectors import signed_deals
        deals = signed_deals(since=day)
    except Exception:  # noqa: BLE001 — jamais un 500/crash sur une panne Odoo
        logger.warning(
            'adsdeep62: lecture des signatures Odoo échouée pour %s',
            getattr(company, 'pk', None), exc_info=True)
        return None
    count = 0
    for deal in deals:
        raw_date = deal.get('date')
        try:
            d = datetime.date.fromisoformat(str(raw_date)[:10])
        except (TypeError, ValueError):
            continue
        if d == day:
            count += 1
    return count


def _active_alerts_count(company):
    """Alertes moteur non acquittées (ENG13 ``EngineAlert``), toutes
    sévérités confondues."""
    return EngineAlert.objects.filter(
        company=company, acknowledged=False).count()


def _top_ad_for_day(company, day):
    """Meilleure ad de la veille (résultats), depuis les instantanés AU
    NIVEAU AD (synchro ADSDEEP2 — pas encore garantie en prod, gap documenté
    dans ``docs/engine/research/adsdeep-existing-map.md``). ``None`` si aucun
    instantané ad-level pour ``day`` : jamais un « top ad » fabriqué depuis
    des données absentes."""
    ct = ContentType.objects.get_for_model(AdMirror)
    best = (InsightSnapshot.objects
            .filter(company=company, content_type=ct, date=day,
                    results__gt=0)
            .order_by('-results', '-spend')
            .first())
    if best is None:
        return None
    ad = AdMirror.objects.filter(company=company, pk=best.object_id).first()
    if ad is None:
        return None
    return {
        'name': ad.name or ad.meta_id,
        'results': best.results,
        'spend': str(best.spend or 0),
    }


def build_digest_data(company, *, now=None):
    """Construit le contenu du digest de la VEILLE pour ``company``. Chaque
    section est isolée (best-effort) : une section en échec vaut ``None``/0
    sans jamais casser les autres."""
    day = yesterday(now)
    try:
        spend, conversations = _spend_conversations_for_day(company, day)
    except Exception:  # pragma: no cover - défensif par section
        logger.warning(
            'adsdeep62: section dépense/conversations en échec pour %s',
            getattr(company, 'pk', None), exc_info=True)
        spend, conversations = 0, 0
    try:
        leads = _leads_for_day(company, day)
    except Exception:  # pragma: no cover - défensif par section
        logger.warning('adsdeep62: section leads en échec pour %s',
                       getattr(company, 'pk', None), exc_info=True)
        leads = 0
    try:
        signatures = _signatures_for_day(company, day)
    except Exception:  # pragma: no cover - défensif par section
        logger.warning('adsdeep62: section signatures en échec pour %s',
                       getattr(company, 'pk', None), exc_info=True)
        signatures = None
    try:
        alertes_actives = _active_alerts_count(company)
    except Exception:  # pragma: no cover - défensif par section
        logger.warning('adsdeep62: section alertes en échec pour %s',
                       getattr(company, 'pk', None), exc_info=True)
        alertes_actives = 0
    try:
        top_ad = _top_ad_for_day(company, day)
    except Exception:  # pragma: no cover - défensif par section
        logger.warning('adsdeep62: section top ad en échec pour %s',
                       getattr(company, 'pk', None), exc_info=True)
        top_ad = None

    # PUB57 — liens profonds PAR ITEM (jamais un seul lien générique vers le
    # dashboard quand une entité précise est mentionnée) : chaque section
    # actionnable porte SON propre lien vers l'écran où AGIR — l'alerte vers
    # « Règles & anomalies » (son historique), la meilleure ad vers le
    # Cockpit. Réutilisables par tout futur consommateur riche du digest ;
    # ``send_daily_digest`` (ci-dessous) choisit déjà le plus pertinent comme
    # lien PRINCIPAL de la notification.
    alertes_lien = '/publicite/regles' if alertes_actives else None
    top_ad_lien = '/publicite/cockpit' if top_ad else None

    return {
        'date': day.isoformat(),
        'spend': str(spend),
        'conversations': conversations,
        'leads': leads,
        'signatures': signatures,
        'alertes_actives': alertes_actives,
        'alertes_lien': alertes_lien,
        'top_ad': top_ad,
        'top_ad_lien': top_ad_lien,
    }


def format_body(data):
    """Corps FR lisible du digest — uniquement des NOMBRES calculés dans des
    phrases template (même doctrine anti-hallucination que ``brief.py``).

    PUB57 — chaque ligne ACTIONNABLE (alertes/meilleure ad) porte désormais
    son lien profond en clair (``→ /publicite/...``) : lisible tel quel en
    in-app (texte brut) et en email (repli texte du corps HTML)."""
    lines = [f"Récapitulatif publicité du {data['date']} :", '']
    lines.append(f"- Dépense : {data['spend']} MAD")
    lines.append(f"- Conversations WhatsApp : {data['conversations']}")
    lines.append(f"- Leads : {data['leads']}")
    if data['signatures'] is not None:
        lines.append(f"- Signatures : {data['signatures']}")
    alertes_line = f"- Alertes actives : {data['alertes_actives']}"
    if data.get('alertes_lien'):
        alertes_line += f" → {data['alertes_lien']}"
    lines.append(alertes_line)
    top_ad = data.get('top_ad')
    if top_ad:
        top_ad_line = (
            f"- Meilleure ad de la veille : {top_ad['name']} "
            f"({top_ad['results']} résultat(s), {top_ad['spend']} MAD)")
        if data.get('top_ad_lien'):
            top_ad_line += f" → {data['top_ad_lien']}"
        lines.append(top_ad_line)
    return '\n'.join(lines)


def send_daily_digest(company, *, now=None):
    """Construit le digest de la veille et le notifie à chaque gérant/staff
    de ``company`` (in-app + email best-effort, opt-out PAR UTILISATEUR
    respecté via ``notify()`` — ``EventType.DIGEST``, la même préférence que
    le récap N76). Renvoie le nombre de notifications ÉMISES (préférence
    in-app active — ``notify()`` renvoie ``None`` sinon).

    PUB57 — le lien PRINCIPAL de la notification (clic sur la cloche/l'email)
    n'est plus TOUJOURS le dashboard générique : il pointe vers l'item le
    plus actionnable du jour — des alertes actives priment (sécurité budget),
    sinon la meilleure ad de la veille, sinon le dashboard par défaut."""
    from apps.notifications.models import EventType
    from apps.notifications.services import notify

    data = build_digest_data(company, now=now)
    body = format_body(data)
    primary_link = (
        data.get('alertes_lien') or data.get('top_ad_lien')
        or '/publicite/tableau-de-bord')
    emitted = 0
    for user in _recipients(company):
        if notify(
                user, EventType.DIGEST, 'Récapitulatif publicité quotidien',
                body=body, link=primary_link,
                company=company) is not None:
            emitted += 1
    return emitted


def run_daily_digest_for_all():
    """ADSDEEP62 — Digest quotidien de chaque société ayant au moins une
    campagne synchronisée. Best-effort par société (une société en échec
    n'empêche jamais les suivantes, comme ``generate_weekly_brief``). Appelée
    par la tâche Celery ``adsengine.daily_ads_digest`` (``tasks.py`` — même
    répartition que ``brief.build_brief``/``tasks.generate_weekly_brief``)."""
    sent = 0
    for company in _companies_with_campaigns():
        try:
            sent += send_daily_digest(company)
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'adsengine.daily_ads_digest: échec société %s',
                company.pk, exc_info=True)
            continue
    logger.info('adsengine.daily_ads_digest: %s notification(s) émise(s)', sent)
    return {'digests_emitted': sent}
