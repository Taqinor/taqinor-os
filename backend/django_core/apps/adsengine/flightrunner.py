"""ADSENG35 — ``FlightRunner`` : la machine à états de l'orchestrateur autonome.

C'est la pièce qui NOUE tout ce que P1-P5 ont bâti (bandit, allocation, pacing,
rotation, gardien, briefs, plans de vol, gabarits de lancement) en UNE machine à
états qui exécute un ``FlightPlan`` validé :

  * ``materialize`` — matérialise les phases (préflight ADSENG28) puis crée, via
    le gabarit ADSENG24, des structures Meta **nées PAUSED** (règle #3, forcé par
    ``meta_client``). Le go-live est un **unpause HUMAIN** — le runner ne dé-pause
    JAMAIS rien par programme (invariant permanent re-testé ici).
  * ``run_daily`` — boucle quotidienne : synchro → bandit (repondération +
    ``DecisionLog`` par expérience, ADSENG12/21) → gardien (ENG9, propose-only).
  * ``run_weekly`` — boucle hebdo : rotation (ADSENG25, propose-only), kill/
    promote (propose-only), brief (ENG11).
  * ``advance_phase`` — transitions de phase selon la fenêtre calendaire ; fin de
    plan ⇒ ``FlightPlan.Statut.TERMINE`` + rapport de fin de plan.
  * ``engage_kill_switch`` — **interrupteur global** : un drapeau (cache) met en
    pause TOUT ce que le moteur a créé, via le client (donc PAUSED-safe — jamais
    un flip DB qui court-circuiterait Meta), et fait no-op les boucles.

INVARIANT PERMANENT (règle #3, re-testé) : AUCUN chemin de ce module n'active ni
ne dé-pause quoi que ce soit. Le client n'expose aucune méthode d'activation ;
les seules écritures Meta possibles sont ``create_*`` (PAUSED forcé) et
``update_status_paused`` (PAUSED-only). Le kill-switch pause, ne relâche jamais.

IDEMPOTENCE (défer Fable G3) : les chemins de CRÉATION sont idempotents sous
retry — un POST Meta rejoué après une réponse perdue ne doit PAS créer d'objet en
double. La dédup se fait par **contrôle de nom** contre l'inventaire vivant
(``get_campaigns``/``get_adsets``) AVANT tout POST : si un objet du même nom
existe déjà, on réutilise son id au lieu de re-poster.

Multi-tenant : la société est TOUJOURS dérivée du plan (jamais reçue de
l'extérieur). Ce module reste dans ``apps/adsengine`` (lecture des autres apps
uniquement via leurs ``selectors``/``services`` — non requis ici).
"""
from __future__ import annotations

import datetime
import logging

from django.core.cache import cache
from django.utils import timezone

from . import (
    backlog as backlog_mod,
    brief as brief_mod,
    decisionlog,
    flightplan as flightplan_mod,
    guardrails,
    launch_templates,
    rotation,
)
from .models import (
    AdCampaignMirror,
    AdSetMirror,
    ArmDailyStat,
    DecisionLog,
    EngineAction,
    Experiment,
    ExperimentArm,
    FlightPhase,
    FlightPlan,
    GuardrailConfig,
)

logger = logging.getLogger(__name__)

# Gabarit de lancement par défaut si une phase n'en précise aucun.
DEFAULT_TEMPLATE = 'resid_ctwa'

# Durée de vie (secondes) du drapeau kill-switch en cache. Long (30 j) : le
# kill-switch doit SURVIVRE aux redémarrages tant qu'un humain ne le relâche pas.
KILL_SWITCH_TTL = 60 * 60 * 24 * 30

# Durée de vie (secondes) du drapeau « autonomie activée » en cache (30 j).
AUTONOMY_TTL = 60 * 60 * 24 * 30

# ── PUB120 — Clés de gabarit des propositions issues de la rotation hebdo ──────
# ``plan_rotation`` (ADSENG25) CALCULAIT déjà sorties/revues/entrées et
# ``run_weekly`` ne faisait que les COMPTER : le backlog ne devenait jamais des
# ads. Chaque décision est désormais MATÉRIALISÉE en PROPOSITION (jamais une
# application, jamais un unpause). Ces clés estampillent ``payload['template_key']``
# pour que la dédup au niveau proposeur (``rules_engine._recently_acted``) couvre
# la rotation : un re-run la MÊME semaine ne duplique rien.
ROTATION_TEMPLATE_EXIT = 'rotation_exit'
ROTATION_TEMPLATE_ENTRY = 'rotation_entry'
ROTATION_TEMPLATE_REVIEW = 'rotation_review'

# Durée de vie (secondes) de la série de semaines faibles par bras (90 j) : elle
# doit SURVIVRE aux semaines pour que la règle des deux coups ait un sens.
WEAK_STREAK_TTL = 60 * 60 * 24 * 90

# PUB121 — clé de gabarit des alertes « ad set sans créatif » au lancement.
LAUNCH_TEMPLATE_CREATIVE = 'launch_adset_creative'


# ── Drapeau d'autonomie PAR société (DB = source de vérité, cache = accélérateur)
# L'activation est OFF PAR DÉFAUT et ne peut être posée QUE via ``preflight.
# activate`` (ADSENG38), qui exige d'abord que TOUTES les portes soient vertes —
# c'est la garantie structurelle « le mode autonome ne peut PAS s'activer tant que
# tout n'est pas vert ». Ces helpers sont bas-niveau (le gate vit dans preflight).
# PUB21 : l'état est PERSISTÉ (``GuardrailConfig.autonomy_active``) ; le cache
# n'est qu'un accélérateur ré-échauffé depuis la DB sur miss — un flush/restart
# ne perd donc jamais l'état.
def _autonomy_key(company):
    return f'adsengine:autonomy:{company.pk}'


def _db_autonomy_active(company):
    """Lecture de la SOURCE DE VÉRITÉ (DB). Absence de config = non activé."""
    config = GuardrailConfig.objects.filter(company=company).first()
    return bool(config and config.autonomy_active)


def is_autonomy_active(company):
    """Vrai si le mode autonome est ACTIVÉ pour cette société (OFF par défaut).

    PUB21 : cache d'abord (accélérateur) ; sur miss (flush/restart), on lit la DB
    (source de vérité) et on ré-échauffe le cache — l'état survit à un flush."""
    key = _autonomy_key(company)
    cached = cache.get(key)
    if cached is not None:
        return bool(cached)
    active = _db_autonomy_active(company)
    cache.set(key, active, AUTONOMY_TTL)
    return active


