"""ENG11 — Générateur de brief hebdomadaire déterministe (v1, SANS LLM).

Le brief agrège les chiffres RÉELS de la semaine (dépense, résultats, CPL,
fréquence vs seuil de fatigue, coût-par-signature cumulé, conformité SLA) et les
rend en phrases template FR. **Aucun LLM en v1** : chaque phrase n'insère que des
NOMBRES calculés — jamais de prose générée (motif anti-hallucination).

Il propose 0 à 3 ``EngineAction`` (chacune avec une ``reason_fr`` obligatoire),
dédupliquées contre les propositions déjà ouvertes pour ne pas spammer la boîte
d'approbation. La métrique coût-par-signature réutilise ``metrics`` (réconciliée
avec les miroirs, traçable) ; les chiffres opérationnels (dépense/fréquence/CPL)
sont calculés sur la FENÊTRE de la semaine.
"""
from __future__ import annotations

import datetime
import logging
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db.models import Avg, Sum

from . import metrics
from .models import AdCampaignMirror, EngineAction, InsightSnapshot, WeeklyBrief

logger = logging.getLogger(__name__)

# Seuil de fatigue créative (fréquence moyenne). En dessous de 2.0 = sain ;
# 2.0–2.5 = attention ; au-delà de 2.5 = fatigue forte (rotation conseillée).
FATIGUE_THRESHOLD_LOW = Decimal('2.0')
FATIGUE_THRESHOLD_HIGH = Decimal('2.5')

MAX_PROPOSALS = 3

# PUB130 — nombre d'entrées par section d'observation (top/flop/fatigue/junk).
# Un brief se lit en 2 minutes : on montre la tête de liste, pas l'inventaire.
OBSERVATION_TOP_N = 3


def weekly_window(now=None):
    """Fenêtre de 7 jours se terminant à ``now`` (date). Retourne (début, fin)."""
    end = now if isinstance(now, datetime.date) else datetime.date.today()
    start = end - datetime.timedelta(days=6)
    return start, end


# ── ADSDEEP48 — Benchmarks internes (cadence créative + taux de gagnants) ────
# Repères du dossier concurrent (Motion, benchmark §2) : les comptes qui
# performent le mieux sortent 12-19 créatifs neufs/semaine avec ~9 % de
# gagnants. Ce sont des REPÈRES affichés à côté du chiffre réel — jamais un
# objectif imposé ni une action déclenchée automatiquement.
CADENCE_TARGET_MIN = 12
CADENCE_TARGET_MAX = 19
WINNER_RATE_BENCHMARK = 0.09

STATUS_BELOW_TARGET = 'sous_cible'
STATUS_ON_TARGET = 'dans_la_cible'
STATUS_ABOVE_TARGET = 'au_dessus_cible'


def weekly_creative_cadence(company, *, start, end):
    """ADSDEEP48 — Nombre de ``CreativeAsset`` NEUFS créés sur la fenêtre
    ``[start, end]`` (bornes incluses) — le rythme de production créative de la
    semaine, comparé au repère marché [12, 19]/semaine (dossier concurrent).
    Renvoie ``{count, target_min, target_max, statut}``."""
    from .models import CreativeAsset

    count = CreativeAsset.objects.filter(
        company=company, created_at__date__gte=start,
        created_at__date__lte=end).count()
    if count < CADENCE_TARGET_MIN:
        statut = STATUS_BELOW_TARGET
    elif count > CADENCE_TARGET_MAX:
        statut = STATUS_ABOVE_TARGET
    else:
        statut = STATUS_ON_TARGET
    return {'count': count, 'target_min': CADENCE_TARGET_MIN,
            'target_max': CADENCE_TARGET_MAX, 'statut': statut}


