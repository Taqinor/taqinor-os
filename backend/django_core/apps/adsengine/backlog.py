"""ADSENG27 — Gestion du backlog créatif (dd-creative-sci §c).

Le backlog (``CreativeBacklogItem``) est le STOCK 3-6 mois de créatifs prêts,
comme données. Ce module calcule :
  * le **runway** — semaines restantes au rythme du plan (un ajout/semaine par
    défaut, aligné sur la ration de rotation ADSENG25) ;
  * l'**alerte « backlog bas »** quand le runway passe sous 3 semaines
    (indicateur avancé — jamais un échec silencieux, leçon Madgicx) ;
  * le **plancher de diversité** — ≥4 accroches DISTINCTES sur 3 mois (un
    backlog de 12 recombinaisons d'une seule accroche = fausse diversité) ;
  * la **file** par campagne cible, ordonnée par date-au-plus-tôt puis tag
    saisonnier.

Logique de lecture pure (aucune écriture Meta). L'``EngineAlert`` réel
(WhatsApp) est rendu/émis ailleurs (gated) ; on renvoie ici un descripteur.
"""
from __future__ import annotations

import datetime

from .models import CreativeBacklogItem

# PUB63 — Pipeline témoignage → brief créatif.
TESTIMONIAL_SATISFACTION_MIN = 4.0  # satisfaction qhse ≥ 4/5 requise
TESTIMONIAL_SCOPES = ('photo', 'temoignage')  # portées de consentement requises

# Un ajout de challenger par semaine (ration ADSENG25) — rythme par défaut.
DEFAULT_WEEKLY_RATE = 1

# Seuil « backlog bas » : sous 3 semaines de runway.
LOW_BACKLOG_WEEKS = 3

# Plancher de diversité : ≥4 accroches distinctes sur la fenêtre.
DIVERSITY_FLOOR_HOOKS = 4
DIVERSITY_WINDOW_DAYS = 90  # 3 mois


def _base_queue(company, *, campaign=None):
    """Items EN FILE de la société (option : pour une campagne cible)."""
    qs = CreativeBacklogItem.objects.filter(
        company=company, status=CreativeBacklogItem.Statut.EN_FILE)
    if campaign is not None:
        qs = qs.filter(target_campaign=campaign)
    return qs


def _earliest_le_q(day):
    """``Q`` : ``earliest_date`` nulle OU ≤ ``day`` (import local de
    ``django.db.models`` pour ne rien importer au chargement du module)."""
    from django.db.models import Q
    return Q(earliest_date__isnull=True) | Q(earliest_date__lte=day)


def _ready_now(qs, today):
    """Items publiables MAINTENANT : date-au-plus-tôt nulle ou atteinte."""
    return qs.filter(_earliest_le_q(today))


def ready_count(company, *, today=None, campaign=None, ready_only=False):
    """Nombre d'items publiables maintenant. ``ready_only`` limite aux
    assets dont la policy est validée (créatifs réellement diffusables)."""
    today = today or datetime.date.today()
    qs = _ready_now(_base_queue(company, campaign=campaign), today)
    if ready_only:
        qs = qs.filter(asset__policy_stamp__passed=True)
    return qs.count()


def compute_runway(company, *, weekly_rate=DEFAULT_WEEKLY_RATE, today=None,
                   campaign=None):
    """Runway en SEMAINES : items publiables maintenant ÷ rythme hebdomadaire.

    ``weekly_rate`` ≤ 0 est traité comme 1 (garde anti-division par zéro).
    """
    rate = weekly_rate if weekly_rate and weekly_rate > 0 else 1
    count = ready_count(company, today=today, campaign=campaign)
    return count / float(rate)


def is_backlog_low(company, *, weekly_rate=DEFAULT_WEEKLY_RATE, today=None,
                   threshold_weeks=LOW_BACKLOG_WEEKS, campaign=None):
    """Vrai si le runway est sous le seuil (3 semaines par défaut)."""
    runway = compute_runway(
        company, weekly_rate=weekly_rate, today=today, campaign=campaign)
    return runway < threshold_weeks


def hook_diversity(company, *, window_days=DIVERSITY_WINDOW_DAYS, today=None):
    """Nombre d'accroches DISTINCTES (``asset__hook_id`` non vide) dans la file
    sur la fenêtre glissante (date-au-plus-tôt nulle ou dans la fenêtre)."""
    today = today or datetime.date.today()
    horizon = today + datetime.timedelta(days=window_days)
    qs = _base_queue(company).filter(_earliest_le_q(horizon))
    hooks = (qs.exclude(asset__hook_id='')
               .values_list('asset__hook_id', flat=True)
               .distinct())
    return len({h for h in hooks if h})


