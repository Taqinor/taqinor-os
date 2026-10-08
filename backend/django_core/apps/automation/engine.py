"""Moteur d'évaluation des règles d'automatisation (N72 / N73).

Point d'entrée : ``evaluate(trigger_type, instance, company, *, context=None,
user=None)``. Il trouve les règles ACTIVÉES de la même société qui matchent le
déclencheur (avec leur ``trigger_config``), puis pour chacune :

  - si l'action exige une approbation (N73) → crée une ``AutomationApproval``
    en attente et journalise un run ``pending_approval`` (l'action ne part PAS) ;
  - sinon → exécute l'action et journalise le run (success / noop / failed).

TOUT est best-effort : aucune exception ne remonte vers l'enregistrement
d'origine — les handlers de signaux enveloppent déjà l'appel, et chaque action
est isolée. Sans règle, ``evaluate`` ne fait rien (aucun changement de
comportement par défaut).
"""
import logging
import threading

from django.db import transaction

from .models import (
    ActionType, AutomationApproval, AutomationRule, AutomationRun,
    AutomationStep, TriggerType,
)

logger = logging.getLogger(__name__)

# Garde anti-récursion : quand une action écrit l'enregistrement (SET_FIELD /
# ASSIGN_RECORD), son ``instance.save()`` ré-émet le ``post_save`` qui a
# déclenché la règle. Sans garde, une règle qui écrit le champ que son propre
# déclencheur surveille reboucle jusqu'à ``RecursionError`` et bloque tout save.
# Ce drapeau thread-local marque « on est en train d'exécuter une automatisation »
# pour que ``evaluate`` n'enchaîne pas une nouvelle évaluation pendant ce temps.
_GUARD = threading.local()


def _in_automation():
    return getattr(_GUARD, 'active', False)


def _log_run(rule, company, instance, status, message):
    """Journalise UNE exécution de règle, sans jamais lever."""
    try:
        AutomationRun.objects.create(
            company=company,
            rule=rule,
            target_model=_model_label(instance),
            target_id=getattr(instance, 'pk', None),
            status=status,
            message=(message or '')[:4000],
        )
    except Exception:  # pragma: no cover - journalisation défensive
        logger.exception('automation: échec de journalisation du run')


def _model_label(instance):
    if instance is None:
        return ''
    meta = getattr(instance, '_meta', None)
    if meta is None:
        return ''
    return f'{meta.app_label}.{meta.model_name}'


def _has_company_fk(model):
    """Le modèle porte-t-il un champ ``company`` (modèle multi-tenant) ?"""
    try:
        return any(
            f.name == 'company' for f in model._meta.concrete_fields)
    except Exception:  # pragma: no cover - défensif
        return False


# ── ODX23 — gating ModuleToggle des règles d'automatisation ─────────────────
# Une action de règle qui CRÉE un enregistrement dans une AUTRE app que celle
# du déclencheur (ex. CREATE_SAV_TICKET depuis un lead crm) vise explicitement
# ce module-là. Whitelist FERMÉE, additive : une action non listée n'ajoute
# aucun module candidat au-delà de celui du déclencheur.
ACTION_MODULE_MAP = {
    ActionType.CREATE_SAV_TICKET: 'sav',
}


def _rule_disabled_module(rule, instance, company):
    """Clé de module ``ModuleToggle`` visée par ce déclenchement, si
    DÉSACTIVÉE pour ``company`` — sinon ``None``.

    Dérivé génériquement de l'``app_label`` du modèle déclencheur
    (``instance``, quel que soit le ``trigger_type`` — aucune table de
    correspondance à maintenir) ET, pour les actions qui écrivent dans une
    AUTRE app (:data:`ACTION_MODULE_MAP`), du module cible de l'action.
    Défaut = actif (policy FG391 : sans ``ModuleToggle``, aucun changement de
    comportement) ; best-effort, ne lève jamais.
    """
    try:
        from core.feature_flags import module_actif
    except Exception:  # pragma: no cover - défensif
        return None
    candidats = []
    label = _model_label(instance)
    if label and '.' in label:
        candidats.append(label.split('.', 1)[0])
    action_module = ACTION_MODULE_MAP.get(rule.action_type)
    if action_module:
        candidats.append(action_module)
    for module in candidats:
        try:
            if not module_actif(company, module):
                return module
        except Exception:  # pragma: no cover - défensif
            continue
    return None