def winner_rate(company, *, start, end):
    """ADSDEEP48 — Fraction de GAGNANTS parmi les ads LANCÉS sur la fenêtre
    ``[start, end]`` (``AdMirror.created_at``) : un ad est un « gagnant » s'il a
    généré AU MOINS 1 résultat cumulé (``InsightSnapshot.results``) à ce jour.
    Repère marché : ~9 % (dossier concurrent). ``valeur`` est ``None`` si AUCUN
    ad n'a été lancé sur la fenêtre — JAMAIS un taux de 0 % fabriqué sur un
    dénominateur nul."""
    from .models import AdMirror

    launched = list(AdMirror.objects.filter(
        company=company, created_at__date__gte=start,
        created_at__date__lte=end))
    total = len(launched)
    if total == 0:
        return {'valeur': None, 'gagnants': 0, 'total': 0,
                'reference_marche': WINNER_RATE_BENCHMARK}

    ct = ContentType.objects.get_for_model(AdMirror)
    winners = 0
    for ad in launched:
        agg = InsightSnapshot.objects.filter(
            company=company, content_type=ct, object_id=ad.pk).aggregate(
                total_results=Sum('results'))
        if (agg['total_results'] or 0) > 0:
            winners += 1
    return {'valeur': winners / total, 'gagnants': winners, 'total': total,
            'reference_marche': WINNER_RATE_BENCHMARK}


def _fatigue_level(freq):
    """Niveau de fatigue à partir de la fréquence moyenne (Decimal|None)."""
    if freq is None:
        return 'inconnu'
    if freq >= FATIGUE_THRESHOLD_HIGH:
        return 'forte'
    if freq >= FATIGUE_THRESHOLD_LOW:
        return 'attention'
    return 'ok'


def _window_aggregate(company, start, end):
    """Agrège dépense / résultats / fréquence des campagnes sur la fenêtre.

    Renvoie ``(spend, results, freq_avg, last_date, per_campaign)`` où
    ``per_campaign`` = ``[(mirror, spend, results, freq_avg), ...]``."""
    ct = ContentType.objects.get_for_model(AdCampaignMirror)
    campaigns = list(
        AdCampaignMirror.objects.filter(company=company).order_by('meta_id'))
    per_campaign = []
    total_spend = Decimal('0')
    total_results = 0
    freqs = []
    last_date = None
    for camp in campaigns:
        agg = (InsightSnapshot.objects
               .filter(company=company, content_type=ct, object_id=camp.pk,
                       date__gte=start, date__lte=end)
               .aggregate(spend=Sum('spend'), results=Sum('results'),
                          freq=Avg('frequency')))
        spend = agg['spend'] or Decimal('0')
        results = agg['results'] or 0
        freq = agg['freq']
        max_date = (InsightSnapshot.objects
                    .filter(company=company, content_type=ct,
                            object_id=camp.pk, date__lte=end)
                    .order_by('-date').values_list('date', flat=True).first())
        if max_date and (last_date is None or max_date > last_date):
            last_date = max_date
        total_spend += spend
        total_results += results
        if freq is not None:
            freqs.append(freq)
        per_campaign.append((camp, spend, results, freq))
    freq_avg = (sum(freqs) / len(freqs)) if freqs else None
    return total_spend, total_results, freq_avg, last_date, per_campaign


# ═════════════════════════════════════════════════════════════════════════════
# PUB130 — Brief en mode OBSERVATION (avant tout plan de vol)
# ═════════════════════════════════════════════════════════════════════════════
# Le brief ne savait parler que de campagnes agrégées : une société qui OBSERVE
# (miroirs + instantanés synchronisés, mais aucune expérience ni plan de vol)
# recevait un brief sans rien d'actionnable à lire. On ajoute des sections
# d'OBSERVATION bâties UNIQUEMENT sur les données déjà synchronisées — et le
# périmètre est dit HONNÊTEMENT : sans chiffres suffisants, le brief le déclare
# et ne recommande rien. Les candidats à dupliquer / pauser sont en LECTURE
# SEULE : aucune ``EngineAction`` n'est créée depuis eux.
OBSERVATION_READ_ONLY_FR = (
    "Ces candidats sont en LECTURE SEULE : le brief ne propose AUCUNE action à "
    "partir d'eux — c'est vous qui décidez, depuis le cockpit.")


