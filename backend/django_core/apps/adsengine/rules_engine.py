"""ADSENG15 — Évaluateur de règles du Gardien (orchestration, cadencé par beat).

Le moteur PARCOURT les ``RulePolicy`` activées d'une société, ÉVALUE le template
du catalogue fixe (``rule_templates.py``, ADSENG14) contre les données réelles, et
— quand une condition se déclenche — MATÉRIALISE une ``EngineAction`` via
``services.py`` (jamais une action directe sur Meta). Trois chemins d'exécution,
dans un ordre d'invariants STRICT :

  * ``dry_run=True``  → PROPOSE seulement, ``reason_fr`` préfixée « [Simulation] »,
    aucune alerte envoyée (visible en journal in-app uniquement). ``mode='auto'``
    est structurellement neutralisé en simulation (invariant ``is_auto_effective``).
  * ``mode='auto'`` (hors simulation) → ``services.execute_auto_action`` : la
    capacité ENG8 (``auto_rotate_creative``…) décide auto-apply vs proposition —
    une ligne ``EngineAction`` est TOUJOURS écrite (auto=True si jouée), jamais
    d'action sans trace.
  * ``mode='propose'`` → ``services.propose_action`` (approbation humaine requise).

**Idempotence (défensif double-beat, Fable G6)** : avant de créer une action, le
moteur DÉDUPLIQUE par ``(company, template_key, cible)`` sur une fenêtre de
cooldown — un beat rejoué ne crée JAMAIS d'action auto en double. Le cooldown par
cible est aussi la fenêtre anti-spam (dd-guardian §C3).

**Leçon Madgicx** : ``last_result`` est écrit à CHAQUE évaluation (déclenchée ou
non, données suffisantes ou non) — jamais un échec silencieux. Une branche
``insufficient_data`` ALERTE toujours (jamais un skip muet). Un template dont
l'évaluateur n'est pas encore câblé (autre lane) est CONSIGNÉ dans ``last_result``
(``evaluated: False``), pas ignoré en silence.

Cadences (dd-guardian §A9 — JAMAIS sub-horaire) : la boucle critique (6 h) évalue
les templates ``CADENCE_CRITICAL`` ; la boucle quotidienne évalue le reste
(daily + weekly). Enregistrées dans ``erp_agentique/celery.py`` via ``tasks.py``.
"""
from __future__ import annotations

import datetime
import logging

from . import rule_templates
from .rule_templates import CADENCE_CRITICAL, CADENCE_DAILY, CADENCE_WEEKLY

logger = logging.getLogger(__name__)

# Cadences évaluées par chaque boucle beat (ADSENG15).
CRITICAL_CADENCES = frozenset({CADENCE_CRITICAL})
OPTIMIZATION_CADENCES = frozenset({CADENCE_DAILY, CADENCE_WEEKLY})


def _window_start_date(now, days):
    """Date de début de fenêtre glissante (les insights sont datés au jour)."""
    base = now
    if isinstance(base, datetime.datetime):
        base = base.date()
    elif not isinstance(base, datetime.date):
        base = datetime.date.today()
    return base - datetime.timedelta(days=max(1, int(days)) - 1)


# ── Évaluateurs par template (registre ; d'autres lanes/tasks en câblent plus) ─
def _eval_frequency_high(company, policy, template, *, now, config):
    """Fatigue créative : fréquence glissante d'un ad set > seuil.

    Lit ``InsightSnapshot.frequency`` (max sur la fenêtre) par ad set. Sous le
    plancher d'échantillons → ``insufficient_data`` (ALERTE toujours, jamais un
    skip). Renvoie une liste de findings (un par ad set)."""
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Count, Max

    from .models import AdSetMirror, InsightSnapshot

    params = rule_templates.resolve_params(policy.template_key, policy.params)
    freq_max = float(params.get('frequency_max', 3.0))
    window_days = int(params.get('window_days', 7))
    min_samples = int(params.get('min_samples', 3))
    start = _window_start_date(now, window_days)
    ct = ContentType.objects.get_for_model(AdSetMirror)

    findings = []
    for adset in AdSetMirror.objects.filter(company=company):
        agg = (InsightSnapshot.objects
               .filter(company=company, content_type=ct, object_id=adset.pk,
                       date__gte=start)
               .aggregate(freq=Max('frequency'), n=Count('id')))
        n = agg['n'] or 0
        freq = agg['freq']
        base = {
            'target_type': 'adset',
            'target_meta_id': adset.meta_id,
            'target_object_id': adset.pk,
            'severity': template['severity'],
        }
        if n < min_samples or freq is None:
            findings.append({**base, 'fired': False, 'insufficient_data': True,
                             'computed': {'frequency': None, 'samples': n}})
            continue
        findings.append({
            **base, 'fired': float(freq) > freq_max,
            'insufficient_data': False,
            'computed': {'frequency': float(freq), 'threshold': freq_max,
                         'samples': n}})
    return findings