# ── Correspondance déclencheur ────────────────────────────────────────────

def _trigger_matches(rule, instance, context):
    """Le déclencheur de la règle correspond-il à cet événement ?

    ``context`` peut porter des indices calculés par le signal (ex.
    ``new_stage``). On reste tolérant : une config vide matche tout événement
    du bon type.
    """
    cfg = rule.trigger_config or {}
    ctx = context or {}

    if rule.trigger_type == TriggerType.LEAD_STAGE_CHANGE:
        wanted = cfg.get('stage')
        if not wanted:
            return True
        return ctx.get('new_stage') == wanted or getattr(
            instance, 'stage', None) == wanted

    if rule.trigger_type == TriggerType.CHANTIER_STATUS:
        wanted = cfg.get('statut')
        if not wanted:
            return True
        return getattr(instance, 'statut', None) == wanted

    # APAR43 — branche PROJET_STATUS_CHANGE / PROJET_PHASE_CHANGE retirée :
    # leur émetteur (gestion_projet) est parqué, aucune évaluation n'arrive
    # plus (``selectors.DECLENCHEURS_PARQUES``).

    if rule.trigger_type == TriggerType.RECORD_STATE_CHANGE:
        # ARC34 — déclencheur générique : le couple (model, field) de la règle
        # doit correspondre à l'événement émis (contexte posé par le SERVICE
        # émetteur : {'model', 'field', 'old_value', 'new_value'} — champs
        # statut de DOMAINE, jamais les étapes STAGES.py, règle #2). ``value``
        # (optionnel) exige une nouvelle valeur précise ; ``conditions``
        # (optionnel) délègue à l'évaluateur d'arbre FG367 (``core.rules``)
        # sur le contexte plat — jamais un nouvel évaluateur. La whitelist
        # registre est appliquée à la CRÉATION de la règle (serializer).
        cfg_model = (cfg.get('model') or '').strip().lower()
        if cfg_model and cfg_model != _model_label(instance):
            return False
        cfg_field = (cfg.get('field') or '').strip()
        if cfg_field and cfg_field != ctx.get('field'):
            return False
        wanted = cfg.get('value')
        if wanted not in (None, '') and ctx.get('new_value') != wanted:
            return False
        conditions = cfg.get('conditions')
        if conditions:
            from core.rules import evaluate_condition_group
            return evaluate_condition_group(conditions, ctx)
        return True

    if rule.trigger_type == TriggerType.WEBHOOK_INBOUND:
        # APAR9 — un webhook entrant n'exécute QUE la règle de son jeton
        # (``rule_id`` posé par la vue publique) : sans cette garde, un POST
        # sur le jeton A tirait toutes les règles WEBHOOK_INBOUND de la
        # société, y compris celles dont le déclencheur est désactivé ou
        # protégé par HMAC.
        return ctx.get('rule_id') == rule.pk

    if rule.trigger_type == TriggerType.CUSTOM_RECORD_SAVED:
        # NTEXT27 — ``object_code`` posé dans le contexte par le signal
        # (``signals._custom_record_saved``) : vide ⇒ matche tout objet
        # personnalisé de la société (comportement générique par défaut,
        # cohérent avec les autres déclencheurs sans config).
        wanted = cfg.get('object_code')
        if not wanted:
            return True
        return ctx.get('object_code') == wanted

    # DEVIS_ACCEPTED / FACTURE_OVERDUE / WARRANTY_EXPIRING / MAINTENANCE_DUE /
    # STOCK_BELOW_THRESHOLD : la condition est déjà tranchée par l'émetteur du
    # signal (le moteur n'est appelé que quand l'événement s'est produit).
    return True


# ── APAR7 — prédicat d'état MÉTIER des déclencheurs temporels ─────────────
# FACTURE_OVERDUE et DATE_ECHEANCE_CHAMP réagissent à une DATE ; la date seule
# ne dit pas si la relance a encore un objet. Une facture annulée, un brouillon
# jamais émis ou une facture déjà soldée ne se relancent pas ; un devis accepté,
# refusé ou resté brouillon ne reçoit pas « toujours d'actualité ? ». Ce
# prédicat UNIQUE est lu par le signal, le balayage ET la reprise après
# approbation (``run_approved``) — jamais trois copies divergentes.

