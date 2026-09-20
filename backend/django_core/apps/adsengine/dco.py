"""ADSENG29 — Arbitrage DCO (Dynamic Creative Optimization) — creative-sci §e.

STATUT (PUB118, 2026-09-20) — CÂBLÉ. L'appelant que ce module attendait existe :
``services.propose_dco_recombination`` (bouton « Recombiner (DCO) » du cockpit)
consulte l'arbitre au bootstrap cold-start, moissonne le pool des créatifs
mirorés GAGNANTS (``harvest_winning_pool``) et compose une spec plafonnée
(``build_asset_feed_spec``) validée par ``validate_dco_asset_spec`` +
``validate_mutual_exclusion``. Historique : ce module est resté sans appelant du
19/07 au 20/09 (PUB25) — prêt + testé, jamais mort silencieux.

Le DCO natif de Meta est réservé au **bootstrap de démarrage à froid** (aucune
donnée) : Meta assemble automatiquement image/vidéo/texte pour amorcer un
signal, mais expose UN SEUL ad par ad set et une attribution par asset limitée.
Dès qu'un signal existe, on repasse à la **rotation multi-ads discrète**
(ADSENG25) où le bandit a une attribution par bras.

INVARIANT STRUCTUREL (dd-creative-sci §e — vérifié) : **exclusion mutuelle
DCO ↔ rotation multi-ads par ad set**. Un ad set DCO ne porte qu'UN ad ; un ad
set en rotation en porte plusieurs — les deux ne coexistent jamais.

CHOIX D'IMPLÉMENTATION (voir rapport de lane) : cette exclusion N'EST PAS une
contrainte de MODÈLE — l'``is_dynamic_creative`` vit côté Meta (pas sur
``AdSetMirror``, qui n'a pas de champ « mode ») et l'inscrire exigerait une
MIGRATION, interdite dans cette lane. Elle est donc une **validation au niveau
SERVICE** : un invariant validé et testé ici (``validate_mutual_exclusion``),
appliqué à chaque choix de mode — jamais une garde silencieuse. Les plafonds
d'assets DCO natifs sont eux aussi validés (``validate_dco_asset_spec``).
"""
from __future__ import annotations

import dataclasses
import logging

logger = logging.getLogger(__name__)

# ── Plafonds d'assets DCO natifs (dd-creative-sci §e — vérifiés) ─────────────
DCO_MAX_IMAGES = 10
DCO_MAX_VIDEOS = 10
DCO_MAX_BODIES = 5          # textes principaux
DCO_MAX_TITLES = 5          # titres
DCO_MAX_DESCRIPTIONS = 5    # descriptions
DCO_MAX_CTAS = 5            # types d'appel à l'action
DCO_MAX_LINKS = 5           # liens
DCO_MAX_TOTAL_ASSETS = 30   # total tous champs confondus
DCO_ADS_PER_ADSET = 1       # UN seul ad par ad set en DCO

# Plafond par champ de la spec DCO (clé de spec → plafond).
_FIELD_CAPS = {
    'images': DCO_MAX_IMAGES,
    'videos': DCO_MAX_VIDEOS,
    'bodies': DCO_MAX_BODIES,
    'titles': DCO_MAX_TITLES,
    'descriptions': DCO_MAX_DESCRIPTIONS,
    'ctas': DCO_MAX_CTAS,
    'links': DCO_MAX_LINKS,
}

# ── Modes créatifs mutuellement exclusifs par ad set ─────────────────────────
MODE_DCO_BOOTSTRAP = 'dco_bootstrap'
MODE_MULTI_AD_ROTATION = 'multi_ad_rotation'
MODES = (MODE_DCO_BOOTSTRAP, MODE_MULTI_AD_ROTATION)


class DcoModeConflict(ValueError):
    """Violation de l'exclusion mutuelle DCO ↔ rotation multi-ads."""


class DcoCapExceeded(ValueError):
    """Un plafond d'assets DCO natif est dépassé."""


@dataclasses.dataclass(frozen=True)
class ModeDecision:
    """Choix EXPLICITE de mode créatif pour UN ad set."""

    adset_ref: object
    mode: str
    is_cold_start: bool
    reason_fr: str