def meets_diversity_floor(company, *, floor=DIVERSITY_FLOOR_HOOKS,
                          window_days=DIVERSITY_WINDOW_DAYS, today=None):
    """Vrai si le plancher de diversité (≥4 accroches/3 mois) est atteint."""
    return hook_diversity(
        company, window_days=window_days, today=today) >= floor


def queue_for_campaign(company, campaign, *, today=None):
    """File ordonnée (date-au-plus-tôt puis tag saisonnier) pour une campagne
    cible — TOUS les items EN FILE programmés (y compris datés dans le futur),
    la file complète à visualiser/planifier. ``today`` est accepté pour une
    signature cohérente mais n'exclut rien (le runway, lui, filtre le prêt-
    maintenant)."""
    qs = _base_queue(company, campaign=campaign)
    return list(qs.order_by('earliest_date', 'seasonal_tag', 'id'))


def backlog_alert(company, *, weekly_rate=DEFAULT_WEEKLY_RATE, today=None,
                  campaign=None):
    """Descripteur d'alerte backlog (rendu WhatsApp ailleurs, gated).

    Renvoie ``should_alert`` vrai si le backlog est bas OU si la diversité est
    sous le plancher, avec un message FR et les chiffres. Ne crée AUCUNE ligne
    ``EngineAlert`` (son type ne couvre pas le backlog) — c'est un descripteur.
    """
    today = today or datetime.date.today()
    runway = compute_runway(
        company, weekly_rate=weekly_rate, today=today, campaign=campaign)
    low = runway < LOW_BACKLOG_WEEKS
    diversity = hook_diversity(company, today=today)
    diversity_ok = diversity >= DIVERSITY_FLOOR_HOOKS
    parts = []
    if low:
        parts.append(
            f"Backlog bas : {runway:.1f} semaine(s) de runway restantes "
            f"(seuil {LOW_BACKLOG_WEEKS}).")
    if not diversity_ok:
        parts.append(
            f"Diversité insuffisante : {diversity} accroche(s) distincte(s) "
            f"sur 3 mois (plancher {DIVERSITY_FLOOR_HOOKS}).")
    return {
        'should_alert': bool(low or not diversity_ok),
        'severity': 'warning',
        'runway_weeks': runway,
        'backlog_low': low,
        'diversity': diversity,
        'diversity_ok': diversity_ok,
        'message': ' '.join(parts),
    }


# ── PUB63 — Pipeline témoignage → brief créatif (client réel) ────────────────
#
# Un deal SIGNÉ + une satisfaction qhse ≥ 4/5 + des photos de chantier forment
# la matière première d'un témoignage — aujourd'hui AUCUNE source créative ne
# part du client réel. Ce pipeline construit un brief STRUCTURÉ à partir des
# faits VÉRIFIÉS du projet (kWc / économie / ville / avant-après) et le met en
# file ``CreativeBacklogItem`` pour approbation. Le consentement PUB75 est
# BLOQUANT : sans consentement actif couvrant image + témoignage, rien n'est mis
# en file (jamais d'usage d'image/nom sans accord signé). Les lectures cross-app
# passent par les sélecteurs (ventes / qhse / installations), jamais un import
# de leurs modèles.


def _active_consent_for_client(company, client_id, scopes, *, now=None):
    """Consentement ACTIF d'un client couvrant TOUTES les ``scopes`` (ou None)."""
    from .models import ConsentRecord

    if not client_id:
        return None
    candidates = ConsentRecord.objects.filter(
        company=company, client_id=client_id, revoked_at__isnull=True)
    for consent in candidates:
        if consent.is_active(now=now) and all(
                consent.covers(s) for s in scopes):
            return consent
    return None


def evaluate_testimonial_eligibility(company, *, devis_id, chantier_id, now=None):
    """PUB63 — Évalue l'éligibilité d'un projet à un brief témoignage.

    Renvoie ``{eligible, blocked_reason, facts, satisfaction, has_photos}``.
    ``blocked_reason`` (FR, ou ``None``) indique le premier critère non rempli :
    deal non signé, satisfaction insuffisante, ou aucune photo de chantier. Le
    consentement (PUB75) est vérifié séparément au moment de la mise en file.
    Toutes les lectures cross-app passent par des sélecteurs (lecture seule)."""
    from apps.installations import selectors as inst_selectors
    from apps.qhse import selectors as qhse_selectors
    from apps.ventes import selectors as ventes_selectors

    facts = ventes_selectors.faits_temoignage_devis(company, devis_id)
    result = {
        'eligible': False, 'blocked_reason': None,
        'facts': facts, 'satisfaction': None, 'has_photos': False,
    }
    if facts is None or not facts.get('signed'):
        result['blocked_reason'] = 'deal_non_signe'
        return result

    satisfaction = qhse_selectors.satisfaction_moyenne(
        company, chantier_id=chantier_id)
    result['satisfaction'] = satisfaction
    if satisfaction is None or satisfaction < TESTIMONIAL_SATISFACTION_MIN:
        result['blocked_reason'] = 'satisfaction_insuffisante'
        return result

    has_photos = inst_selectors.chantier_a_photos(company, chantier_id)
    result['has_photos'] = has_photos
    if not has_photos:
        result['blocked_reason'] = 'pas_de_photos'
        return result

    result['eligible'] = True
    return result


