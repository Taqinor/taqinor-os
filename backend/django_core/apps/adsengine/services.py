"""ENG7 — Orchestration de la boucle propose→approuve→applique.

Le seul chemin qui atteint ``meta_client`` est ``apply_action`` SUR UNE ACTION
APPROUVÉE. Une action ``proposee`` / ``rejetee`` / ``appliquee`` / ``echouee``
n'atteint JAMAIS le client (garde de sécurité en tête de ``apply_action``, testée).
Il n'existe aucun chemin d'auto-application : ``apply_action`` doit être appelé
explicitement, jamais déclenché par une proposition.

Pattern : ``contrats.EtapeApprobation`` (statut local persistant + acteur posé
côté serveur), pas le registre stateless ``apps/agent``.
"""
from __future__ import annotations

import logging

from django.utils import timezone

from . import guardrails
from .models import EngineAction
from .pacing import (
    KIND_ENABLE_CBO, KIND_INCREASE_PACE, KIND_PAUSE_FOR_MONTH,
    KIND_REBALANCE_ADSET_BUDGET,
)

logger = logging.getLogger(__name__)

# ENGFIX1/G2 — Contrat d'unité de budget. Les budgets de l'API Marketing Meta
# sont en UNITÉS MINEURES (centimes) de la devise du compte ; le plafond
# ``GuardrailConfig.daily_budget_ceiling_mad`` est en MAD (unités majeures).
# CONVENTION FIGÉE : ``payload['daily_budget']`` / ``payload['current_budget']``
# sont en CENTIMES ; on les convertit en MAD (÷100) AVANT toute comparaison au
# plafond (voir ``_centimes_to_mad`` / ``_guard_before_dispatch``).
CENTIMES_PER_MAD = 100

# ADSDEEP40 — Borne LEARNING-SAFE d'une montée de budget de règle (surf-scaling).
# Meta réinitialise la phase d'apprentissage au-delà de ~20 % de variation
# (``models.LEARNING_RESET_BUDGET_PCT``) : une montée de règle est CLAMPÉE à ce
# plafond AVANT même l'applicateur budget (qui la resserre encore à ``MAX_STEP_PCT``
# = 15 %/jour). Un pas > 20 % est donc structurellement impossible par ce chemin.
LEARNING_SAFE_MAX_PCT = 20


# ── ENG8 — Toggles de capacités (par société) ────────────────────────────────
# Chaque ``kind`` auto-applicable est associé au champ booléen de capacité qui,
# une fois activé sur la ``GuardrailConfig`` de la société, autorise l'exécution
# SANS approbation humaine (mais avec une trace ``EngineAction auto=True`` +
# journalisation). Tout kind ABSENT de ce mapping exige TOUJOURS l'approbation.
CAPABILITY_FOR_KIND = {
    EngineAction.Kind.ROTATE_CREATIVE: 'auto_rotate_creative',
    EngineAction.Kind.REBALANCE_BUDGET: 'auto_rebalance_within_band',
}


def capability_enabled(config, kind):
    """ENG8 — Vrai si le ``kind`` est couvert par une capacité ACTIVÉE.

    ``config`` ``None`` (aucune GuardrailConfig) ou kind hors mapping →
    ``False`` : par défaut, tout exige l'approbation (aucune auto-application).
    """
    if config is None:
        return False
    field = CAPABILITY_FOR_KIND.get(kind)
    if not field:
        return False
    return bool(getattr(config, field, False))


class ActionNotApproved(Exception):
    """Levée si on tente d'appliquer une action non approuvée (jamais de client)."""


class CreativePolicyNotPassed(ValueError):
    """ENG15 — Levée si une création d'ad référence un asset non validé policy."""


class ActionPayloadInvalid(ValueError):
    """PUB22 — Levée si le payload d'une action proposée par POST BRUT est
    invalide (champ requis manquant / valeur incohérente). Sous-classe de
    ``ValueError`` — traduite en 400 par la vue, jamais une 500."""


class ActionNotInvertible(ValueError):
    """PUB45 — Levée si une action appliquée n'a pas d'inverse AUTOMATIQUE (kind
    de création, mise en pause non ré-activable — règle #3, ou valeur précédente
    non mémorisée). Sous-classe de ``ValueError`` — la vue rend une explication."""


# Kinds qui créent une ad et peuvent donc référencer un ``CreativeAsset``.
_AD_CREATING_KINDS = frozenset({
    EngineAction.Kind.CREATE_AD, EngineAction.Kind.ROTATE_CREATIVE,
})

# ADSENG22 — kinds trésorerie qui MODIFIENT un budget ad set : passent par les
# garde-fous budget (plafond quotidien + variation hebdo + pas ≤15% + ligne de
# base G4 + validation propriété miroir). ``pause_for_month`` (PAUSED-only) et
# ``enable_cbo`` (propose-only) n'en font PAS partie — cf. ``_dispatch``.
_TREASURY_BUDGET_KINDS = frozenset({
    KIND_INCREASE_PACE, KIND_REBALANCE_ADSET_BUDGET,
})


def assert_creative_ok_for_ad(company, kind, payload):
    """ENG15 — Garde-fou policy créative : un asset dont ``policy_stamp.passed``
    n'est pas vrai NE PEUT PAS être référencé par une action de création d'ad.

    No-op si le kind ne crée pas d'ad ou si aucun ``creative_asset_id`` n'est
    référencé. Lève ``CreativePolicyNotPassed`` (sous-classe de ``ValueError``)
    sinon — l'action n'est jamais créée."""
    if kind not in _AD_CREATING_KINDS:
        return
    asset_id = (payload or {}).get('creative_asset_id')
    if not asset_id:
        return
    from .models import CreativeAsset
    asset = CreativeAsset.objects.filter(company=company, id=asset_id).first()
    if asset is None:
        raise CreativePolicyNotPassed(
            "Créatif introuvable pour cette société.")
    if not asset.is_policy_passed:
        raise CreativePolicyNotPassed(
            "Créatif non validé (policy_stamp.passed absent) : il ne peut pas "
            "être référencé par une création d'ad.")


# ── PUB22 — Validation de payload PAR KIND pour les kinds atteignables par POST
# BRUT sans producteur curé (``create_ad`` / ``set_spend_cap`` / ``rename``). Un
# producteur (``propose_duplicate``, ``propose_pause_for_month``…) construit déjà
# un payload correct ; ces trois-là peuvent être proposés depuis l'UI sans passer
# par un service dédié — on valide donc leur payload AVANT de créer l'action, pour
# ne jamais matérialiser une action inapplicable (name/adset_id/campaign_id vides,
# plafond ≤ 0…). AUCUN autre kind n'est soumis à ce contrôle (leur producteur
# curé garantit déjà la forme). ────────────────────────────────────────────────
def _require_nonempty(payload, key, label):
    value = payload.get(key)
    if value is None or not str(value).strip():
        raise ActionPayloadInvalid(f"Champ requis manquant : {label}.")


