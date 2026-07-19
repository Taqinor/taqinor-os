"""ADSDEEP63 — Audit de compte à la demande (Madgicx-style), FR, actionnable.

Cinq sections, chacune ``{statut, resume, items[], lien}`` — jamais un score
opaque : chaque item porte un CHIFFRE RÉEL (jamais un texte généré/LLM, même
doctrine anti-hallucination que ``brief.py``) et un ``lien`` vers l'écran
console qui permet d'agir.

- **structure/naming** — ads sans tag de convention de nommage
  (``naming.py``, ADSDEEP46) : un compte qui ne suit aucune convention perd le
  bénéfice du classement créatif (``reporting.creative_leaderboard``).
- **fragmentation budgétaire** — campagnes à BEAUCOUP d'ad sets dont
  PLUSIEURS restent simultanément en apprentissage/limité
  (``AdSetMirror.learning_status``, ADSDEEP32) : signe classique de
  sur-segmentation qui empêche chaque ad set de sortir de l'apprentissage.
- **fatigue créative** — réutilise TEL QUEL le seuil et l'agrégat 7 jours de
  ``brief.py`` (``FATIGUE_THRESHOLD_HIGH``, ``_window_aggregate``) : jamais un
  second seuil qui divergerait du brief hebdomadaire.
- **tracking** — pixel/CAPI câblés (même logique de présence que
  ``MetaConnectionHealthView``) + liens créatifs sans paramètre ``utm_``
  détecté (``AdCreativeMirror.link_url``).
- **fenêtres de données** — rappel FR des limites Meta (mêmes fenêtres que
  ``DataWindowNotice`` côté frontend, ADSDEEP66 — dupliquées ici en constantes
  documentées, aucun import cross-stack possible entre Python et JS).

Défensif : chaque section est calculée dans son propre try/except — une
section en échec dégrade en ``{statut: 'inconnu'}`` sans jamais casser l'audit
ni les autres sections (comme ``brief.build_brief``/``digest.build_digest_data``).
100 % LECTURE : aucune écriture, aucun appel réseau Meta (tout vient de
miroirs/instantanés déjà synchronisés).
"""
from __future__ import annotations

import datetime
import logging
import os

logger = logging.getLogger(__name__)

# Une campagne avec au moins ce nombre d'ad sets ET au moins 2 d'entre eux
# encore en apprentissage/limité simultanément est un signe classique de
# sur-fragmentation budgétaire (chaque ad set trop petit pour sortir de la
# phase d'apprentissage Meta — dossier concurrent §2).
MIN_ADSETS_FOR_FRAGMENTATION_FLAG = 3
MIN_LEARNING_LIMITED_FOR_FLAG = 2

STATUT_OK = 'ok'
STATUT_ATTENTION = 'attention'
STATUT_INCONNU = 'inconnu'
STATUT_INFO = 'info'

# ADSDEEP66 — mêmes fenêtres/messages que ``frontend/.../adsengine.js``
# ``DATA_WINDOWS`` (dupliquées ici : aucun partage de constantes possible
# entre le backend Python et le frontend JS dans ce dépôt). Tenir synchronisé
# si les fenêtres frontend changent.
DATA_WINDOWS = {
    'leads': {
        'window_days': 90,
        'message_fr': (
            "Meta efface les leads après 90 jours — l'historique complet "
            'vit dans l\'ERP/Odoo.'),
    },
    'insights': {
        'window_days': 37 * 30,
        'message_fr': (
            'Meta ne conserve les insights détaillés que 37 mois glissants '
            '— au-delà, l\'historique n\'est plus interrogeable côté Meta.'),
    },
    'uniques': {
        'window_days': 13 * 30,
        'message_fr': (
            'Les métriques UNIQUES (portée/reach, fréquence) ne sont '
            'disponibles que sur 13 mois glissants côté Meta.'),
    },
    'breakdowns': {
        'window_days': 28,
        'message_fr': (
            'Les ventilations (âge, placement, région, heure) sont '
            'synchronisées sur une fenêtre glissante de 28 jours.'),
    },
    'retention': {
        'window_days': 13 * 30,
        'message_fr': (
            'Meta ne conserve les données brutes que 13 mois — au-delà, '
            'seul l\'historique ERP/Odoo fait foi.'),
    },
}


def _audit_naming(company):
    """Ads sans AUCUN tag de convention de nommage (hook/angle/format,
    ADSDEEP46) : sans convention suivie, le classement créatif spend-weighted
    (``reporting.creative_leaderboard``) reste vide."""
    from .models import AdMirror

    ads = AdMirror.objects.filter(company=company)
    total = ads.count()
    if total == 0:
        return {
            'statut': STATUT_INCONNU,
            'resume': 'Aucune ad synchronisée — audit non calculable.',
            'items': [], 'lien': '/publicite/campagnes',
        }
    untagged = ads.filter(
        hook_tag='', angle_tag='', format_tag='').count()
    items = []
    if untagged:
        items.append(
            f"{untagged}/{total} ad(s) sans tag de convention de nommage "
            "(hook/angle/format) — retaguez via la bibliothèque créative ou "
            "ajustez la convention positionnelle.")
    statut = STATUT_ATTENTION if untagged / total > 0.5 else STATUT_OK
    return {
        'statut': statut,
        'resume': f"{total - untagged}/{total} ad(s) taguée(s) selon la "
                  "convention de nommage.",
        'items': items, 'lien': '/publicite/creatifs',
    }