def _eval_cpl_band(company, policy, template, *, now, config):
    """Bande CPL (ADSENG16) : coût par lead d'une campagne hors de sa bande
    trainante ±2× (détecteur pur ``anomaly.detect_cpl_band``). Sous le plancher
    de leads → ``insufficient_data`` (ALERTE toujours). Une anomalie déclenchée
    matérialise une ``AnomalyEvent``."""
    from django.contrib.contenttypes.models import ContentType

    from . import anomaly
    from .models import AdCampaignMirror, InsightSnapshot

    params = rule_templates.resolve_params(policy.template_key, policy.params)
    window_days = int(params.get('window_days', 14))
    min_samples = int(params.get('min_samples', 5))
    low_mult = float(params.get('band_low_mult', 0.5))
    high_mult = float(params.get('band_high_mult', 2.0))
    start = _window_start_date(now, window_days)
    today = now.date() if isinstance(now, datetime.datetime) else (
        now if isinstance(now, datetime.date) else datetime.date.today())
    ct = ContentType.objects.get_for_model(AdCampaignMirror)

    findings = []
    for camp in AdCampaignMirror.objects.filter(company=company):
        snaps = list(InsightSnapshot.objects.filter(
            company=company, content_type=ct, object_id=camp.pk,
            date__gte=start).order_by('date'))
        daily_cpls = [s.cpl for s in snaps
                      if s.cpl is not None and (s.results or 0) >= 1
                      and s.date < today]
        n_leads = sum((s.results or 0) for s in snaps)
        cpl_today = next((s.cpl for s in snaps if s.date == today), None)
        det = anomaly.detect_cpl_band(
            daily_cpls, cpl_today, n_leads,
            band_low_mult=low_mult, band_high_mult=high_mult,
            min_samples=min_samples)
        if det.fired:
            anomaly.record_anomaly(
                company, det, entity_type='campaign',
                entity_meta_id=camp.meta_id, rule_policy=policy)
        findings.append({
            'target_type': 'campaign', 'target_meta_id': camp.meta_id,
            'target_object_id': camp.pk, 'fired': det.fired,
            'insufficient_data': det.insufficient_data,
            'computed': det.computed, 'severity': det.severity})
    return findings


# ══════════════════════════════════════════════════════════════════════════
# ADSDEEP38 — Vocabulaire de conditions v2 : métriques dérivées, fenêtres
# comparées, classement top/bottom-N. Un évaluateur GÉNÉRIQUE par forme de
# condition (seuil / fenêtres comparées / classement) lit le bloc ``v2`` du
# template pour choisir la métrique — jamais de logique dupliquée en base.
# ══════════════════════════════════════════════════════════════════════════
def _mirror_model_for_scope(scope):
    """Modèle miroir pour un ``scope`` de template (campaign/adset/ad)."""
    from .models import AdCampaignMirror, AdMirror, AdSetMirror
    return {
        'campaign': AdCampaignMirror, 'adset': AdSetMirror, 'ad': AdMirror,
    }.get(scope)


def _name_matches(pattern, name):
    """ADSDEEP39 — Vrai si ``name`` matche le motif de sélection (glob
    insensible à la casse, style Bïrch Selection Filter). Un motif vide matche
    TOUT (aucune restriction). ``*``/``?`` supportés (fnmatch)."""
    import fnmatch
    if not pattern:
        return True
    return fnmatch.fnmatch((name or '').lower(), str(pattern).lower())


