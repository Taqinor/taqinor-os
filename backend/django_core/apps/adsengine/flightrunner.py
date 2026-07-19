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
)

logger = logging.getLogger(__name__)

# Gabarit de lancement par défaut si une phase n'en précise aucun.
DEFAULT_TEMPLATE = 'resid_ctwa'

# Durée de vie (secondes) du drapeau kill-switch en cache. Long (30 j) : le
# kill-switch doit SURVIVRE aux redémarrages tant qu'un humain ne le relâche pas.
KILL_SWITCH_TTL = 60 * 60 * 24 * 30

# Durée de vie (secondes) du drapeau « autonomie activée » en cache (30 j).
AUTONOMY_TTL = 60 * 60 * 24 * 30


# ── Drapeau d'autonomie PAR société (cache — jamais un champ modèle) ──────────
# L'activation est OFF PAR DÉFAUT et ne peut être posée QUE via ``preflight.
# activate`` (ADSENG38), qui exige d'abord que TOUTES les portes soient vertes —
# c'est la garantie structurelle « le mode autonome ne peut PAS s'activer tant que
# tout n'est pas vert ». Ces helpers sont bas-niveau (le gate vit dans preflight).
def _autonomy_key(company):
    return f'adsengine:autonomy:{company.pk}'


def is_autonomy_active(company):
    """Vrai si le mode autonome est ACTIVÉ pour cette société (OFF par défaut)."""
    return bool(cache.get(_autonomy_key(company)))


def set_autonomy_active(company, active):
    """Pose/retire le drapeau d'autonomie (bas-niveau — appelé par
    ``preflight.activate``/``preflight.deactivate`` APRÈS la garde préflight,
    jamais directement pour contourner le gate)."""
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

    def is_killed(self):
        """Vrai si l'interrupteur global est engagé pour cette société."""
        return bool(cache.get(self._kill_key()))

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
        cache.set(self._kill_key(), True, KILL_SWITCH_TTL)
        reason_fr = reason_fr or (
            "Interrupteur global engagé : mise en pause de toutes les "
            "structures créées par le moteur (sécurité).")

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
        — les structures restent PAUSED jusqu'à une action humaine hors moteur."""
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

        return {
            'template': template_key,
            'campaign_id': camp_id,
            'campaign_reused': camp_reused,
            'adset_ids': adset_ids,
            'status': launch_templates.PAUSED_STATUS,
        }

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
        aucune activation, aucun unpause programmatique."""
        if self.is_killed():
            return {'skipped': 'kill_switch'}

        today = today or self.today()
        rotations = []
        for experiment in Experiment.objects.filter(
                company=self.company,
                status=Experiment.Statut.EN_COURS):
            snapshots = [
                rotation.snapshot_from_arm(arm, today=today)
                for arm in ExperimentArm.objects.filter(
                    company=self.company, experiment=experiment,
                    is_active=True)
            ]
            if not snapshots:
                continue
            queue = backlog_mod.queue_for_campaign(
                self.company, experiment.campaign, today=today) \
                if experiment.campaign_id else []
            decision = rotation.plan_rotation(
                snapshots, backlog=list(queue), today=today)
            rotations.append({
                'experiment_id': experiment.pk,
                'exits': len(decision.exits),
                'reviews': len(decision.reviews),
                'entries': decision.added_count,
            })

        # Brief hebdomadaire déterministe (ENG11) — best-effort.
        brief_generated = False
        try:
            brief_mod.build_brief(self.company)
            brief_generated = True
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning('flightrunner: build_brief a échoué société=%s',
                           self.company.pk, exc_info=True)

        logger.info('flightrunner: run_weekly société=%s rotations=%s brief=%s',
                    self.company.pk, len(rotations), brief_generated)
        return {
            'state': self.state(),
            'rotations': rotations,
            'brief_generated': brief_generated,
        }

    # ── Transition 4 : avancement de phase / fin de plan ─────────────────────
    def advance_phase(self, *, today=None):
        """Fait avancer le plan selon la fenêtre calendaire des phases.

        Si la phase courante est terminée (``end_date <= today``) et qu'une phase
        suivante existe → on lance ses structures PAUSED (nouvelle phase). Si
        c'était la dernière → le plan passe ``TERMINE`` (ACTIVE → COMPLETED) et on
        renvoie le rapport de fin de plan. NO-OP si l'interrupteur est engagé.

        ASG3 — quand l'ordonnanceur VoI est ACTIVÉ pour la société (drapeau cache
        ``voi.voi_scheduler_active``, OFF par défaut), la transition de phase FIXE
        est DÉSACTIVÉE : la file d'hypothèses (argmax VoI, ``voi.schedule_next``)
        gouverne alors ce qui est testé, pas la fenêtre calendaire. Flag OFF ⇒
        comportement calendaire historique byte-identique."""
        if self.is_killed():
            return {'skipped': 'kill_switch', 'state': self.STATE_KILLED}

        from . import voi
        if voi.voi_scheduler_active(self.company):
            self._log_transition(
                self.STATE_ACTIVE, self.STATE_ACTIVE,
                summary_fr=("Mode VoI actif : la file d'hypothèses (argmax VoI) "
                            "gouverne les transitions — fenêtre calendaire fixe "
                            "désactivée."))
            return {'state': self.state(), 'advanced': False, 'voi_mode': True}

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