#: Statuts de facture qui peuvent faire l'objet d'une relance.
FACTURE_STATUTS_RELANCABLES = ('emise', 'en_retard')


def _motif_facture(facture):
    statut = getattr(facture, 'statut', None)
    if statut == 'payee':
        return 'Facture soldée : relance sans objet.'
    if statut == 'annulee':
        return 'Facture annulée : relance sans objet.'
    if statut not in FACTURE_STATUTS_RELANCABLES:
        return (f'Facture non émise ({statut or "sans statut"}) : '
                f'relance sans objet.')
    try:
        reste = facture.montant_exigible
    except Exception:  # pragma: no cover - défensif (facture détachée)
        reste = None
    if reste is not None and reste <= 0:
        return 'Facture soldée : relance sans objet.'
    return None


def motif_etat_metier(trigger_type, instance):
    """Motif (français) pour lequel l'état MÉTIER de ``instance`` interdit
    l'action d'un déclencheur temporel, ou ``None`` si l'action a un objet.

    - FACTURE_OVERDUE : seule une facture ``emise``/``en_retard`` dont le
      reste exigible est > 0 est relancée ;
    - DATE_ECHEANCE_CHAMP : sur un devis, seul un devis ``envoye`` est ciblé ;
      sur un lead, un lead perdu est exclu.
    Ne lève jamais.
    """
    if instance is None:
        return None
    try:
        if trigger_type == TriggerType.FACTURE_OVERDUE:
            return _motif_facture(instance)
        if trigger_type == TriggerType.DATE_ECHEANCE_CHAMP:
            label = _model_label(instance)
            if label == 'ventes.devis':
                statut = getattr(instance, 'statut', None)
                if statut != 'envoye':
                    return (f'Devis {statut or "sans statut"} : relance sans '
                            f'objet (seul un devis envoyé est relancé).')
            elif label == 'crm.lead' and getattr(instance, 'perdu', False):
                return 'Lead perdu : relance sans objet.'
    except Exception:  # pragma: no cover - défensif
        logger.exception("automation: prédicat d'état métier en échec")
    return None


# ── Approbation (N73) ─────────────────────────────────────────────────────

def _needs_approval(rule, context):
    """La règle exige-t-elle une approbation pour CE déclenchement ?

    Inconditionnel quand ``requires_approval`` et pas de seuil. Avec un seuil,
    on compare à une valeur numérique posée dans le contexte
    (``context['amount']``, ex. un pourcentage de remise).
    """
    if not rule.requires_approval:
        return False
    threshold = rule.approval_threshold
    if threshold is None:
        return True
    amount = (context or {}).get('amount')
    if amount is None:
        # Pas de montant à comparer → on exige l'approbation par prudence.
        return True
    try:
        return float(amount) > float(threshold)
    except (TypeError, ValueError):
        return True


def _create_approval(rule, company, instance, context, user):
    AutomationApproval.objects.create(
        company=company,
        rule=rule,
        target_model=_model_label(instance),
        target_id=getattr(instance, 'pk', None),
        description=f'{rule.get_action_type_display()} — {rule.nom}'[:255],
        context=context or {},
        requested_by=user,
    )


# ── Évaluation ────────────────────────────────────────────────────────────

