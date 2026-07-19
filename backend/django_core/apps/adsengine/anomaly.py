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

import datetime
import logging
import statistics
from dataclasses import dataclass, field

from .rules import SEVERITY_CRITICAL, SEVERITY_INFO, SEVERITY_WARNING

logger = logging.getLogger(__name__)

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
# PUB33 — vélocité d'apprentissage (volume d'événements d'optimisation/7 j).
KIND_LEARNING_VELOCITY = 'apprentissage_lent'
# PUB34 — santé structurelle (doctrine Andromeda : fragmentation ad sets/créas).
KIND_STRUCTURAL_FRAGMENTATION = 'fragmentation_structurelle'
# PUB74 — kind EN CONSTANTE SIMPLE (même pattern qu'ADSDEEP45 ci-dessus) :
# fatigue au niveau du VISUEL (``visual_asset_key``), DISTINCTE de la fatigue
# par ad ci-dessus (fréquence/CTR d'UNE ad) — ici le signal est « le même
# visuel ressert sur N créas malgré des hooks différents ».
KIND_VISUAL_FATIGUE = 'visual_fatigue'

# PUB33 — Meta cible ~50 événements d'optimisation (résultats de la campagne
# d'optimisation) par ad set sur une fenêtre glissante de 7 jours pour sortir
# proprement de la phase d'apprentissage ; en dessous, l'ad set reste affamé de
# signal (CPA instable, apprentissage qui ne se stabilise jamais).
DEFAULT_LEARNING_EVENTS_PER_WEEK = 50

# PUB34 — doctrine Andromeda 2025/2026 (le ranking Meta lit désormais le
# créatif) : 2-3 ad sets actifs par campagne, 15-25 créations diverses par ad
# set restant. Au-delà du max d'ad sets → fragmentation du budget/signal ; en
# dessous du min de créas → l'algorithme de sélection créative manque de
# variété pour bien apprendre.
IDEAL_ACTIVE_ADSETS_MIN = 2
IDEAL_ACTIVE_ADSETS_MAX = 3
IDEAL_CREATIVES_MIN = 15
IDEAL_CREATIVES_MAX = 25


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


# ── PUB33 — Vigie vélocité d'apprentissage (~50 événements d'optimisation/7 j) ─
def detect_learning_velocity(daily_optimization_events, *,
                             min_events_per_week=DEFAULT_LEARNING_EVENTS_PER_WEEK,
                             min_samples=3):
    """Ad set sous le seuil ~50 événements d'optimisation/7 j (Meta) — signal
    que PERSONNE ne surveille aujourd'hui : un ad set structurellement affamé
    de volume ne sort jamais proprement de l'apprentissage et ne se voit qu'a
    posteriori dans le CPA.

    ``daily_optimization_events`` = compte quotidien d'événements
    d'optimisation DÉJÀ SYNCHRONISÉS (``InsightSnapshot.results``, ou
    ``leads_count`` à défaut) sur la fenêtre glissante (7 j par défaut) —
    fonction PURE, aucun I/O, le câblage DB vit dans
    ``evaluate_learning_velocity`` ci-dessous. Sous ``min_samples`` jours de
    donnée → ``insufficient_data`` (ALERTE toujours, jamais un skip muet,
    même doctrine que le reste du module)."""
    clean = _floats(daily_optimization_events)
    if len(clean) < min_samples:
        return _insufficient(
            'learning_velocity', KIND_LEARNING_VELOCITY,
            "Vélocité d'apprentissage : historique insuffisant pour juger — "
            "vérification impossible.", {'samples': len(clean)})
    total = sum(clean)
    computed = {'total_events_7d': total, 'threshold': min_events_per_week,
                'samples': len(clean)}
    if total < min_events_per_week:
        deficit = min_events_per_week - total
        return Detection(
            'learning_velocity', True, False, SEVERITY_WARNING,
            KIND_LEARNING_VELOCITY,
            (f"Ad set sous le seuil d'apprentissage Meta : {total:g} "
             f"événement(s) d'optimisation sur 7 jours (seuil ~"
             f"{min_events_per_week:g}) — déficit de {deficit:g}. Volume trop "
             "faible pour sortir proprement de la phase d'apprentissage : "
             "envisagez de CONSOLIDER cet ad set avec un autre proche (même "
             "audience/objectif) pour concentrer le volume d'optimisation, ou "
             "élargir le ciblage."),
            computed)
    return Detection('learning_velocity', False, False, SEVERITY_WARNING,
                     KIND_LEARNING_VELOCITY, '', computed)


