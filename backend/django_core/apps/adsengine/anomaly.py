"""ADSENG16 — Détecteurs d'anomalies SMB-RELATIFS (formules dd-guardian §b).

Chaque seuil est défini RELATIVEMENT à l'historique récent de la société, jamais
comme un nombre absolu d'échelle entreprise (« dépense > 5 000 MAD/j » n'a aucun
sens sous un plafond de 100 MAD/j). Chaque formule porte un PLANCHER
d'échantillons : à 5-15 leads/semaine, une bande statistique sur n=2 est pire
qu'inutile — sous le plancher, la détection renvoie ``insufficient_data``, qui
**ALERTE TOUJOURS (info), jamais un skip muet et jamais une action de pause**
(LE piège Madgicx, dd-guardian §B6).

Fonctions PURES : aucun I/O, aucun import de modèle — entièrement testables avec
des nombres synthétiques (les valeurs de dossier reproduites en test). Le câblage
DB (lecture ``InsightSnapshot``, écriture ``AnomalyEvent``) vit dans
``rules_engine.py`` + ``record_anomaly`` ci-dessous.

Choix délibéré (dd-guardian §B2) : les bandes sont des RATIOS simples (±2×), pas
des écarts-types — 5-15 leads/semaine sont trop épars pour qu'un stddev signifie
quoi que ce soit, et un ratio est explicable en une phrase FR au fondateur.

WIR140 — SÉPARATION DÉLIBÉRÉE du socle ``core.anomaly`` : ce module ne le
consomme PAS (et ne doit pas). Le socle fait du z-score sur des séries denses et
matérialise un ``core.AnomalyFlag`` générique ; ici on fait des ratios relatifs
sur des données SMB éparses et on matérialise un ``adsengine.AnomalyEvent``
(kind ads, ``rule_policy``, ``alert``). Réexprimer ces détecteurs via le z-score
du socle régresserait le design dd-guardian. Dossier de décision complet :
``docs/engine/anomaly-engine-separation.md``.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from .rules import SEVERITY_CRITICAL, SEVERITY_INFO, SEVERITY_WARNING

# ── Types d'anomalie (valeurs ALIGNÉES sur ``AnomalyEvent.Kind`` — pas d'import
# de modèle, on partage les littéraux, comme ``rules.py`` pour la sévérité). ──
KIND_ZERO_DELIVERY = 'zero_delivery'
KIND_ZERO_RESULTS = 'zero_results'
KIND_COST_SPIKE = 'cost_spike'
KIND_FREQUENCY_HIGH = 'frequency_high'
KIND_OTHER = 'autre'
# ADSDEEP45 — kind EN CONSTANTE SIMPLE, hors de ``AnomalyEvent.Kind.choices``
# (même pattern déjà établi que ``services.KIND_CREATE_AD_STUDY`` : Django
# n'applique PAS ``choices`` au ``.save()``, donc aucune migration requise pour
# un nouveau kind qui suit ce pattern).
KIND_CREATIVE_FATIGUE = 'creative_fatigue'
# PUB74 — kind EN CONSTANTE SIMPLE (même pattern qu'ADSDEEP45 ci-dessus) :
# fatigue au niveau du VISUEL (``visual_asset_key``), DISTINCTE de la fatigue
# par ad ci-dessus (fréquence/CTR d'UNE ad) — ici le signal est « le même
# visuel ressert sur N créas malgré des hooks différents ».
KIND_VISUAL_FATIGUE = 'visual_fatigue'


@dataclass(frozen=True)
class Detection:
    """Résultat d'un détecteur. ``insufficient_data`` True ⇒ le moteur ALERTE
    (info) mais ne PAUSE jamais. ``fired`` True ⇒ anomalie confirmée."""
    detector: str
    fired: bool
    insufficient_data: bool
    severity: str
    kind: str
    message_fr: str
    computed: dict = field(default_factory=dict)


def _floats(values):
    """Convertit une liste en floats en ignorant les ``None`` (robuste Decimal)."""
    out = []
    for v in values or []:
        if v is None:
            continue
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


def _insufficient(detector, kind, message, computed=None):
    return Detection(
        detector=detector, fired=False, insufficient_data=True,
        severity=SEVERITY_INFO, kind=kind, message_fr=message,
        computed=computed or {})


# ── B1 — Dépense vs médiane 7 j (pic / chute) ────────────────────────────────
def detect_spend_anomaly(daily_spends, spend_today, *, spike_mult=3.0,
                         collapse_mult=0.2, spend_floor_mad=20.0,
                         min_samples=3):
    """Pic (ratio > 3,0×) ou chute (ratio < 0,2×) de dépense vs la médiane des
    7 jours précédents. Un plancher ``spend_floor_mad`` évite les faux positifs
    près de zéro (4 MAD→1 MAD = « 4× » opérationnellement insignifiant).

    Chute = plus urgente (paiement échoué / suspension) ⇒ CRITICAL ; pic ⇒
    WARNING (dd-guardian §B1)."""
    clean = _floats(daily_spends)
    if len(clean) < min_samples:
        return _insufficient(
            'spend_vs_median', KIND_COST_SPIKE,
            "Dépense : historique insuffisant pour une médiane fiable — "
            "vérification impossible.", {'samples': len(clean)})
    try:
        today = float(spend_today)
    except (TypeError, ValueError):
        return _insufficient(
            'spend_vs_median', KIND_COST_SPIKE,
            "Dépense du jour illisible — vérification impossible.")
    median_7d = statistics.median(clean)
    ref = median_7d if median_7d > 0 else spend_floor_mad
    ratio = today / ref if ref else 0.0
    computed = {'spend_today': today, 'median_7d': median_7d,
                'ratio': round(ratio, 3), 'floor': spend_floor_mad}
    # Chute (CRITICAL) — n'a de sens que si la médiane était non triviale.
    if ratio < collapse_mult and median_7d > spend_floor_mad:
        return Detection(
            'spend_vs_median', True, False, SEVERITY_CRITICAL, KIND_OTHER,
            (f"Dépense {today:g} MAD quasi nulle vs médiane {median_7d:g} "
             f"MAD/j — chute anormale (paiement échoué ou compte suspendu ?)."),
            computed)
    # Pic (WARNING) — seulement au-dessus du plancher (bruit sinon).
    if ratio > spike_mult and today > spend_floor_mad:
        return Detection(
            'spend_vs_median', True, False, SEVERITY_WARNING, KIND_COST_SPIKE,
            (f"Dépense {today:g} MAD = {ratio:.1f}× la médiane des 7 derniers "
             f"jours ({median_7d:g} MAD/j) — pic de dépense anormal."),
            computed)
    return Detection('spend_vs_median', False, False, SEVERITY_WARNING,
                     KIND_COST_SPIKE, '', computed)


# ── B2 — CPL vs bande trainante ±2× (ratio, PAS d'écart-type) ────────────────
def detect_cpl_band(daily_cpls, cpl_today, n_leads, *, band_low_mult=0.5,
                    band_high_mult=2.0, min_samples=5):
    """Coût par lead hors de sa bande ``[0,5× ; 2,0×]`` de la médiane trainante
    (14 j). Sous ``min_samples`` leads cumulés → ``insufficient_data`` (bande
    non fiable à ce volume) — dd-guardian §B2."""
    clean = _floats(daily_cpls)
    try:
        leads = int(n_leads or 0)
    except (TypeError, ValueError):
        leads = 0
    if leads < min_samples or not clean:
        return _insufficient(
            'cpl_band', KIND_COST_SPIKE,
            "Coût par lead : trop peu de leads pour une bande fiable — "
            "vérification impossible.", {'n_leads': leads})
    if cpl_today is None:
        return _insufficient(
            'cpl_band', KIND_COST_SPIKE,
            "Coût par lead du jour indisponible — vérification impossible.",
            {'n_leads': leads})
    today = float(cpl_today)
    median_cpl = statistics.median(clean)
    low = band_low_mult * median_cpl
    high = band_high_mult * median_cpl
    computed = {'cpl_today': today, 'median_cpl': median_cpl,
                'band_low': round(low, 2), 'band_high': round(high, 2),
                'n_leads': leads}
    if today < low or today > high:
        return Detection(
            'cpl_band', True, False, SEVERITY_WARNING, KIND_COST_SPIKE,
            (f"Coût par lead {today:g} MAD hors de sa bande "
             f"[{low:.0f} ; {high:.0f}] MAD (médiane 14 j {median_cpl:g})."),
            computed)
    return Detection('cpl_band', False, False, SEVERITY_WARNING,
                     KIND_COST_SPIKE, '', computed)


# ── B3 — Zéro-delivery à deux niveaux ────────────────────────────────────────
def detect_zero_delivery(*, spend, impressions, clicks, leads,
                         hours_since_launch, min_spend_mad=0.0):
    """Deux niveaux (dd-guardian §B3) :

    * Tier 1 (CRITICAL) — dépense > 0 ET 0 impression : l'ad ne tourne
      littéralement pas (paiement / révision / restriction Meta).
    * Tier 2 (WARNING) — diffuse + clics mais 0 résultat, campagne lancée
      depuis > 24 h : souci création / ciblage / offre.

    Dépense ou diffusion inconnue → ``insufficient_data`` (jamais un skip muet)."""
    if spend is None:
        return _insufficient(
            'zero_delivery', KIND_ZERO_DELIVERY,
            "Dépense inconnue — diffusion non vérifiable.")
    spend_f = float(spend)
    if impressions is None:
        return _insufficient(
            'zero_delivery', KIND_ZERO_DELIVERY,
            "Diffusion (impressions) inconnue — vérification impossible.",
            {'spend': spend_f})
    impressions = int(impressions)
    clicks_i = int(clicks or 0)
    leads_i = int(leads or 0)
    hours = float(hours_since_launch or 0)
    computed = {'spend': spend_f, 'impressions': impressions,
                'clicks': clicks_i, 'leads': leads_i, 'hours': hours}
    # Tier 1 — dépense sans aucune diffusion.
    if spend_f > min_spend_mad and impressions == 0:
        return Detection(
            'zero_delivery', True, False, SEVERITY_CRITICAL,
            KIND_ZERO_DELIVERY,
            (f"Dépense {spend_f:g} MAD mais 0 diffusion — souci Meta probable "
             f"(paiement / révision / compte)."),
            computed)
    # Tier 2 — diffuse + clics mais 0 résultat après la phase de ramp-up.
    if (impressions > 0 and clicks_i > 0 and leads_i == 0 and hours > 24):
        return Detection(
            'zero_delivery', True, False, SEVERITY_WARNING, KIND_ZERO_RESULTS,
            ("Diffuse et reçoit des clics mais 0 résultat depuis > 24 h — "
             "création / ciblage à revoir."),
            computed)
    return Detection('zero_delivery', False, False, SEVERITY_WARNING,
                     KIND_ZERO_RESULTS, '', computed)


# ── B4 — Fréquence en fuite (plafond + pente) ────────────────────────────────
def detect_frequency_runaway(frequency_series, *, freq_ceiling=3.0,
                             min_samples=3):
    """Fréquence trainante > plafond, OU fréquence encore en HAUSSE au-dessus de
    70 % du plafond (alerte précoce avant le plafond dur). ``frequency_series``
    est ordonnée du plus ancien au plus récent — dd-guardian §B4."""
    clean = _floats(frequency_series)
    if len(clean) < min_samples:
        return _insufficient(
            'frequency_runaway', KIND_FREQUENCY_HIGH,
            "Fréquence : historique insuffisant — vérification impossible.",
            {'samples': len(clean)})
    trailing = clean[-1]
    slope = clean[-1] - clean[0]
    computed = {'frequency': trailing, 'ceiling': freq_ceiling,
                'climbing': slope > 0}
    if trailing > freq_ceiling or (slope > 0 and trailing > freq_ceiling * 0.7):
        suffix = ', en hausse' if slope > 0 else ''
        return Detection(
            'frequency_runaway', True, False, SEVERITY_WARNING,
            KIND_FREQUENCY_HIGH,
            (f"Fréquence {trailing:g} (seuil {freq_ceiling:g}{suffix}) — "
             f"lassitude créative, faire tourner une nouvelle création."),
            computed)
    return Detection('frequency_runaway', False, False, SEVERITY_WARNING,
                     KIND_FREQUENCY_HIGH, '', computed)


# ── B5 — Annonce refusée par Meta ────────────────────────────────────────────
_DISAPPROVED_STATUSES = frozenset({'DISAPPROVED', 'WITH_ISSUES', 'REJECTED'})


def detect_disapproved(status, *, rejection_reason=''):
    """Annonce dans un état de refus Meta (le mode d'échec le plus rapide :
    0 impression). Statut inconnu → ``insufficient_data`` (on n'assume jamais
    « OK » en silence) — dd-guardian §B5."""
    normalized = str(status or '').strip().upper()
    if not normalized:
        return _insufficient(
            'disapproved_ad', KIND_OTHER,
            "Statut de révision de l'annonce inconnu — impossible de confirmer "
            "qu'elle est bien approuvée.")
    computed = {'status': normalized, 'reason': rejection_reason or ''}
    if normalized in _DISAPPROVED_STATUSES:
        detail = rejection_reason or normalized
        return Detection(
            'disapproved_ad', True, False, SEVERITY_CRITICAL, KIND_OTHER,
            (f"Annonce refusée par Meta (« {detail} ») — corriger et "
             f"resoumettre dans Meta directement."),
            computed)
    return Detection('disapproved_ad', False, False, SEVERITY_CRITICAL,
                     KIND_OTHER, '', computed)


# ── ADSDEEP45 — Fatigue créative COMBINÉE (fréquence × déclin CTR [× hausse
# CPA]), barre Motion (benchmark concurrent §2) ──────────────────────────────
# Seuils usuels du dossier concurrent : CTR −25 à −35 %, fréquence >4 (en
# prospection), CPA +40 à +50 % ⇒ fatigue confirmée. La paire PRIMAIRE reste
# fréquence × déclin CTR (le nom du diagnostic) ; une hausse de CPA est un
# signal de CONFIRMATION qui ESCALADE la sévérité en CRITICAL, jamais le seul
# déclencheur pris isolément.
DEFAULT_FATIGUE_THRESHOLDS = {
    'freq_ceiling': 4.0,
    'ctr_decline_warn': 0.25,
    'ctr_decline_critical': 0.35,
    'cpa_increase_warn': 0.40,
    'cpa_increase_critical': 0.50,
}


def detect_creative_fatigue(*, frequency, ctr_current, ctr_baseline,
                            cpa_current=None, cpa_baseline=None,
                            recent_samples=0, baseline_samples=0,
                            freq_ceiling=4.0, ctr_decline_warn=0.25,
                            ctr_decline_critical=0.35, cpa_increase_warn=0.40,
                            cpa_increase_critical=0.50, min_samples=3):
    """ADSDEEP45 — Fatigue créative : fréquence en fuite × déclin de CTR (+
    hausse de CPA en confirmation/escalade). Compare une fenêtre COURTE
    (``ctr_current``/``cpa_current``/``frequency``) à une fenêtre de RÉFÉRENCE
    précédente (``ctr_baseline``/``cpa_baseline``) — les deux fenêtres sont
    calculées par l'appelant (jamais ici : ce détecteur est PUR, aucun I/O).

    Sous le plancher d'échantillons (fenêtre courte OU de référence), CTR de
    référence nul, ou fréquence/CTR indisponibles → ``insufficient_data``
    (ALERTE toujours — info —, jamais un skip muet, dd-guardian §B6). Le CPA
    est OPTIONNEL : son absence ne bloque jamais l'évaluation fréquence×CTR."""
    if (recent_samples < min_samples or baseline_samples < min_samples
            or frequency is None or ctr_current is None
            or ctr_baseline is None):
        return _insufficient(
            'creative_fatigue', KIND_CREATIVE_FATIGUE,
            "Fatigue créative : historique insuffisant (fréquence/CTR) — "
            "vérification impossible.",
            {'recent_samples': recent_samples,
             'baseline_samples': baseline_samples})
    if ctr_baseline <= 0:
        return _insufficient(
            'creative_fatigue', KIND_CREATIVE_FATIGUE,
            "Fatigue créative : CTR de référence nul — déclin non calculable.",
            {'ctr_baseline': ctr_baseline})

    ctr_decline_pct = (ctr_baseline - ctr_current) / ctr_baseline
    cpa_increase_pct = None
    if (cpa_current is not None and cpa_baseline is not None
            and cpa_baseline > 0):
        cpa_increase_pct = (cpa_current - cpa_baseline) / cpa_baseline

    computed = {
        'frequency': frequency, 'freq_ceiling': freq_ceiling,
        'ctr_current': ctr_current, 'ctr_baseline': ctr_baseline,
        'ctr_decline_pct': round(ctr_decline_pct, 4),
        'cpa_current': cpa_current, 'cpa_baseline': cpa_baseline,
        'cpa_increase_pct': (round(cpa_increase_pct, 4)
                             if cpa_increase_pct is not None else None),
    }

    freq_over = frequency > freq_ceiling
    ctr_confirmed = ctr_decline_pct >= ctr_decline_warn
    cpa_confirmed = (cpa_increase_pct is not None
                     and cpa_increase_pct >= cpa_increase_warn)

    if not (freq_over and (ctr_confirmed or cpa_confirmed)):
        return Detection('creative_fatigue', False, False, SEVERITY_WARNING,
                         KIND_CREATIVE_FATIGUE, '', computed)

    severity = SEVERITY_WARNING
    if (ctr_decline_pct >= ctr_decline_critical
            or (cpa_increase_pct is not None
                and cpa_increase_pct >= cpa_increase_critical)):
        severity = SEVERITY_CRITICAL

    message = (
        f"Fréquence {frequency:g} (seuil {freq_ceiling:g}) + CTR en baisse de "
        f"{ctr_decline_pct * 100:.0f} % vs référence"
        + (f", CPA +{cpa_increase_pct * 100:.0f} %"
           if cpa_increase_pct is not None else '')
        + " — fatigue créative confirmée : rotation conseillée.")
    return Detection('creative_fatigue', True, False, severity,
                     KIND_CREATIVE_FATIGUE, message, computed)


