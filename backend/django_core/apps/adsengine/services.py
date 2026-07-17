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
    payload = dict(payload or {})
    _merge_warnings(payload, edit_warnings(kind, payload))
    return EngineAction.objects.create(
        company=company, kind=kind, payload=payload,
        reason_fr=str(reason_fr).strip(),
        status=EngineAction.Statut.PROPOSEE, auto=auto)


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
