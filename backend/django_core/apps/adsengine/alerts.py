"""ENG13 — Alertes moteur WhatsApp-first (rendu + deep-link, envoi gated).

Ce module RÉEND les alertes du moteur en messages FR courts avec un deep-link
``wa.me`` vers les destinataires (Reda / Meryem) — mais **n'ENVOIE rien** :
l'envoi réel via template WhatsApp Business (BSP) est une décision fondateur
GATED (voir la liste GATED ENG de PLAN.md). Ici on rend + on liste seulement.

``create_alert`` est le point d'entrée que le moteur de garde-fous (ENG9) branche
via ``guardrails.emit_alert`` : une violation / anomalie / règle inopérante crée
une ligne ``EngineAlert`` (persistée, listable par le dashboard ENG23).

Destinataires : lus depuis ``ADSENGINE_ALERT_RECIPIENTS`` (numéros séparés par
des virgules) — jamais un numéro personnel codé en dur. Sans destinataire, le
lien ``wa.me`` ouvre WhatsApp sans numéro pré-rempli (choix manuel).
"""
from __future__ import annotations

import datetime
import os
from urllib.parse import quote

from .rules import (
    DEFAULT_COOLDOWN_HOURS, SEVERITY_CRITICAL, SEVERITY_EMOJI,
    SEVERITY_INFO, SEVERITY_LABELS_FR, SEVERITY_WARNING,
)


def alert_recipients():
    """Numéros destinataires (WhatsApp) depuis l'environnement, ou liste vide."""
    raw = os.environ.get('ADSENGINE_ALERT_RECIPIENTS', '') or ''
    return [n.strip() for n in raw.split(',') if n.strip()]


def wa_link(message, recipient=None):
    """Deep-link ``wa.me`` avec le message pré-rempli (URL-encodé).

    ``recipient`` fourni → ``https://wa.me/<numéro>?text=…`` ; sinon
    ``https://wa.me/?text=…`` (WhatsApp demande le destinataire). Jamais de
    numéro personnel codé en dur."""
    text = quote(message or '')
    if recipient:
        num = str(recipient).lstrip('+').replace(' ', '')
        return f'https://wa.me/{num}?text={text}'
    return f'https://wa.me/?text={text}'


def wa_links(message):
    """Un deep-link par destinataire configuré (liste). Vide → un lien sans
    numéro (choix manuel du destinataire)."""
    recipients = alert_recipients()
    if not recipients:
        return [wa_link(message)]
    return [wa_link(message, r) for r in recipients]


def create_alert(company, *, alert_type, message, action=None, detail=None):
    """ENG13 — Matérialise une ``EngineAlert`` (branché par ENG9 ``emit_alert``).

    Renvoie l'instance créée. La construction du deep-link ``wa.me`` reste au
    moment du RENDU (serializer / dashboard) — on ne stocke que le message FR."""
    from .models import EngineAlert

    return EngineAlert.objects.create(
        company=company, alert_type=alert_type, message=message,
        action=action, detail=detail or {})


# ── ADSENG18 — Gabarits d'alerte WhatsApp FR (dd-guardian §C2) ────────────────
# Chaque gabarit suit la forme : [emoji] cause racine (1 ligne) → recommandation
# (1 ligne) → deep link ERP. L'ENVOI réel via template WhatsApp Business (BSP)
# reste GATED ; ces payloads sont le CONTENU (prêt le jour où le gate s'ouvre) et
# rendent à l'identique dans le flux d'alertes in-app entre-temps.

# Chemins ERP profonds (front `module.config.jsx`). Base optionnelle via
# ADSENGINE_APP_BASE_URL ; sans elle, lien relatif.
DEEP_LINKS = {
    'approvals': '/publicite/approbations',
    'dashboard': '/publicite/tableau-de-bord',
    'campaign': '/publicite/campagnes',
    'connection': '/publicite/connexion',
}


def deep_link(name):
    """URL profonde ERP (relative par défaut, absolue si ADSENGINE_APP_BASE_URL)."""
    base = (os.environ.get('ADSENGINE_APP_BASE_URL', '') or '').rstrip('/')
    return base + DEEP_LINKS.get(name, DEEP_LINKS['dashboard'])