# ── PUB74 — Fatigue au niveau du VISUEL (visual_asset_key réutilisé) ─────────
# ``visual_asset_key`` (ADSENG5) identifie précisément un visuel réutilisable
# à travers plusieurs ``CreativeAsset`` (recombinaison hook × visuel) — AUCUNE
# analytique ne s'en sert jusqu'ici. Le signal : un visuel qui ressert sur
# beaucoup de créas MALGRÉ des accroches différentes est un candidat à la
# lassitude visuelle, indépendant de la fatigue par-ad (fréquence/CTR d'UNE
# ad, ci-dessus) — le câblage DB (regroupement par visuel + déclin CTR
# cross-ads) vit dans ``metrics.visual_fatigue_report``.
DEFAULT_VISUAL_REUSE_THRESHOLDS = {
    'min_reuse': 3,
    'min_distinct_hooks': 2,
    'ctr_decline_warn': 0.25,
}


def detect_visual_reuse_fatigue(reuse_count, distinct_hook_count, *,
                                min_reuse=3, min_distinct_hooks=2,
                                ctr_decline_pct=None, ctr_decline_warn=0.25):
    """PUB74 — Un visuel réutilisé sur ``reuse_count`` créas MALGRÉ
    ``distinct_hook_count`` accroches différentes est un signal de lassitude
    visuelle. Confirmé (WARNING) dès ``reuse_count >= min_reuse`` ET
    ``distinct_hook_count >= min_distinct_hooks`` (sinon simple recyclage
    normal d'un visuel avec le MÊME hook — pas un signal) ; ESCALADE en
    CRITICAL si le déclin de CTR cross-ads fourni (``ctr_decline_pct``, du
    plus ancien ad utilisant ce visuel au plus récent) dépasse
    ``ctr_decline_warn``. ``ctr_decline_pct`` est OPTIONNEL (calculé par
    l'appelant) : son absence n'empêche jamais la détection de fuite de
    réutilisation elle-même. Fonction PURE — aucun I/O, aucun import de
    modèle."""
    computed = {
        'reuse_count': reuse_count, 'distinct_hook_count': distinct_hook_count,
        'min_reuse': min_reuse, 'min_distinct_hooks': min_distinct_hooks,
        'ctr_decline_pct': (round(ctr_decline_pct, 4)
                            if ctr_decline_pct is not None else None),
    }
    if reuse_count < min_reuse or distinct_hook_count < min_distinct_hooks:
        return Detection('visual_fatigue', False, False, SEVERITY_WARNING,
                         KIND_VISUAL_FATIGUE, '', computed)

    severity = SEVERITY_WARNING
    decline_suffix = ''
    if ctr_decline_pct is not None and ctr_decline_pct >= ctr_decline_warn:
        severity = SEVERITY_CRITICAL
        decline_suffix = (
            f", CTR en baisse de {ctr_decline_pct * 100:.0f} % entre le "
            f"1er et le dernier usage")
    message = (
        f"Visuel réutilisé sur {reuse_count} créas malgré {distinct_hook_count} "
        f"accroches différentes{decline_suffix} — lassitude visuelle probable, "
        f"tester un nouveau visuel.")
    return Detection('visual_fatigue', True, False, severity,
                     KIND_VISUAL_FATIGUE, message, computed)


# ── Matérialisation (câblage DB — le seul point non pur du module) ────────────
def record_anomaly(company, detection, *, entity_type='', entity_meta_id='',
                   rule_policy=None, alert=None):
    """Crée une ``AnomalyEvent`` à partir d'un ``Detection`` DÉCLENCHÉ. Appelé
    par le moteur (jamais pour un ``insufficient_data`` — ce n'est pas une
    anomalie, seulement une lacune de données). ``detail`` = ``computed`` (déjà
    JSON-natif : floats/ints/strings, aucun Decimal)."""
    from .models import AnomalyEvent
    return AnomalyEvent.objects.create(
        company=company, kind=detection.kind, entity_type=entity_type,
        entity_meta_id=entity_meta_id, severity=detection.severity,
        message_fr=detection.message_fr, detail=detection.computed,
        rule_policy=rule_policy, alert=alert)