def _scoped_mirrors(company, policy, scope):
    """Liste des miroirs d'un scope pour la société, RESTREINTE au motif de nom
    de la règle (ADSDEEP39 — s'applique DYNAMIQUEMENT, donc aux campagnes
    FUTURES matchant le motif puisque l'évaluation relit les miroirs à chaque
    beat). Un motif vide = tous les miroirs."""
    model = _mirror_model_for_scope(scope)
    if model is None:
        return None, []
    pattern = getattr(policy, 'name_pattern', '') or ''
    mirrors = [
        m for m in model.objects.filter(company=company)
        if _name_matches(pattern, m.name)]
    return model, mirrors


def _sum_attr(snaps, attr):
    """Somme d'un attribut numérique sur des snapshots (ignore les None)."""
    total = 0.0
    for s in snaps:
        v = getattr(s, attr, None)
        if v is not None:
            try:
                total += float(v)
            except (TypeError, ValueError):
                continue
    return total


def _sum_video(snaps, key):
    """Somme d'une clé de ``video_metrics`` (ex. ``s6``) sur des snapshots."""
    total = 0.0
    for s in snaps:
        vm = getattr(s, 'video_metrics', None) or {}
        v = vm.get(key)
        if v is not None:
            try:
                total += float(v)
            except (TypeError, ValueError):
                continue
    return total


def _derived_metric(snaps, metric):
    """Valeur d'une métrique DÉRIVÉE sur une fenêtre de snapshots.

    Renvoie ``(valeur|None, samples)`` : ``None`` quand le dénominateur est nul
    ou la donnée absente (le déclencheur retombe alors sur ``insufficient_data``
    — jamais un faux 0). ``samples`` = nombre de snapshots de la fenêtre."""
    n = len(snaps)
    if metric == 'cpl':
        spend = _sum_attr(snaps, 'spend')
        results = _sum_attr(snaps, 'results')
        return ((spend / results) if results > 0 else None), n
    if metric == 'cost_per_conversation':
        spend = _sum_attr(snaps, 'spend')
        conv = _sum_attr(snaps, 'conversations')
        return ((spend / conv) if conv > 0 else None), n
    if metric == 'ctr_link':
        clicks = _sum_attr(snaps, 'link_clicks')
        impr = _sum_attr(snaps, 'impressions')
        return ((clicks / impr) if impr > 0 else None), n
    if metric == 'hold_rate':
        s6 = _sum_video(snaps, 's6')
        impr = _sum_attr(snaps, 'impressions')
        return ((s6 / impr) if impr > 0 else None), n
    if metric == 'spend':
        return _sum_attr(snaps, 'spend'), n
    if metric == 'frequency':
        freqs = [float(s.frequency) for s in snaps
                 if getattr(s, 'frequency', None) is not None]
        return ((max(freqs)) if freqs else None), n
    return None, n


def _window_snaps(company, ct, obj_pk, *, now, days):
    """Snapshots d'un objet sur une fenêtre glissante de ``days`` jours."""
    from .models import InsightSnapshot
    start = _window_start_date(now, days)
    return list(InsightSnapshot.objects.filter(
        company=company, content_type=ct, object_id=obj_pk, date__gte=start))