# 8 gabarits. ``body`` = cause racine + recommandation (une phrase chacune) ;
# ``severity`` pilote emoji + label + cooldown ; ``link`` = destination du deep
# link ; ``cta`` = libellé de l'appel à l'action.
WA_TEMPLATES = {
    'cost_per_signature_ceiling': {
        'severity': SEVERITY_CRITICAL, 'link': 'approvals',
        'cta': 'Voir et approuver',
        'body': ("Campagne « {campaign_name} » : coût par signature = {value} "
                 "MAD sur {window_days} j (plafond {threshold} MAD). "
                 "Recommandation : mettre en pause ou revoir le ciblage."),
    },
    'zero_delivery': {
        'severity': SEVERITY_CRITICAL, 'link': 'dashboard', 'cta': 'Détails',
        'body': ("« {campaign_name} » dépense ({spend} MAD depuis {hours} h) "
                 "mais 0 diffusion. Probable souci Meta "
                 "(paiement / révision / compte). Recommandation : vérifier le "
                 "compte Meta directement."),
    },
    'zero_results': {
        'severity': SEVERITY_WARNING, 'link': 'approvals',
        'cta': 'Voir et approuver',
        'body': ("« {ad_name} » diffuse et reçoit des clics mais 0 résultat "
                 "depuis {hours} h. Recommandation : tester une nouvelle "
                 "création."),
    },
    'frequency_runaway': {
        'severity': SEVERITY_WARNING, 'link': 'approvals',
        'cta': 'Voir et approuver',
        'body': ("Fréquence de « {adset_name} » = {frequency} (seuil "
                 "{ceiling}), signe de lassitude créative. Recommandation : "
                 "faire tourner une nouvelle création."),
    },
    'disapproved_ad': {
        'severity': SEVERITY_CRITICAL, 'link': 'campaign', 'cta': 'Détails',
        'body': ("« {ad_name} » refusée par Meta : « {rejection_reason} ». "
                 "Recommandation : corriger et resoumettre dans Meta "
                 "directement."),
    },
    'spend_spike': {
        'severity': SEVERITY_WARNING, 'link': 'dashboard', 'cta': 'Détails',
        'body': ("Dépense de « {campaign_name} » = {spend_today} MAD "
                 "aujourd'hui, {ratio}× la médiane des 7 derniers jours. "
                 "Recommandation : vérifier qu'aucun changement involontaire "
                 "n'a eu lieu."),
    },
    'spend_collapse': {
        'severity': SEVERITY_CRITICAL, 'link': 'dashboard', 'cta': 'Détails',
        'body': ("Dépense de « {campaign_name} » quasi nulle ({spend_today} "
                 "MAD, médiane {median} MAD/j). Probable paiement échoué ou "
                 "compte suspendu. Recommandation : vérifier le compte Meta "
                 "immédiatement."),
    },
    'rule_execution_failed': {
        'severity': SEVERITY_WARNING, 'link': 'connection', 'cta': 'Détails',
        'body': ("La règle « {template_label_fr} » n'a pas pu s'exécuter "
                 "({error_summary}). Aucune vérification automatique n'a eu "
                 "lieu depuis {hours} h. Recommandation : vérifier la "
                 "connexion Meta."),
    },
}

# Correspondance clé de catalogue (ADSENG14) → gabarit WhatsApp (dd-guardian §C2)
# pour que le moteur (rules_engine) émette le bon rendu. Les clés non mappées
# retombent sur une alerte basique.
_WA_FOR_CATALOGUE = {
    'frequency_high': 'frequency_runaway',
    'zero_delivery': 'zero_delivery',
    'stop_loss_cpl': 'cost_per_signature_ceiling',
    'zero_results': 'zero_results',
}


class _SafeDict(dict):
    """``format_map`` tolérant : une clé manquante rend « ? » (jamais KeyError)."""

    def __missing__(self, key):
        return '?'


def wa_template_for_catalogue(catalogue_key):
    """Clé de gabarit WhatsApp pour une clé de catalogue, ou ``None``."""
    return _WA_FOR_CATALOGUE.get(catalogue_key)


def context_from_computed(target_name, computed):
    """Contexte de rendu depuis un ``computed`` de détecteur + le nom de cible.
    Ajoute des alias de nom (campaign/ad/adset) et de seuil, tolérants."""
    ctx = {'campaign_name': target_name, 'ad_name': target_name,
           'adset_name': target_name}
    ctx.update(computed or {})
    ctx.setdefault('ceiling', ctx.get('threshold'))
    ctx.setdefault('value', ctx.get('cost_per_lead_mad'))
    ctx.setdefault('spend_today', ctx.get('spend_today', ctx.get('spend')))
    return ctx


def wa_template_severity(template_key):
    """Sévérité d'un gabarit WhatsApp (repli WARNING si inconnu)."""
    tpl = WA_TEMPLATES.get(template_key)
    return tpl['severity'] if tpl else SEVERITY_WARNING


