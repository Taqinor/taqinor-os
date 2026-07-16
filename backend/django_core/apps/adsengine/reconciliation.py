"""ADSENG31 — Réconciliation Meta-vs-ERP (dd-attribution part b).

Instantané QUOTIDIEN par campagne : le nombre de leads que **Meta compte**
(``InsightSnapshot.results``, côté plateforme) vs le nombre que **l'ERP compte**
(leads CRM déduplifiés, lus via ``apps.crm.selectors`` UNIQUEMENT). Les deux
chiffres sont montrés CÔTE À CÔTE et ne sont JAMAIS fusionnés — c'est la source
de la confiance (leçon ux-adtools : « ne jamais laisser le dashboard diverger du
chiffre Meta sans caveat visible »).

Deux dénominateurs EXPLICITES, jamais mélangés (dd-attribution §3.2) :
  * **côté Meta-attribuable** — ce qui se compare au chiffre de Meta : leads
    FORMULAIRE (``source=meta_lead_ads``, appariés 1:1 via leadgen_id) + leads
    SITE pilotés par une pub Meta (``source=site_web`` + canal/utm Meta) ;
  * **réalité métier** — les leads SAISIS-MAIN (téléphone/walk-in/référence…) que
    Meta n'a jamais connus : comptés à part, JAMAIS mêlés au chiffre « côté Meta ».
Les leads CTWA (``canal=whatsapp_ctwa``) sont AUTO-DÉCLARÉS (jamais confirmés
côté Meta, cf. dd-attribution §2.4) → montrés séparément, jamais comparés.

Dédup : réutilise la normalisation QW10 (téléphone/email) exposée par le
sélecteur CRM — on compte des leads DÉDUPLIFIÉS, jamais un payload webhook brut
(dd-attribution §3.3).

Règle de tolérance (dd-attribution §3.4) : à l'échelle SMB (5-15 leads/sem),
un seuil en % pur est du bruit ; on combine un plancher ABSOLU et un RATIO. Un
écart au-delà ⇒ statut « écart » + alerte 🟠 « divergence silencieuse » (sévérité
ATTENTION par défaut d'``EngineAlert``). Les seuils sont un point de départ
(folklore 15-25 %), à retuner sur 4-8 semaines de données réelles — jamais
présentés comme une vérité mesurée.

Ne crée AUCUNE migration, AUCUN champ : ``ReconciliationSnapshot`` (P0) suffit.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

# ── Règle de tolérance (dd-attribution §3.4 — point de départ, à retuner) ─────
TOLERANCE_MIN_ABS = 2        # écart absolu minimal (un lead fait ±20 % à ce volume)
TOLERANCE_MIN_RATIO = 0.20   # 20 % de l'effectif le plus grand

# utm_source qui signale un lead SITE piloté par Meta (heuristique adsengine —
# jamais dans le CRM). Minuscules, comparé au ``utm_source`` normalisé du lead.
META_UTM_SOURCES = frozenset({
    'facebook', 'fb', 'facebook.com', 'instagram', 'ig', 'instagram.com', 'meta',
})

# Taxonomie FIXE de causes en français (dd-attribution §3.5) : une hypothèse
# courte, jamais un nombre nu sans explication.
CAUSE_WEBHOOK = 'webhook non reçu'
CAUSE_FETCH = 'fetch échoué'
CAUSE_UTM = 'attribution UTM manquante'
CAUSE_MANUAL = 'lead manuel non-Meta inclus par erreur'
CAUSE_WINDOW = 'fenêtre de comptage Meta différente'


def is_divergent(meta_count, erp_count):
    """Règle de tolérance combinée : divergent SEULEMENT si l'écart absolu ≥
    ``TOLERANCE_MIN_ABS`` ET le ratio (écart / plus grand effectif) ≥
    ``TOLERANCE_MIN_RATIO``. Deux effectifs nuls ⇒ jamais divergent (rien à
    comparer, pas d'alarme fantôme)."""
    delta = abs(int(meta_count) - int(erp_count))
    denom = max(int(meta_count), int(erp_count))
    if denom == 0:
        return False
    return delta >= TOLERANCE_MIN_ABS and (delta / denom) >= TOLERANCE_MIN_RATIO


def _cause_fr(meta_count, erp_count):
    """Hypothèse de cause (taxonomie fixe) pour un écart. Jamais affirmée comme
    certaine — une piste pour l'humain qui inspecte les leads sous-jacents."""
    if erp_count == 0 and meta_count > 0:
        return CAUSE_WEBHOOK
    if meta_count > erp_count:
        return CAUSE_UTM
    if erp_count > meta_count:
        return CAUSE_WINDOW
    return ''


def _is_meta_site(row):
    """Un lead SITE est Meta-attribuable si son canal est « Publicité Meta » ou
    si son ``utm_source`` figure dans ``META_UTM_SOURCES``."""
    return row['is_site'] and (
        row['is_meta_ads_canal'] or row['utm_source'] in META_UTM_SOURCES)


def _dedup_identity(row):
    """Identité de dédup d'un lead (QW10) : téléphone normalisé d'abord, sinon
    email normalisé, sinon l'id (jamais deux leads du même contact comptés
    deux fois dans une même case)."""
    if row['phone_key']:
        return ('p', row['phone_key'])
    if row['email_key']:
        return ('e', row['email_key'])
    return ('id', row['id'])


def _campaign_index(company):
    """(campagnes, {meta_id: camp}, {name: camp}) des miroirs de campagne de la
    société. En cas de noms dupliqués, le premier vu gagne (rapprochement
    d'affichage best-effort, jamais la clé de comptage dure)."""
    from .models import AdCampaignMirror
    campaigns = list(AdCampaignMirror.objects.filter(company=company))
    by_meta = {c.meta_id: c for c in campaigns}
    by_name = {}
    for c in campaigns:
        if c.name:
            by_name.setdefault(c.name, c)
    return campaigns, by_meta, by_name


def _meta_counts(company, campaigns, date_start, date_end):
    """{campaign_pk: {'results': int, 'spend': Decimal}} depuis
    ``InsightSnapshot`` (côté Meta), sommé sur la fenêtre. C'est le chiffre de
    Meta auquel on compare l'ERP."""
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Sum

    from .models import AdCampaignMirror, InsightSnapshot

    if not campaigns:
        return {}
    ct = ContentType.objects.get_for_model(AdCampaignMirror)
    rows = (InsightSnapshot.objects
            .filter(company=company, content_type=ct,
                    object_id__in=[c.pk for c in campaigns],
                    date__gte=date_start, date__lte=date_end)
            .values('object_id')
            .annotate(results=Sum('results'), spend=Sum('spend')))
    return {
        r['object_id']: {
            'results': int(r['results'] or 0),
            'spend': r['spend'] or Decimal('0'),
        }
        for r in rows
    }


def _new_bucket():
    return {'form': set(), 'site': set(), 'ctwa': set(),
            'form_ids': [], 'site_ids': [], 'ctwa_ids': []}


def _classify(rows, by_meta, by_name):
    """Répartit les lignes de lead par campagne + mécanisme de capture, en
    déduplifiant (QW10). Renvoie ``(per_campaign_pk, unmatched, hand_entered)``.

    ``per_campaign_pk`` : {campaign_pk: bucket} ; ``unmatched`` : leads Meta-
    attribuables sans campagne résolue (JAMAIS fondus dans « organique ») ;
    ``hand_entered`` : leads saisis-main (réalité métier, hors comparaison Meta).
    """
    per_campaign = {}
    unmatched = _new_bucket()
    hand_entered = {'ids': set(), 'lead_ids': []}

    for row in rows:
        is_form = row['is_meta_form']
        is_site = _is_meta_site(row)
        is_ctwa = row['is_ctwa']
        identity = _dedup_identity(row)

        if not (is_form or is_site or is_ctwa):
            # Saisi-main / organique : réalité métier, jamais dans la comparaison.
            if identity not in hand_entered['ids']:
                hand_entered['ids'].add(identity)
                hand_entered['lead_ids'].append(row['id'])
            continue

        # Résolution de campagne : meta_campaign_id (clé stable) puis utm_campaign.
        camp = None
        if row['meta_campaign_id'] and row['meta_campaign_id'] in by_meta:
            camp = by_meta[row['meta_campaign_id']]
        elif row['utm_campaign'] and row['utm_campaign'] in by_name:
            camp = by_name[row['utm_campaign']]

        bucket = unmatched if camp is None else per_campaign.setdefault(
            camp.pk, _new_bucket())

        if is_form:
            kind, ids_key = 'form', 'form_ids'
        elif is_site:
            kind, ids_key = 'site', 'site_ids'
        else:
            kind, ids_key = 'ctwa', 'ctwa_ids'
        if identity not in bucket[kind]:
            bucket[kind].add(identity)
            bucket[ids_key].append(row['id'])

    return per_campaign, unmatched, hand_entered


def _campaign_entry(camp, bucket, meta):
    """Construit l'entrée JSON stable d'une campagne (contrat P7). ``erp_leads``
    = FORMULAIRE + SITE (Meta-attribuables) ; CTWA auto-déclaré à part."""
    form_n = len(bucket['form'])
    site_n = len(bucket['site'])
    ctwa_n = len(bucket['ctwa'])
    erp_leads = form_n + site_n
    meta_leads = meta['results']
    delta = meta_leads - erp_leads
    denom = max(meta_leads, erp_leads)
    divergent = is_divergent(meta_leads, erp_leads)
    if not divergent:
        status = 'ok'
    elif erp_leads == 0 and meta_leads > 0:
        status = 'a_verifier'
    else:
        status = 'ecart'
    return {
        'campaign_meta_id': camp.meta_id,
        'campaign_name': camp.name or '',
        'meta_leads': meta_leads,
        'meta_spend': str(meta['spend']),
        'erp_leads': erp_leads,
        'delta_leads': delta,
        'ratio': (round(abs(delta) / denom, 3) if denom else 0.0),
        'status': status,
        'divergent': divergent,
        'cause_fr': (_cause_fr(meta_leads, erp_leads) if divergent else ''),
        'denominators': {
            'form_leads': form_n,
            'site_leads': site_n,
            'ctwa_self_reported': ctwa_n,
        },
        'lead_ids': {
            'form': list(bucket['form_ids']),
            'site': list(bucket['site_ids']),
            'ctwa': list(bucket['ctwa_ids']),
        },
    }


def reconcile(company, *, date=None, date_start=None, date_end=None):
    """ADSENG31 — Contrat JSON de réconciliation (stable, pour le frontend P7).

    Par défaut, snapshot d'UN jour (``date``, ou aujourd'hui). ``date_start``/
    ``date_end`` permettent une fenêtre. Ne persiste rien (lecture pure) ; voir
    :func:`run_daily_reconciliation` pour l'écriture + les alertes.

    Renvoie ::

        {
          'date_start', 'date_end',
          'campaigns': [ {campaign_meta_id, campaign_name, meta_leads,
              meta_spend, erp_leads, delta_leads, ratio, status, divergent,
              cause_fr, denominators:{form_leads, site_leads,
              ctwa_self_reported}, lead_ids:{form, site, ctwa}}, ... ],
          'unmatched': {form_leads, site_leads, ctwa_self_reported, lead_ids},
          'hand_entered': {count, lead_ids},   # réalité métier, hors comparaison
          'totals': {meta_leads, erp_meta_attributable_leads, delta,
                     divergent_campaigns},
        }
    """
    from apps.crm.selectors import reconciliation_lead_rows

    if date is not None:
        date_start = date_end = date
    if date_start is None:
        date_start = date_end = datetime.date.today()
    if date_end is None:
        date_end = date_start

    campaigns, by_meta, by_name = _campaign_index(company)
    meta_counts = _meta_counts(company, campaigns, date_start, date_end)
    rows = reconciliation_lead_rows(
        company, date_start=date_start, date_end=date_end)
    per_campaign, unmatched, hand_entered = _classify(
        rows, by_meta, by_name)

    # Une entrée par campagne ayant des données d'un côté OU de l'autre (une
    # campagne sans dépense ni lead n'encombre pas le contrat).
    entries = []
    for camp in campaigns:
        bucket = per_campaign.get(camp.pk, _new_bucket())
        meta = meta_counts.get(camp.pk, {'results': 0, 'spend': Decimal('0')})
        has_meta = meta['results'] or meta['spend']
        has_erp = bucket['form'] or bucket['site'] or bucket['ctwa']
        if not (has_meta or has_erp):
            continue
        entries.append(_campaign_entry(camp, bucket, meta))
    entries.sort(key=lambda e: (not e['divergent'], e['campaign_meta_id']))

    total_meta = sum(e['meta_leads'] for e in entries)
    total_erp = sum(e['erp_leads'] for e in entries)
    return {
        'date_start': date_start.isoformat(),
        'date_end': date_end.isoformat(),
        'campaigns': entries,
        'unmatched': {
            'form_leads': len(unmatched['form']),
            'site_leads': len(unmatched['site']),
            'ctwa_self_reported': len(unmatched['ctwa']),
            'lead_ids': {
                'form': list(unmatched['form_ids']),
                'site': list(unmatched['site_ids']),
                'ctwa': list(unmatched['ctwa_ids']),
            },
        },
        'hand_entered': {
            'count': len(hand_entered['ids']),
            'lead_ids': list(hand_entered['lead_ids']),
        },
        'totals': {
            'meta_leads': total_meta,
            'erp_meta_attributable_leads': total_erp,
            'delta': total_meta - total_erp,
            'divergent_campaigns': sum(1 for e in entries if e['divergent']),
        },
    }


def run_daily_reconciliation(company, day=None, *, persist=True):
    """ADSENG31 — Réconcilie un JOUR et PERSISTE un ``ReconciliationSnapshot``
    par campagne (upsert idempotent sur ``(company, date, campaign)`` — un
    re-run du même jour met à jour, jamais de doublon).

    Sur une divergence NOUVELLE (le snapshot n'était pas déjà en écart), émet une
    alerte 🟠 « divergence silencieuse » via le hook ENG9→ENG13 (sévérité
    ATTENTION par défaut). On n'alerte pas deux fois pour la même divergence
    persistante (le compteur de re-run ne spamme pas le fondateur).

    Renvoie le contrat de :func:`reconcile` (identique), pour que l'appelant
    dispose du même JSON stable. ``persist=False`` = calcul seul (aucune écriture,
    aucune alerte)."""
    from .models import AdCampaignMirror, ReconciliationSnapshot as RS

    if day is None:
        day = datetime.date.today()
    contract = reconcile(company, date=day)
    if not persist:
        return contract

    status_map = {
        'ok': RS.Statut.OK,
        'ecart': RS.Statut.ECART,
        'a_verifier': RS.Statut.A_VERIFIER,
    }
    by_meta = {c.meta_id: c
               for c in AdCampaignMirror.objects.filter(company=company)}

    for entry in contract['campaigns']:
        camp = by_meta.get(entry['campaign_meta_id'])
        if camp is None:
            continue
        existing = RS.objects.filter(
            company=company, date=day, campaign=camp).first()
        prev_divergent = bool(existing) and existing.status in (
            RS.Statut.ECART, RS.Statut.A_VERIFIER)

        RS.objects.update_or_create(
            company=company, date=day, campaign=camp,
            defaults={
                'meta_leads': entry['meta_leads'],
                'erp_leads': entry['erp_leads'],
                'meta_spend': Decimal(entry['meta_spend']),
                'delta_leads': entry['delta_leads'],
                'status': status_map[entry['status']],
                'detail': entry,
            })

        if entry['divergent'] and not prev_divergent:
            _emit_divergence_alert(company, day, entry)

    return contract


def _emit_divergence_alert(company, day, entry):
    """Émet l'alerte 🟠 « divergence silencieuse » (best-effort, jamais bloquant).

    Passe par ``guardrails.emit_alert`` (hook ENG9→ENG13 déjà branché : log +
    ``EngineAlert`` persistée). La sévérité par défaut d'``EngineAlert`` est
    ATTENTION (🟠) — exactement le niveau voulu ici."""
    from .guardrails import ALERT_ANOMALY, emit_alert

    name = entry['campaign_name'] or entry['campaign_meta_id']
    msg = (
        f"🟠 Divergence silencieuse — campagne « {name} » ({day.isoformat()}) : "
        f"Meta {entry['meta_leads']} leads vs ERP {entry['erp_leads']} "
        f"(écart {entry['delta_leads']}). Cause probable : "
        f"{entry['cause_fr'] or 'à vérifier'}.")
    emit_alert(
        company, alert_type=ALERT_ANOMALY, message=msg,
        detail={
            'kind': 'reconciliation_divergence',
            'date': day.isoformat(),
            'campaign_meta_id': entry['campaign_meta_id'],
            'meta_leads': entry['meta_leads'],
            'erp_leads': entry['erp_leads'],
            'delta_leads': entry['delta_leads'],
            'cause_fr': entry['cause_fr'],
        })