def observation_mode(company):
    """Vrai quand la société n'a NI expérience NI plan de vol.

    Une société qui en possède garde le brief ENG11 **inchangé** (les sections
    d'observation ne sont alors pas calculées ni rendues)."""
    from .models import Experiment, FlightPlan
    return not (
        Experiment.objects.filter(company=company).exists()
        or FlightPlan.objects.filter(company=company).exists())


def _ad_window_rows(company, start, end):
    """Agrégats PAR AD sur la fenêtre, lus sur les instantanés DÉJÀ synchronisés.

    Renvoie ``[{meta_id, name, spend, results, impressions, frequence}]`` trié par
    résultats puis impressions décroissants. Une ad sans instantané sur la fenêtre
    est ABSENTE (jamais une ligne de zéros fabriquée)."""
    from .models import AdMirror

    ads = {a.pk: a for a in AdMirror.objects.filter(company=company)}
    if not ads:
        return []
    ct = ContentType.objects.get_for_model(AdMirror)
    rows = []
    for agg in (InsightSnapshot.objects
                .filter(company=company, content_type=ct,
                        object_id__in=list(ads),
                        date__gte=start, date__lte=end)
                .values('object_id')
                .annotate(spend=Sum('spend'), results=Sum('results'),
                          impressions=Sum('impressions'),
                          freq=Avg('frequency'))):
        ad = ads.get(agg['object_id'])
        if ad is None:
            continue
        rows.append({
            'meta_id': ad.meta_id,
            'name': ad.name or '',
            'spend': str(agg['spend'] or Decimal('0')),
            'results': int(agg['results'] or 0),
            'impressions': int(agg['impressions'] or 0),
            'frequence': (str(agg['freq']) if agg['freq'] is not None
                          else None),
        })
    rows.sort(key=lambda r: (-r['results'], -r['impressions'], r['meta_id']))
    return rows


def _junk_rows(company):
    """Signal qualité JUNK par ad (PUB28), lu sur l'attribution existante.

    Dégrade à une liste VIDE si l'attribution n'est pas calculable (aucun lead
    rattaché, jointure indisponible) — jamais un taux fabriqué, et jamais une
    exception qui ferait perdre tout le brief."""
    from . import attribution

    try:
        report = attribution.variant_attribution(company)
    except Exception:  # noqa: BLE001 — section optionnelle, jamais bloquante
        logger.warning('brief: attribution par ad indisponible société=%s',
                       getattr(company, 'pk', company), exc_info=True)
        return []
    rows = [
        {'meta_id': v.get('meta_id', ''), 'name': v.get('name', ''),
         'leads': v.get('leads', 0), 'junk': v.get('junk', 0),
         'junk_rate': v.get('junk_rate')}
        for v in (report.get('variants') or []) if v.get('junk')
    ]
    rows.sort(key=lambda r: (-(r['junk_rate'] or 0), -r['junk'], r['meta_id']))
    return rows[:OBSERVATION_TOP_N]