def render_whatsapp(template_key, context=None):
    """Rend le message FR d'un gabarit : [emoji] label — cause+reco → CTA link.
    Clé inconnue → chaîne vide (jamais d'exception)."""
    tpl = WA_TEMPLATES.get(template_key)
    if tpl is None:
        return ''
    severity = tpl['severity']
    emoji = SEVERITY_EMOJI.get(severity, '')
    label = SEVERITY_LABELS_FR.get(severity, '')
    body = tpl['body'].format_map(_SafeDict(context or {}))
    link = deep_link(tpl['link'])
    return f"{emoji} {label} — {body} {tpl['cta']} → {link}"


def _alert_type(template_key):
    """Type d'``EngineAlert`` d'un gabarit (règle inopérante vs anomalie)."""
    from . import guardrails
    if template_key == 'rule_execution_failed':
        return guardrails.ALERT_INOPERATIVE
    return guardrails.ALERT_ANOMALY


def _entity_key(template_key, target_type, target_id):
    return f'{template_key}:{target_type or ""}:{target_id or ""}'[:80]


def emit_guarded_alert(company, *, template_key, target_type='', target_id='',
                       context=None, action=None, dry_run=False):
    """ADSENG18 — Émet/actualise une ``EngineAlert`` WhatsApp avec DÉDUP +
    COOLDOWN + ESCALADE (dd-guardian §C3).

    * Première occurrence (aucune alerte ouverte pour la clé) → création + envoi.
    * Ré-occurrence dans le cooldown → actualise la valeur, N'ENVOIE PAS (anti-
      spam) ; incrémente le cycle non résolu (escalade WARNING→CRITICAL au 3e).
    * Ré-occurrence après le cooldown, condition toujours vraie → renvoi (sans
      réinitialiser ``created_at`` : « depuis {N} h » reste calculé sur la
      première détection).
    * ``dry_run`` → jamais d'« envoi » (aucun ``last_sent_at`` posé) — visible
      in-app seulement (dd-guardian §A10).

    Renvoie l'``EngineAlert`` (attribut transitoire ``._sent`` indique l'envoi)."""
    from django.utils import timezone
    from django.utils.dateparse import parse_datetime

    from .models import EngineAlert

    if company is None:
        return None
    tpl = WA_TEMPLATES.get(template_key)
    if tpl is None:
        return None
    severity = tpl['severity']
    cooldown = DEFAULT_COOLDOWN_HOURS.get(severity, 24)
    entity_key = _entity_key(template_key, target_type, target_id)
    message = render_whatsapp(template_key, context)
    now = timezone.now()

    existing = (EngineAlert.objects
                .filter(company=company, entity_key=entity_key, resolved=False)
                .order_by('-created_at').first())

    if existing is None:
        alert = EngineAlert.objects.create(
            company=company, alert_type=_alert_type(template_key),
            message=message, severity=severity, entity_key=entity_key,
            cooldown_hours=cooldown, action=action,
            detail={'template_key': template_key, 'computed': context or {},
                    'last_sent_at': (None if dry_run else now.isoformat())})
        alert._sent = not dry_run
        return alert

    # Ré-occurrence : actualise + un cycle non résolu de plus (escalade au 3e).
    existing.message = message
    detail = existing.detail or {}
    detail['computed'] = context or {}
    existing.register_unresolved_cycle()  # incr + escalade éventuelle (save)

    resend = False
    if not dry_run:
        last_sent = detail.get('last_sent_at')
        ls = parse_datetime(last_sent) if last_sent else None
        cooldown_delta = datetime.timedelta(
            hours=existing.effective_cooldown_hours)
        if ls is None or (now - ls) >= cooldown_delta:
            resend = True
            detail['last_sent_at'] = now.isoformat()

    existing.detail = detail
    existing.save(update_fields=['message', 'detail', 'updated_at'])
    existing._sent = resend
    return existing


def resolve_alert(company, *, template_key, target_type='', target_id=''):
    """Condition redevenue fausse : marque l'alerte ouverte résolue. Pour une
    CRITICAL uniquement, émet un suivi ``✅ Résolu`` (dd-guardian §C3). Renvoie
    le suivi (critical) ou l'alerte résolue, ou ``None`` si rien d'ouvert."""
    from .models import EngineAlert

    entity_key = _entity_key(template_key, target_type, target_id)
    alert = (EngineAlert.objects
             .filter(company=company, entity_key=entity_key, resolved=False)
             .order_by('-created_at').first())
    if alert is None:
        return None
    alert.resolved = True
    alert.save(update_fields=['resolved', 'updated_at'])
    if alert.severity == SEVERITY_CRITICAL:
        target = target_id or target_type or template_key
        return EngineAlert.objects.create(
            company=company, alert_type=alert.alert_type,
            message=f"✅ Résolu — {template_key} pour {target}.",
            severity=SEVERITY_INFO, entity_key=entity_key + ':resolved',
            resolved=True, detail={'resolves': entity_key})
    return alert