def _eval_metric_threshold(company, policy, template, *, now, config):
    """ADSDEEP38 — Évaluateur GÉNÉRIQUE « métrique dérivée vs seuil » (opérateurs
    ``gt``/``lt``). Lit ``template['v2']`` (metric/operator/threshold_param).
    Sous le plancher d'échantillons → ``insufficient_data``."""
    from django.contrib.contenttypes.models import ContentType

    spec = template.get('v2', {})
    metric = spec['metric']
    operator = spec.get('operator', 'gt')
    params = rule_templates.resolve_params(policy.template_key, policy.params)
    threshold = float(params.get(spec['threshold_param']))
    window_days = int(params.get('window_days', 7))
    min_samples = int(params.get('min_samples', 3))
    scope = template['scope']
    model, mirrors = _scoped_mirrors(company, policy, scope)
    if model is None:
        return []
    ct = ContentType.objects.get_for_model(model)

    findings = []
    for m in mirrors:
        snaps = _window_snaps(company, ct, m.pk, now=now, days=window_days)
        value, n = _derived_metric(snaps, metric)
        base = {'target_type': scope, 'target_meta_id': m.meta_id,
                'target_object_id': m.pk, 'severity': template['severity']}
        if n < min_samples or value is None:
            findings.append({**base, 'fired': False, 'insufficient_data': True,
                             'computed': {'metric': metric, 'value': value,
                                          'samples': n}})
            continue
        fired = value > threshold if operator == 'gt' else value < threshold
        findings.append({
            **base, 'fired': fired, 'insufficient_data': False,
            'computed': {'metric': metric, 'value': round(value, 4),
                         'threshold': threshold, 'operator': operator,
                         'window_days': window_days, 'samples': n}})
    return findings


def _eval_window_regression(company, policy, template, *, now, config):
    """ADSDEEP38 — Évaluateur GÉNÉRIQUE « fenêtres comparées » (« CPA 3 j > CPA
    7 j × 1,2 »). Compare la métrique sur une fenêtre COURTE vs une fenêtre
    LONGUE × facteur. ``direction`` ``up`` = déclenche si court > long × facteur
    (dégradation) ; ``down`` = si court < long × facteur (amélioration, surf-
    scaling). La fenêtre longue borne le plancher d'échantillons."""
    from django.contrib.contenttypes.models import ContentType

    spec = template.get('v2', {})
    metric = spec['metric']
    direction = spec.get('direction', 'up')
    params = rule_templates.resolve_params(policy.template_key, policy.params)
    short_days = int(params.get('short_days', 3))
    long_days = int(params.get('long_days', 7))
    factor = float(params.get('regression_factor',
                              params.get('improve_factor', 1.0)))
    min_samples = int(params.get('min_samples', 3))
    scope = template['scope']
    model, mirrors = _scoped_mirrors(company, policy, scope)
    if model is None:
        return []
    ct = ContentType.objects.get_for_model(model)

    findings = []
    for m in mirrors:
        short_snaps = _window_snaps(company, ct, m.pk, now=now, days=short_days)
        long_snaps = _window_snaps(company, ct, m.pk, now=now, days=long_days)
        short_val, _ = _derived_metric(short_snaps, metric)
        long_val, long_n = _derived_metric(long_snaps, metric)
        base = {'target_type': scope, 'target_meta_id': m.meta_id,
                'target_object_id': m.pk, 'severity': template['severity']}
        if (long_n < min_samples or short_val is None or long_val is None
                or long_val <= 0):
            findings.append({**base, 'fired': False, 'insufficient_data': True,
                             'computed': {'metric': metric,
                                          'short': short_val, 'long': long_val,
                                          'samples': long_n}})
            continue
        boundary = long_val * factor
        fired = short_val > boundary if direction == 'up' else (
            short_val < boundary)
        findings.append({
            **base, 'fired': fired, 'insufficient_data': False,
            'computed': {'metric': metric, 'short': round(short_val, 4),
                         'long': round(long_val, 4), 'factor': factor,
                         'boundary': round(boundary, 4), 'direction': direction,
                         'short_days': short_days, 'long_days': long_days,
                         'samples': long_n}})
    return findings