def evaluate(trigger_type, instance, company, *, context=None, user=None):
    """Évalue toutes les règles activées matchant ``trigger_type``.

    Best-effort : journalise chaque run, ne lève jamais.
    """
    if company is None:
        return
    # Garde anti-récursion : un save déclenché PAR une action ne relance pas le
    # moteur (sinon une règle self-référentielle reboucle à l'infini).
    if _in_automation():
        return
    try:
        rules = list(AutomationRule.objects.filter(
            company=company, enabled=True, trigger_type=trigger_type
        ).order_by('ordre', 'id'))
    except Exception:  # pragma: no cover
        logger.exception('automation: chargement des règles impossible')
        return

    for rule in rules:
        try:
            if not _trigger_matches(rule, instance, context):
                continue
            # ODX23 — un module désactivé ModuleToggle n'inscrit même pas de
            # demande d'approbation : la règle est journalisée SKIPPED et
            # s'arrête là (run_action referait le même contrôle de toute
            # façon pour le chemin d'exécution immédiate ci-dessous).
            disabled_module = _rule_disabled_module(rule, instance, company)
            if disabled_module:
                _log_run(
                    rule, company, instance, AutomationRun.Status.SKIPPED,
                    f'Module désactivé ({disabled_module}) : '
                    f'automatisation ignorée.')
                continue
            if _needs_approval(rule, context):
                _create_approval(rule, company, instance, context, user)
                _log_run(
                    rule, company, instance,
                    AutomationRun.Status.PENDING_APPROVAL,
                    'Action différée : approbation requise.')
                continue
            run_action(rule, instance, company, context=context, user=user)
        except Exception as exc:  # best-effort par règle
            logger.exception('automation: règle %s échouée', rule.pk)
            _log_run(
                rule, company, instance, AutomationRun.Status.FAILED, str(exc))


class _StepView:
    """NTEXT4 — vue « règle » d'une ÉTAPE, pour les handlers d'action.

    ``actions.run`` et ses handlers ne lisent de la règle que
    ``action_type`` / ``action_config`` / ``company`` / ``nom``. Cette vue
    substitue le couple action de l'ÉTAPE et DÉLÈGUE tout le reste à la règle,
    sans dupliquer un seul handler ni changer leur signature.

    Jamais persistée : le journal (``AutomationRun.rule``) reçoit toujours la
    VRAIE règle.
    """

    __slots__ = ('_rule', 'step', 'action_type', 'action_config')

    def __init__(self, rule, step):
        self._rule = rule
        self.step = step
        self.action_type = step.action_type
        self.action_config = step.action_config

    def __getattr__(self, name):
        return getattr(self._rule, name)


def _rule_steps(rule):
    """Étapes ORDONNÉES d'une règle (liste vide si aucune). Ne lève jamais."""
    try:
        return list(rule.steps.all())
    except Exception:  # pragma: no cover - défensif (règle détachée)
        return []


# ── APAR10 — frontière transactionnelle du moteur ──────────────────────────
#
# 1) Chaque action tourne dans son POINT DE SAUVEGARDE (``transaction.atomic``):
#    une erreur SQL d'une action (valeur trop longue…) annule l'action seule ;
#    sans lui, la transaction de l'ÉMETTEUR (la requête qui a changé l'étape du
#    lead) était avortée et sa requête suivante levait
#    ``TransactionManagementError``.
# 2) Les actions d'ENVOI (e-mail, futurs canaux) partent en
#    ``transaction.on_commit`` et sont journalisées AU COMMIT : un fait annulé
#    (rollback de l'émetteur) n'envoie rien et ne journalise rien. Hors bloc
#    atomique (beat, autocommit), ``on_commit`` exécute immédiatement : le
#    statut rendu est alors le statut réel.

#: Actions dont l'effet SORT de l'application (jamais rattrapable par un
#: rollback) : exécutées au commit de la transaction de l'émetteur.
ACTIONS_ENVOI = frozenset({ActionType.SEND_EMAIL})

#: Statut rendu quand l'envoi attend le commit de l'émetteur (le run réel est
#: journalisé à l'exécution, au commit).
MESSAGE_ENVOI_DIFFERE = (
    "Envoi programmé : il partira à la validation de l'opération.")


def _run_isole(action_source, instance, company, context, user):
    """Exécute ``actions.run`` sous la garde anti-récursion ET dans un point
    de sauvegarde. Une erreur SQL annule l'action seule ; le message du
    handler (s'il a déjà conclu FAILED) est conservé. Ne lève jamais."""
    from . import actions
    # Marque la fenêtre d'exécution : tout ``instance.save()` déclenché par
    # l'action (SET_FIELD / ASSIGN_RECORD) ré-émet le post_save, mais
    # ``evaluate`` se court-circuite tant que ce drapeau est posé → pas de
    # récursion.
    previous = _in_automation()
    _GUARD.active = True
    resultat = None
    try:
        with transaction.atomic():
            resultat = actions.run(
                action_source, instance, company, context, user)
    except Exception as exc:
        # Le point de sauvegarde est annulé : la transaction de l'émetteur
        # reste UTILISABLE. On garde le message du handler s'il a déjà
        # conclu à l'échec (ex. « value too long »), sinon celui de l'erreur.
        if not (resultat and resultat[0] == AutomationRun.Status.FAILED):
            resultat = (AutomationRun.Status.FAILED, str(exc))
    finally:
        _GUARD.active = previous
    return resultat