def _observation_sections(company, start, end):
    """PUB130 — Sections d'OBSERVATION du brief (lecture seule).

    Tout vient des données DÉJÀ synchronisées : top/flop ads, fatigue par ad,
    fréquence moyenne, junk par ad, et les candidats à dupliquer / pauser. Le
    périmètre est DIT : ``donnees_suffisantes=False`` ⇒ aucune liste de candidats
    n'est produite et le brief l'écrit noir sur blanc."""
    rows = _ad_window_rows(company, start, end)
    with_results = [r for r in rows if r['results'] > 0]
    flop = sorted(
        (r for r in rows
         if Decimal(r['spend']) > 0 and r['results'] == 0),
        key=lambda r: (-Decimal(r['spend']), r['meta_id']))
    fatigue = sorted(
        (r for r in rows if r['frequence'] is not None
         and Decimal(r['frequence']) >= FATIGUE_THRESHOLD_LOW),
        key=lambda r: (-Decimal(r['frequence']), r['meta_id']))
    freqs = [Decimal(r['frequence']) for r in rows
             if r['frequence'] is not None]
    freq_avg = (sum(freqs) / len(freqs)) if freqs else None
    enough = bool(rows)

    if not enough:
        perimetre = (
            "Mode OBSERVATION : aucun instantané de performance sur la fenêtre. "
            "Ce brief n'a donc RIEN à observer et ne formule aucune "
            "recommandation — il le dit plutôt que de fabriquer un constat.")
    else:
        perimetre = (
            f"Mode OBSERVATION (aucune expérience ni plan de vol en cours) : "
            f"{len(rows)} ad(s) avec des chiffres sur la fenêtre, dont "
            f"{len(with_results)} avec au moins un résultat.")
        if not with_results:
            perimetre += (
                " Aucune ad n'a produit de résultat : impossible de désigner un "
                "gagnant, ce brief ne le fait donc pas.")

    return {
        'perimetre_fr': perimetre,
        'donnees_suffisantes': enough,
        'lecture_seule_fr': OBSERVATION_READ_ONLY_FR,
        'ads_observees': len(rows),
        'ads_avec_resultat': len(with_results),
        'top_ads': with_results[:OBSERVATION_TOP_N],
        'flop_ads': flop[:OBSERVATION_TOP_N],
        'fatigue_ads': fatigue[:OBSERVATION_TOP_N],
        'frequence_moyenne': (str(freq_avg) if freq_avg is not None else None),
        'seuil_fatigue': str(FATIGUE_THRESHOLD_LOW),
        'junk_ads': _junk_rows(company),
        # LECTURE SEULE — aucune action n'est proposée depuis ces listes.
        'candidats_duplication': ([r['meta_id'] for r in with_results]
                                  [:OBSERVATION_TOP_N] if enough else []),
        'candidats_pause': ([r['meta_id'] for r in flop]
                            [:OBSERVATION_TOP_N] if enough else []),
    }


def _existing_open_kinds(company):
    """Ensemble (kind, target_object_id) des propositions déjà OUVERTES, pour
    dédupliquer les propositions du brief (jamais deux fois la même)."""
    open_qs = EngineAction.objects.filter(
        company=company, status=EngineAction.Statut.PROPOSEE)
    seen = set()
    for a in open_qs:
        seen.add((a.kind, (a.payload or {}).get('target_object_id')))
    return seen


def _build_proposals(company, per_campaign):
    """Crée 0-3 ``EngineAction`` proposées à partir de règles déterministes.

    * fréquence de campagne ≥ 2.5 (fatigue forte) → rotation créative ;
    * dépense > 0 ET 0 résultat sur la fenêtre → mise en pause.
    Déduplique contre les propositions déjà ouvertes ; plafonne à 3.
    """
    from . import services

    seen = _existing_open_kinds(company)
    proposals = []
    for camp, spend, results, freq in per_campaign:
        if len(proposals) >= MAX_PROPOSALS:
            break
        if freq is not None and freq >= FATIGUE_THRESHOLD_HIGH:
            key = (EngineAction.Kind.ROTATE_CREATIVE, camp.pk)
            if key not in seen:
                proposals.append(services.propose_action(
                    company, kind=EngineAction.Kind.ROTATE_CREATIVE,
                    reason_fr=(
                        f"Fréquence {freq:.1f} sur {camp.meta_id} (≥ 2,5) : "
                        f"roter le créatif pour combattre la fatigue."),
                    payload={'target_type': 'campaign',
                             'target_meta_id': camp.meta_id,
                             'target_object_id': camp.pk}))
                seen.add(key)
                continue
        if spend > 0 and results == 0:
            key = (EngineAction.Kind.PAUSE, camp.pk)
            if key not in seen:
                proposals.append(services.propose_action(
                    company, kind=EngineAction.Kind.PAUSE,
                    reason_fr=(
                        f"{camp.meta_id} a dépensé {spend} MAD pour 0 résultat "
                        f"cette semaine : mise en pause conseillée."),
                    payload={'target_type': 'campaign',
                             'target_meta_id': camp.meta_id,
                             'target_object_id': camp.pk}))
                seen.add(key)
    return proposals[:MAX_PROPOSALS]