def adset_has_signal(adset):
    """Vrai si l'ad set a déjà un signal (dépense ou résultat > 0).

    Démarrage à FROID = aucun signal → éligible au bootstrap DCO. Lit les
    ``InsightSnapshot`` rattachés (FK générique). Dégrade à ``False`` (froid)
    si l'ad set est ``None`` ou n'a aucun instantané.
    """
    if adset is None:
        return False
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Q
    from .models import InsightSnapshot

    ct = ContentType.objects.get_for_model(adset.__class__)
    return InsightSnapshot.objects.filter(
        company=adset.company, content_type=ct, object_id=adset.pk,
    ).filter(Q(spend__gt=0) | Q(results__gt=0)).exists()


def validate_dco_asset_spec(spec):
    """Valide les plafonds d'assets d'une spec DCO native.

    ``spec`` : dict de listes par champ (``images``/``videos``/``bodies``/…).
    Lève ``DcoCapExceeded`` (raisons FR) si un champ dépasse son plafond ou si
    le total dépasse 30. Renvoie le total d'assets si valide.
    """
    spec = spec or {}
    violations = []
    total = 0
    for field, cap in _FIELD_CAPS.items():
        count = len(spec.get(field, []) or [])
        total += count
        if count > cap:
            violations.append(
                f"{field} : {count} > plafond {cap}.")
    if total > DCO_MAX_TOTAL_ASSETS:
        violations.append(
            f"total : {total} > plafond {DCO_MAX_TOTAL_ASSETS} assets.")
    if violations:
        raise DcoCapExceeded(
            "Plafonds DCO dépassés — " + " ".join(violations))
    return total


def validate_mutual_exclusion(*, mode, existing_ad_count=0,
                              is_dynamic_creative=None):
    """Invariant SERVICE : exclusion mutuelle DCO ↔ rotation multi-ads.

    * ``MODE_DCO_BOOTSTRAP`` sur un ad set qui porte déjà >1 ad → conflit (le
      DCO n'expose qu'UN ad par ad set).
    * ``MODE_MULTI_AD_ROTATION`` sur un ad set déjà marqué DCO
      (``is_dynamic_creative=True``) → conflit.

    Lève ``DcoModeConflict`` (raison FR) en cas de violation ; renvoie ``mode``
    sinon.
    """
    if mode not in MODES:
        raise DcoModeConflict(
            f"Mode inconnu « {mode} » (attendu : {' / '.join(MODES)}).")
    if mode == MODE_DCO_BOOTSTRAP and int(existing_ad_count or 0) > 1:
        raise DcoModeConflict(
            "DCO impossible : l'ad set porte déjà plusieurs ads (le DCO "
            "n'expose qu'un seul ad par ad set) — exclusion mutuelle avec la "
            "rotation multi-ads.")
    if mode == MODE_MULTI_AD_ROTATION and is_dynamic_creative:
        raise DcoModeConflict(
            "Rotation multi-ads impossible : l'ad set est en DCO "
            "(is_dynamic_creative) — exclusion mutuelle.")
    return mode


# ═════════════════════════════════════════════════════════════════════════════
# PUB118 — Recombinaison DCO ZÉRO-CLÉ depuis les MIROIRS
# ═════════════════════════════════════════════════════════════════════════════
# Le premier « mes pubs créent des pubs » sans aucune clé externe : la synchro
# miroite DÉJÀ les visuels (``image_hash``/``video_id``) et les textes
# (``body``/``title``/``description``/``cta_type``/``link_url``) de chaque
# créatif diffusé (``AdCreativeMirror``, ADSDEEP11). Meta, lui, sait recombiner
# une spec d'assets et AUTO-TESTER les combinaisons à l'impression. Il suffit
# donc de MOISSONNER le pool des créatifs GAGNANTS et de composer une spec
# plafonnée — aucun LLM, aucune clé, aucune dépense.
#
# Le pool est CONDITIONNÉ À LA PERFORMANCE (un remix superficiel ne gagne rien) :
# seules les ads qui ont réellement produit des résultats sur la fenêtre entrent,
# classées par résultats décroissants. Une société sans aucun gagnant ne produit
# AUCUNE proposition (``DcoPoolEmpty``) — jamais une spec bâtie sur du vide.
HARVEST_WINDOW_DAYS = 30
HARVEST_MIN_RESULTS = 1

# Champs de pool (clés internes de ``_FIELD_CAPS``) lus sur le miroir de créatif.
_MIRROR_FIELD_FOR_POOL = {
    'images': 'image_hash',
    'videos': 'video_id',
    'titles': 'title',
    'bodies': 'body',
    'descriptions': 'description',
    'ctas': 'cta_type',
    'links': 'link_url',
}