# ── PUB34 — Santé structurelle (doctrine Andromeda 2025/2026) ────────────────
def detect_structural_fragmentation(active_adset_count, creatives_per_adset=None,
                                    *, ideal_adsets_max=IDEAL_ACTIVE_ADSETS_MAX,
                                    ideal_creatives_min=IDEAL_CREATIVES_MIN):
    """Doctrine Andromeda (le ranking Meta lit désormais le créatif) : 2-3 ad
    sets actifs par campagne, 15-25 créations diverses par ad set. Beaucoup de
    petits ad sets AFFAME l'algorithme (chaque ad set trop petit, signal
    dispersé) ; peu de créations par ad set prive le sélecteur créatif de
    variété pour apprendre.

    ``active_adset_count`` = nb d'ad sets ACTIFS de la campagne, déjà
    synchronisé (``None`` ⇒ aucune donnée d'ad set encore synchronisée pour
    cette campagne → ``insufficient_data``, jamais un skip muet).
    ``creatives_per_adset`` = liste du nb de créas (ads) de chacun de ces ad
    sets actifs (ordre indifférent). Fonction PURE, aucun I/O ; le câblage DB
    vit dans ``evaluate_structural_fragmentation`` ci-dessous.

    Renvoie une RECOMMANDATION de consolidation seulement — **jamais une
    action automatique** : la décision de fusionner des ad sets reste
    humaine (règle du moteur : propose→approve→apply, jamais d'écriture
    directe depuis un détecteur)."""
    if active_adset_count is None:
        return _insufficient(
            'structural_fragmentation', KIND_STRUCTURAL_FRAGMENTATION,
            "Santé structurelle : nombre d'ad sets actifs inconnu (aucune "
            "synchro) — vérification impossible.")
    creatives = [c for c in (creatives_per_adset or []) if c is not None]
    starved = [c for c in creatives if c < ideal_creatives_min]
    too_many_adsets = active_adset_count > ideal_adsets_max
    computed = {
        'active_adsets': active_adset_count, 'ideal_adsets_max': ideal_adsets_max,
        'creatives_per_adset': creatives,
        'ideal_creatives_min': ideal_creatives_min,
        'starved_adsets': len(starved),
    }
    if not too_many_adsets and not starved:
        return Detection('structural_fragmentation', False, False,
                         SEVERITY_WARNING, KIND_STRUCTURAL_FRAGMENTATION, '',
                         computed)
    bits = []
    if too_many_adsets:
        bits.append(
            f"{active_adset_count} ad sets actifs (doctrine "
            f"{IDEAL_ACTIVE_ADSETS_MIN}-{ideal_adsets_max}) — fragmentation "
            "probable du budget/signal.")
    if starved:
        bits.append(
            f"{len(starved)} ad set(s) avec moins de {ideal_creatives_min} "
            "créations diverses — l'algorithme de sélection créative manque "
            "de variété pour bien apprendre.")
    message = (
        "Structure sous-optimale (doctrine Andromeda — le ranking Meta lit "
        "désormais le créatif) : " + ' '.join(bits) + " Plan de consolidation "
        f"suggéré : regrouper en {IDEAL_ACTIVE_ADSETS_MIN}-{ideal_adsets_max} "
        f"ad sets, chacun avec {ideal_creatives_min}-{IDEAL_CREATIVES_MAX} "
        "créations diversifiées. Recommandation seulement — AUCUNE action "
        "automatique, décision humaine requise.")
    return Detection('structural_fragmentation', True, False, SEVERITY_WARNING,
                     KIND_STRUCTURAL_FRAGMENTATION, message, computed)


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


# ── PUB90 — Feedback utile/faux-positif : précision par détecteur + throttle ──
# Chaque fausse alarme érode la confiance. Un utilisateur vote « utile » ou
# « faux positif » sur une anomalie ; on suit la PRÉCISION par détecteur et, sous
# une constance d'inutilité, on FREINE ce détecteur (cadence réduite). Le throttle
# est BRAKE-ONLY : il ne fait que SUPPRIMER des enregistrements redondants, jamais
# lever une nouvelle alerte auto (invariant règle #3).
DETECTOR_THROTTLE_MIN_FALSE_POSITIVES = 5   # votes « inutile » avant de freiner
DETECTOR_THROTTLE_COOLDOWN_HOURS = 24       # 1 anomalie / fenêtre quand throttlé
DETECTOR_THROTTLE_FACTOR = 4                 # facteur de cadence affiché


def precision(useful, labelled):
    """Précision = fraction de retours « utile » parmi les votés. Pure.

    None quand rien n'a été voté (jamais un 0 % trompeur : « pas de vote » ≠
    « détecteur inutile »)."""
    return (useful / labelled) if labelled else None