def build_brief(company, *, now=None, create_proposals=True):
    """ENG11 — Construit (ou met à jour) le brief hebdomadaire de la société.

    Idempotent par ``(company, period_start)``. Renvoie l'instance
    ``WeeklyBrief`` persistée (avec ``data`` + ``markdown``).

    PUB130 — une société en mode OBSERVATION (ni expérience ni plan de vol)
    reçoit EN PLUS des sections d'observation bâties sur les données déjà
    synchronisées (top/flop, fatigue, fréquence, junk, candidats en LECTURE
    seule) avec son périmètre dit honnêtement. Une société qui a une expérience
    ou un plan garde le brief INCHANGÉ (``data`` et ``markdown`` identiques).
    """
    start, end = weekly_window(now)
    spend, results, freq_avg, last_date, per_campaign = _window_aggregate(
        company, start, end)

    cpl = (spend / results) if results else None
    summary = metrics.cost_per_signature_summary(company)

    proposals = _build_proposals(company, per_campaign) if create_proposals else []

    data = {
        'periode': {'debut': start.isoformat(), 'fin': end.isoformat()},
        'spend_semaine': str(spend),
        'resultats_semaine': results,
        'cpl_semaine': (str(cpl) if cpl is not None else None),
        'frequence_moyenne': (str(freq_avg) if freq_avg is not None else None),
        'fatigue': {
            'seuil_bas': str(FATIGUE_THRESHOLD_LOW),
            'seuil_haut': str(FATIGUE_THRESHOLD_HIGH),
            'niveau': _fatigue_level(freq_avg),
        },
        'cout_par_signature_cumule': summary['cost_per_signature'],
        'signatures_cumulees': summary['total_signed'],
        'sla_ok': bool(last_date is not None and last_date >= start),
        'derniere_sync': (last_date.isoformat() if last_date else None),
        # ADSDEEP48 — benchmarks internes (cadence créative + taux de gagnants).
        'cadence_creative': weekly_creative_cadence(company, start=start, end=end),
        'taux_de_gagnants': winner_rate(company, start=start, end=end),
        'propositions': [
            {'id': p.id, 'kind': p.kind, 'reason_fr': p.reason_fr}
            for p in proposals
        ],
    }
    # PUB130 — la clé ``observation`` n'est AJOUTÉE qu'en mode observation : une
    # société avec expérience/plan garde donc un ``data`` (et un markdown)
    # strictement identique à l'avant-PUB130.
    if observation_mode(company):
        data['observation'] = _observation_sections(company, start, end)
    markdown = render_markdown(data)

    brief, _ = WeeklyBrief.objects.update_or_create(
        company=company, period_start=start,
        defaults={'period_end': end, 'data': data, 'markdown': markdown})
    return brief


def render_markdown(data):
    """Rend le brief en markdown FR — uniquement des NOMBRES dans des phrases
    template (aucun texte généré). Déterministe."""
    p = data['periode']
    lines = [
        f"# Brief hebdomadaire ({p['debut']} → {p['fin']})",
        '',
        '## Ce qui s\'est passé',
        f"- Dépense de la semaine : {data['spend_semaine']} MAD "
        f"pour {data['resultats_semaine']} résultat(s).",
    ]
    if data['cpl_semaine'] is not None:
        lines.append(f"- Coût par lead (semaine) : {data['cpl_semaine']} MAD.")
    if data['frequence_moyenne'] is not None:
        fat = data['fatigue']['niveau']
        lines.append(
            f"- Fréquence moyenne : {data['frequence_moyenne']} "
            f"(seuil de fatigue {data['fatigue']['seuil_bas']}–"
            f"{data['fatigue']['seuil_haut']}) → {fat}.")
    if data['cout_par_signature_cumule'] is not None:
        lines.append(
            f"- Coût par signature (cumulé) : "
            f"{data['cout_par_signature_cumule']} MAD "
            f"pour {data['signatures_cumulees']} signature(s).")
    # ADSDEEP48 — benchmarks internes (cadence créative + taux de gagnants),
    # repères du dossier concurrent (Motion, benchmark §2).
    cadence = data.get('cadence_creative')
    if cadence is not None:
        statut_fr = cadence['statut'].replace('_', ' ')
        lines.append(
            f"- Cadence créative : {cadence['count']} créatif(s) neuf(s) cette "
            f"semaine (repère marché {cadence['target_min']}-"
            f"{cadence['target_max']}/semaine) → {statut_fr}.")
    gagnants = data.get('taux_de_gagnants')
    if gagnants is not None:
        if gagnants['valeur'] is not None:
            lines.append(
                f"- Taux de gagnants : {gagnants['gagnants']}/"
                f"{gagnants['total']} ad(s) lancé(s) cette semaine "
                f"({gagnants['valeur'] * 100:.0f} %, repère marché "
                f"~{gagnants['reference_marche'] * 100:.0f} %).")
        else:
            lines.append(
                '- Taux de gagnants : aucun ad lancé cette semaine — '
                'indicateur non calculable.')
    lines.append(
        f"- SLA de synchronisation : "
        f"{'à jour' if data['sla_ok'] else 'EN RETARD'}"
        f"{' (dernière sync ' + data['derniere_sync'] + ')' if data['derniere_sync'] else ''}.")
    lines.append('')
    lines.append('## Suggestions')
    if data['propositions']:
        for prop in data['propositions']:
            lines.append(f"- {prop['reason_fr']}")
    else:
        lines.append('- Aucune action proposée cette semaine.')
    # PUB130 — section OBSERVATION : rendue UNIQUEMENT si le brief en porte une
    # (une société avec expérience/plan garde donc un markdown inchangé).
    lines.extend(_render_observation(data.get('observation')))
    return '\n'.join(lines)