def set_autonomy_active(company, active):
    """Pose/retire le drapeau d'autonomie (bas-niveau — appelé par
    ``preflight.activate``/``preflight.deactivate`` APRÈS la garde préflight,
    jamais directement pour contourner le gate).

    PUB21 : écrit la DB (source de vérité) PUIS le cache (accélérateur)."""
    active = bool(active)
    config, _ = GuardrailConfig.objects.get_or_create(company=company)
    if config.autonomy_active != active:
        config.autonomy_active = active
        config.save(update_fields=['autonomy_active'])
    if active:
        cache.set(_autonomy_key(company), True, AUTONOMY_TTL)
    else:
        cache.delete(_autonomy_key(company))


class FlightRunner:
    """Machine à états exécutant UN ``FlightPlan``.

    États (persistants, dérivés des données — jamais un champ modèle ajouté) :

      * ``DRAFT``      — plan en brouillon, non matérialisé ;
      * ``ACTIVE``     — phases matérialisées (structures PAUSED), boucles
        quotidienne/hebdo actives ; le go-live reste un unpause HUMAIN ;
      * ``COMPLETED``  — dernière phase franchie → plan terminé + rapport ;
      * ``KILLED``     — interrupteur global engagé (tout est en pause).

    ``client`` : une **``platforms.AdsPlatform``** (ADSENG48) — le runner ne parle
    qu'au CONTRAT abstrait (``get_*``/``create_*`` PAUSED/``update_status_paused``),
    jamais à un client concret ; ``MetaPlatform`` en est l'implémentation, un faux
    injecté (tests / simulateur ADSENG36) suffit tant qu'il respecte le contrat.
    ``clock`` : callable ``() -> date`` injectable (horloge accélérée du
    simulateur) ; défaut = ``datetime.date.today``.
    """

    STATE_DRAFT = 'draft'
    STATE_ACTIVE = 'active'
    STATE_COMPLETED = 'completed'
    STATE_KILLED = 'killed'

    def __init__(self, plan, *, client=None, clock=None):
        self.plan = plan
        self.company = plan.company
        self._client = client
        self._clock = clock or (lambda: datetime.date.today())

    # ── Horloge injectable ───────────────────────────────────────────────────
    def today(self):
        return self._clock()

    # ── Interrupteur global (kill-switch) ────────────────────────────────────
    def _kill_key(self):
        return f'adsengine:killswitch:{self.company.pk}'

    def _db_kill_engaged(self):
        """Lecture de la SOURCE DE VÉRITÉ (DB). Absence de config = non engagé."""
        config = GuardrailConfig.objects.filter(company=self.company).first()
        return bool(config and config.kill_switch_engaged)

    def is_killed(self):
        """Vrai si l'interrupteur global est engagé pour cette société.

        PUB21 : la DB (``GuardrailConfig.kill_switch_engaged``) est la SOURCE DE
        VÉRITÉ ; le cache n'est qu'un accélérateur. Sur miss (flush/restart), on
        relit la DB et on ré-échauffe le cache — un arrêt d'urgence ne peut donc
        JAMAIS être relâché silencieusement par un flush cache."""
        key = self._kill_key()
        cached = cache.get(key)
        if cached is not None:
            return bool(cached)
        engaged = self._db_kill_engaged()
        cache.set(key, engaged, KILL_SWITCH_TTL)
        return engaged

    def engage_kill_switch(self, *, client=None, reason_fr=''):
        """ADSENG35 — Interrupteur GLOBAL : met en pause TOUT ce que le moteur a
        créé (mirrors ``created_via_engine=True``), via le client (PAUSED-safe —
        ``update_status_paused`` force PAUSED, jamais une activation, jamais un
        flip DB qui contournerait Meta), puis lève le drapeau (cache) qui fait
        no-op toutes les boucles.

        Chaque pause écrit une ligne ``EngineAction`` (actions-log) ; l'ensemble
        écrit une transition. Renvoie ``{'paused': n, 'targets': [...]}``.
        Idempotent : ré-engager ne double aucune pause (dédup mirror par mirror
        via la garde du client PAUSED-only, et le drapeau reste levé)."""
        client = client or self._client
        reason_fr = reason_fr or (
            "Interrupteur global engagé : mise en pause de toutes les "
            "structures créées par le moteur (sécurité).")
        # PUB21 — DB = source de vérité, écrite AVANT le cache : l'arrêt d'urgence
        # survit à un flush/restart infra (un kill-switch de sécurité ne doit
        # jamais disparaître tant qu'un humain ne l'a pas relâché).
        config, _ = GuardrailConfig.objects.get_or_create(company=self.company)
        config.kill_switch_engaged = True
        if config.kill_switch_engaged_at is None:
            config.kill_switch_engaged_at = timezone.now()
        config.kill_switch_reason = reason_fr
        config.save(update_fields=['kill_switch_engaged',
                                   'kill_switch_engaged_at',
                                   'kill_switch_reason'])
        cache.set(self._kill_key(), True, KILL_SWITCH_TTL)

        targets = []
        if client is not None:
            for mirror, level in self._engine_created_targets():
                try:
                    client.update_status_paused(
                        object_id=mirror.meta_id, level=level)
                except Exception as exc:  # noqa: BLE001 — best-effort par cible
                    logger.warning(
                        'flightrunner: kill-switch pause échouée pour %s : %s',
                        mirror.meta_id, exc)
                    continue
                self._log_action(
                    kind=EngineAction.Kind.PAUSE,
                    reason_fr=reason_fr,
                    payload={'target_type': level,
                             'target_meta_id': mirror.meta_id,
                             'kill_switch': True},
                    result={'paused': True})
                targets.append(mirror.meta_id)

        self._log_transition(
            self.state(), self.STATE_KILLED,
            summary_fr=(f"Interrupteur global engagé — {len(targets)} "
                        f"structure(s) mise(s) en pause."))
        logger.info('flightrunner: kill-switch ENGAGÉ société=%s (%s cible[s])',
                    self.company.pk, len(targets))
        return {'paused': len(targets), 'targets': targets}

    def release_kill_switch(self):
        """Relâche le drapeau kill-switch. NE DÉ-PAUSE RIEN (invariant : le
        re-lancement d'une structure est un unpause HUMAIN, jamais programmatique)
        — les structures restent PAUSED jusqu'à une action humaine hors moteur.

        PUB21 : lève l'état persisté (DB, source de vérité) PUIS purge le cache."""
        config = GuardrailConfig.objects.filter(company=self.company).first()
        if config is not None and (
                config.kill_switch_engaged or config.kill_switch_engaged_at):
            config.kill_switch_engaged = False
            config.kill_switch_engaged_at = None
            config.save(update_fields=['kill_switch_engaged',
                                       'kill_switch_engaged_at'])
        cache.delete(self._kill_key())
        logger.info('flightrunner: kill-switch relâché société=%s (aucune '
                    'structure dé-pausée — unpause humain requis)',
                    self.company.pk)
        return {'released': True, 'unpaused': 0}

    def _engine_created_targets(self):
        """Itère ``(mirror, level)`` de tout ce que le moteur a créé (campagnes
        puis ad sets), pour le kill-switch. Les ads héritent de la pause de leur
        ad set côté Meta ; on cible les niveaux campagne + ad set (suffisant et
        borné)."""
        for camp in AdCampaignMirror.objects.filter(
                company=self.company, created_via_engine=True):
            yield camp, 'campaign'
        for adset in AdSetMirror.objects.filter(
                company=self.company, created_via_engine=True):
            yield adset, 'adset'

    # ── État courant (dérivé, jamais un champ modèle) ────────────────────────
    def state(self):
        if self.is_killed():
            return self.STATE_KILLED
        status = self.plan.status
        if status == FlightPlan.Statut.TERMINE:
            return self.STATE_COMPLETED
        if status == FlightPlan.Statut.BROUILLON:
            return self.STATE_DRAFT
        return self.STATE_ACTIVE

    # ── Transition 1 : matérialisation (DRAFT → ACTIVE) ──────────────────────
    def materialize(self, phase_specs=None, *, client=None, city='',
                    today=None, mde_check=None):
        """DRAFT → ACTIVE : valide le plan (préflight ADSENG28) et matérialise ses
        phases. Puis, si un client est disponible, crée les structures Meta de la
        PREMIÈRE phase — **nées PAUSED** (règle #3). Le go-live est un unpause
        HUMAIN : ce runner ne dé-pause jamais.

        Lève ``ValueError`` (raisons FR du préflight) si le plan est invalide —
        aucune phase n'est alors créée. Renvoie un dict de rapport."""
        client = client or self._client
        specs = (phase_specs if phase_specs is not None
                 else flightplan_mod.default_phase_specs())
        today = today or self.today()

        # Matérialise les phases (préflight inclus ; lève si invalide).
        phases = flightplan_mod.materialize(
            self.plan, specs, today=today, mde_check=mde_check)
        self.plan.refresh_from_db()

        created = {}
        if client is not None and phases:
            created = self._launch_phase(phases[0], client=client, city=city)

        self._log_transition(
            self.STATE_DRAFT, self.STATE_ACTIVE,
            summary_fr=(f"Plan matérialisé en {len(phases)} phase(s) ; "
                        "structures de la 1re phase créées PAUSED "
                        "(unpause humain requis)."))
        return {
            'state': self.state(),
            'phases': len(phases),
            'launched': created,
        }

    def _launch_phase(self, phase, *, client, city=''):
        """Crée les structures Meta d'une phase — PAUSED, idempotentes (G3).

        Utilise le gabarit de lancement de la phase (ADSENG24) : une campagne +
        ses ad sets, tous PAUSED (le client force PAUSED de toute façon). La
        création est dédupliquée par nom contre l'inventaire vivant : un retry
        après réponse perdue réutilise l'objet existant au lieu d'en créer un
        doublon."""
        template_key = phase.launch_template or DEFAULT_TEMPLATE
        try:
            structure = launch_templates.dry_run_launch(
                template_key, city=city or 'Casablanca',
                launch_date=phase.start_date or self.today(),
                variant=(phase.tested_variable or 'A'),
                company=self.company,
                total_daily_budget_mad=phase.budget_mad or None)
        except ValueError as exc:
            logger.warning('flightrunner: gabarit inconnu %s (%s) — phase non '
                           'lancée', template_key, exc)
            return {}

        campaign = structure['campaign']
        camp_id, camp_reused = self._idempotent_create_campaign(
            client, name=campaign['name'], objective=campaign['objective'])

        adset_ids = []
        for adset in structure['adsets']:
            adset_id, _ = self._idempotent_create_adset(
                client, name=adset['name'], campaign_id=camp_id)
            adset_ids.append(adset_id)

        # PUB121 — les slots créatifs des ad sets sont remplis par des
        # PROPOSITIONS d'ads : un plan lancé sans aucune ad ne peut pas diffuser,
        # même entièrement approuvé.
        creatives = self._propose_phase_creatives(phase, adset_ids)

        return {
            'template': template_key,
            'campaign_id': camp_id,
            'campaign_reused': camp_reused,
            'adset_ids': adset_ids,
            'status': launch_templates.PAUSED_STATUS,
            'creatives': creatives,
        }

    # ── PUB121 — Slots créatifs remplis au lancement (propose-only) ───────────
    def _propose_phase_creatives(self, phase, adset_ids):
        """PUB121 — Pour chaque ad set créé, PROPOSE les ads de ses slots.

        Délègue à ``services.propose_adset_launch_ads`` (arbitrage DCO au
        cold-start, file de backlog de la campagne, puis créatif du gagnant) :
        chaque ad est une PROPOSITION née PAUSED à l'application — aucune
        création directe, aucun unpause.

        Un ad set sans aucun candidat produit une ALERTE explicite (jamais une
        coquille silencieuse). Renvoie
        ``{'proposed': n, 'alerts': n, 'by_adset': {meta_id: [action_ids]}}``."""
        from . import guardrails, services
        from .models import AdSetMirror

        summary = {'proposed': 0, 'alerts': 0, 'by_adset': {}}
        context_fr = (f"Lancement de la phase {phase.order} "
                      f"« {phase.name} » : ") if phase is not None else ''
        for meta_id in adset_ids:
            if not meta_id:
                continue
            adset = AdSetMirror.objects.filter(
                company=self.company, meta_id=meta_id).first()
            if adset is None:
                continue
            try:
                # L'horloge du RUNNER est la date de référence du lancement
                # (``_launch_phase`` datant déjà son gabarit sur ``self.today()``) :
                # c'est elle qui borne la moisson du pool gagnant et la
                # date-au-plus-tôt des items de backlog (PUB-P8/C7), jamais
                # l'heure murale du serveur.
                result = services.propose_adset_launch_ads(
                    self.company, adset=adset, now=self.today(),
                    context_fr=context_fr)
            except ValueError as exc:
                # ``AdsetWithoutCreative`` (aucun candidat) et ``DcoModeConflict``
                # (exclusion mutuelle) portent tous deux leur raison FR.
                guardrails.emit_alert(
                    self.company, alert_type=guardrails.ALERT_ANOMALY,
                    message=f'{context_fr}{exc}',
                    detail={'template_key': LAUNCH_TEMPLATE_CREATIVE,
                            'plan_id': self.plan.pk,
                            'target_type': 'adset',
                            'target_meta_id': meta_id})
                summary['alerts'] += 1
                summary['by_adset'][meta_id] = []
                continue
            actions = result.get('actions') or []
            summary['proposed'] += len(actions)
            summary['by_adset'][meta_id] = [a.pk for a in actions]
            if result.get('fallback_fr'):
                logger.info(
                    'flightrunner: ad set %s — bootstrap DCO impossible (%s), '
                    'slots remplis par les chemins ordinaires',
                    meta_id, result['fallback_fr'])
        return summary

    # ── Création idempotente (G3 : dédup par nom contre l'inventaire vivant) ──
    @staticmethod
    def _find_named(items, name):
        for it in items or []:
            if isinstance(it, dict) and it.get('name') == name:
                return it.get('id')
        return None

    def _idempotent_create_campaign(self, client, *, name, objective):
        """Crée une campagne PAUSED, ou réutilise l'existante du même nom (G3).

        Contrôle de nom AVANT le POST contre l'inventaire vivant Meta
        (``get_campaigns``) : survit à une réponse perdue puis retry (aucun
        doublon). Le miroir local est upserté ``created_via_engine=True``."""
        existing = self._find_named(
            self._safe_get(client, 'get_campaigns'), name)
        if existing:
            self._mirror_campaign(existing, name, objective)
            self._log_action(
                kind=EngineAction.Kind.CREATE_CAMPAIGN,
                reason_fr=(f"Campagne « {name} » déjà présente (dédup G3) — "
                           "réutilisée, aucun doublon créé."),
                payload={'name': name, 'objective': objective},
                result={'id': existing, 'reused': True, 'paused': True})
            return existing, True

        result = client.create_campaign(
            name=name, objective=objective) or {}
        meta_id = result.get('id') or ''
        self._mirror_campaign(meta_id, name, objective)
        self._log_action(
            kind=EngineAction.Kind.CREATE_CAMPAIGN,
            reason_fr=(f"Campagne « {name} » créée PAUSED (go-live = unpause "
                       "humain)."),
            payload={'name': name, 'objective': objective},
            result={'id': meta_id, 'reused': False, 'paused': True})
        return meta_id, False

    def _idempotent_create_adset(self, client, *, name, campaign_id):
        """Crée un ad set PAUSED, ou réutilise l'existant du même nom (G3)."""
        existing = self._find_named(
            self._safe_get(client, 'get_adsets'), name)
        if existing:
            self._mirror_adset(existing, name, campaign_id)
            self._log_action(
                kind=EngineAction.Kind.CREATE_ADSET,
                reason_fr=(f"Ad set « {name} » déjà présent (dédup G3) — "
                           "réutilisé, aucun doublon créé."),
                payload={'name': name, 'campaign_id': campaign_id},
                result={'id': existing, 'reused': True, 'paused': True})
            return existing, True

        result = client.create_adset(
            name=name, campaign_id=campaign_id) or {}
        meta_id = result.get('id') or ''
        self._mirror_adset(meta_id, name, campaign_id)
        self._log_action(
            kind=EngineAction.Kind.CREATE_ADSET,
            reason_fr=f"Ad set « {name} » créé PAUSED.",
            payload={'name': name, 'campaign_id': campaign_id},
            result={'id': meta_id, 'reused': False, 'paused': True})
        return meta_id, False

    @staticmethod
    def _safe_get(client, method_name):
        """Appelle ``client.<method_name>()`` en tolérant l'absence de méthode /
        une erreur réseau — la dédup dégrade proprement (on postera alors, quitte
        à ce que la dédup repose sur le miroir en second recours)."""
        fn = getattr(client, method_name, None)
        if not callable(fn):
            return []
        try:
            return fn() or []
        except Exception:  # noqa: BLE001 — dédup best-effort
            return []

    def _mirror_campaign(self, meta_id, name, objective):
        if not meta_id:
            return
        AdCampaignMirror.objects.update_or_create(
            company=self.company, meta_id=meta_id,
            defaults={'name': name, 'status': launch_templates.PAUSED_STATUS,
                      'objective': objective, 'created_via_engine': True})

    def _mirror_adset(self, meta_id, name, campaign_id):
        if not meta_id:
            return
        campaign = AdCampaignMirror.objects.filter(
            company=self.company, meta_id=campaign_id).first()
        AdSetMirror.objects.update_or_create(
            company=self.company, meta_id=meta_id,
            defaults={'name': name, 'status': launch_templates.PAUSED_STATUS,
                      'campaign': campaign, 'created_via_engine': True})

    # ── Transition 2 : boucle quotidienne (ACTIVE, idempotente) ──────────────
    def run_daily(self, *, today=None, window_days=None):
        """Boucle quotidienne : synchro (hors-scope réseau ici — la synchro
        vit dans ``tasks.sync_insights_daily`` / le simulateur pré-alimente les
        stats), puis, pour chaque expérience EN COURS de la société, repondération
        bandit + ``DecisionLog`` (ADSENG12/21), puis gardien (ENG9, propose-only).

        NO-OP propre si l'interrupteur global est engagé. Idempotente : une
        seconde exécution le même jour re-calcule (le bandit est déterministe) et
        le gardien dédup ses propositions (aucune pause en double)."""
        if self.is_killed():
            return {'skipped': 'kill_switch', 'decisions': 0}

        today = today or self.today()
        decisions = 0
        for experiment in Experiment.objects.filter(
                company=self.company,
                status=Experiment.Statut.EN_COURS):
            arms = self._experiment_arms(experiment, window_days=window_days)
            if not arms:
                continue
            budget = self._daily_budget_mad()
            decisionlog.decide_and_log(
                experiment, arms, budget, window_days=window_days)
            decisions += 1

        # Gardien : propose des pauses sur « dépense > 0 et 0 résultat »
        # (idempotent — dédup interne). Jamais d'application, jamais d'activation.
        guardian = guardrails.detect_anomalies(self.company)

        logger.info('flightrunner: run_daily société=%s décisions=%s '
                    'gardien=%s', self.company.pk, decisions, len(guardian))
        return {
            'state': self.state(),
            'decisions': decisions,
            'guardian_pauses_proposed': len(guardian),
        }

    def _experiment_arms(self, experiment, *, window_days=None, as_of=None):
        """Agrège les ``ArmDailyStat`` des bras ACTIFS d'une expérience en la
        liste de dicts ``{'label', 'impressions', 'conversions'}`` attendue par le
        bandit (``conversions`` = ``conversations`` du modèle)."""
        as_of = as_of or self.today()
        from django.db.models import Sum
        arms = []
        qs = ExperimentArm.objects.filter(
            company=self.company, experiment=experiment, is_active=True)
        for arm in qs:
            # Toujours borné « à date » (``date <= as_of``) : le futur n'existe
            # pas, et l'horloge injectée (simulateur ADSENG36) voit ainsi la
            # croyance du bandit ÉVOLUER dans le temps accéléré. ``window_days``
            # limite en plus le regard en arrière.
            stat_qs = ArmDailyStat.objects.filter(
                company=self.company, arm=arm, date__lte=as_of)
            if window_days:
                start = as_of - datetime.timedelta(days=window_days)
                stat_qs = stat_qs.filter(date__gte=start)
            agg = stat_qs.aggregate(
                imp=Sum('impressions'), conv=Sum('conversations'))
            arms.append({
                'label': arm.label or f'arm-{arm.pk}',
                'impressions': int(agg['imp'] or 0),
                'conversions': int(agg['conv'] or 0),
            })
        return arms

    def _daily_budget_mad(self):
        """Budget quotidien de repondération = plafond quotidien des garde-fous
        (source unique, jamais un littéral). Défaut prudent si non configuré."""
        from .models import GuardrailConfig
        config = GuardrailConfig.objects.filter(company=self.company).first()
        return float(config.daily_budget_ceiling_mad) if config else 100.0

    # ── Transition 3 : boucle hebdomadaire (ACTIVE) ──────────────────────────
    def run_weekly(self, *, today=None):
        """Boucle hebdomadaire : rotation (ADSENG25, propose-only), puis brief
        (ENG11). NO-OP propre si l'interrupteur global est engagé. Toutes les
        décisions de rotation sont des PROPOSITIONS (sorties/revues/entrées) —
        aucune activation, aucun unpause programmatique.

        PUB120 — chaque décision est MATÉRIALISÉE (``_materialize_rotation``) :
        sorties → PAUSE, revues → alerte, entrées → ROTATE_CREATIVE à payload
        complet depuis l'item de backlog. Le retour ``rotations`` (compteurs de
        décisions par expérience) reste INCHANGÉ ; le compte-rendu de
        matérialisation vit dans la clé ``rotation_proposals``."""
        if self.is_killed():
            return {'skipped': 'kill_switch'}

        today = today or self.today()
        rotations = []
        materialized = {'pauses': 0, 'reviews': 0, 'rotations': 0, 'alerts': 0}
        for experiment in Experiment.objects.filter(
                company=self.company,
                status=Experiment.Statut.EN_COURS):
            snapshots = self._rotation_snapshots(experiment, today=today)
            if not snapshots:
                continue
            # Cette file DÉCIDE des entrées proposées : elle doit donc voir
            # EXACTEMENT ce que ``services._rotation_backlog_head`` acceptera au
            # moment du payload (et ce que demande ``propose_adset_launch_ads``).
            #   * File de la CAMPAGNE, PUIS les items SANS campagne cible : un
            #     item CIBLÉ n'est jamais détourné vers une autre campagne, mais
            #     un item sans cible est utilisable partout. Sans ce second
            #     passage, la décision comptait ZÉRO candidat alors que le
            #     résolveur en acceptait un — et tout item né de la chaîne
            #     génération → ``recombine.approve_lot`` (qui ne pose AUCUNE
            #     campagne cible) restait invisible à la rotation hebdo.
            #   * PUB-P8/C7 ``ready_only`` : la file COMPLÈTE sert l'écran de
            #     planification, pas un proposeur. Compter un item daté pour plus
            #     tard rendait le nombre d'entrées OPTIMISTE (entrée décidée, puis
            #     repli sur le créatif LIVE au payload).
            queue = list(backlog_mod.queue_for_campaign(
                self.company, experiment.campaign, today=today,
                ready_only=True)
                if experiment.campaign_id else [])
            queue += [it for it in backlog_mod.queue_for_campaign(
                self.company, None, today=today, ready_only=True)
                if it.target_campaign_id is None]
            decision = rotation.plan_rotation(
                snapshots, backlog=queue, today=today)
            rotations.append({
                'experiment_id': experiment.pk,
                'exits': len(decision.exits),
                'reviews': len(decision.reviews),
                'entries': decision.added_count,
            })
            report = self._materialize_rotation(
                experiment, decision, today=today)
            for key, value in report.items():
                materialized[key] += value

        # Brief hebdomadaire déterministe (ENG11) — best-effort.
        brief_generated = False
        try:
            brief_mod.build_brief(self.company)
            brief_generated = True
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning('flightrunner: build_brief a échoué société=%s',
                           self.company.pk, exc_info=True)

        logger.info('flightrunner: run_weekly société=%s rotations=%s '
                    'propositions=%s brief=%s', self.company.pk, len(rotations),
                    materialized, brief_generated)
        return {
            'state': self.state(),
            'rotations': rotations,
            'rotation_proposals': materialized,
            'brief_generated': brief_generated,
        }

    # ── PUB120 — Instantanés de rotation ALIMENTÉS par le bandit ──────────────
    def _rotation_snapshots(self, experiment, *, today):
        """``ArmSnapshot`` des bras ACTIFS, avec leur ``p_best`` et leur série
        faible RÉELS.

        ``plan_rotation`` exige ces deux valeurs « injectées, jamais recalculées
        ici » (contrat de ``rotation.py``) : avec les défauts (0.0 / 0), la règle
        des deux coups ne pouvait structurellement JAMAIS sortir un bras — la
        boucle hebdo ne calculait donc que des revues. On les alimente :

          * ``p_best`` = dernière repondération JOURNALISÉE de l'expérience
            (``DecisionLog.allocations['prob_best']``, par libellé de bras —
            écrite par ``run_daily``) ; aucun bras journalisé ⇒ 0.0, jamais un
            chiffre fabriqué ;
          * ``weak_streak`` = série de semaines FAIBLES consécutives, avancée par
            ``rotation.next_weak_streak`` UNE SEULE FOIS par semaine évaluée
            (re-jouer la boucle la même semaine ne la fait pas avancer deux
            fois — l'idempotence vaut aussi pour l'état de la rotation)."""
        prob_map = self._last_prob_best(experiment)
        week = self._rotation_week_key(today)
        snapshots = []
        for arm in ExperimentArm.objects.filter(
                company=self.company, experiment=experiment, is_active=True):
            label = arm.label or f'arm-{arm.pk}'
            try:
                p_best = float(prob_map.get(label) or 0.0)
            except (TypeError, ValueError):
                p_best = 0.0
            streak = self._advance_weak_streak(arm, p_best, week=week)
            snapshots.append(rotation.snapshot_from_arm(
                arm, p_best=p_best, weak_streak=streak, today=today))
        return snapshots

    def _last_prob_best(self, experiment):
        """``{libellé: P(meilleur)}`` de la DERNIÈRE décision journalisée de
        l'expérience (dict vide si aucune — jamais une croyance inventée)."""
        last = (DecisionLog.objects
                .filter(company=self.company, experiment=experiment)
                .order_by('-created_at', '-id').first())
        allocations = getattr(last, 'allocations', None)
        if not isinstance(allocations, dict):
            return {}
        prob = allocations.get('prob_best')
        return prob if isinstance(prob, dict) else {}

    @staticmethod
    def _rotation_week_key(today):
        """Clé ISO de la SEMAINE de ``today`` (``2026-W29``) — l'unité de la
        rotation hebdo, et le garde-fou anti-double-avancement de la série."""
        year, week, _ = today.isocalendar()
        return f'{year}-W{week:02d}'

    def _advance_weak_streak(self, arm, p_best, *, week):
        """Série de semaines FAIBLES du bras, avancée d'un cran pour ``week``.

        Persistée en cache (même parti que la graduation de ``tier_router`` :
        aucun champ modèle, donc aucune migration). Déjà avancée pour cette
        semaine ⇒ on RELIT la valeur au lieu de la faire progresser (un re-run le
        même lundi ne change ni la décision ni les propositions)."""
        key = f'adsengine:rotation_weak_streak:{self.company.pk}:{arm.pk}'
        stored = cache.get(key)
        if not isinstance(stored, dict):
            stored = {}
        previous = int(stored.get('streak') or 0)
        if stored.get('week') == week:
            return previous
        streak = rotation.next_weak_streak(previous, p_best)
        cache.set(key, {'week': week, 'streak': streak}, WEAK_STREAK_TTL)
        return streak

    # ── PUB120 — Matérialisation des décisions de rotation (propose-only) ─────
    @staticmethod
    def _rotation_dedup_since(today):
        """Début (datetime) de la SEMAINE calendaire de ``today`` — la fenêtre de
        dédup des propositions de rotation. La rotation s'évalue le lundi
        (``rotation.is_rotation_day``) : re-jouer la boucle le même lundi (ou
        n'importe quel jour de cette semaine) retombe donc sur les propositions
        déjà écrites au lieu d'en créer de nouvelles."""
        monday = today - datetime.timedelta(days=today.weekday())
        since = datetime.datetime.combine(monday, datetime.time.min)
        if timezone.is_naive(since):
            since = timezone.make_aware(
                since, timezone.get_default_timezone())
        return since

    def _materialize_rotation(self, experiment, decision, *, today):
        """PUB120 — Transforme UNE ``RotationDecision`` en PROPOSITIONS.

        Rien n'est appliqué ni activé ici : on écrit des ``EngineAction``
        PROPOSÉES (l'approbation humaine reste requise) et des alertes.

          * **sorties** → ``PAUSE`` sur l'ad du bras, précédée de la garde
            ``guardrails.enforce_paused_only`` (la seule transition de statut que
            le moteur propose — jamais une activation) ;
          * **revues** → ALERTE (une revue est un jugement humain : aucune action
            n'est proposée à sa place) ;
          * **entrées** → ``ROTATE_CREATIVE`` à payload COMPLET
            (``services.resolve_rotation_payload``, PUB119) ; l'item de backlog
            réellement consommé avance ``EN_FILE`` → ``PROGRAMME`` (il quitte la
            file libre, donc une seconde entrée prend l'item SUIVANT).

        Un bras sans ad miroir, ou une entrée sans aucun créatif prêt, produit une
        ALERTE explicite — jamais une proposition creuse. Renvoie les compteurs
        ``{pauses, reviews, rotations, alerts}``."""
        from . import guardrails, rules_engine, services
        from .models import CreativeBacklogItem, EngineAction, ExperimentArm

        since = self._rotation_dedup_since(today)
        report = {'pauses': 0, 'reviews': 0, 'rotations': 0, 'alerts': 0}
        arms = {a.pk: a for a in ExperimentArm.objects.filter(
            company=self.company, experiment=experiment)}

        def _label(arm, arm_id):
            return (getattr(arm, 'label', '') or '') or f'bras #{arm_id}'

        def _alert(message, *, template_key, arm_id=None, ad_id=''):
            guardrails.emit_alert(
                self.company, alert_type=guardrails.ALERT_ANOMALY,
                message=message,
                detail={'template_key': template_key,
                        'experiment_id': experiment.pk,
                        'rotation_arm_id': arm_id,
                        'target_meta_id': ad_id})

        # (1) SORTIES — pause propose-only du bras sortant.
        for arm_id in decision.exits:
            arm = arms.get(arm_id)
            ad_id = (getattr(arm, 'ad_id', '') or '').strip()
            if not ad_id:
                _alert(
                    f"Rotation hebdomadaire de « {experiment.name} » : le bras "
                    f"{_label(arm, arm_id)} sort du test mais ne porte aucune ad "
                    f"miroir Meta — impossible de proposer sa mise en pause "
                    f"(resynchroniser les miroirs).",
                    template_key=ROTATION_TEMPLATE_EXIT, arm_id=arm_id)
                report['alerts'] += 1
                continue
            if rules_engine._recently_acted(
                    self.company, ROTATION_TEMPLATE_EXIT, ad_id, since=since):
                continue
            # Garde PAUSED-only AVANT d'écrire la proposition : le moteur ne
            # propose que des transitions vers PAUSED (invariant règle #3).
            guardrails.enforce_paused_only('PAUSED', company=self.company)
            services.propose_action(
                self.company, kind=EngineAction.Kind.PAUSE,
                reason_fr=(
                    f"Rotation hebdomadaire de « {experiment.name} » : le bras "
                    f"{_label(arm, arm_id)} sort du test (P(best) sous "
                    f"{rotation.EXIT_P_BEST_THRESHOLD:.0%} sur "
                    f"{rotation.EXIT_CONSECUTIVE_WEAK_WEEKS} semaines "
                    f"consécutives, un bras strictement meilleur existe) — mise "
                    f"en pause de l'ad {ad_id} proposée."),
                payload={
                    'template_key': ROTATION_TEMPLATE_EXIT,
                    'target_type': 'ad',
                    'target_meta_id': ad_id,
                    'target_object_id': self._ad_mirror_pk(ad_id),
                    'experiment_id': experiment.pk,
                    'rotation_arm_id': arm_id,
                })
            report['pauses'] += 1

        # (2) REVUES — alerte/annotation, jamais une action à la place de l'humain.
        for arm_id in decision.reviews:
            arm = arms.get(arm_id)
            ad_id = (getattr(arm, 'ad_id', '') or '').strip()
            if self._rotation_review_alerted(arm_id, since=since):
                continue
            _alert(
                f"Rotation hebdomadaire de « {experiment.name} » : le bras "
                f"{_label(arm, arm_id)} demande une REVUE humaine (fin de vie "
                f"au-delà de {rotation.MAX_LIFESPAN_WEEKS} semaines, ou "
                f"fréquence au-delà de {rotation.FATIGUE_FREQUENCY}) — aucune "
                f"action n'est proposée à votre place.",
                template_key=ROTATION_TEMPLATE_REVIEW, arm_id=arm_id,
                ad_id=ad_id)
            report['reviews'] += 1

        # (3) ENTRÉES — rotation créative à payload COMPLET depuis le backlog.
        anchor_ad_id = self._rotation_anchor_ad_id(arms, decision)
        for entry in decision.entries:
            if not anchor_ad_id:
                _alert(
                    f"Rotation hebdomadaire de « {experiment.name} » : un item de "
                    f"backlog est prêt à entrer mais aucun bras ne porte d'ad "
                    f"miroir Meta — l'ad set cible est introuvable, aucune "
                    f"rotation n'est proposée.",
                    template_key=ROTATION_TEMPLATE_ENTRY)
                report['alerts'] += 1
                continue
            if rules_engine._recently_acted(
                    self.company, ROTATION_TEMPLATE_ENTRY, anchor_ad_id,
                    since=since):
                continue
            try:
                payload = services.resolve_rotation_payload(
                    self.company, target_type='ad',
                    target_meta_id=anchor_ad_id)
            except services.RotationCreativeUnavailable as exc:
                _alert(
                    f"Rotation hebdomadaire de « {experiment.name} » : {exc}",
                    template_key=ROTATION_TEMPLATE_ENTRY, ad_id=anchor_ad_id)
                report['alerts'] += 1
                continue
            payload.update({
                'template_key': ROTATION_TEMPLATE_ENTRY,
                'target_type': 'ad',
                'target_meta_id': anchor_ad_id,
                'experiment_id': experiment.pk,
                # Lignée de la décision de rotation (ADSENG23) : l'item PLANIFIÉ
                # et le nom de lancement calculé restent lisibles à l'approbation,
                # même quand la source créative résolue est un créatif LIVE.
                'rotation_backlog_item_id': entry.source_ref,
                'rotation_launch_name': entry.launch_name,
            })
            services.propose_action(
                self.company, kind=EngineAction.Kind.ROTATE_CREATIVE,
                reason_fr=(
                    f"Rotation hebdomadaire de « {experiment.name} » : entrée "
                    f"d'une nouvelle ad sur l'ad set {payload['adset_id']} "
                    f"(un seul ajout par rotation) — {entry.reason_fr}"),
                payload=payload)
            report['rotations'] += 1
            # L'item RÉELLEMENT consommé par le payload quitte la file libre.
            consumed = payload.get('backlog_item_id')
            if consumed:
                CreativeBacklogItem.objects.filter(
                    company=self.company, pk=consumed,
                    status=CreativeBacklogItem.Statut.EN_FILE,
                ).update(status=CreativeBacklogItem.Statut.PROGRAMME)
        return report

    def _ad_mirror_pk(self, ad_meta_id):
        """PK du miroir d'ad pour ``ad_meta_id`` (``None`` si non miroité) —
        renseigne ``payload['target_object_id']`` comme le fait le proposeur de
        règles, sans jamais inventer d'identifiant."""
        from .models import AdMirror
        return (AdMirror.objects
                .filter(company=self.company, meta_id=ad_meta_id)
                .values_list('pk', flat=True).first())

    def _rotation_review_alerted(self, arm_id, *, since):
        """Vrai si la revue de CE bras a déjà été signalée cette semaine (dédup
        des alertes de revue : un re-run n'en écrit pas une seconde)."""
        from .models import EngineAlert
        return EngineAlert.objects.filter(
            company=self.company,
            detail__template_key=ROTATION_TEMPLATE_REVIEW,
            detail__rotation_arm_id=arm_id,
            created_at__gte=since,
        ).exists()

    @staticmethod
    def _rotation_anchor_ad_id(arms, decision):
        """Ad miroir servant d'ANCRE pour résoudre l'ad set cible d'une entrée.

        On privilégie un bras qui RESTE en place (une ad sortante peut disparaître
        de l'ad set) ; à défaut, n'importe quel bras porteur d'un ``ad_id``.
        Renvoie ``''`` quand aucun bras n'est miroité — l'appelant alerte alors."""
        exiting = set(decision.exits)
        fallback = ''
        for arm_id, arm in sorted(arms.items()):
            ad_id = (getattr(arm, 'ad_id', '') or '').strip()
            if not ad_id:
                continue
            if arm_id not in exiting:
                return ad_id
            fallback = fallback or ad_id
        return fallback

    # ── Transition 4 : avancement de phase / fin de plan ─────────────────────
    def advance_phase(self, *, today=None, voi_params=None,
                      voi_experiment=None):
        """Fait avancer le plan selon la fenêtre calendaire des phases.

        Si la phase courante est terminée (``end_date <= today``) et qu'une phase
        suivante existe → on lance ses structures PAUSED (nouvelle phase). Si
        c'était la dernière → le plan passe ``TERMINE`` (ACTIVE → COMPLETED) et on
        renvoie le rapport de fin de plan. NO-OP si l'interrupteur est engagé.

        ASG3/PUB17 — quand l'ordonnanceur VoI est ACTIVÉ pour la société (drapeau
        cache ``voi.voi_scheduler_active``, OFF par défaut), la transition de phase
        FIXE est DÉSACTIVÉE : la file d'hypothèses (argmax VoI) gouverne ce qui est
        testé. ``voi.schedule_next`` est RÉELLEMENT appelé (il ne l'était pas avant)
        avec l'expérience courante et le contexte MDE/coût par nœud ``voi_params``
        (fourni par la boucle autonome qui connaît les volumes). Flag OFF ⇒
        comportement calendaire historique BYTE-IDENTIQUE (les nouveaux paramètres
        sont ignorés)."""
        if self.is_killed():
            return {'skipped': 'kill_switch', 'state': self.STATE_KILLED}

        from . import voi
        if voi.voi_scheduler_active(self.company):
            return self._advance_via_voi(
                voi_params=voi_params, experiment=voi_experiment)

        today = today or self.today()
        phases = list(FlightPhase.objects.filter(
            company=self.company, plan=self.plan).order_by('order', 'id'))
        if not phases:
            return {'state': self.state(), 'advanced': False,
                    'reason': 'aucune phase'}

        current = self._current_phase(phases, today)
        # Phase courante encore en cours → rien à avancer.
        if current is not None and (current.end_date is None
                                    or current.end_date > today):
            return {'state': self.state(), 'advanced': False,
                    'current_phase': current.order}

        nxt = self._next_phase(phases, current)
        if nxt is not None:
            launched = {}
            if self._client is not None:
                launched = self._launch_phase(nxt, client=self._client)
            self._log_transition(
                self.STATE_ACTIVE, self.STATE_ACTIVE,
                summary_fr=(f"Transition vers la phase {nxt.order} "
                            f"« {nxt.name} » (structures PAUSED)."))
            return {'state': self.state(), 'advanced': True,
                    'phase': nxt.order, 'launched': launched}

        # Dernière phase franchie → fin de plan.
        return self.complete()

    def _advance_via_voi(self, *, voi_params=None, experiment=None):
        """PUB17 — Mode VoI ACTIF (ASG3/ASG5) : la file d'hypothèses (argmax VoI,
        ``voi.schedule_next``) gouverne la transition — la fenêtre calendaire FIXE
        est désactivée.

        Ouvre un slot pour l'expérience courante avec le contexte MDE/coût par
        nœud ``voi_params`` : ``schedule_next`` calcule l'argmax VoI, écrit un
        ``DecisionLog`` OBLIGATOIRE, et renvoie le nœud gagnant (= « la phase
        suivante »). Sans expérience ouverte OU sans contexte MDE, aucune sélection
        n'est FORCÉE (``advanced=False``) — jamais un chiffre MDE fabriqué, jamais
        un crash."""
        from . import voi

        experiment = experiment or self._voi_experiment()
        if experiment is None or voi_params is None:
            self._log_transition(
                self.STATE_ACTIVE, self.STATE_ACTIVE,
                summary_fr=("Mode VoI actif : la file d'hypothèses gouverne les "
                            "transitions (fenêtre calendaire désactivée) ; aucun "
                            "slot ouvert (expérience/contexte MDE absent)."))
            return {'state': self.state(), 'advanced': False, 'voi_mode': True,
                    'voi_node_id': None}

        result = voi.schedule_next(
            self.company, experiment=experiment, params=voi_params)
        winner = result.get('winner')
        winner_id = winner.pk if winner is not None else None
        score = result.get('score') or {}
        self._log_transition(
            self.STATE_ACTIVE, self.STATE_ACTIVE,
            summary_fr=(
                f"Mode VoI : slot ouvert par argmax VoI (nœud {winner_id})."
                if winner_id is not None else
                "Mode VoI : file vide — aucun nœud testable à ordonnancer."))
        return {
            'state': self.state(), 'advanced': winner is not None,
            'voi_mode': True, 'voi_node_id': winner_id,
            'voi_score': score.get('voi'),
            'decision_log_id': getattr(result.get('log'), 'pk', None),
        }

    def _voi_experiment(self):
        """PUB17 — Expérience courante où tracer les décisions VoI (le
        ``DecisionLog`` de ``schedule_next`` s'y rattache) : la plus récente
        EN_COURS de la société, ou ``None`` (aucun slot forcé sans elle)."""
        return (Experiment.objects
                .filter(company=self.company,
                        status=Experiment.Statut.EN_COURS)
                .order_by('-created_at').first())

    def _current_phase(self, phases, today):
        """La phase dont la fenêtre contient ``today`` (repli : la dernière phase
        commencée)."""
        started = [p for p in phases
                   if p.start_date is None or p.start_date <= today]
        for p in started:
            if p.end_date is None or p.end_date > today:
                return p
        return started[-1] if started else None

    @staticmethod
    def _next_phase(phases, current):
        if current is None:
            return phases[0] if phases else None
        for p in phases:
            if p.order > current.order:
                return p
        return None

    def complete(self):
        """ACTIVE → COMPLETED : passe le plan ``TERMINE`` et renvoie le rapport
        de fin de plan. Idempotent (déjà terminé → renvoie le rapport)."""
        if self.plan.status != FlightPlan.Statut.TERMINE:
            self.plan.status = FlightPlan.Statut.TERMINE
            self.plan.save(update_fields=['status', 'updated_at'])
            self._log_transition(
                self.STATE_ACTIVE, self.STATE_COMPLETED,
                summary_fr="Plan terminé — rapport de fin de plan généré.")
        report = self.end_of_plan_report()
        return {'state': self.state(), 'advanced': True, 'completed': True,
                'report': report}

    def end_of_plan_report(self):
        """Rapport de fin de plan : phases, décisions journalisées, actions
        proposées/appliquées, expériences et bras gagnants (P(best) le plus
        élevé de la dernière décision). Structure JSON stable (P7 la lit)."""
        phases = FlightPhase.objects.filter(
            company=self.company, plan=self.plan).count()
        experiments = []
        for experiment in Experiment.objects.filter(company=self.company):
            last = (DecisionLog.objects
                    .filter(company=self.company, experiment=experiment)
                    .order_by('-created_at').first())
            best = None
            if last and isinstance(last.allocations, dict):
                prob = last.allocations.get('prob_best') or {}
                if prob:
                    best = max(prob, key=lambda label: prob[label])
            experiments.append({
                'experiment_id': experiment.pk,
                'name': experiment.name,
                'best_arm': best,
                'decisions': DecisionLog.objects.filter(
                    company=self.company, experiment=experiment).count(),
            })
        actions = EngineAction.objects.filter(company=self.company)
        return {
            'plan_id': self.plan.pk,
            'plan_name': self.plan.name,
            'phases': phases,
            'experiments': experiments,
            'actions_proposed': actions.filter(
                status=EngineAction.Statut.PROPOSEE).count(),
            'actions_applied': actions.filter(
                status=EngineAction.Statut.APPLIQUEE).count(),
            'decisions_total': DecisionLog.objects.filter(
                company=self.company).count(),
        }

    # ── Journalisation (DecisionLog + actions-log) ───────────────────────────
    def _log_action(self, *, kind, reason_fr, payload, result):
        """Écrit une ligne ``EngineAction`` d'AUDIT (l'actions-log du runner).

        Les créations PAUSED et les pauses kill-switch sont des actions SYSTÈME
        déjà exécutées côté client (PAUSED garanti) : on les consigne
        ``auto=True``, ``APPLIQUEE`` (jamais un ``approved_by`` humain, jamais une
        activation). C'est une trace, pas un chemin d'application Meta."""
        return EngineAction.objects.create(
            company=self.company, kind=kind, payload=payload or {},
            reason_fr=reason_fr,
            status=EngineAction.Statut.APPLIQUEE, auto=True,
            applied_at=timezone.now(),
            result=result if isinstance(result, dict) else {'result': result})

    def _log_transition(self, from_state, to_state, *, summary_fr):
        """Journalise une transition d'état (logger + actions-log léger).

        La journalisation par expérience (``DecisionLog``) est écrite par les
        boucles elles-mêmes (``decide_and_log`` par expérience) ; ici on trace la
        transition de plus haut niveau (plan) qui n'a pas d'expérience unique."""
        logger.info('flightrunner: transition %s → %s société=%s : %s',
                    from_state, to_state, self.company.pk, summary_fr)
        return summary_fr