def _audit_budget_fragmentation(company):
    """Campagnes à beaucoup d'ad sets dont plusieurs restent SIMULTANÉMENT en
    apprentissage/limité (``AdSetMirror.learning_status``) — fragmentation
    budgétaire probable (chaque ad set trop petit pour sortir de
    l'apprentissage Meta)."""
    from .models import AdCampaignMirror, AdSetMirror

    campaigns = list(AdCampaignMirror.objects.filter(company=company))
    if not campaigns:
        return {
            'statut': STATUT_INCONNU,
            'resume': 'Aucune campagne synchronisée — audit non calculable.',
            'items': [], 'lien': '/publicite/campagnes',
        }
    flagged_items = []
    for camp in campaigns:
        adsets = list(
            AdSetMirror.objects.filter(company=company, campaign=camp))
        if len(adsets) < MIN_ADSETS_FOR_FRAGMENTATION_FLAG:
            continue
        learning_limited = [
            a for a in adsets
            if a.learning_status in (
                AdSetMirror.LearningStatus.LEARNING,
                AdSetMirror.LearningStatus.FAIL)]
        if len(learning_limited) >= MIN_LEARNING_LIMITED_FOR_FLAG:
            flagged_items.append(
                f"{camp.name or camp.meta_id} : {len(adsets)} ad sets, "
                f"{len(learning_limited)} en apprentissage/limité "
                "simultanément — fragmentation budgétaire probable, "
                "envisagez de consolider les ad sets.")
    statut = STATUT_ATTENTION if flagged_items else STATUT_OK
    return {
        'statut': statut,
        'resume': f"{len(flagged_items)}/{len(campaigns)} campagne(s) avec "
                  "fragmentation budgétaire probable.",
        'items': flagged_items, 'lien': '/publicite/campagnes',
    }


def _audit_fatigue(company, *, now=None):
    """Réutilise TEL QUEL le seuil + l'agrégat 7 jours de ``brief.py``
    (jamais un second seuil de fatigue qui divergerait du brief
    hebdomadaire)."""
    from . import brief as brief_mod

    start, end = brief_mod.weekly_window(now)
    _spend, _results, _freq, _last, per_campaign = (
        brief_mod._window_aggregate(company, start, end))
    items = []
    for camp, _spend_c, _results_c, freq in per_campaign:
        if freq is not None and freq >= brief_mod.FATIGUE_THRESHOLD_HIGH:
            items.append(
                f"{camp.name or camp.meta_id} : fréquence {freq:.1f} "
                f"(≥ {brief_mod.FATIGUE_THRESHOLD_HIGH}) sur 7 jours — "
                "rotation créative conseillée.")
    statut = STATUT_ATTENTION if items else STATUT_OK
    return {
        'statut': statut,
        'resume': f"{len(items)} campagne(s) en fatigue forte sur "
                  f"{start.isoformat()}–{end.isoformat()}.",
        'items': items, 'lien': '/publicite/regles',
    }


def _audit_tracking(company):
    """Pixel/CAPI câblés (même logique de PRÉSENCE que
    ``MetaConnectionHealthView`` — jamais un secret exposé) + liens créatifs
    sans paramètre UTM détecté."""
    from .models import AdCreativeMirror, MetaConnection

    conn = MetaConnection.objects.filter(company=company).first()
    has_pixel = bool(conn and conn.pixel_id)
    capi_ok = bool(os.environ.get('META_CAPI_ACCESS_TOKEN')
                   and os.environ.get('META_CAPI_PIXEL_ID'))
    items = []
    if not has_pixel:
        items.append(
            'Aucun pixel Meta enregistré — le suivi de conversion sur site '
            'est incomplet.')
    if not capi_ok:
        items.append(
            "CAPI (Conversions API) non câblée — clé serveur absente, "
            "suivi moins résilient au blocage des cookies tiers.")
    links = list(
        AdCreativeMirror.objects.filter(company=company)
        .exclude(link_url='').values_list('link_url', flat=True))
    no_utm = [link for link in links if 'utm_' not in link]
    if links and no_utm:
        items.append(
            f"{len(no_utm)}/{len(links)} lien(s) créatif(s) sans paramètre "
            "UTM détecté — attribution web dégradée pour ces ads.")
    statut = STATUT_ATTENTION if items else STATUT_OK
    return {
        'statut': statut,
        'resume': ('Pixel, CAPI et UTM en ordre.' if not items
                   else f"{len(items)} point(s) de suivi à corriger."),
        'items': items, 'lien': '/publicite/connexion',
    }