def _render_observation(observation):
    """PUB130 — Rend les sections d'observation en markdown FR (liste de lignes).

    ``None`` (société avec expérience/plan) ⇒ liste VIDE : rien n'est ajouté au
    brief historique. Données insuffisantes ⇒ le périmètre est écrit et AUCUNE
    liste de candidats n'est rendue (le brief dit ce qu'il ne sait pas)."""
    if not observation:
        return []
    lines = ['', '## Observation (lecture seule)',
             f"- {observation['perimetre_fr']}"]
    if not observation['donnees_suffisantes']:
        return lines

    def _ad_label(row):
        return f"{row['name'] or row['meta_id']} ({row['meta_id']})"

    if observation['top_ads']:
        lines.append('- Meilleures ads de la semaine :')
        for row in observation['top_ads']:
            lines.append(
                f"  - {_ad_label(row)} — {row['results']} résultat(s) pour "
                f"{row['spend']} dépensé(s), {row['impressions']} impression(s).")
    if observation['flop_ads']:
        lines.append('- Ads qui dépensent sans résultat :')
        for row in observation['flop_ads']:
            lines.append(
                f"  - {_ad_label(row)} — {row['spend']} dépensé(s), 0 résultat.")
    if observation['frequence_moyenne'] is not None:
        lines.append(
            f"- Fréquence moyenne par ad : {observation['frequence_moyenne']} "
            f"(seuil d'attention {observation['seuil_fatigue']}).")
    if observation['fatigue_ads']:
        lines.append('- Ads au-delà du seuil de fatigue :')
        for row in observation['fatigue_ads']:
            lines.append(
                f"  - {_ad_label(row)} — fréquence {row['frequence']}.")
    if observation['junk_ads']:
        lines.append('- Qualité des leads (junk) par ad :')
        for row in observation['junk_ads']:
            rate = row['junk_rate']
            rate_fr = (f"{rate * 100:.0f} %" if rate is not None
                       else 'taux non calculable')
            lines.append(
                f"  - {_ad_label(row)} — {row['junk']} junk sur "
                f"{row['leads']} lead(s) ({rate_fr}).")
    if observation['candidats_duplication']:
        lines.append(
            "- Candidats à DUPLIQUER (lecture seule) : "
            + ', '.join(observation['candidats_duplication']) + '.')
    if observation['candidats_pause']:
        lines.append(
            "- Candidats à PAUSER (lecture seule) : "
            + ', '.join(observation['candidats_pause']) + '.')
    if observation['candidats_duplication'] or observation['candidats_pause']:
        lines.append(f"- {observation['lecture_seule_fr']}")
    return lines