def is_detector_throttled(company, detector, *,
                          min_false_positives=DETECTOR_THROTTLE_MIN_FALSE_POSITIVES):
    """Vrai si ce détecteur a été voté « faux positif » au moins
    ``min_false_positives`` fois pour la société → cadence à réduire (brake-only).
    Un détecteur vide n'est jamais throttlé."""
    if not detector:
        return False
    from .models import AnomalyEvent
    fp = AnomalyEvent.objects.filter(
        company=company, detector=detector,
        feedback=AnomalyEvent.Feedback.FAUX_POSITIF).count()
    return fp >= min_false_positives


def detector_stats(company, detector):
    """Statistiques de confiance d'UN détecteur (society-scopé) : total, votés,
    utiles, faux positifs, précision, et état de throttle (VISIBLE dans l'UI)."""
    from .models import AnomalyEvent
    qs = AnomalyEvent.objects.filter(company=company, detector=detector)
    labelled = qs.exclude(feedback='').count()
    useful = qs.filter(feedback=AnomalyEvent.Feedback.UTILE).count()
    fp = qs.filter(feedback=AnomalyEvent.Feedback.FAUX_POSITIF).count()
    throttled = fp >= DETECTOR_THROTTLE_MIN_FALSE_POSITIVES
    prec = precision(useful, labelled)
    return {
        'detector': detector, 'total': qs.count(), 'labelled': labelled,
        'useful': useful, 'false_positive': fp,
        'precision': (round(prec, 4) if prec is not None else None),
        'throttled': throttled,
        'throttle_factor': DETECTOR_THROTTLE_FACTOR if throttled else 1,
    }


def all_detector_stats(company):
    """Stats de confiance de TOUS les détecteurs ayant produit une anomalie pour
    la société (les détecteurs sans anomalie sont absents — jamais fabriqués)."""
    from .models import AnomalyEvent
    detectors = (AnomalyEvent.objects.filter(company=company)
                 .exclude(detector='')
                 .values_list('detector', flat=True).distinct())
    return [detector_stats(company, d) for d in sorted(set(detectors))]


# ── Matérialisation (câblage DB — le seul point non pur du module) ────────────
def record_anomaly(company, detection, *, entity_type='', entity_meta_id='',
                   rule_policy=None, alert=None, now=None):
    """Crée une ``AnomalyEvent`` à partir d'un ``Detection`` DÉCLENCHÉ. Appelé
    par le moteur (jamais pour un ``insufficient_data`` — ce n'est pas une
    anomalie, seulement une lacune de données). ``detail`` = ``computed`` (déjà
    JSON-natif : floats/ints/strings, aucun Decimal). Le ``detector`` est stocké
    (clé de la précision PUB90).

    **Throttle BRAKE-ONLY (PUB90)** : si le détecteur a été voté inutile ≥ 5 fois,
    sa cadence est réduite — on n'enregistre pas une anomalie du même détecteur
    plus d'une fois par fenêtre de ``DETECTOR_THROTTLE_COOLDOWN_HOURS`` (renvoie
    ``None``). Jamais une nouvelle alerte : uniquement un frein."""
    from django.utils import timezone

    from .models import AnomalyEvent

    detector = detection.detector
    if detector and is_detector_throttled(company, detector):
        now = now or timezone.now()
        window_start = now - datetime.timedelta(
            hours=DETECTOR_THROTTLE_COOLDOWN_HOURS)
        recent = AnomalyEvent.objects.filter(
            company=company, detector=detector,
            created_at__gte=window_start).exists()
        if recent:
            return None
    return AnomalyEvent.objects.create(
        company=company, kind=detection.kind, entity_type=entity_type,
        entity_meta_id=entity_meta_id, severity=detection.severity,
        message_fr=detection.message_fr, detail=detection.computed,
        detector=detector, rule_policy=rule_policy, alert=alert)