def _execute(action_source, rule, instance, company, context, user):
    """Exécute UNE action (règle mono-action ou étape) et journalise son run.

    APAR10 — une action d'envoi est différée au commit (et journalisée là) ;
    les autres s'exécutent tout de suite, isolées dans un point de sauvegarde.
    """
    if action_source.action_type in ACTIONS_ENVOI:
        return _execute_au_commit(
            action_source, rule, instance, company, context, user)
    status, message = _run_isole(
        action_source, instance, company, context, user)
    _log_run(rule, company, instance, status, message)
    return status, message


def _execute_au_commit(action_source, rule, instance, company, context, user):
    """APAR10 — programme l'envoi au commit de la transaction en cours."""
    resultat = {}

    def _envoyer():
        status, message = _run_isole(
            action_source, instance, company, context, user)
        _log_run(rule, company, instance, status, message)
        resultat['run'] = (status, message)

    transaction.on_commit(_envoyer)
    if 'run' in resultat:  # autocommit : exécuté immédiatement
        return resultat['run']
    return AutomationRun.Status.NOOP, MESSAGE_ENVOI_DIFFERE


def run_action(rule, instance, company, *, context=None, user=None):
    """Exécute l'action d'une règle et journalise le résultat.

    Utilisée par ``evaluate`` (immédiat) et par l'approbation (différée).

    NTEXT4 — si la règle porte des ``AutomationStep``, la SÉQUENCE remplace
    l'action unique : chaque étape est exécutée dans l'ordre et journalise son
    PROPRE ``AutomationRun``. La valeur de retour est celle de la DERNIÈRE
    étape exécutée. Sans étape, le comportement mono-action historique est
    STRICTEMENT inchangé (une action, un run, même message).

    ODX23 — si le module visé (déclencheur ou action, voir
    :func:`_rule_disabled_module`) est désactivé ``ModuleToggle`` pour
    ``company``, l'action n'est PAS exécutée : un run ``SKIPPED`` est
    journalisé (« module désactivé ») à la place. Couvre le chemin immédiat
    ET l'approbation différée (``run_approved`` appelle cette même fonction),
    y compris le cas où le module a été désactivé ENTRE la demande
    d'approbation et sa décision. Le contrôle est refait PAR ÉTAPE (une étape
    qui écrit dans un module désactivé est ignorée sans stopper la séquence).
    """
    disabled_module = _rule_disabled_module(rule, instance, company)
    if disabled_module:
        message = f'Module désactivé ({disabled_module}) : automatisation ignorée.'
        _log_run(rule, company, instance, AutomationRun.Status.SKIPPED, message)
        return AutomationRun.Status.SKIPPED, message

    steps = _rule_steps(rule)
    if not steps:
        return _execute(rule, rule, instance, company, context, user)

    return _run_steps(rule, steps, 0, instance, company, context, user)


def _instance_field_context(instance):
    """NTEXT5 — valeurs des champs concrets de l'instance, pour l'évaluation
    de conditions de step. Ignore les champs relationnels. Contrairement à
    ``_json_safe`` (qui sert à GELER un contexte en JSON pour persistance),
    les valeurs restent NATIVES (``Decimal``/``date``…) : ``core.rules``
    compare des types Python natifs, jamais une chaîne stringifiée. Purement
    en mémoire, jamais persisté. Ne lève jamais."""
    out = {}
    if instance is None:
        return out
    try:
        for f in instance._meta.concrete_fields:
            if f.is_relation:
                continue
            try:
                out[f.attname] = getattr(instance, f.attname)
            except Exception:  # pragma: no cover - défensif
                continue
    except Exception:  # pragma: no cover - défensif
        pass
    return out