def _require_positive_number(payload, key, label):
    value = payload.get(key)
    if value is None:
        raise ActionPayloadInvalid(f"Champ requis manquant : {label}.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ActionPayloadInvalid(f"{label} doit être un nombre.")
    if number <= 0:
        raise ActionPayloadInvalid(f"{label} doit être strictement positif.")


def validate_manual_payload(kind, payload):
    """Valide le payload d'un kind proposable par POST brut. No-op pour tout kind
    hors du trio contrôlé. Lève ``ActionPayloadInvalid`` (→ 400) sinon."""
    payload = payload or {}
    if kind == EngineAction.Kind.CREATE_AD:
        _require_nonempty(payload, 'name', "le nom de l'ad")
        _require_nonempty(payload, 'adset_id', "l'id de l'ad set")
    elif kind == EngineAction.Kind.SET_SPEND_CAP:
        _require_nonempty(payload, 'campaign_id', "l'id de la campagne")
        _require_positive_number(payload, 'spend_cap', "le plafond de dépense")
    elif kind == EngineAction.Kind.RENAME:
        _require_nonempty(payload, 'object_id', "l'id de l'objet")
        _require_nonempty(payload, 'name', 'le nouveau nom')


# ── ADSDEEP31 — Avertissements montrés à l'APPROBATEUR (surface d'édition) ────
# EDIT_COPY (changer le texte / le créatif d'une ad existante) est un
# *significant edit* Meta : (a) il RÉINITIALISE la phase d'apprentissage de
# l'ad set (Meta ré-explore — coûts instables quelques jours) ; (b) changer le
# texte crée un NOUVEAU post → la preuve sociale accumulée (J'aime, commentaires,
# partages) est PERDUE. Les DEUX avertissements sont poussés dans
# ``payload['warnings']`` à la proposition et donc rendus à l'approbateur.
WARN_LEARNING_RESET = (
    "Édition significative : cette action réinitialise la phase d'apprentissage "
    "de l'ad set (Meta ré-explore — coûts instables pendant quelques jours).")
WARN_SOCIAL_PROOF_LOSS = (
    "Changer le texte crée un NOUVEAU post : la preuve sociale déjà accumulée "
    "(J'aime, commentaires, partages) est perdue.")


def edit_warnings(kind, payload=None):
    """ADSDEEP31 — Avertissements à montrer à l'approbateur pour une action de la
    surface d'édition. ``EDIT_COPY`` = édition significative ⇒ reset
    d'apprentissage ET, le texte changeant, création d'un nouveau post ⇒ perte de
    preuve sociale : les DEUX avertissements. ``RENAME`` / ``SET_SPEND_CAP`` ne
    réinitialisent rien et ne recréent aucun post → aucun avertissement."""
    if kind == EngineAction.Kind.EDIT_COPY:
        return [WARN_LEARNING_RESET, WARN_SOCIAL_PROOF_LOSS]
    return []


def _merge_warnings(payload, warns):
    """Fusionne ``warns`` dans ``payload['warnings']`` sans doublon (préserve
    tout avertissement déjà fourni par l'appelant, ex. le reset-seuil ADSDEEP32)."""
    if not warns:
        return payload
    existing = list(payload.get('warnings') or [])
    for w in warns:
        if w not in existing:
            existing.append(w)
    payload['warnings'] = existing
    return payload


def propose_action(company, *, kind, reason_fr, payload=None, auto=False):
    """Crée une action PROPOSÉE. ``reason_fr`` (une phrase FR) est obligatoire.

    ADSDEEP31 — pour un kind de la surface d'édition, les avertissements destinés
    à l'approbateur (reset d'apprentissage / perte de preuve sociale) sont
    injectés dans ``payload['warnings']`` (fusionnés, jamais un doublon)."""
    if not (reason_fr and str(reason_fr).strip()):
        raise ValueError(
            "Une raison en une phrase (français) est obligatoire pour proposer "
            "une action.")
    assert_creative_ok_for_ad(company, kind, payload)
    validate_manual_payload(kind, payload)
    payload = dict(payload or {})
    _merge_warnings(payload, edit_warnings(kind, payload))
    return EngineAction.objects.create(
        company=company, kind=kind, payload=payload,
        reason_fr=str(reason_fr).strip(),
        status=EngineAction.Statut.PROPOSEE, auto=auto)


# ── ADSDEEP34 — A/B test NATIF Meta (ad_studies SPLIT_TEST_V2) ───────────────
# Kind en constante simple (même pattern que les kinds trésorerie ADSENG22 —
# ``pacing.KIND_*`` — hors de ``EngineAction.Kind`` : le ``CharField.choices``
# n'est pas appliqué par Django au ``save()``, donc aucune migration requise
# pour un nouveau kind qui suit ce pattern déjà établi).
KIND_CREATE_AD_STUDY = 'create_ad_study'

WARN_AD_STUDY_IMMUTABLE = (
    "Étude A/B native Meta : la répartition (treatment_percentage) et la date "
    "de début sont IMMUABLES après le lancement — seule la date de fin reste "
    "éditable.")


def propose_ad_study(company, *, name, cells, experiment=None, reason_fr=None):
    """ADSDEEP34 — Propose la création d'une étude A/B NATIVE (``ad_studies``
    SPLIT_TEST_V2, dossier §7) : validation de FORME dès la proposition (2-5
    cellules, treatment_percentage >= 10 %, somme 100 — fail-fast, la MÊME borne
    que ``MetaClient.create_ad_study`` revalidera au dispatch). L'avertissement
    d'IMMUTABILITÉ après lancement est poussé dans ``payload['warnings']`` — donc
    rendu à l'approbateur, comme les avertissements ADSDEEP31/32."""
    cells = list(cells or [])
    if not (2 <= len(cells) <= 5):
        raise ValueError(
            f"Une étude SPLIT_TEST_V2 exige entre 2 et 5 cellules (reçu {len(cells)}).")
    total_pct = sum(float(c.get('treatment_percentage', 0) or 0) for c in cells)
    if abs(total_pct - 100) > 0.01:
        raise ValueError(
            f"La somme des treatment_percentage doit faire 100 (reçu {total_pct}).")
    if any(float(c.get('treatment_percentage', 0) or 0) < 10 for c in cells):
        raise ValueError(
            "Chaque cellule doit avoir treatment_percentage >= 10 %.")
    reason_fr = reason_fr or (
        f"Lancer l'étude A/B native « {name} » ({len(cells)} cellules).")
    payload = {
        'name': name, 'cells': cells,
        'experiment_id': experiment.pk if experiment is not None else None,
        'warnings': [WARN_AD_STUDY_IMMUTABLE],
    }
    return propose_action(
        company, kind=KIND_CREATE_AD_STUDY, reason_fr=reason_fr, payload=payload)


def sync_ad_study_results(experiment, *, client):
    """ADSDEEP34 — Lit (LECTURE SEULE — AUCUN write Meta) les résultats de
    l'étude native liée à ``experiment.meta_study_id`` et journalise un
    ``DecisionLog`` REJOUABLE (même contrat que le reste de la science, ADSENG3).
    No-op (renvoie ``None``) si l'expérience ne porte encore aucun
    ``meta_study_id`` (aucune étude native créée pour l'instant)."""
    if not experiment.meta_study_id:
        return None
    from .models import DecisionLog
    raw = client.get_ad_study_results(experiment.meta_study_id)
    results = raw.get('results') if isinstance(raw.get('results'), dict) else {}
    return DecisionLog.objects.create(
        company=experiment.company, experiment=experiment,
        inputs={'meta_study_id': experiment.meta_study_id, 'cells': raw.get('cells')},
        posteriors=results, allocations={},
        summary_fr=(
            f"Résultats lus depuis l'étude native Meta {experiment.meta_study_id}."))


# ── ADSDEEP36 — Dayparting : horaire NATIF (lifetime budget) OU planification
# INTERNE (budget quotidien, jamais un adrule Meta auto-exécuté) ────────────
KIND_SET_SCHEDULE = 'set_schedule'


def propose_native_schedule(company, *, adset_id, grid, reason_fr=None):
    """ADSDEEP36 — Propose l'horaire NATIF Meta (``adset_schedule``) pour un ad
    set en budget LIFETIME. La grille est convertie en blocs natifs DÈS la
    proposition (``dayparting.to_native_adset_schedule`` — fail-fast : une
    grille invalide lève ici, jamais un rejet Graph tardif)."""
    from . import dayparting
    native = dayparting.to_native_adset_schedule(grid)
    reason_fr = reason_fr or (
        f"Poser un horaire de diffusion (dayparting natif) sur l'ad set {adset_id}.")
    payload = {'adset_id': adset_id, 'adset_schedule': native, 'grid': grid,
               'mode': 'native'}
    return propose_action(
        company, kind=KIND_SET_SCHEDULE, reason_fr=reason_fr, payload=payload)


def propose_internal_dayparting_pause(company, *, adset, grid, now=None,
                                      reason_fr=None):
    """ADSDEEP36 — Chemin INTERNE (ad set à budget QUOTIDIEN, le natif exige un
    budget lifetime) : propose une PAUSE (kind EXISTANT ``pause``, ENGFIX5 —
    JAMAIS un adrule Meta auto-exécuté, dossier §6) si ``now`` tombe hors de la
    fenêtre autorisée par ``grid``. Renvoie ``None`` (rien à proposer) si l'ad
    set est déjà en pause ou dans sa fenêtre — ne propose JAMAIS de
    ré-activation (aucune méthode ne l'exécute, invariant permanent règle #3)."""
    from django.utils import timezone as dj_tz

    from . import dayparting
    now = now or dj_tz.now()
    is_paused = (adset.status or '').upper() == 'PAUSED'
    if not dayparting.internal_pause_needed(
            grid, now=now, is_currently_paused=is_paused):
        return None
    reason_fr = reason_fr or (
        f"Dayparting interne : « {adset.name} » hors fenêtre autorisée à "
        f"{now.strftime('%H:%M')} ({now.strftime('%A')}) — mise en pause proposée.")
    return propose_action(
        company, kind=EngineAction.Kind.PAUSE, reason_fr=reason_fr,
        payload={'target_type': 'adset', 'target_meta_id': adset.meta_id})


# ── ADSDEEP37 — Duplication (ad set + 1 ad réutilisant le créatif LIVE) ──────
KIND_DUPLICATE = 'duplicate'


def propose_duplicate(company, *, adset, name_suffix=' (copie)', reason_fr=None):
    """ADSDEEP37 — Propose une DUPLICATION d'``adset`` (``AdSetMirror`` source,
    même société) : un NOUVEL ad set (copie du budget du miroir) + UNE ad qui
    RÉUTILISE le créatif LIVE de la première ad source portant un
    ``AdCreativeMirror`` (``AdMirror`` seul ne porte pas le créatif — dossier
    ADSDEEP11). Lève ``ValueError`` (jamais une action créée à moitié) si aucun
    créatif LIVE n'est trouvé, ou si l'ad set n'a pas de campagne/nom miroir."""
    if not adset.campaign_id or not adset.campaign or not adset.campaign.meta_id:
        raise ValueError(
            "Ad set sans campagne miroir (meta_id) : duplication impossible.")
    source_ad = (adset.ads
                 .filter(creative_mirror__isnull=False)
                 .exclude(creative_mirror__creative_meta_id='')
                 .first())
    if source_ad is None:
        raise ValueError(
            "Aucun créatif LIVE (AdCreativeMirror) trouvé pour cet ad set : "
            "dupliquer sans créatif est impossible — resynchroniser d'abord.")
    creative_id = source_ad.creative_mirror.creative_meta_id

    new_adset_name = f'{adset.name}{name_suffix}'
    new_ad_name = f'{source_ad.name}{name_suffix}'
    adset_extra_fields = {}
    if adset.budget is not None:
        adset_extra_fields['daily_budget'] = int(adset.budget)

    reason_fr = reason_fr or f"Dupliquer l'ad set « {adset.name} » ({new_adset_name})."
    payload = {
        'campaign_id': adset.campaign.meta_id,
        'new_adset_name': new_adset_name,
        'adset_extra_fields': adset_extra_fields,
        'new_ad_name': new_ad_name,
        'creative_id': creative_id,
        'source_adset_id': adset.meta_id,
        'source_ad_id': source_ad.meta_id,
    }
    return propose_action(
        company, kind=KIND_DUPLICATE, reason_fr=reason_fr, payload=payload)


# ── ADSDEEP40 — Action de règle « montée de budget » LEARNING-SAFE (≤20 %) ────
def propose_learning_safe_scale_up(company, *, adset_meta_id,
                                   current_daily_budget_mad, scale_pct,
                                   reason_fr, config=None):
    """ADSDEEP40 — Propose une MONTÉE de budget ad set learning-safe (surf-scaling)
    — TOUJOURS propose-first (jamais auto-appliquée : une ``EngineAction`` proposée,
    l'approbation humaine reste requise).

    Double bornage inviolable : ``scale_pct`` est d'abord CLAMPÉ à
    ``LEARNING_SAFE_MAX_PCT`` (20 %, le seuil de reset d'apprentissage Meta), puis
    délégué à ``budget_applier.propose_increase_pace`` qui le resserre encore à
    ``MAX_STEP_PCT`` (15 %/jour) ET au plafond quotidien. Le budget proposé ne peut
    donc JAMAIS dépasser +20 % du courant (en pratique +15 %). ``current_daily_budget_mad``
    est en MAD (le miroir stocke des centimes — l'appelant convertit). Une pause /
    dé-pause n'est JAMAIS possible par ce chemin (montée de budget uniquement)."""
    from . import budget_applier
    bump = min(float(scale_pct), float(LEARNING_SAFE_MAX_PCT))
    return budget_applier.propose_increase_pace(
        company, adset_meta_id=adset_meta_id,
        current_daily_budget_mad=current_daily_budget_mad,
        reason_fr=reason_fr, bump_pct=bump, config=config)


def propose_pause_for_month(company, *, target_meta_id, target_type='campaign',
                            reason_fr=None):
    """ADSENG22 — Propose une pause « pour le mois » (chemin breach-imminent du
    pacing, dd-treasury §A3). PAUSED-only par construction : l'application route
    vers ``update_status_paused`` (jamais un statut paramétrable). Propose-only —
    l'approbation humaine reste requise avant toute pause effective."""
    reason_fr = reason_fr or (
        f"Mettre en pause {target_type} {target_meta_id} pour le mois : "
        f"franchissement imminent du plafond mensuel (protection d'invariant).")
    return propose_action(
        company, kind=KIND_PAUSE_FOR_MONTH, reason_fr=reason_fr,
        payload={'target_type': target_type, 'target_meta_id': target_meta_id})


# ── PUB22 — Dispatch de proposition CURÉE (kinds qui exigent une résolution /
# validation backend et ne peuvent donc PAS être proposés par POST brut) ─────────
def _resolve_adset(company, meta_id):
    """Ad set miroir de la société par son ``meta_id`` (jamais cross-société).
    Lève ``ActionPayloadInvalid`` (→ 400) si introuvable."""
    from .models import AdSetMirror
    if not meta_id or not str(meta_id).strip():
        raise ActionPayloadInvalid("Champ requis manquant : l'id de l'ad set.")
    adset = AdSetMirror.objects.filter(
        company=company, meta_id=str(meta_id).strip()).first()
    if adset is None:
        raise ActionPayloadInvalid(
            "Ad set introuvable pour cette société.")
    return adset


def propose_manual_curated(company, *, kind, params, reason_fr=None):
    """PUB22 — Route une proposition d'action CURÉE (``duplicate`` /
    ``set_schedule`` / ``create_ad_study``) vers son producteur dédié — lequel
    passe TOUJOURS par ``propose_action`` (naissance PAUSED intacte, aucune
    activation). Company-scopé : les objets référencés sont bornés à la société.
    Un producteur lève ``ValueError`` sur entrée invalide (→ 400)."""
    params = params or {}
    if kind == KIND_DUPLICATE:
        adset = _resolve_adset(company, params.get('adset_id'))
        return propose_duplicate(
            company, adset=adset,
            name_suffix=(params.get('name_suffix') or ' (copie)'),
            reason_fr=reason_fr)
    if kind == KIND_SET_SCHEDULE:
        return propose_native_schedule(
            company, adset_id=(params.get('adset_id') or ''),
            grid=params.get('grid'), reason_fr=reason_fr)
    if kind == KIND_CREATE_AD_STUDY:
        return propose_ad_study(
            company, name=(params.get('name') or ''),
            cells=params.get('cells'), reason_fr=reason_fr)
    raise ActionPayloadInvalid(f"Kind curé inconnu : {kind}.")


# ── PUB45 — Annuler une action APPLIQUÉE = proposer son INVERSE ────────────────
# L'annulation ne fait JAMAIS un write direct : elle CRÉE une proposition inverse
# qui repasse par le circuit propose→approuve normal. Seule une poignée de kinds a
# un inverse automatique (rétablir une valeur MÉMORISÉE) ; les autres sont
# expliqués (une CRÉATION ne s'annule pas par ce circuit — on met en pause l'objet
# né PAUSED ; une PAUSE ne se ré-active pas — règle #3).
_INVERTIBLE_BUDGET_KINDS = frozenset({
    EngineAction.Kind.REBALANCE_BUDGET, KIND_INCREASE_PACE,
    KIND_REBALANCE_ADSET_BUDGET,
})

# Explications FR pour les kinds SANS inverse automatique (rendues à l'opérateur).
_NOT_INVERTIBLE_REASONS = {
    EngineAction.Kind.CREATE_CAMPAIGN: (
        "Une création de campagne ne s'annule pas par ce circuit : mettre en "
        "pause la campagne créée (elle est née PAUSED)."),
    EngineAction.Kind.CREATE_ADSET: (
        "Une création d'ad set ne s'annule pas par ce circuit : mettre en pause "
        "l'ad set créé (né PAUSED)."),
    EngineAction.Kind.CREATE_AD: (
        "Une création d'ad ne s'annule pas par ce circuit : mettre en pause "
        "l'ad créée (née PAUSED)."),
    EngineAction.Kind.ROTATE_CREATIVE: (
        "Une rotation crée une NOUVELLE ad (née PAUSED) : mettre en pause l'ad "
        "créée plutôt que d'annuler."),
    EngineAction.Kind.PAUSE: (
        "Une mise en pause ne s'annule pas automatiquement : ré-activer est "
        "interdit (règle #3). Ré-activer manuellement côté Meta si nécessaire."),
    KIND_PAUSE_FOR_MONTH: (
        "Une pause pour le mois ne s'annule pas automatiquement : ré-activer est "
        "interdit (règle #3)."),
    KIND_DUPLICATE: (
        "Une duplication crée de nouveaux objets (nés PAUSED) : les mettre en "
        "pause plutôt que d'annuler."),
    KIND_ENABLE_CBO: (
        "L'activation CBO n'a pas d'inverse automatique."),
    KIND_SET_SCHEDULE: (
        "Un horaire n'a pas d'inverse automatique : reposer un horaire différent."),
    KIND_CREATE_AD_STUDY: (
        "Une étude A/B native ne s'annule pas par ce circuit."),
}


def propose_inverse_action(action, *, reason_fr=None):
    """PUB45 — Propose l'action INVERSE d'une action APPLIQUÉE, via le circuit
    propose→approuve normal (jamais un write direct). Rétablit la valeur
    MÉMORISÉE sur l'action d'origine (budget précédent ``current_budget``, texte
    précédent ``current_creative``…). Lève ``ActionNotInvertible`` (avec une
    explication FR) pour tout kind sans inverse automatique. La proposition
    inverse porte ``payload['inverse_of']`` = pk de l'action annulée (traçabilité)."""
    if action.status != EngineAction.Statut.APPLIQUEE:
        raise ActionNotInvertible(
            "Seule une action APPLIQUÉE peut être annulée.")
    payload = action.payload or {}
    kind = action.kind

    if kind in _INVERTIBLE_BUDGET_KINDS:
        previous = payload.get('current_budget')
        if previous is None:
            raise ActionNotInvertible(
                "Le budget précédent n'a pas été mémorisé sur cette action : "
                "ré-proposer le budget voulu manuellement.")
        inv_reason = reason_fr or (
            f"Annuler l'action #{action.pk} : rétablir le budget précédent.")
        return propose_action(
            action.company, kind=EngineAction.Kind.REBALANCE_BUDGET,
            reason_fr=inv_reason,
            payload={
                'adset_id': payload.get('adset_id', ''),
                'daily_budget': previous,
                'current_budget': payload.get('daily_budget'),
                'inverse_of': action.pk,
            })

    if kind == EngineAction.Kind.EDIT_COPY:
        previous_creative = payload.get('current_creative')
        if not previous_creative:
            raise ActionNotInvertible(
                "Le texte/créatif précédent n'a pas été mémorisé sur cette "
                "action : ré-proposer le texte voulu manuellement.")
        inv_reason = reason_fr or (
            f"Annuler l'action #{action.pk} : rétablir le texte précédent.")
        return propose_action(
            action.company, kind=EngineAction.Kind.EDIT_COPY,
            reason_fr=inv_reason,
            payload={
                'ad_id': payload.get('ad_id', ''),
                'current_creative': payload.get('creative_spec'),
                'creative_spec': previous_creative,
                'inverse_of': action.pk,
            })

    if kind == EngineAction.Kind.SET_SPEND_CAP:
        previous = payload.get('previous_spend_cap')
        if previous is None:
            raise ActionNotInvertible(
                "Le plafond de dépense précédent n'a pas été mémorisé : reposer "
                "un plafond manuellement.")
        inv_reason = reason_fr or (
            f"Annuler l'action #{action.pk} : rétablir le plafond précédent.")
        return propose_action(
            action.company, kind=EngineAction.Kind.SET_SPEND_CAP,
            reason_fr=inv_reason,
            payload={
                'campaign_id': payload.get('campaign_id', ''),
                'spend_cap': previous,
                'previous_spend_cap': payload.get('spend_cap'),
                'inverse_of': action.pk,
            })

    if kind == EngineAction.Kind.RENAME:
        previous = payload.get('previous_name')
        if not previous:
            raise ActionNotInvertible(
                "Le nom précédent n'a pas été mémorisé : renommer manuellement.")
        inv_reason = reason_fr or (
            f"Annuler l'action #{action.pk} : rétablir le nom précédent.")
        return propose_action(
            action.company, kind=EngineAction.Kind.RENAME,
            reason_fr=inv_reason,
            payload={
                'object_id': payload.get('object_id', ''),
                'name': previous,
                'previous_name': payload.get('name'),
                'inverse_of': action.pk,
            })

    raise ActionNotInvertible(_NOT_INVERTIBLE_REASONS.get(
        kind, "Cette action n'a pas d'inverse automatique."))


def non_invertible_reason_fr(action):
    """PUB45 — Raison FR (sûre, curée) de non-inversibilité d'une action, pour
    l'AFFICHAGE client — dérivée du KIND (constante ``_NOT_INVERTIBLE_REASONS``)
    et JAMAIS du texte d'une exception attrapée (CodeQL py/stack-trace-exposure :
    on n'expose aucune trace ni détail interne au client, seulement un message
    métier volontairement rédigé)."""
    if action.status != EngineAction.Statut.APPLIQUEE:
        return "Seule une action APPLIQUÉE peut être annulée."
    return _NOT_INVERTIBLE_REASONS.get(
        action.kind, "Cette action n'a pas d'inverse automatique.")


# ── ADSDEEP49-52 — Posts ORGANIQUES de Page (propose→approuve→applique) ───────
# Kinds en constantes simples (même pattern que KIND_DUPLICATE / KIND_SET_SCHEDULE
# / KIND_CREATE_AD_STUDY — hors de ``EngineAction.Kind`` : le ``CharField.choices``
# n'est pas appliqué par Django au ``save()``, donc AUCUNE migration requise pour
# un nouveau kind qui suit ce pattern déjà établi).
KIND_EDIT_POST = 'edit_post'
KIND_CREATE_POST = 'create_post'
KIND_BOOST_POST = 'boost_post'

# ADSDEEP50 — avertissements montrés à l'approbateur pour une édition de post.
WARN_POST_MESSAGE_ONLY = (
    "Seul le message est éditable : le visuel (image/vidéo) d'un post déjà "
    "publié est IMMUABLE côté Meta — le changer imposerait de supprimer puis "
    "recréer le post (perte de l'historique d'engagement).")
WARN_POST_AD_LINKED = (
    "Post adossé à une pub : l'éditer est à RISQUE. Le post a été reviewé comme "
    "publicité — un changement de texte peut déclencher une re-review Meta et "
    "une désynchronisation de l'annonce.")


def propose_edit_post(company, *, post, message, reason_fr=None):
    """ADSDEEP50 — Propose l'édition du TEXTE d'un post de Page (kind EDIT_POST).

    REFUS PROPRE (``ValueError``, AUCUNE action créée) si le post n'a pas été créé
    par l'app : Meta n'autorise l'édition QUE des posts créés par l'app elle-même
    (dossier organic-posts §1). Avertissements portés à l'approbateur : « seul le
    message est éditable » TOUJOURS ; DOUBLE avertissement quand le post est
    adossé à une pub (édition à risque / re-review). Seul ``message`` est
    transmis — le visuel d'un post publié est immuable."""
    if not getattr(post, 'created_by_app', False):
        raise ValueError(
            "Post non créé par l'app : Meta n'autorise l'édition que des posts "
            "créés par l'app elle-même — édition refusée.")
    warnings = [WARN_POST_MESSAGE_ONLY]
    if getattr(post, 'ad_linked', False):
        warnings.append(WARN_POST_AD_LINKED)
    reason_fr = reason_fr or f"Éditer le texte du post de Page {post.meta_id}."
    payload = {
        'post_id': post.meta_id, 'message': message, 'warnings': warnings}
    return propose_action(
        company, kind=KIND_EDIT_POST, reason_fr=reason_fr, payload=payload)


def propose_create_post(company, *, message='', link='', mode='published',
                        scheduled_publish_time=None, media=None, reason_fr=None):
    """ADSDEEP51 — Propose la création d'un post de Page (kind CREATE_POST).

    ``mode`` ∈ {published, dark, scheduled} ; ``media`` optionnel
    ``{'kind': 'photo'|'photos'|'video', …}`` (aucun = post texte/lien). Un post
    programmé exige un ``scheduled_publish_time`` (fenêtre 10 min-30 j revalidée
    au dispatch par le client, fail-fast). Le dispatch route vers la bonne
    méthode de publication du client selon le média et le mode."""
    mode = str(mode or 'published').strip().lower()
    if mode not in ('published', 'dark', 'scheduled'):
        raise ValueError("mode doit être published, dark ou scheduled.")
    if mode == 'scheduled' and scheduled_publish_time is None:
        raise ValueError(
            "Un post programmé exige un scheduled_publish_time (unix).")
    reason_fr = reason_fr or "Publier un post de Page."
    payload = {
        'mode': mode, 'message': message, 'link': link,
        'scheduled_publish_time': scheduled_publish_time,
        'media': media or {},
    }
    return propose_action(
        company, kind=KIND_CREATE_POST, reason_fr=reason_fr, payload=payload)


def propose_boost_post(company, *, post, adset, name=None, reason_fr=None):
    """ADSDEEP52 — Propose de BOOSTER un post existant (kind BOOST_POST) : une ad
    portant ``object_story_id`` (preuve sociale PRÉSERVÉE) dans l'ad set choisi,
    née PAUSED (invariant permanent règle #3 — garanti par ``meta_client``,
    jamais d'activation). ``post`` = ``PagePostMirror`` ; ``adset`` =
    ``AdSetMirror`` possédé."""
    name = name or f'Boost post {post.meta_id}'
    reason_fr = reason_fr or (
        f"Booster le post de Page {post.meta_id} dans l'ad set "
        f"{adset.meta_id} (ad née PAUSED).")
    payload = {
        'post_id': post.meta_id, 'adset_id': adset.meta_id, 'name': name}
    return propose_action(
        company, kind=KIND_BOOST_POST, reason_fr=reason_fr, payload=payload)


# ── ADSDEEP53 — Actions sur les commentaires (propose→approuve→applique) ─────
# Kinds en constantes simples (même pattern que les kinds posts ci-dessus — hors
# de ``EngineAction.Kind``, aucune migration requise).
KIND_HIDE_COMMENT = 'hide_comment'
KIND_REPLY_COMMENT = 'reply_comment'
KIND_DELETE_COMMENT = 'delete_comment'
KIND_PRIVATE_REPLY = 'private_reply'

# Fenêtre Meta d'une réponse privée : UNE par commentaire, dans les 7 jours.
PRIVATE_REPLY_WINDOW_DAYS = 7

WARN_COMMENT_HIDE_READBACK = (
    "Le masquage sera RE-VÉRIFIÉ après application (``is_hidden`` est éventuellement "
    "consistant côté Meta) : le badge « caché-vérifié » ne s'allume que si le "
    "re-contrôle confirme l'état.")


def propose_hide_comment(company, *, comment, hidden=True, reason_fr=None):
    """ADSDEEP53 — Propose de masquer (``hidden=True``) ou démasquer un
    commentaire. L'application fera un READ-BACK obligatoire (dossier §3) : elle
    re-GET le commentaire et ne pose ``hidden_verified`` que si l'état observé
    confirme la demande."""
    verb = 'Masquer' if hidden else 'Démasquer'
    reason_fr = reason_fr or f"{verb} le commentaire {comment.meta_id}."
    payload = {
        'comment_id': comment.meta_id, 'hidden': bool(hidden),
        'warnings': [WARN_COMMENT_HIDE_READBACK]}
    return propose_action(
        company, kind=KIND_HIDE_COMMENT, reason_fr=reason_fr, payload=payload)


def propose_reply_comment(company, *, comment, message, reason_fr=None):
    """ADSDEEP53 — Propose une réponse PUBLIQUE à un commentaire."""
    if not (message and str(message).strip()):
        raise ValueError("Une réponse ne peut pas être vide.")
    reason_fr = reason_fr or f"Répondre au commentaire {comment.meta_id}."
    payload = {'comment_id': comment.meta_id, 'message': str(message)}
    return propose_action(
        company, kind=KIND_REPLY_COMMENT, reason_fr=reason_fr, payload=payload)


def propose_delete_comment(company, *, comment, reason_fr=None):
    """ADSDEEP53 — Propose la SUPPRESSION d'un commentaire (irréversible côté
    Meta — passe donc, comme tout, par l'approbation humaine)."""
    reason_fr = reason_fr or f"Supprimer le commentaire {comment.meta_id}."
    payload = {'comment_id': comment.meta_id}
    return propose_action(
        company, kind=KIND_DELETE_COMMENT, reason_fr=reason_fr, payload=payload)


def propose_private_reply(company, *, comment, message, reason_fr=None):
    """ADSDEEP53 — Propose une RÉPONSE PRIVÉE (DM) à un commentaire.

    GARDE-FOU (dossier §3, fail-fast — AUCUNE action créée si violé) : Meta
    n'autorise QU'UNE réponse privée par commentaire, dans les 7 jours. On refuse
    donc proprement si (a) une réponse privée a déjà été envoyée
    (``private_reply_sent_at`` renseigné) ou (b) le commentaire a plus de 7 jours."""
    from django.utils import timezone

    if not (message and str(message).strip()):
        raise ValueError("Une réponse privée ne peut pas être vide.")
    if comment.private_reply_sent_at is not None:
        raise ValueError(
            "Une réponse privée a déjà été envoyée pour ce commentaire "
            "(Meta n'en autorise qu'une).")
    created = comment.created_time
    if created is not None:
        age = timezone.now() - created
        if age.days >= PRIVATE_REPLY_WINDOW_DAYS:
            raise ValueError(
                "Fenêtre de réponse privée expirée : Meta n'autorise le DM que "
                f"dans les {PRIVATE_REPLY_WINDOW_DAYS} jours suivant le commentaire.")
    reason_fr = reason_fr or (
        f"Répondre en privé (DM) au commentaire {comment.meta_id}.")
    payload = {'comment_id': comment.meta_id, 'message': str(message)}
    return propose_action(
        company, kind=KIND_PRIVATE_REPLY, reason_fr=reason_fr, payload=payload)


def propose_keyword_hides(company, *, rules=None, auto_only=False):
    """ADSDEEP53 — Depuis le DRY-RUN du moteur de règles mot-clé
    (``comments.plan_keyword_hides``), crée les propositions de masquage.

    Mode PROPOSE par défaut : chaque correspondance devient une ``EngineAction``
    HIDE_COMMENT À APPROUVER (jamais un masquage silencieux). Une règle qui porte
    ``auto=True`` (opt-in explicite fondateur) produit une action ``auto=True``
    (trace d'audit — l'auto-apply éventuel reste géré par le chemin garde-fou
    ENG8, jamais ici). ``auto_only=True`` restreint aux seules règles auto.
    Renvoie la liste des actions proposées."""
    from . import comments as comments_mod

    plan = comments_mod.plan_keyword_hides(company, rules=rules)
    actions = []
    for item in plan:
        if auto_only and not item['auto']:
            continue
        comment = item['comment']
        action = propose_action(
            company, kind=KIND_HIDE_COMMENT,
            reason_fr=(
                f"Masquage par règle mot-clé « {item['keyword']} » — "
                f"commentaire {comment.meta_id}."),
            payload={
                'comment_id': comment.meta_id, 'hidden': True,
                'keyword': item['keyword'],
                'warnings': [WARN_COMMENT_HIDE_READBACK]},
            auto=bool(item['auto']))
        actions.append(action)
    return actions


def _dispatch_hide_comment(client, action):
    """ADSDEEP53 — Applique un masquage/démasquage AVEC READ-BACK obligatoire
    (dossier §3 : ``is_hidden`` est éventuellement consistant côté Meta).

    Séquence : (1) POST is_hidden ; (2) re-GET le commentaire ; (3) compare l'état
    observé à l'état demandé ; (4) met à jour le miroir (``is_hidden`` observé +
    ``hidden_verified`` = confirmation stricte). Le badge « caché-vérifié » de
    l'UI ne s'allume donc que quand le re-contrôle CONFIRME le masquage."""
    from .models import CommentMirror

    payload = action.payload or {}
    comment_id = str(payload.get('comment_id') or '')
    hidden = bool(payload.get('hidden', True))
    client.hide_comment(comment_id=comment_id, hidden=hidden)
    # READ-BACK — on ne croit jamais le POST en aveugle : on re-lit l'état réel.
    observed = None
    verified = False
    try:
        fresh = client.get_comment(comment_id) or {}
        observed = bool(fresh.get('is_hidden'))
        verified = (observed == hidden)
    except Exception:  # noqa: BLE001 — read-back en échec ⇒ non vérifié (jamais un faux vert)
        observed = None
        verified = False
    CommentMirror.objects.filter(
        company=action.company, meta_id=comment_id).update(
            is_hidden=(observed if observed is not None else hidden),
            hidden_verified=verified)
    return {
        'comment_id': comment_id, 'requested_hidden': hidden,
        'observed_is_hidden': observed, 'verified': verified}


def _dispatch_reply_comment(client, action):
    """ADSDEEP53 — Applique une réponse publique + marque le miroir « répondu »."""
    from .models import CommentMirror

    payload = action.payload or {}
    comment_id = str(payload.get('comment_id') or '')
    result = client.reply_to_comment(
        comment_id=comment_id, message=payload.get('message', ''))
    CommentMirror.objects.filter(
        company=action.company, meta_id=comment_id).update(answered=True)
    return result if isinstance(result, dict) else {'result': result}


def _dispatch_delete_comment(client, action):
    """ADSDEEP53 — Applique une suppression + retire le miroir local."""
    from .models import CommentMirror

    payload = action.payload or {}
    comment_id = str(payload.get('comment_id') or '')
    result = client.delete_comment(comment_id=comment_id)
    CommentMirror.objects.filter(
        company=action.company, meta_id=comment_id).delete()
    return result if isinstance(result, dict) else {'result': result}


def _dispatch_private_reply(client, action):
    """ADSDEEP53 — Applique une réponse privée + horodate le miroir (le garde-fou
    « une seule / 7 j » repose ensuite sur ``private_reply_sent_at`` — une 2e
    tentative sera refusée à la proposition)."""
    from django.utils import timezone

    from .models import CommentMirror

    payload = action.payload or {}
    comment_id = str(payload.get('comment_id') or '')
    result = client.private_reply(
        comment_id=comment_id, message=payload.get('message', ''))
    CommentMirror.objects.filter(
        company=action.company, meta_id=comment_id).update(
            private_reply_sent_at=timezone.now())
    return result if isinstance(result, dict) else {'result': result}


# ── ADSDEEP55 — Instagram (publication container + commentaires) ─────────────
KIND_PUBLISH_IG = 'publish_ig'
KIND_HIDE_IG_COMMENT = 'hide_ig_comment'
KIND_REPLY_IG_COMMENT = 'reply_ig_comment'
KIND_DELETE_IG_COMMENT = 'delete_ig_comment'
KIND_TOGGLE_IG_COMMENTS = 'toggle_ig_comments'

WARN_IG_CAPTION_IMMUTABLE = (
    "La légende Instagram ne pourra PLUS être modifiée après publication (Reels "
    "compris) — relisez-la avant d'approuver, c'est définitif.")

# Types de média IG publiables (miroir de MetaClient.IG_MEDIA_TYPES).
IG_MEDIA_TYPES = ('IMAGE', 'VIDEO', 'REELS', 'STORIES', 'CAROUSEL')


def propose_publish_ig(company, *, media_type, image_url='', video_url='',
                       caption='', alt_text='', scheduled_at=None,
                       reason_fr=None):
    """ADSDEEP55 — Propose la PUBLICATION d'un média Instagram (kind PUBLISH_IG).

    L'application passe par le flux CONTAINER (create → poll FINISHED → publish)
    et vérifie le QUOTA 50/24 h AVANT toute création. La ``caption`` est posée à
    la création du container et devient IMMUABLE — l'avertissement est porté à
    l'approbateur (``payload['warnings']``). ``scheduled_at`` (optionnel) est
    conservé : l'action proposée reste en attente jusqu'à ce qu'un humain
    l'approuve/applique au moment voulu (aucune activation automatique)."""
    mtype = str(media_type or '').strip().upper()
    if mtype not in IG_MEDIA_TYPES:
        raise ValueError(
            f"media_type Instagram invalide : {media_type} "
            f"(attendu l'un de {', '.join(IG_MEDIA_TYPES)}).")
    if mtype in ('VIDEO', 'REELS') and not video_url:
        raise ValueError("Une publication vidéo/Reel exige video_url.")
    if mtype in ('IMAGE', 'CAROUSEL') and not image_url:
        raise ValueError("Une publication image/carrousel exige image_url.")
    reason_fr = reason_fr or f"Publier un média Instagram ({mtype})."
    payload = {
        'media_type': mtype, 'image_url': image_url, 'video_url': video_url,
        'caption': caption, 'alt_text': alt_text,
        'scheduled_at': scheduled_at,
        'warnings': [WARN_IG_CAPTION_IMMUTABLE]}
    return propose_action(
        company, kind=KIND_PUBLISH_IG, reason_fr=reason_fr, payload=payload)


def propose_hide_ig_comment(company, *, comment, hidden=True, reason_fr=None):
    """ADSDEEP55 — Propose de masquer/démasquer un commentaire Instagram."""
    verb = 'Masquer' if hidden else 'Démasquer'
    reason_fr = reason_fr or f"{verb} le commentaire Instagram {comment.meta_id}."
    payload = {'comment_id': comment.meta_id, 'hidden': bool(hidden)}
    return propose_action(
        company, kind=KIND_HIDE_IG_COMMENT, reason_fr=reason_fr, payload=payload)


def propose_reply_ig_comment(company, *, comment, message, reason_fr=None):
    """ADSDEEP55 — Propose une réponse à un commentaire Instagram."""
    if not (message and str(message).strip()):
        raise ValueError("Une réponse ne peut pas être vide.")
    reason_fr = reason_fr or f"Répondre au commentaire Instagram {comment.meta_id}."
    payload = {'comment_id': comment.meta_id, 'message': str(message)}
    return propose_action(
        company, kind=KIND_REPLY_IG_COMMENT, reason_fr=reason_fr, payload=payload)


def propose_delete_ig_comment(company, *, comment, reason_fr=None):
    """ADSDEEP55 — Propose la suppression d'un commentaire Instagram."""
    reason_fr = reason_fr or f"Supprimer le commentaire Instagram {comment.meta_id}."
    payload = {'comment_id': comment.meta_id}
    return propose_action(
        company, kind=KIND_DELETE_IG_COMMENT, reason_fr=reason_fr, payload=payload)


def propose_toggle_ig_comments(company, *, media, enabled, reason_fr=None):
    """ADSDEEP55 — Propose de couper / rouvrir les commentaires d'un média IG
    (``comment_enabled`` — SEUL champ écrivable d'un média ; la légende reste
    immuable)."""
    verb = 'Rouvrir' if enabled else 'Couper'
    reason_fr = reason_fr or (
        f"{verb} les commentaires du média Instagram {media.meta_id}.")
    payload = {'media_id': media.meta_id, 'enabled': bool(enabled)}
    return propose_action(
        company, kind=KIND_TOGGLE_IG_COMMENTS, reason_fr=reason_fr, payload=payload)


def _dispatch_publish_ig(client, action):
    """ADSDEEP55 — Applique une publication Instagram via le flux CONTAINER
    (create → poll FINISHED → publish, quota 50/24 h vérifié dans le client).
    Journalise un ``InstagramPublishJob`` (état + quota surfacé). La caption est
    posée à la création et n'est jamais ré-éditée."""
    from django.utils.dateparse import parse_datetime

    from .models import InstagramPublishJob

    payload = action.payload or {}
    scheduled = payload.get('scheduled_at')
    scheduled_dt = parse_datetime(str(scheduled)) if scheduled else None
    job = InstagramPublishJob.objects.create(
        company=action.company,
        media_type=str(payload.get('media_type') or ''),
        image_url=payload.get('image_url', '') or '',
        video_url=payload.get('video_url', '') or '',
        caption=payload.get('caption', '') or '',
        scheduled_at=scheduled_dt,
        status=InstagramPublishJob.Status.PENDING)
    try:
        result = client.publish_ig_media(
            image_url=payload.get('image_url') or None,
            video_url=payload.get('video_url') or None,
            media_type=payload.get('media_type') or None,
            caption=payload.get('caption', '') or '',
            alt_text=payload.get('alt_text') or None,
            file_size=payload.get('file_size'))
    except Exception as exc:
        job.status = InstagramPublishJob.Status.ERROR
        job.error = str(exc)
        job.save(update_fields=['status', 'error', 'updated_at'])
        raise
    result = result if isinstance(result, dict) else {'result': result}
    quota = result.get('quota') or {}
    job.creation_id = str(result.get('creation_id') or '')
    job.published_media_id = str(result.get('media_id') or '')
    job.status = InstagramPublishJob.Status.PUBLISHED
    job.status_code = 'FINISHED'
    job.quota_used = quota.get('used')
    job.quota_total = quota.get('total')
    job.save(update_fields=[
        'creation_id', 'published_media_id', 'status', 'status_code',
        'quota_used', 'quota_total', 'updated_at'])
    out = dict(result)
    out['job_id'] = job.pk
    return out


def _dispatch_hide_ig_comment(client, action):
    """ADSDEEP55 — Masque/démasque un commentaire IG + met à jour le miroir."""
    from .models import InstagramCommentMirror

    payload = action.payload or {}
    comment_id = str(payload.get('comment_id') or '')
    hidden = bool(payload.get('hidden', True))
    result = client.hide_ig_comment(comment_id=comment_id, hidden=hidden)
    InstagramCommentMirror.objects.filter(
        company=action.company, meta_id=comment_id).update(hidden=hidden)
    return result if isinstance(result, dict) else {'result': result}


def _dispatch_reply_ig_comment(client, action):
    """ADSDEEP55 — Répond à un commentaire IG + marque le miroir « répondu »."""
    from .models import InstagramCommentMirror

    payload = action.payload or {}
    comment_id = str(payload.get('comment_id') or '')
    result = client.reply_ig_comment(
        comment_id=comment_id, message=payload.get('message', ''))
    InstagramCommentMirror.objects.filter(
        company=action.company, meta_id=comment_id).update(answered=True)
    return result if isinstance(result, dict) else {'result': result}


def _dispatch_delete_ig_comment(client, action):
    """ADSDEEP55 — Supprime un commentaire IG + retire le miroir."""
    from .models import InstagramCommentMirror

    payload = action.payload or {}
    comment_id = str(payload.get('comment_id') or '')
    result = client.delete_ig_comment(comment_id=comment_id)
    InstagramCommentMirror.objects.filter(
        company=action.company, meta_id=comment_id).delete()
    return result if isinstance(result, dict) else {'result': result}


def _dispatch_toggle_ig_comments(client, action):
    """ADSDEEP55 — Coupe/rouvre les commentaires d'un média IG + met à jour le
    miroir (``comment_enabled`` — la légende reste immuable, jamais touchée)."""
    from .models import InstagramMediaMirror

    payload = action.payload or {}
    media_id = str(payload.get('media_id') or '')
    enabled = bool(payload.get('enabled', True))
    result = client.set_ig_comment_enabled(media_id=media_id, enabled=enabled)
    InstagramMediaMirror.objects.filter(
        company=action.company, meta_id=media_id).update(comment_enabled=enabled)
    return result if isinstance(result, dict) else {'result': result}


def _dispatch_create_post(client, payload):
    """ADSDEEP51 — Route une action CREATE_POST vers la bonne méthode de
    publication du client selon le média (aucun / photo / multi-photos / vidéo)
    et le mode (publié / dark / programmé)."""
    media = payload.get('media') or {}
    mkind = str(media.get('kind') or '').strip().lower()
    message = payload.get('message', '') or ''
    if mkind == 'photo':
        return client.upload_page_photo(
            image_url=media.get('image_url', ''), published=True,
            caption=message)
    if mkind == 'photos':
        return client.create_multi_photo_post(
            message=message, image_urls=media.get('image_urls') or [])
    if mkind == 'video':
        return client.upload_page_video(
            file_url=media.get('file_url', ''), message=message,
            file_size=media.get('file_size'))
    mode = str(payload.get('mode') or 'published').strip().lower()
    published = mode == 'published'
    scheduled = (payload.get('scheduled_publish_time')
                 if mode == 'scheduled' else None)
    return client.create_page_post(
        message=message, link=payload.get('link', '') or '',
        published=published, scheduled_publish_time=scheduled)


def approve_action(action, *, user):
    """Approuve une action PROPOSÉE (acteur posé côté serveur).

    ENGFIX3 — Verrou de ligne (``select_for_update``) + re-vérification du statut
    SOUS le verrou : deux décisions concurrentes (approuver contre rejeter) ne
    peuvent pas toutes deux gagner (course dernier-écrivain). Seule une action
    ENCORE ``proposee`` sous le verrou passe ``approuvee``."""
    from django.db import transaction
    with transaction.atomic():
        locked = (EngineAction.objects
                  .select_for_update()
                  .filter(pk=action.pk).first())
        if locked is None or locked.status != EngineAction.Statut.PROPOSEE:
            raise ValueError("Seule une action proposée peut être approuvée.")
        locked.status = EngineAction.Statut.APPROUVEE
        locked.approved_by = user
        locked.save(update_fields=['status', 'approved_by', 'updated_at'])
    # Réaligne l'objet en mémoire fourni par l'appelant sur l'état réclamé.
    action.status = EngineAction.Statut.APPROUVEE
    action.approved_by = user
    return action


def reject_action(action, *, user, commentaire=''):
    """Rejette une action PROPOSÉE (elle ne pourra jamais être appliquée).

    ENGFIX3 — Même discipline verrou-de-ligne + re-vérification sous verrou que
    ``approve_action`` (course approuver/rejeter)."""
    from django.db import transaction
    with transaction.atomic():
        locked = (EngineAction.objects
                  .select_for_update()
                  .filter(pk=action.pk).first())
        if locked is None or locked.status != EngineAction.Statut.PROPOSEE:
            raise ValueError("Seule une action proposée peut être rejetée.")
        locked.status = EngineAction.Statut.REJETEE
        locked.approved_by = user
        if commentaire:
            locked.error = str(commentaire)
        locked.save(
            update_fields=['status', 'approved_by', 'error', 'updated_at'])
    action.status = EngineAction.Statut.REJETEE
    action.approved_by = user
    if commentaire:
        action.error = str(commentaire)
    return action


def _dispatch(client, action):
    """Route une action APPROUVÉE vers la bonne méthode de création du client.

    Toutes les créations naissent PAUSED (garanti par ``meta_client`` lui-même).
    Aucune activation n'est routable ici — le client n'en expose aucune.
    """
    payload = action.payload or {}
    kind = action.kind
    if kind == EngineAction.Kind.CREATE_CAMPAIGN:
        return client.create_campaign(
            name=payload.get('name', ''),
            objective=payload.get('objective', ''),
            special_ad_categories=payload.get('special_ad_categories'),
            extra_fields=payload.get('extra_fields'))
    if kind == EngineAction.Kind.CREATE_ADSET:
        return client.create_adset(
            name=payload.get('name', ''),
            campaign_id=payload.get('campaign_id', ''),
            extra_fields=payload.get('extra_fields'))
    if kind == EngineAction.Kind.CREATE_AD:
        return client.create_ad(
            name=payload.get('name', ''),
            adset_id=payload.get('adset_id', ''),
            extra_fields=payload.get('extra_fields'))
    if kind == EngineAction.Kind.ROTATE_CREATIVE:
        # Roter le créatif = créer une NOUVELLE ad (toujours PAUSED) portant le
        # nouveau créatif ; le client garantit le statut PAUSED (jamais d'activ.).
        return client.create_ad(
            name=payload.get('name', ''),
            adset_id=payload.get('adset_id', ''),
            extra_fields=payload.get('extra_fields'))
    if kind == EngineAction.Kind.REBALANCE_BUDGET:
        # Rééquilibrage de budget dans la bande. La méthode concrète de mise à
        # jour de budget du client atterrit avec le groupe budget (ADSENG) ; ici
        # on route déjà l'appel. Un client réel qui ne l'expose pas encore lève
        # (→ action « echouee », jamais d'application silencieuse ni d'activation).
        return client.update_adset_budget(
            adset_id=payload.get('adset_id', ''),
            daily_budget=payload.get('daily_budget'),
            extra_fields=payload.get('extra_fields'))
    if kind == EngineAction.Kind.PAUSE:
        # ENGFIX5 — Mise en pause : l'action de sécurité par excellence (proposée
        # par le détecteur d'anomalie ENG9 + le brief hebdo ENG11). Gardée
        # PAUSED-only AVANT tout appel (belt-and-suspenders : la transition ne peut
        # être que vers PAUSED), puis routée vers la méthode dédiée du client qui
        # FORCE PAUSED — aucun statut ACTIVE possible (invariant permanent #3).
        guardrails.enforce_paused_only('PAUSED', company=action.company)
        return client.update_status_paused(
            object_id=payload.get('target_meta_id', ''),
            level=payload.get('target_type'))
    if kind == KIND_PAUSE_FOR_MONTH:
        # ADSENG22 — Pause « pour le mois » (chemin breach-imminent du pacing,
        # dd-treasury §A3). PAUSED-only par construction, MÊME défense que PAUSE :
        # garde PAUSED-only AVANT l'appel + méthode client qui FORCE PAUSED.
        guardrails.enforce_paused_only('PAUSED', company=action.company)
        return client.update_status_paused(
            object_id=payload.get('target_meta_id', ''),
            level=payload.get('target_type'))
    if kind == EngineAction.Kind.EDIT_COPY:
        # ADSDEEP31 — édition du texte / créatif d'une ad EXISTANTE. Route vers
        # ``swap_ad_creative`` (crée un NOUVEAU adcreative puis rattache — dossier
        # §4) : aucun ``status`` n'est envoyé (jamais d'activation, invariant #3).
        return client.swap_ad_creative(
            ad_id=payload.get('ad_id', ''),
            creative_spec=payload.get('creative_spec'),
            creative_id=payload.get('creative_id'),
            extra_fields=payload.get('extra_fields'))
    if kind == EngineAction.Kind.SET_SPEND_CAP:
        # ADSDEEP31 — plafond de dépense TOTAL d'une campagne. Un plafond ne peut
        # QUE limiter la dépense (jamais activer) — aucun ``status`` envoyé.
        return client.set_campaign_spend_cap(
            campaign_id=payload.get('campaign_id', ''),
            spend_cap=payload.get('spend_cap'),
            extra_fields=payload.get('extra_fields'))
    if kind == EngineAction.Kind.RENAME:
        # ADSDEEP31 — renommage (name uniquement). N'active ni ne dé-pause rien.
        return client.rename_object(
            object_id=payload.get('object_id', ''),
            name=payload.get('name', ''),
            extra_fields=payload.get('extra_fields'))
    if kind in (KIND_INCREASE_PACE, KIND_REBALANCE_ADSET_BUDGET):
        # ADSENG22 — Changement de budget ad set (increase_pace / rebalance).
        # Les garde-fous budget ont été appliqués AVANT par
        # ``_guard_before_dispatch`` (plafond + variation hebdo + pas ≤15% + G4
        # + propriété miroir) ; on route vers la même méthode budget que
        # REBALANCE_BUDGET (un client réel qui ne l'expose pas encore lève →
        # « echouee », jamais d'activation ni d'application silencieuse).
        return client.update_adset_budget(
            adset_id=payload.get('adset_id', ''),
            daily_budget=payload.get('daily_budget'),
            extra_fields=payload.get('extra_fields'))
    if kind == KIND_DUPLICATE:
        # ADSDEEP37 — duplication (adset + 1 ad réutilisant le créatif LIVE de
        # la source). Les 2 créations internes sont TOUJOURS PAUSED (garanti par
        # meta_client — invariant permanent règle #3).
        return client.duplicate_adset_with_ad(
            campaign_id=payload.get('campaign_id', ''),
            new_adset_name=payload.get('new_adset_name', ''),
            new_ad_name=payload.get('new_ad_name', ''),
            creative_id=payload.get('creative_id', ''),
            adset_extra_fields=payload.get('adset_extra_fields'),
            ad_extra_fields=payload.get('ad_extra_fields'))
    if kind == KIND_SET_SCHEDULE:
        # ADSDEEP36 — horaire NATIF (adset_schedule). Aucun ``status`` n'est
        # jamais envoyé (invariant permanent règle #3).
        return client.set_adset_schedule(
            adset_id=payload.get('adset_id', ''),
            adset_schedule=payload.get('adset_schedule', []),
            extra_fields=payload.get('extra_fields'))
    if kind == KIND_CREATE_AD_STUDY:
        # ADSDEEP34 — étude A/B native (ad_studies SPLIT_TEST_V2). Aucun
        # ``status`` n'est jamais envoyé (une étude n'en porte pas) ; les cellules
        # référencent des objets DÉJÀ nés PAUSED par le reste du moteur.
        return client.create_ad_study(
            name=payload.get('name', ''), cells=payload.get('cells', []),
            extra_fields=payload.get('extra_fields'))
    if kind == KIND_EDIT_POST:
        # ADSDEEP50 — édition du TEXTE d'un post de Page (message SEUL, le visuel
        # d'un post publié est immuable). La contrainte « app-created only » a été
        # vérifiée à la proposition (``propose_edit_post`` refuse un post non créé
        # par l'app) ; aucun ``status`` n'est envoyé (invariant permanent #3).
        return client.edit_page_post(
            post_id=payload.get('post_id', ''),
            message=payload.get('message', ''),
            extra_fields=payload.get('extra_fields'))
    if kind == KIND_CREATE_POST:
        # ADSDEEP51 — publication organique (publié / dark / programmé ; texte /
        # photo / multi-photos / vidéo). Ce n'est pas un objet publicitaire —
        # aucun ``status`` de campagne/adset/ad n'est en jeu.
        return _dispatch_create_post(client, payload)
    if kind == KIND_BOOST_POST:
        # ADSDEEP52 — boost d'un post existant : adcreative object_story_id
        # (preuve sociale préservée) → ad née PAUSED (garanti par meta_client,
        # invariant permanent règle #3 : aucune activation possible).
        return client.boost_page_post(
            post_id=payload.get('post_id', ''),
            adset_id=payload.get('adset_id', ''),
            name=payload.get('name', ''),
            extra_fields=payload.get('extra_fields'))
    if kind == KIND_HIDE_COMMENT:
        # ADSDEEP53 — masquage/démasquage AVEC READ-BACK obligatoire (le badge
        # « caché-vérifié » ne s'allume que si le re-GET confirme). Aucun statut
        # d'objet publicitaire en jeu.
        return _dispatch_hide_comment(client, action)
    if kind == KIND_REPLY_COMMENT:
        # ADSDEEP53 — réponse publique à un commentaire.
        return _dispatch_reply_comment(client, action)
    if kind == KIND_DELETE_COMMENT:
        # ADSDEEP53 — suppression d'un commentaire (miroir local retiré).
        return _dispatch_delete_comment(client, action)
    if kind == KIND_PRIVATE_REPLY:
        # ADSDEEP53 — réponse privée (DM) : garde « une seule / 7 j » posée à la
        # proposition ; l'application horodate le miroir pour bloquer une 2e.
        return _dispatch_private_reply(client, action)
    if kind == KIND_PUBLISH_IG:
        # ADSDEEP55 — publication Instagram via le flux container (create → poll
        # FINISHED → publish, quota 50/24 h vérifié). Caption immuable, jamais
        # ré-éditée. Aucun statut de campagne/adset/ad en jeu.
        return _dispatch_publish_ig(client, action)
    if kind == KIND_HIDE_IG_COMMENT:
        return _dispatch_hide_ig_comment(client, action)
    if kind == KIND_REPLY_IG_COMMENT:
        return _dispatch_reply_ig_comment(client, action)
    if kind == KIND_DELETE_IG_COMMENT:
        return _dispatch_delete_ig_comment(client, action)
    if kind == KIND_TOGGLE_IG_COMMENTS:
        # ADSDEEP55 — couper/rouvrir les commentaires (comment_enabled — SEUL
        # champ écrivable d'un média IG ; la légende reste immuable).
        return _dispatch_toggle_ig_comments(client, action)
    if kind == KIND_ENABLE_CBO:
        # ADSENG22 — ``enable_cbo`` est PROPOSE-ONLY : activer l'Advantage+
        # campaign budget (CBO) est une décision HUMAINE hors moteur — jamais
        # appliquée programmatiquement (aucune méthode client, par conception).
        # Une tentative d'apply lève → l'action passe « echouee » (jamais Meta).
        raise ValueError(
            "enable_cbo est propose-only : l'activation CBO (Advantage+ "
            "campaign budget) est une décision humaine hors moteur, jamais "
            "appliquée programmatiquement par le moteur.")
    raise ValueError(f"Type d'action non routable : {kind}")


def _centimes_to_mad(value):
    """ENGFIX1/G2 — Centimes (unités mineures Meta) → MAD (unités majeures).

    ``None`` reste ``None`` (le garde-fou le traitera comme inopérant → blocage
    fail-safe) ; une valeur illisible est renvoyée telle quelle pour que la règle
    lève ``GuardrailInoperative`` plutôt que d'être silencieusement ignorée."""
    if value is None:
        return None
    try:
        return float(value) / CENTIMES_PER_MAD
    except (TypeError, ValueError):
        return value


def _guard_before_dispatch(action):
    """ENGFIX1 — Applique les garde-fous AVANT tout appel au client Meta.

    Câble les checks de ``guardrails`` (jusqu'ici définis mais JAMAIS appelés sur
    le chemin d'``apply``), pour que ``_dispatch`` n'atteigne jamais le client sur
    une action qui viole un garde-fou :

    * ``REBALANCE_BUDGET`` → plafond quotidien (``check_daily_ceiling``) +
      variation hebdomadaire (``check_weekly_change``). Le budget du payload
      (``daily_budget`` = nouveau, ``current_budget`` = courant) est en CENTIMES
      (unités mineures Meta) ; on le convertit en MAD (÷100) avant de le comparer
      au plafond MAD. La variation en % est indépendante de l'unité (ratio) — on
      convertit tout de même par cohérence de contrat.
    * Toute transition de statut explicite (``payload['target_status']``) →
      ``enforce_paused_only`` + ``enforce_never_activate`` (PAUSED-only, jamais
      d'activation — invariant permanent règle #3).

    Lève ``GuardrailViolation`` / ``GuardrailInoperative`` (budget/courant manquant
    → règle inopérante = blocage fail-safe, jamais un skip silencieux) ; l'appelant
    ``apply_action`` marque alors l'action ``echouee`` et relance."""
    from .models import GuardrailConfig
    payload = action.payload or {}
    config = GuardrailConfig.objects.filter(company=action.company).first()

    if action.kind == EngineAction.Kind.REBALANCE_BUDGET:
        new_mad = _centimes_to_mad(payload.get('daily_budget'))
        current_mad = _centimes_to_mad(payload.get('current_budget'))
        guardrails.check_daily_ceiling(config, new_mad, company=action.company)
        guardrails.check_weekly_change(
            config, current_budget=current_mad, new_budget=new_mad,
            company=action.company)

    # ADSENG22 — kinds trésorerie de budget (increase_pace / rebalance_adset_
    # budget) : mêmes garde-fous budget + DEFER (propriété miroir) + pas ≤15% +
    # G4 (ligne de base à 7 jours). Bloc DISJOINT du REBALANCE_BUDGET ci-dessus
    # (dont la logique reste inchangée : aucune validation miroir rétroactive).
    if action.kind in _TREASURY_BUDGET_KINDS:
        from . import budget_applier, pacing
        new_mad = _centimes_to_mad(payload.get('daily_budget'))
        current_mad = _centimes_to_mad(payload.get('current_budget'))
        # DEFER ADSENG21 — cible = ad set POSSÉDÉ (jamais un id hors miroirs).
        budget_applier.validate_adset_target(action.company, payload)
        guardrails.check_daily_ceiling(config, new_mad, company=action.company)
        guardrails.check_weekly_change(
            config, current_budget=current_mad, new_budget=new_mad,
            company=action.company)
        # Pas quotidien ≤ 15 % (belt-and-suspenders au-delà du plafond hebdo).
        budget_applier.assert_step_within_cap(
            current_mad, new_mad, company=action.company)
        # G4 — variation hebdo contre la VRAIE ligne de base à 7 jours (jamais
        # la veille) : N pas quotidiens ne composent pas au-delà de la limite.
        if config is not None:
            baseline = pacing.weekly_baseline_budget_mad(
                action.company, payload.get('adset_id'))
            if not pacing.weekly_change_within_baseline(
                    new_mad, baseline, config.weekly_change_pct_max):
                msg = (
                    "Variation hebdomadaire vs ligne de base 7 j > maximum "
                    f"{config.weekly_change_pct_max}% (anti-compounding G4).")
                guardrails.emit_alert(
                    action.company, alert_type=guardrails.ALERT_GUARDRAIL,
                    message=msg)
                raise guardrails.GuardrailViolation(msg)

    # Toute transition de statut demandée reste PAUSED-only (jamais d'activation).
    target_status = payload.get('target_status')
    if target_status:
        guardrails.enforce_paused_only(target_status, company=action.company)
        guardrails.enforce_never_activate(target_status, company=action.company)


def apply_action(action, *, connection=None, client=None):
    """Applique une action **UNIQUEMENT si elle est approuvée**.

    Garde de sécurité EN PREMIER : une action non ``approuvee`` lève
    ``ActionNotApproved`` AVANT toute construction/appel du client Meta (le
    client n'est jamais atteint).

    ENGFIX3 — Réclamation ATOMIQUE (compare-and-swap) : la transition
    ``approuvee → appliquee`` se fait par un ``UPDATE ... WHERE status=approuvee``
    unique (verrou de ligne du SGBD). Deux workers concurrents : le premier
    réclame (``claimed=1``) et dispatche ; le second voit 0 ligne encore
    ``approuvee`` (``claimed=0``) → ``ActionNotApproved`` — aucun double-dispatch,
    jamais d'objet Meta dupliqué. En cas d'échec Meta OU de violation de garde-fou
    (ENGFIX1) APRÈS réclamation, l'action est repassée ``echouee`` (jamais laissée
    faussement ``appliquee``) et l'exception relancée ; en cas de succès elle
    reste ``appliquee`` (``applied_at`` + ``result`` posés côté serveur).
    """
    from django.db import transaction

    # Garde de sécurité rapide (non atomique) : une action non approuvée est
    # refusée d'emblée, avant toute construction de client. Le compare-and-swap
    # ci-dessous reste l'AUTORITÉ anti-double-apply (l'objet en mémoire peut être
    # périmé ; la base tranche).
    if action.status != EngineAction.Statut.APPROUVEE:
        raise ActionNotApproved(
            "Action non approuvée : refus d'appliquer (le client Meta n'est "
            "jamais atteint).")

    if client is None:
        from .meta_client import MetaClient
        from .models import MetaConnection
        if connection is None:
            connection = MetaConnection.objects.filter(
                company=action.company, enabled=True).first()
        if connection is None:
            raise ActionNotApproved(
                "Aucune connexion Meta active : application impossible.")
        client = MetaClient.from_connection(connection)

    # ENGFIX3 — Réclamation atomique : SEULE une ligne encore ``approuvee`` en
    # base peut être réclamée (elle passe ``appliquee`` dans le même UPDATE).
    with transaction.atomic():
        claimed = (EngineAction.objects
                   .filter(pk=action.pk,
                           status=EngineAction.Statut.APPROUVEE)
                   .update(status=EngineAction.Statut.APPLIQUEE))
    if claimed != 1:
        raise ActionNotApproved(
            "Action déjà réclamée ou non approuvée : refus d'appliquer (aucun "
            "double-dispatch — le client Meta n'est pas rappelé).")
    # Réaligne l'objet en mémoire sur l'état réclamé.
    action.status = EngineAction.Statut.APPLIQUEE

    try:
        # ENGFIX1 — garde-fous AVANT le dispatch : une violation lève ici et le
        # client n'est jamais appelé (l'action repasse « echouee » ci-dessous).
        _guard_before_dispatch(action)
        result = _dispatch(client, action)
    except Exception as exc:
        # Un échec APRÈS réclamation ne doit pas laisser l'action faussement
        # « appliquee » : on la repasse « echouee » (erreur consignée) et on
        # relance.
        action.status = EngineAction.Statut.ECHOUEE
        action.error = str(exc)
        action.save(update_fields=['status', 'error', 'updated_at'])
        raise

    action.applied_at = timezone.now()
    action.result = result if isinstance(result, dict) else {'result': result}
    action.error = ''
    action.save(
        update_fields=['status', 'applied_at', 'result', 'error', 'updated_at'])
    return action


# ── ADSDEEP33 — Lot (batch) : kinds SIMPLES routables en UN SEUL appel Graph ──
# Limite de lot — miroir de ``MetaClient.MAX_BATCH_OPERATIONS`` (dupliquée en
# constante simple ici pour éviter d'instancier un client rien que pour lire la
# borne avant même de savoir s'il y en a un).
MetaClientBatchLimit = 50

# Un kind hors de cette liste (ex. EDIT_COPY, CREATE_AD, DUPLICATE — plusieurs
# appels réseau internes) reste dispatché INDIVIDUELLEMENT via ``apply_action``.
_BATCHABLE_KINDS = frozenset({
    EngineAction.Kind.RENAME, EngineAction.Kind.SET_SPEND_CAP,
    EngineAction.Kind.PAUSE, KIND_PAUSE_FOR_MONTH,
})


def _build_batch_op(client, action):
    """ADSDEEP33 — Construit l'opération de lot (method/relative_url/body) pour
    UNE action APPROUVÉE dont le kind est batchable. Lève ``ValueError`` pour un
    kind non batchable (jamais un lot silencieusement incomplet)."""
    payload = action.payload or {}
    kind = action.kind
    if kind == EngineAction.Kind.RENAME:
        return client.build_batch_op_rename(
            object_id=payload.get('object_id', ''), name=payload.get('name', ''))
    if kind == EngineAction.Kind.SET_SPEND_CAP:
        return client.build_batch_op_spend_cap(
            campaign_id=payload.get('campaign_id', ''),
            spend_cap=payload.get('spend_cap'))
    if kind in (EngineAction.Kind.PAUSE, KIND_PAUSE_FOR_MONTH):
        guardrails.enforce_paused_only('PAUSED', company=action.company)
        return client.build_batch_op_pause(object_id=payload.get('target_meta_id', ''))
    raise ValueError(f"Kind non batchable pour le lot ADSDEEP33 : {kind}")


def apply_batch(actions, *, connection=None, client=None):
    """ADSDEEP33 — Applique un LOT d'actions APPROUVÉES en UN SEUL appel Graph
    (``POST /?batch=``, ≤50 opérations, PAS transactionnel — dossier §8).

    Chaque action est RÉCLAMÉE (CAS ``approuvee → appliquee``) INDIVIDUELLEMENT
    et AVANT tout appel réseau — exactement la même discipline qu'``apply_action``
    (ENGFIX3) : le journal EngineAction (ids déjà réclamés) est l'unique dédup,
    Graph n'ayant AUCUNE clé d'idempotence. Un échec PARTIEL du lot (ex. l'opération
    2/3 renvoie une erreur) laisse les opérations RÉUSSIES ``appliquee`` et
    repasse SEULEMENT la ou les opérations en échec ``echouee`` — jamais tout
    le lot invalidé pour la faute d'une seule (PAS transactionnel, comme Graph
    lui-même). ``error_user_msg`` est repris VERBATIM dans ``action.error``.

    Renvoie la liste des actions (même ordre que l'entrée), chacune avec son
    statut final exact."""
    if not actions:
        return []
    if len(actions) > MetaClientBatchLimit:
        raise ValueError(
            f"Un lot est limité à {MetaClientBatchLimit} opérations Graph.")

    for action in actions:
        if action.status != EngineAction.Statut.APPROUVEE:
            raise ActionNotApproved(
                "Action non approuvée : refus d'appliquer en lot (le client "
                "Meta n'est jamais atteint).")

    if client is None:
        from .meta_client import MetaClient
        from .models import MetaConnection
        company = actions[0].company
        if connection is None:
            connection = MetaConnection.objects.filter(
                company=company, enabled=True).first()
        if connection is None:
            raise ActionNotApproved(
                "Aucune connexion Meta active : application impossible.")
        client = MetaClient.from_connection(connection)

    from django.db import transaction

    # Réclamation atomique de CHAQUE action AVANT tout appel réseau — le journal
    # (statut déjà passé APPLIQUEE en base) est l'unique dédup si le lot entier
    # doit être rejoué après une panne (Graph n'a aucune clé d'idempotence).
    claimed_actions = []
    for action in actions:
        with transaction.atomic():
            claimed = (EngineAction.objects
                       .filter(pk=action.pk, status=EngineAction.Statut.APPROUVEE)
                       .update(status=EngineAction.Statut.APPLIQUEE))
        if claimed != 1:
            raise ActionNotApproved(
                "Action déjà réclamée ou non approuvée : refus d'appliquer en "
                "lot (aucun double-dispatch).")
        action.status = EngineAction.Statut.APPLIQUEE
        claimed_actions.append(action)

    # Garde-fous AVANT dispatch + construction de l'opération — une violation ou
    # un kind non batchable ne fait échouer QUE cette action-là.
    ops, batchable = [], []
    for action in claimed_actions:
        try:
            _guard_before_dispatch(action)
            if action.kind not in _BATCHABLE_KINDS:
                raise ValueError(
                    f"Kind non batchable pour le lot ADSDEEP33 : {action.kind}")
            op = _build_batch_op(client, action)
        except Exception as exc:
            action.status = EngineAction.Statut.ECHOUEE
            action.error = str(exc)
            action.save(update_fields=['status', 'error', 'updated_at'])
            continue
        ops.append(op)
        batchable.append(action)

    if not batchable:
        return claimed_actions

    try:
        results = client.batch_execute(ops)
    except Exception as exc:
        # Panne du lot ENTIER (réseau/HTTP) — repasse toutes les opérations
        # encore en jeu en échec (jamais laissées faussement « appliquee »).
        for action in batchable:
            action.status = EngineAction.Statut.ECHOUEE
            action.error = str(exc)
            action.save(update_fields=['status', 'error', 'updated_at'])
        return claimed_actions

    for action, result in zip(batchable, results):
        if result.get('success'):
            action.applied_at = timezone.now()
            action.result = result.get('body') or {}
            action.error = ''
            action.save(update_fields=[
                'status', 'applied_at', 'result', 'error', 'updated_at'])
        else:
            # ``error_user_msg`` FAIT pour être montré verbatim à l'approbateur
            # (dossier §8) ; repli sur le message brut si absent.
            action.status = EngineAction.Statut.ECHOUEE
            action.error = (
                result.get('error_user_msg')
                or (result.get('error') or {}).get('message', '')
                or 'Échec Graph (lot).')
            action.save(update_fields=['status', 'error', 'updated_at'])

    return claimed_actions


def execute_auto_action(company, *, kind, reason_fr, payload=None,
                        config=None, client=None, connection=None):
    """ENG8 — Exécute une action en respectant les toggles de capacités.

    * Capacité NON activée pour ce ``kind`` (défaut) → l'action est simplement
      PROPOSÉE (``auto=False``) : le chemin humain propose→approuve→applique reste
      obligatoire, comme pour tout le reste.
    * Capacité ACTIVÉE → on saute l'approbation humaine, MAIS on écrit quand même
      une ligne ``EngineAction`` (``auto=True``) marquée approuvée côté SYSTÈME
      (jamais un ``approved_by`` humain), on JOURNALISE, puis on applique via
      ``apply_action`` (qui passe par ``meta_client`` — statut PAUSED garanti,
      jamais d'activation). La trace d'audit existe toujours.

    ``config`` : ``GuardrailConfig`` de la société (résolue si non fournie).
    """
    if config is None:
        from .models import GuardrailConfig
        config = GuardrailConfig.objects.filter(company=company).first()

    if not capability_enabled(config, kind):
        # Capacité non activée → approbation humaine requise (aucun auto-apply).
        return propose_action(
            company, kind=kind, reason_fr=reason_fr, payload=payload, auto=False)

    if not (reason_fr and str(reason_fr).strip()):
        raise ValueError(
            "Une raison en une phrase (français) est obligatoire.")

    # ENG15 — même en auto, un asset non validé policy ne part jamais en prod.
    assert_creative_ok_for_ad(company, kind, payload)

    # Capacité activée : trace d'audit auto=True, approuvée côté système, appliquée.
    action = EngineAction.objects.create(
        company=company, kind=kind, payload=payload or {},
        reason_fr=str(reason_fr).strip(),
        status=EngineAction.Statut.APPROUVEE, auto=True)
    logger.info(
        'ENG8 auto-apply capacité=%s kind=%s société=%s action=%s',
        CAPABILITY_FOR_KIND.get(kind), kind, company.pk, action.pk)
    return apply_action(action, client=client, connection=connection)