# Formes GRAPH d'``asset_feed_spec`` (Marketing API). Les trois premières sont
# celles que ce dépôt OBSERVE déjà : ``sync._extract_creative_fields`` miroite
# l'``asset_feed_spec`` tel quel et la fixture ADSDEEP11 porte
# ``{'bodies': [{'text': 'A'}]}`` ; PUB117 écrit ``images: [{'hash': …}]`` /
# ``titles: [{'text': …}]`` / ``ad_formats: ['SINGLE_IMAGE']``. On n'invente
# aucune autre forme : chaque entrée ci-dessous suit exactement ce gabarit.
AD_FORMAT_IMAGE = 'SINGLE_IMAGE'
AD_FORMAT_VIDEO = 'SINGLE_VIDEO'


class DcoPoolEmpty(ValueError):
    """PUB118 — Le pool de recombinaison est inexploitable (raison FR)."""


def harvest_winning_pool(company, *, now=None, window_days=HARVEST_WINDOW_DAYS,
                         min_results=HARVEST_MIN_RESULTS, max_ads=None):
    """Moissonne le pool d'assets des créatifs mirorés GAGNANTS d'une société.

    « Gagnant » = l'ad a produit au moins ``min_results`` résultats RÉELS sur la
    fenêtre (``InsightSnapshot``) ; les ads sans résultat n'entrent pas, même
    avec des impressions (le pool est conditionné à la perf — un remix de
    perdants ne gagne rien). Les ads sont parcourues par résultats décroissants,
    puis impressions, pour que les plafonds tronquent les MOINS bons.

    Renvoie ``{images, videos, titles, bodies, descriptions, ctas, links,
    sources}`` — des listes de chaînes DÉDUPLIQUÉES dans l'ordre de mérite
    (``sources`` = les ``creative_meta_id`` d'où viennent les assets, pour la
    traçabilité de la proposition). Tout est lu sur les MIROIRS : aucun asset
    n'est fabriqué.
    """
    import datetime

    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Sum
    from django.utils import timezone

    from .models import AdCreativeMirror, AdMirror, InsightSnapshot

    now = now or timezone.now()
    today = now.date() if hasattr(now, 'date') else now
    start = today - datetime.timedelta(days=max(1, window_days) - 1)
    ct = ContentType.objects.get_for_model(AdMirror)

    ranked = (InsightSnapshot.objects
              .filter(company=company, content_type=ct,
                      date__gte=start, date__lte=today)
              .values('object_id')
              .annotate(results=Sum('results'), impressions=Sum('impressions'))
              .filter(results__gte=min_results)
              .order_by('-results', '-impressions', 'object_id'))
    ad_ids = [row['object_id'] for row in ranked]
    if max_ads:
        ad_ids = ad_ids[:max_ads]

    mirrors = {
        m.ad_id: m
        for m in AdCreativeMirror.objects.filter(
            company=company, ad_id__in=ad_ids)}

    pool = {key: [] for key in _MIRROR_FIELD_FOR_POOL}
    pool['sources'] = []
    for ad_id in ad_ids:
        mirror = mirrors.get(ad_id)
        if mirror is None:
            continue
        used = False
        for pool_key, attr in _MIRROR_FIELD_FOR_POOL.items():
            value = (getattr(mirror, attr, '') or '').strip()
            if value and value not in pool[pool_key]:
                pool[pool_key].append(value)
                used = True
        if used and mirror.creative_meta_id:
            pool['sources'].append(mirror.creative_meta_id)
    return pool


def cap_pool(pool):
    """Applique les plafonds DCO à un pool moissonné (copie ; jamais en place).

    Deux passes : (1) plafond PAR CHAMP (``_FIELD_CAPS`` — 10 visuels, 5 titres,
    5 textes…) ; (2) plafond TOTAL (30 assets) en retirant la queue du champ le
    PLUS fourni, jusqu'à repasser sous la barre (on sacrifie toujours l'asset le
    moins méritant du champ le plus redondant). ``sources`` n'est pas un champ
    d'assets et n'entre dans aucun plafond."""
    capped = {key: list(values or [])[:_FIELD_CAPS[key]]
              for key, values in ((k, pool.get(k)) for k in _FIELD_CAPS)}
    total = sum(len(v) for v in capped.values())
    while total > DCO_MAX_TOTAL_ASSETS:
        biggest = max(capped, key=lambda k: (len(capped[k]), k))
        if not capped[biggest]:
            break  # défensif : plus rien à retirer
        capped[biggest].pop()
        total -= 1
    capped['sources'] = list(pool.get('sources') or [])
    return capped