def _eval_rank_low_result(company, policy, template, *, now, config):
    """ADSDEEP38 — Évaluateur GÉNÉRIQUE « classement top-N » : classe les objets
    du scope par dépense décroissante sur la fenêtre, prend les ``top_n``
    premiers, et DÉCLENCHE ceux dont les résultats restent sous le plancher
    ``min_results`` (top dépensiers sans résultat). Les objets sans assez de
    snapshots sont ``insufficient_data`` (jamais un skip muet)."""
    from django.contrib.contenttypes.models import ContentType

    params = rule_templates.resolve_params(policy.template_key, policy.params)
    top_n = int(params.get('top_n', 3))
    min_results = float(params.get('min_results', 1))
    window_days = int(params.get('window_days', 7))
    min_samples = int(params.get('min_samples', 3))
    scope = template['scope']
    model, mirrors = _scoped_mirrors(company, policy, scope)
    if model is None:
        return []
    ct = ContentType.objects.get_for_model(model)

    ranked = []
    findings = []
    for m in mirrors:
        snaps = _window_snaps(company, ct, m.pk, now=now, days=window_days)
        base = {'target_type': scope, 'target_meta_id': m.meta_id,
                'target_object_id': m.pk, 'severity': template['severity']}
        if len(snaps) < min_samples:
            findings.append({**base, 'fired': False, 'insufficient_data': True,
                             'computed': {'metric': 'spend', 'value': None,
                                          'samples': len(snaps)}})
            continue
        spend = _sum_attr(snaps, 'spend')
        results = _sum_attr(snaps, 'results')
        ranked.append((spend, results, base))
    # Classement top-N par dépense décroissante.
    ranked.sort(key=lambda r: r[0], reverse=True)
    for idx, (spend, results, base) in enumerate(ranked):
        in_top = idx < top_n
        fired = in_top and results < min_results
        findings.append({
            **base, 'fired': fired, 'insufficient_data': False,
            'computed': {'metric': 'spend', 'spend': round(spend, 4),
                         'results': results, 'rank': idx + 1, 'top_n': top_n,
                         'min_results': min_results, 'in_top_n': in_top,
                         'window_days': window_days}})
    return findings


# Registre template_key → évaluateur. Les templates dépendant d'une autre lane
# (pacing, réconciliation) ou d'une donnée non encore stockée (impressions pour
# zéro-delivery) ne sont PAS câblés ici et sont consignés ``evaluated: False``
# (jamais un skip muet — c'est audité dans ``last_result``).
_EVALUATORS = {
    'frequency_high': _eval_frequency_high,
    'cpl_band': _eval_cpl_band,
    # ADSDEEP38 — vocabulaire de conditions v2 (métriques dérivées / fenêtres
    # comparées / classement top-N).
    'cost_per_conversation_high': _eval_metric_threshold,
    'link_ctr_low': _eval_metric_threshold,
    'hold_rate_low': _eval_metric_threshold,
    'cpa_window_regression': _eval_window_regression,
    'frequency_ratio_regression': _eval_window_regression,
    'surf_scale_budget': _eval_window_regression,
    'top_spend_low_result': _eval_rank_low_result,
}


# ── Reasons FR (une phrase par déclenchement) ─────────────────────────────────
def _reason_fr(template, finding):
    """Raison FR (une phrase) pour la proposition d'action. Spécifique au
    template quand utile, générique sinon (toujours non vide)."""
    computed = finding.get('computed', {})
    target = finding.get('target_meta_id', '?')
    key = template.get('_key')
    if key == 'frequency_high':
        return (
            f"Fréquence de l'ad set {target} = {computed.get('frequency')} "
            f"(seuil {computed.get('threshold')}) : fatigue créative — faire "
            f"tourner une nouvelle création.")
    if key == 'zero_delivery':
        return (
            f"Campagne {target} : dépense sans diffusion utile sur la fenêtre — "
            f"mise en pause proposée (vérifier le compte Meta).")
    return (
        f"{template.get('label_fr', 'Règle')} déclenchée pour {target} — "
        f"action proposée par le Gardien.")


# ── Cooldown / idempotence au niveau proposeur ────────────────────────────────
def _cooldown_hours(policy):
    """Cooldown effectif de la règle : explicite si posé, sinon défaut de la
    sévérité du template (6/24/72 h)."""
    if policy.cooldown_hours:
        return policy.cooldown_hours
    return rule_templates.template_cooldown_hours(policy.template_key)