def _build_testimonial_brief(company, chantier_id, facts):
    """Construit le brief STRUCTURÉ (faits vérifiés seulement) + le texte créatif
    déterministe. ``ville`` provient de l'étude du devis ou du chantier."""
    from apps.installations import selectors as inst_selectors

    ville = facts.get('ville') or inst_selectors.chantier_ville(
        company, chantier_id)
    avant = inst_selectors.chantier_photos(
        company, chantier_id, phase='avant').count()
    apres = inst_selectors.chantier_photos(
        company, chantier_id, phase='apres').count()

    kwc = facts.get('puissance_kwc')
    economie = facts.get('economie_annuelle')
    # Texte 100 % ancré sur les faits — aucun chiffre inventé (règle
    # checked-facts-only : un fait absent est OMIS, jamais remplacé par 0).
    hook_bits = []
    if ville:
        hook_bits.append(f'Installation solaire à {ville}')
    else:
        hook_bits.append('Installation solaire Taqinor')
    if kwc:
        hook_bits.append(f'{kwc:g} kWc')
    hook_text = ' — '.join(hook_bits)

    body_bits = []
    if economie:
        body_bits.append(f"Économie annuelle estimée : {economie:g} MAD")
    if facts.get('production_kwh'):
        body_bits.append(
            f"Production : {facts['production_kwh']:g} kWh/an")
    primary_text = '. '.join(body_bits)

    return {
        'ville': ville,
        'puissance_kwc': kwc,
        'economie_annuelle': economie,
        'production_kwh': facts.get('production_kwh'),
        'client_nom': facts.get('client_nom'),
        'reference_devis': facts.get('reference'),
        'photos_avant': avant,
        'photos_apres': apres,
        'avant_apres_disponible': bool(avant and apres),
        'hook_text': hook_text,
        'primary_text': primary_text,
        'faits_verifies': True,
    }


def queue_testimonial_brief(company, *, devis_id, chantier_id, client_id=None,
                            now=None, target_campaign=None, asset_type=None):
    """PUB63 — Met en file un brief témoignage pour approbation, si éligible ET
    consenti.

    Vérifie l'éligibilité (deal signé + satisfaction ≥ 4/5 + photos) puis le
    consentement PUB75 (actif, couvrant image + témoignage). Si tout est réuni :
    crée un ``CreativeAsset`` PENDING (``source_lane='temoignage'``,
    ``depicts_real_client=True``, lié au consentement) et un
    ``CreativeBacklogItem`` EN FILE. Sinon, ne crée RIEN et renvoie
    ``{queued: False, blocked_reason}`` — la garde consentement bloque tout usage
    d'image/nom sans accord signé. Renvoie le brief + les objets créés quand mis
    en file."""
    from .models import CreativeAsset

    elig = evaluate_testimonial_eligibility(
        company, devis_id=devis_id, chantier_id=chantier_id, now=now)
    if not elig['eligible']:
        return {'queued': False, 'blocked_reason': elig['blocked_reason'],
                'eligibility': elig}

    facts = elig['facts']
    consent_client = client_id or facts.get('client_id')
    consent = _active_consent_for_client(
        company, consent_client, TESTIMONIAL_SCOPES, now=now)
    if consent is None:
        # PUB75 — BLOQUÉ : aucun usage d'image/nom sans consentement signé.
        return {'queued': False, 'blocked_reason': 'consentement_manquant',
                'eligibility': elig}

    brief = _build_testimonial_brief(company, chantier_id, facts)
    asset = CreativeAsset.objects.create(
        company=company,
        asset_type=asset_type or CreativeAsset.AssetType.STATIC,
        source_lane='temoignage',
        depicts_real_client=True,
        consent=consent,
        consent_scopes_required=list(TESTIMONIAL_SCOPES),
        hook_text=brief['hook_text'],
        primary_text=brief['primary_text'],
        policy_stamp={},  # PENDING — check-list humaine (ENG16) requise
    )
    item = CreativeBacklogItem.objects.create(
        company=company, asset=asset,
        source=CreativeBacklogItem.Source.MANUEL,
        target_campaign=target_campaign,
        status=CreativeBacklogItem.Statut.EN_FILE)
    return {
        'queued': True, 'blocked_reason': None,
        'brief': brief, 'asset': asset, 'backlog_item': item,
        'consent_id': consent.id,
    }