def build_asset_feed_spec(pool):
    """Compose l'``asset_feed_spec`` GRAPH d'une recombinaison DCO.

    Plafonne (``cap_pool``), VALIDE (``validate_dco_asset_spec`` — la source de
    vérité des plafonds), puis traduit en formes Graph. Un seul FAMILLE de média
    par spec (images OU vidéos, images d'abord) : ``ad_formats`` est déclaré par
    spec et ce dépôt n'a jamais observé de spec mixte — on n'en invente pas une.

    Lève ``DcoPoolEmpty`` (FR) si le pool n'a aucun visuel ou aucun texte
    principal : une spec sans média ni corps ne diffuse rien.
    """
    # Le choix de FAMILLE se fait AVANT les plafonds : sinon le plafond total
    # aurait déjà rogné des visuels au profit de médias qu'on s'apprête à jeter.
    pool = dict(pool or {})
    if pool.get('images'):
        pool['videos'] = []
    elif pool.get('videos'):
        pool['images'] = []
    capped = cap_pool(pool)
    if capped['images']:
        media_field, ad_format = 'images', AD_FORMAT_IMAGE
    elif capped['videos']:
        media_field, ad_format = 'videos', AD_FORMAT_VIDEO
    else:
        raise DcoPoolEmpty(
            "Recombinaison DCO impossible : aucun visuel (image_hash / "
            "video_id) dans les créatifs mirorés gagnants de la société.")
    if not capped['bodies']:
        raise DcoPoolEmpty(
            "Recombinaison DCO impossible : aucun texte principal dans les "
            "créatifs mirorés gagnants (une spec sans corps ne diffuse rien).")

    # Le validateur DCO tranche les plafonds sur la spec EFFECTIVE (après le
    # choix de famille) — jamais sur le pool d'avant.
    validate_dco_asset_spec(
        {key: capped[key] for key in _FIELD_CAPS})

    spec = {'ad_formats': [ad_format]}
    if media_field == 'images':
        spec['images'] = [{'hash': h} for h in capped['images']]
    else:
        spec['videos'] = [{'video_id': v} for v in capped['videos']]
    spec['bodies'] = [{'text': t} for t in capped['bodies']]
    if capped['titles']:
        spec['titles'] = [{'text': t} for t in capped['titles']]
    if capped['descriptions']:
        spec['descriptions'] = [{'text': t} for t in capped['descriptions']]
    if capped['ctas']:
        spec['call_to_action_types'] = list(capped['ctas'])
    if capped['links']:
        spec['link_urls'] = [{'website_url': u} for u in capped['links']]
    return spec


def plan_adset_creative_mode(adset, *, requested_mode=None,
                             existing_ad_count=0, is_dynamic_creative=None,
                             cold_start=None):
    """Choix EXPLICITE et validé du mode créatif d'un ad set.

    Détermine le démarrage à froid (``cold_start`` explicite, sinon
    ``adset_has_signal``). Par défaut : DCO au bootstrap à froid, rotation
    multi-ads dès qu'un signal existe. Un ``requested_mode`` est honoré mais
    VALIDÉ : le DCO est réservé au démarrage à froid (bootstrap ONLY) et
    l'exclusion mutuelle est appliquée. Renvoie une ``ModeDecision``.
    """
    is_cold = cold_start if cold_start is not None else not adset_has_signal(
        adset)
    default_mode = (MODE_DCO_BOOTSTRAP if is_cold
                    else MODE_MULTI_AD_ROTATION)
    mode = requested_mode or default_mode

    if mode == MODE_DCO_BOOTSTRAP and not is_cold:
        # DCO = bootstrap SEULEMENT : refusé s'il y a déjà un signal.
        raise DcoModeConflict(
            "DCO réservé au démarrage à froid (bootstrap uniquement) : cet ad "
            "set a déjà un signal — passez en rotation multi-ads.")
    validate_mutual_exclusion(
        mode=mode, existing_ad_count=existing_ad_count,
        is_dynamic_creative=is_dynamic_creative)

    if mode == MODE_DCO_BOOTSTRAP:
        reason = ("Démarrage à froid (aucun signal) — bootstrap DCO pour "
                  "amorcer, un seul ad par ad set.")
    else:
        reason = ("Signal présent — rotation multi-ads discrète (attribution "
                  "par bras pour le bandit).")
    return ModeDecision(
        adset_ref=getattr(adset, 'pk', None) or getattr(
            adset, 'id', None) or adset,
        mode=mode, is_cold_start=is_cold, reason_fr=reason)