def _step_eval_context(instance, context):
    """NTEXT5 — contexte d'évaluation d'une condition de step : les champs de
    l'enregistrement, complétés/écrasés par le ``context`` de déclenchement
    (plus spécifique à l'événement — priorité sur les champs bruts)."""
    ctx = _instance_field_context(instance)
    ctx.update(context or {})
    return ctx


def _resolve_step_skips(steps, instance, context):
    """NTEXT5 — pour chaque étape, la raison de l'IGNORER avant exécution, ou
    absente si elle s'exécute. Deux mécanismes, appliqués dans l'ordre :

    1) BRANCHE : à ``ordre`` égal, un groupe complet ``si``+``sinon`` est
       mutuellement exclusif — seule la branche gagnante s'exécute (« si »
       gagne si AU MOINS UNE de ses conditions est vraie, sinon « sinon »
       gagne). Un groupe sans les deux branches ne déclenche aucune exclusion
       (chaque étape suit alors sa seule condition individuelle).
    2) CONDITION individuelle : une étape (de n'importe quelle branche, y
       compris « toujours ») dont la ``condition`` est fausse est ignorée.

    Pur, sans effet de bord — calculé une fois avant de dérouler/reprendre la
    séquence. Ne lève jamais.
    """
    from itertools import groupby

    from core.rules import evaluate_condition_group

    eval_ctx = _step_eval_context(instance, context)
    skips = {}

    for _ordre, group_iter in groupby(steps, key=lambda s: s.ordre):
        group = list(group_iter)
        si_steps = [s for s in group if s.branche == AutomationStep.Branche.SI]
        sinon_steps = [
            s for s in group if s.branche == AutomationStep.Branche.SINON]
        if not si_steps or not sinon_steps:
            continue  # pas un groupe SI/SINON complet : pas d'exclusion.
        si_matched = any(
            evaluate_condition_group(s.condition, eval_ctx) if s.condition
            else True
            for s in si_steps)
        if si_matched:
            for s in sinon_steps:
                skips[s.pk] = 'Branche « sinon » non retenue.'
        else:
            for s in si_steps:
                skips[s.pk] = 'Branche « si » non retenue.'

    for s in steps:
        if s.pk in skips:
            continue
        if s.condition and not evaluate_condition_group(s.condition, eval_ctx):
            skips[s.pk] = 'Condition non remplie : étape ignorée.'
    return skips


def _run_steps(rule, steps, start_index, instance, company, context, user):
    """Exécute la séquence ``steps`` à partir du rang ``start_index``.

    NTEXT7 — une étape ``WAIT`` SUSPEND la séquence : l'échéance de reprise est
    écrite (``AutomationScheduledStep``) et la boucle s'arrête là ; le reste de
    la séquence repartira depuis le rang suivant.

    NTEXT5 — avant d'exécuter chaque étape, sa branche/condition est vérifiée
    (``_resolve_step_skips``, calculé UNE FOIS sur toute la séquence, cohérent
    avec une reprise après ``WAIT``) ; une étape ignorée journalise un run
    ``skipped`` motivé et NE STOPPE PAS la séquence.
    """
    result = (AutomationRun.Status.NOOP, '')
    skips = _resolve_step_skips(steps, instance, context)
    for index in range(start_index, len(steps)):
        step = steps[index]
        skip_reason = skips.get(step.pk)
        if skip_reason:
            _log_run(rule, company, instance,
                     AutomationRun.Status.SKIPPED, skip_reason)
            result = (AutomationRun.Status.SKIPPED, skip_reason)
            continue
        if step.action_type == ActionType.WAIT:
            return _schedule_resume(
                rule, step, index + 1, instance, company, context)
        view = _StepView(rule, step)
        step_disabled = _rule_disabled_module(view, instance, company)
        if step_disabled:
            message = (f'Module désactivé ({step_disabled}) : '
                       f'automatisation ignorée.')
            _log_run(rule, company, instance,
                     AutomationRun.Status.SKIPPED, message)
            result = (AutomationRun.Status.SKIPPED, message)
            continue
        try:
            result = _execute(view, rule, instance, company, context, user)
        except Exception as exc:  # best-effort PAR ÉTAPE : la suite continue
            logger.exception(
                'automation: étape %s de la règle %s échouée',
                step.pk, rule.pk)
            _log_run(rule, company, instance,
                     AutomationRun.Status.FAILED, str(exc))
            result = (AutomationRun.Status.FAILED, str(exc))
    return result