# ── PUB33/PUB34 — Matérialisation directe en ``EngineAlert`` (recommandation) ─
# Ces deux détecteurs parlent au fondateur directement (centre d'alertes),
# pas au journal d'anomalies techniques ``AnomalyEvent`` — même patron que
# ``blast_radius._emit_critical_alert`` : dédup par ``entity_key`` sur un
# cooldown (ne renotifie pas à chaque évaluation tant que rien n'a changé).
# JAMAIS d'``EngineAction`` créée ici — une alerte est une RECOMMANDATION,
# jamais une action auto (règle du moteur, hors escalade humaine explicite).
def _emit_alert(company, detection, *, entity_key, cooldown_hours=24):
    """Matérialise une ``EngineAlert`` de type ``anomalie`` à partir d'un
    ``Detection`` DÉCLENCHÉ (jamais pour un ``insufficient_data``). Best-effort
    : une erreur de persistance ne casse jamais l'appelant (déjà journalisée
    via ``logger.warning`` + le ``Detection`` renvoyé par le détecteur pur)."""
    from django.utils import timezone

    from .models import EngineAlert

    if company is None or not detection.fired:
        return None
    try:
        since = timezone.now() - datetime.timedelta(hours=cooldown_hours)
        existing = (EngineAlert.objects
                    .filter(company=company, entity_key=entity_key,
                            resolved=False, created_at__gte=since)
                    .order_by('-created_at').first())
        if existing is not None:
            return existing
        return EngineAlert.objects.create(
            company=company, alert_type=EngineAlert.Type.ANOMALIE,
            message=detection.message_fr, severity=detection.severity,
            entity_key=entity_key, cooldown_hours=cooldown_hours,
            detail=detection.computed)
    except Exception:  # pragma: no cover - défensif, jamais casser l'appelant
        logger.warning(
            'anomaly: échec persistance EngineAlert (%s)', entity_key,
            exc_info=True)
        return None


def evaluate_learning_velocity(company, adset, *, now=None,
                               min_events_per_week=DEFAULT_LEARNING_EVENTS_PER_WEEK,
                               window_days=7, min_samples=3):
    """PUB33 — Lit les ``InsightSnapshot`` DÉJÀ SYNCHRONISÉS de l'ad set sur les
    ``window_days`` derniers jours (``results``, ou ``leads_count`` à défaut),
    calcule ``detect_learning_velocity`` et matérialise une ``EngineAlert`` FR
    si déclenché (dédupliquée par ad set). Renvoie toujours le ``Detection``
    (utile même quand ``insufficient_data`` ou non déclenché — jamais
    d'écriture sur Meta, lecture seule de données déjà synchronisées)."""
    from django.contrib.contenttypes.models import ContentType

    from .models import AdSetMirror, InsightSnapshot

    today = now.date() if isinstance(now, datetime.datetime) else (
        now if isinstance(now, datetime.date) else datetime.date.today())
    start = today - datetime.timedelta(days=max(1, window_days) - 1)
    ct = ContentType.objects.get_for_model(AdSetMirror)
    snaps = (InsightSnapshot.objects
             .filter(company=company, content_type=ct, object_id=adset.pk,
                     date__gte=start, date__lte=today)
             .order_by('date'))
    daily = [
        (s.results if s.results is not None else s.leads_count) for s in snaps]
    detection = detect_learning_velocity(
        daily, min_events_per_week=min_events_per_week,
        min_samples=min_samples)
    if detection.fired:
        _emit_alert(
            company, detection,
            entity_key=f'learning_velocity:adset:{adset.meta_id}'[:80])
    return detection


def evaluate_structural_fragmentation(company, campaign, *, now=None,
                                      ideal_adsets_max=IDEAL_ACTIVE_ADSETS_MAX,
                                      ideal_creatives_min=IDEAL_CREATIVES_MIN):
    """PUB34 — Lit les miroirs DÉJÀ SYNCHRONISÉS (``AdSetMirror``/``AdMirror``)
    de la campagne : nb d'ad sets ACTIFS + nb de créas (ads) de chacun. Calcule
    ``detect_structural_fragmentation`` et matérialise une ``EngineAlert`` FR
    si déclenché (dédupliquée par campagne). Aucune ad set totalement
    non-synchronisée pour cette campagne ⇒ ``None`` transmis au détecteur
    (``insufficient_data`` honnête, jamais un ``0`` fabriqué)."""
    from .models import AdSetMirror

    adsets = list(
        AdSetMirror.objects.filter(company=company, campaign=campaign))
    if not adsets:
        detection = detect_structural_fragmentation(
            None, [], ideal_adsets_max=ideal_adsets_max,
            ideal_creatives_min=ideal_creatives_min)
    else:
        active = [a for a in adsets
                  if (a.status or '').strip().upper() in ('ACTIVE', 'ACTIF')]
        creatives_per_adset = [a.ads.count() for a in active]
        detection = detect_structural_fragmentation(
            len(active), creatives_per_adset, ideal_adsets_max=ideal_adsets_max,
            ideal_creatives_min=ideal_creatives_min)
    if detection.fired:
        _emit_alert(
            company, detection,
            entity_key=(
                f'structural_fragmentation:campaign:{campaign.meta_id}'[:80]))
    return detection