def _recently_acted(company, template_key, target_meta_id, *, since):
    """Vrai si une ``EngineAction`` de CE (company, template, cible) a déjà été
    créée depuis ``since`` — dédup au niveau proposeur (Fable G6 : un beat
    rejoué ne double jamais une action auto). Couvre proposée ET appliquée."""
    from .models import EngineAction
    return EngineAction.objects.filter(
        company=company,
        payload__template_key=template_key,
        payload__target_meta_id=target_meta_id,
        created_at__gte=since,
    ).exists()


# ── Émission d'alerte (ADSENG15 : basique ; ADSENG18 enrichit ce point) ───────
def _emit_alert(company, *, template_key, finding, message, action=None,
                dry_run=False, insufficient=False):
    """Point d'émission d'alerte du moteur. En simulation, aucune alerte n'est
    émise (visible in-app via le journal d'actions uniquement — dd-guardian §A10).

    Un finding DÉCLENCHÉ sur un template mappé (ADSENG18) route vers
    ``alerts.emit_guarded_alert`` (rendu WhatsApp FR + dédup/cooldown/escalade) ;
    une branche insufficient_data ou un template non mappé retombe sur l'alerte
    basique avec son message custom."""
    if dry_run:
        return None
    from . import alerts as alerts_mod
    from . import guardrails

    wa_key = None
    if not insufficient:
        wa_key = alerts_mod.wa_template_for_catalogue(template_key)
    if wa_key:
        target_type = finding.get('target_type', '')
        target_id = finding.get('target_meta_id', '')
        context = alerts_mod.context_from_computed(
            target_id, finding.get('computed', {}))
        return alerts_mod.emit_guarded_alert(
            company, template_key=wa_key, target_type=target_type,
            target_id=target_id, context=context, action=action,
            dry_run=dry_run)
    return guardrails.emit_alert(
        company, alert_type=guardrails.ALERT_ANOMALY, message=message,
        action=action,
        detail={'template_key': template_key,
                'target_meta_id': finding.get('target_meta_id'),
                'computed': finding.get('computed', {})})


def _act_on_finding(company, policy, template, finding, *, config, client):
    """Matérialise l'action/alerte d'un finding DÉCLENCHÉ (jamais d'action
    directe : toujours via ``services``). Déduplique par cooldown. Renvoie
    l'``EngineAction`` créée (ou ``None`` si dédupliquée / alerte seule)."""
    from django.utils import timezone

    from . import services

    template_key = policy.template_key
    target_meta_id = finding.get('target_meta_id', '')
    since = timezone.now() - datetime.timedelta(hours=_cooldown_hours(policy))
    if _recently_acted(company, template_key, target_meta_id, since=since):
        return None  # cooldown / idempotence : jamais de doublon

    reason = _reason_fr({**template, '_key': template_key}, finding)
    kind = rule_templates.action_kind(template_key)
    payload = {
        'template_key': template_key,
        'target_type': finding.get('target_type', ''),
        'target_meta_id': target_meta_id,
        'target_object_id': finding.get('target_object_id'),
        'computed': finding.get('computed', {}),
    }

    action = None
    if kind:
        if policy.dry_run:
            # Simulation : proposée + [Simulation], AUCUNE alerte (in-app seul).
            return services.propose_action(
                company, kind=kind, reason_fr='[Simulation] ' + reason,
                payload=payload, auto=False)
        if policy.is_auto_effective:
            # Auto (hors simulation) : la capacité ENG8 décide auto vs propose ;
            # une ligne EngineAction est TOUJOURS écrite.
            action = services.execute_auto_action(
                company, kind=kind, reason_fr=reason, payload=payload,
                config=config, client=client)
        else:
            action = services.propose_action(
                company, kind=kind, reason_fr=reason, payload=payload,
                auto=False)

    # Alerte (hors simulation) ; liée à l'action si une a été créée.
    _emit_alert(company, template_key=template_key, finding=finding,
                message=reason, action=action, dry_run=policy.dry_run)
    return action


def _record_last_result(policy, result):
    """Écrit ``last_result`` + ``last_evaluated_at`` (à CHAQUE évaluation)."""
    from django.utils import timezone
    policy.last_result = result
    policy.last_evaluated_at = timezone.now()
    policy.save(update_fields=[
        'last_result', 'last_evaluated_at', 'updated_at'])