def _resolve_target(target_model, target_id, company):
    """Résout ``label.model`` + id en instance, SCOPÉE société. None sinon.

    Le filtre société empêche de résoudre (et donc d'écrire dans) la cible d'un
    autre tenant si un couple label/id venait à croiser. Ne lève jamais.
    """
    if not target_model or not target_id:
        return None
    from django.apps import apps as django_apps
    try:
        app_label, model_name = target_model.split('.', 1)
        model = django_apps.get_model(app_label, model_name)
        lookup = {'pk': target_id}
        if company is not None and _has_company_fk(model):
            lookup['company'] = company
        return model.objects.filter(**lookup).first()
    except Exception:  # pragma: no cover - défensif
        return None


def _json_safe(value):
    """Contexte GELÉ en base : rend une valeur sérialisable JSON (best-effort)."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _schedule_resume(rule, step, next_index, instance, company, context):
    """NTEXT7 — écrit l'échéance de reprise d'une séquence après un ``WAIT``."""
    from datetime import timedelta

    from django.utils import timezone

    from .models import AutomationScheduledStep

    cfg = step.action_config or {}
    try:
        delai = int(cfg.get('delai_minutes') or 0)
    except (TypeError, ValueError):
        delai = 0
    delai = max(0, delai)
    run_at = timezone.now() + timedelta(minutes=delai)
    try:
        AutomationScheduledStep.objects.create(
            company=company, rule=rule,
            target_model=_model_label(instance),
            target_id=getattr(instance, 'pk', None),
            next_step_index=next_index,
            run_at=run_at,
            context=_json_safe(context or {}),
        )
    except Exception as exc:  # pragma: no cover - défensif
        logger.exception('automation: échéance de reprise non créée')
        message = f'Attente non planifiée : {exc}'
        _log_run(rule, company, instance,
                 AutomationRun.Status.FAILED, message)
        return AutomationRun.Status.FAILED, message
    message = (f'Séquence suspendue {delai} minute(s) : reprise prévue le '
               f'{run_at:%Y-%m-%d %H:%M}.')
    _log_run(rule, company, instance, AutomationRun.Status.NOOP, message)
    return AutomationRun.Status.NOOP, message


#: APAR26 — marqueur de contexte d'une échéance « envoi reporté hors fenêtre ».
CLE_REPORT_FENETRE = '_report_fenetre'


def resume_scheduled_step(scheduled, *, user=None):
    """NTEXT7 — reprend UNE séquence suspendue (échéance ``run_at`` atteinte).

    Best-effort et IDEMPOTENT : l'échéance passe à ``reprise`` quoi qu'il
    arrive, une échéance déjà traitée est ignorée. Sans Celery beat déployé,
    rien n'appelle cette fonction : la séquence reste simplement suspendue
    (dégradation propre, aucune erreur).
    """
    from django.utils import timezone

    from .models import AutomationScheduledStep

    if scheduled.statut != AutomationScheduledStep.Statut.EN_ATTENTE:
        return AutomationRun.Status.SKIPPED, 'Échéance déjà traitée.'
    rule = scheduled.rule
    company = scheduled.company
    instance = _resolve_target(
        scheduled.target_model, scheduled.target_id, company)
    scheduled.statut = AutomationScheduledStep.Statut.REPRISE
    scheduled.date_reprise = timezone.now()
    scheduled.save(update_fields=['statut', 'date_reprise'])
    if rule is None or not rule.enabled:
        message = 'Règle supprimée ou désactivée : reprise ignorée.'
        _log_run(rule, company, instance,
                 AutomationRun.Status.SKIPPED, message)
        return AutomationRun.Status.SKIPPED, message
    steps = _rule_steps(rule)
    contexte = dict(scheduled.context or {})
    if contexte.pop(CLE_REPORT_FENETRE, False):
        # APAR26 — reprise d'UNE action reportée hors de la fenêtre des
        # messages (``actions.reporter_hors_fenetre``) : seule cette action
        # repart (le reste de la séquence s'est déjà déroulé).
        if not steps:
            return _execute(rule, rule, instance, company, contexte, user)
        if scheduled.next_step_index < len(steps):
            step = steps[scheduled.next_step_index]
            return _execute(_StepView(rule, step), rule, instance, company,
                            contexte, user)
    if scheduled.next_step_index >= len(steps):
        message = 'Séquence terminée : plus aucune étape à reprendre.'
        _log_run(rule, company, instance, AutomationRun.Status.NOOP, message)
        return AutomationRun.Status.NOOP, message
    return _run_steps(rule, steps, scheduled.next_step_index,
                      instance, company, scheduled.context or {}, user)


def run_approved(approval, *, user=None):
    """Relance l'action différée d'une approbation approuvée (N73).

    Résout l'objet cible à partir de ``target_model``/``target_id`` puis exécute
    l'action. Best-effort, journalisé.
    """
    rule = approval.rule
    if rule is None:
        _log_run(None, approval.company, None, AutomationRun.Status.SKIPPED,
                 'Règle supprimée : action ignorée.')
        return
    instance = _resolve_target(
        approval.target_model, approval.target_id, approval.company)
    # APAR7 — l'état métier a pu changer entre la demande et la décision
    # (facture payée entre-temps) : l'action différée n'a plus d'objet.
    motif = motif_etat_metier(rule.trigger_type, instance)
    if motif:
        _log_run(rule, approval.company, instance,
                 AutomationRun.Status.SKIPPED, motif)
        return
    run_action(rule, instance, approval.company,
               context=approval.context, user=user)


# ── YEVNT11 — Séparation des tâches (SOD) : demandeur ≠ approbateur ─────────
#
# Contrôle SOX de base : côté serveur, un utilisateur ne doit jamais pouvoir
# approuver sa propre demande. S'applique aux TROIS moteurs d'approbation du
# repo (chacun appelle cette fonction depuis SA propre vue — automation,
# compta.DemandeApprobationConfig, ventes « Approuver remise ») ; un override
# admin explicite est permis mais écrit lui-même une ligne d'audit distincte.

class SodViolation(Exception):
    """Levée quand l'approbateur est aussi le demandeur (SOD), sans override."""