def _audit_data_windows():
    """Rappel FR des limites de rétention Meta — purement informatif, jamais
    une action à effectuer (aucun lien de correction, juste un rappel)."""
    items = [w['message_fr'] for w in DATA_WINDOWS.values()]
    return {
        'statut': STATUT_INFO,
        'resume': 'Rappel des fenêtres de données Meta (aucune action '
                  'requise).',
        'items': items, 'lien': '/publicite/reporting',
    }


_SECTION_BUILDERS = (
    ('naming', _audit_naming),
    ('fragmentation_budgetaire', _audit_budget_fragmentation),
    ('fatigue', _audit_fatigue),
    ('tracking', _audit_tracking),
)


def run_account_audit(company, *, now=None):
    """ADSDEEP63 — Construit l'audit de compte COMPLET (5 sections), 100 %
    LECTURE, à la demande (jamais planifié — pas de beat). Chaque section est
    isolée dans son propre try/except : une section en échec dégrade en
    ``{statut: 'inconnu'}`` sans jamais casser les autres."""
    sections = {}
    for key, builder in _SECTION_BUILDERS:
        try:
            sections[key] = (
                builder(company, now=now) if key == 'fatigue'
                else builder(company))
        except Exception:  # pragma: no cover - défensif par section
            logger.warning(
                'adsdeep63: section %r en échec pour la société %s',
                key, getattr(company, 'pk', None), exc_info=True)
            sections[key] = {
                'statut': STATUT_INCONNU,
                'resume': 'Section indisponible (erreur interne).',
                'items': [], 'lien': '',
            }
    try:
        sections['fenetres_donnees'] = _audit_data_windows()
    except Exception:  # pragma: no cover - défensif, purement statique
        sections['fenetres_donnees'] = {
            'statut': STATUT_INCONNU, 'resume': 'Section indisponible.',
            'items': [], 'lien': '',
        }

    now_dt = now if isinstance(now, datetime.date) else datetime.date.today()
    return {'genere_le': now_dt.isoformat(), 'sections': sections}


# =============================================================================
# PUB57 — Tuile Dashboard « score d'audit » auto-chargée + tendance hebdo.
# L'audit (ci-dessus) est délibérément SANS score agrégé opaque (chaque item
# porte un chiffre réel + un lien, jamais un chiffre inventé) — cette tuile ne
# CONTREDIT PAS cette doctrine : le score qu'elle affiche est la part
# TRANSPARENTE de sections RÉELLEMENT 'ok' parmi celles évaluables (jamais
# 'inconnu'), donc toujours traçable jusqu'aux 5 sections ci-dessus.
# =============================================================================
AUDIT_SCORE_CACHE_PREFIX = 'adsengine:audit_score'
# 40 j : assez de marge pour toujours retrouver le point « il y a 7 jours »
# même si un jour de calcul a été manqué (weekend, panne...).
AUDIT_SCORE_CACHE_TTL = 40 * 24 * 3600
AUDIT_SCORE_DELTA_DAYS = 7


def _audit_score_cache_key(company, day):
    return f'{AUDIT_SCORE_CACHE_PREFIX}:{getattr(company, "pk", company)}:{day.isoformat()}'


def account_audit_score(company, *, now=None, audit=None):
    """PUB57 — Score de compte 0-100 (part des sections évaluables 'ok') +
    delta hebdomadaire.

    Le delta compare au score mis en CACHE (Django, ``django.core.cache`` —
    Redis en prod) il y a ~7 jours : AUCUNE migration, rien n'est persisté en
    base. Un flush cache ou un premier calcul dégrade proprement en
    ``delta_hebdo: None`` (« pas encore d'historique »), jamais une exception
    ni un delta halluciné. Réutilise l'audit déjà calculé si fourni
    (``audit=``) pour ne jamais recalculer les 5 sections deux fois."""
    audit = audit if audit is not None else run_account_audit(company, now=now)
    sections = audit.get('sections') or {}
    evaluated = [s for s in sections.values() if s.get('statut') != STATUT_INCONNU]
    ok_count = sum(1 for s in evaluated if s.get('statut') == STATUT_OK)
    attention_count = sum(1 for s in evaluated if s.get('statut') == STATUT_ATTENTION)
    total = len(evaluated)
    score = round((ok_count / total) * 100) if total else None

    today = now if isinstance(now, datetime.date) else datetime.date.today()
    score_7d_ago = None
    try:
        from django.core.cache import cache
        cache.set(_audit_score_cache_key(company, today), score, AUDIT_SCORE_CACHE_TTL)
        score_7d_ago = cache.get(_audit_score_cache_key(
            company, today - datetime.timedelta(days=AUDIT_SCORE_DELTA_DAYS)))
    except Exception:  # pragma: no cover - défensif (cache indisponible)
        logger.warning('adsdeep63: cache score d\'audit indisponible', exc_info=True)

    delta_hebdo = (
        score - score_7d_ago
        if (score is not None and score_7d_ago is not None) else None)

    return {
        'score': score, 'ok_count': ok_count, 'attention_count': attention_count,
        'total_sections': total, 'delta_hebdo': delta_hebdo,
        'genere_le': audit.get('genere_le'),
    }