def evaluate_company(company, *, cadences=None, now=None, client=None,
                     config=None):
    """Évalue les ``RulePolicy`` activées d'une société pour les cadences
    demandées. ``cadences`` None = toutes. Renvoie le nombre de règles évaluées.

    Best-effort par règle : une exception sur une règle est consignée
    (``evaluated: False`` + alerte règle-inopérante) et n'empêche pas les
    suivantes (leçon Madgicx : jamais un échec silencieux)."""
    from django.utils import timezone

    from .models import GuardrailConfig, RulePolicy

    now = now or timezone.now()
    if config is None:
        config = GuardrailConfig.objects.filter(company=company).first()

    from . import watchdog

    evaluated = 0
    for policy in RulePolicy.objects.filter(company=company, enabled=True):
        template = rule_templates.get_template(policy.template_key)
        if template is None:
            _record_last_result(
                policy, {'evaluated': False, 'reason': 'template inconnu'})
            continue
        if cadences is not None and template['cadence'] not in cadences:
            continue  # pas le tour de cette cadence — ne touche pas last_result

        evaluator = _EVALUATORS.get(policy.template_key)
        if evaluator is None:
            # Câblé par une autre lane (pacing/réconciliation…) : consigné,
            # jamais un skip muet.
            _record_last_result(policy, {
                'evaluated': False,
                'reason': 'évaluateur non câblé (autre lane)'})
            continue

        try:
            findings = evaluator(company, policy, template, now=now,
                                 config=config) or []
        except Exception as exc:  # noqa: BLE001 — best-effort par règle
            logger.warning('adsengine rules_engine: règle %s inopérante: %s',
                           policy.template_key, exc, exc_info=True)
            _record_last_result(
                policy, {'evaluated': False, 'error': str(exc)})
            _report_inoperative(company, policy, str(exc))
            continue

        fired_any = False
        summaries = []
        for finding in findings:
            summaries.append({
                'target': finding.get('target_meta_id'),
                'fired': finding.get('fired', False),
                'insufficient_data': finding.get('insufficient_data', False),
                'computed': finding.get('computed', {})})
            if finding.get('insufficient_data'):
                # Branche insufficient_data : ALERTE toujours (piège Madgicx).
                _emit_alert(
                    company, template_key=policy.template_key, finding=finding,
                    message=(f"{template['label_fr']} : données insuffisantes "
                             f"pour {finding.get('target_meta_id', '?')} — "
                             f"vérification impossible (jamais un skip muet)."),
                    dry_run=policy.dry_run, insufficient=True)
            elif finding.get('fired'):
                fired_any = True
                _act_on_finding(company, policy, template, finding,
                                config=config, client=client)

        _record_last_result(policy, {
            'evaluated': True, 'fired': fired_any,
            'findings': summaries, 'at': now.isoformat()})
        evaluated += 1

    # ADSENG17 — heartbeat de l'évaluateur (le watchdog détecte son arrêt).
    watchdog.record_heartbeat(company)
    return evaluated


def _report_inoperative(company, policy, error):
    """Alerte 🔴 dédiée « règle inopérante » (leçon Madgicx) — déléguée au
    watchdog (ADSENG17) : sévérité CRITICAL + dédup par (société, règle)."""
    from . import watchdog
    template = rule_templates.get_template(policy.template_key)
    label = template['label_fr'] if template else policy.template_key
    watchdog.report_rule_failure(
        company, template_key=label, error=error)


def evaluate_all(cadences=None, *, now=None, client=None):
    """Évalue toutes les sociétés actives (best-effort par société). Renvoie
    ``{'companies': n, 'rules_evaluated': m}``."""
    from authentication.selectors import active_companies

    companies = 0
    rules = 0
    for company in active_companies():
        try:
            rules += evaluate_company(company, cadences=cadences, now=now,
                                      client=client)
            companies += 1
        except Exception:  # noqa: BLE001 — isolation par société
            logger.warning('adsengine rules_engine: échec société %s',
                           getattr(company, 'pk', company), exc_info=True)
            continue
    return {'companies': companies, 'rules_evaluated': rules}