def enforce_requester_not_approver(
        *, requester, approver, company=None, label='', allow_admin_override=True):
    """Garde SOD générique : lève ``SodViolation`` si ``approver`` est le
    même utilisateur que ``requester`` — SAUF override admin explicite
    (``allow_admin_override`` et l'appelant a déjà vérifié le rôle admin ;
    cette fonction se contente d'écrire la ligne d'audit distincte quand
    l'appelant signale l'override via ``allow_admin_override=True`` ET que
    ``approver`` porte le rôle admin).

    Aucun effet quand ``requester`` est ``None`` (demandeur inconnu/système) :
    on ne peut pas juger d'une auto-approbation sans demandeur identifié.
    """
    if requester is None or approver is None:
        return
    if requester.pk != approver.pk:
        return  # cas nominal : personnes différentes, rien à faire

    is_admin = bool(getattr(approver, 'is_admin_role', False))
    if allow_admin_override and is_admin:
        _audit_sod_override(approver, company, label)
        return

    _audit_sod_blocked(approver, company, label)
    raise SodViolation(
        "Vous ne pouvez pas approuver votre propre demande "
        "(séparation des tâches).")


def _audit_sod_blocked(user, company, label):
    try:
        from apps.audit.recorder import record
        from apps.audit.models import AuditLog
        record(
            AuditLog.Action.SECURITY_ALERT, user=user, company=company,
            detail=f'SOD : auto-approbation refusée ({label}).')
    except Exception:  # pragma: no cover - best-effort
        logger.debug('automation: audit SOD (blocage) indisponible',
                     exc_info=True)


def _audit_sod_override(user, company, label):
    try:
        from apps.audit.recorder import record
        from apps.audit.models import AuditLog
        record(
            AuditLog.Action.SECURITY_ALERT, user=user, company=company,
            detail=f'SOD : override admin — auto-approbation autorisée '
                   f'({label}).')
    except Exception:  # pragma: no cover - best-effort
        logger.debug('automation: audit SOD (override) indisponible',
                     exc_info=True)


# Réexport pratique.
__all__ = [
    'evaluate', 'run_action', 'run_approved', 'resume_scheduled_step',
    'ActionType', 'TriggerType',
]
