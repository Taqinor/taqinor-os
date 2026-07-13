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

from .models import (
    ActionType, AutomationApproval, AutomationRule, AutomationRun, TriggerType,
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

    if rule.trigger_type in (
            TriggerType.PROJET_STATUS_CHANGE, TriggerType.PROJET_PHASE_CHANGE):
        # XPRJ23 — enums PROPRES à gestion_projet (jamais STAGES.py, règle
        # #2) ; émis DEPUIS le module (pas de signal Django ici), donc le
        # nouveau statut/phase est TOUJOURS fourni dans ``context``.
        wanted = cfg.get('statut')
        if not wanted:
            return True
        return ctx.get('new_statut') == wanted

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

    # DEVIS_ACCEPTED / FACTURE_OVERDUE / WARRANTY_EXPIRING / MAINTENANCE_DUE /
    # STOCK_BELOW_THRESHOLD : la condition est déjà tranchée par l'émetteur du
    # signal (le moteur n'est appelé que quand l'événement s'est produit).
    return True


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


def run_action(rule, instance, company, *, context=None, user=None):
    """Exécute l'action d'une règle et journalise le résultat.

    Utilisée par ``evaluate`` (immédiat) et par l'approbation (différée).

    ODX23 — si le module visé (déclencheur ou action, voir
    :func:`_rule_disabled_module`) est désactivé ``ModuleToggle`` pour
    ``company``, l'action n'est PAS exécutée : un run ``SKIPPED`` est
    journalisé (« module désactivé ») à la place. Couvre le chemin immédiat
    ET l'approbation différée (``run_approved`` appelle cette même fonction),
    y compris le cas où le module a été désactivé ENTRE la demande
    d'approbation et sa décision.
    """
    disabled_module = _rule_disabled_module(rule, instance, company)
    if disabled_module:
        message = f'Module désactivé ({disabled_module}) : automatisation ignorée.'
        _log_run(rule, company, instance, AutomationRun.Status.SKIPPED, message)
        return AutomationRun.Status.SKIPPED, message
    from . import actions
    # Marque la fenêtre d'exécution : tout ``instance.save()` déclenché par
    # l'action (SET_FIELD / ASSIGN_RECORD) ré-émet le post_save, mais
    # ``evaluate`` se court-circuite tant que ce drapeau est posé → pas de
    # récursion.
    previous = _in_automation()
    _GUARD.active = True
    try:
        status, message = actions.run(rule, instance, company, context, user)
    finally:
        _GUARD.active = previous
    _log_run(rule, company, instance, status, message)
    return status, message


def run_approved(approval, *, user=None):
    """Relance l'action différée d'une approbation approuvée (N73).

    Résout l'objet cible à partir de ``target_model``/``target_id`` puis exécute
    l'action. Best-effort, journalisé.
    """
    from django.apps import apps as django_apps
    rule = approval.rule
    if rule is None:
        _log_run(None, approval.company, None, AutomationRun.Status.SKIPPED,
                 'Règle supprimée : action ignorée.')
        return
    instance = None
    if approval.target_model and approval.target_id:
        try:
            app_label, model_name = approval.target_model.split('.', 1)
            model = django_apps.get_model(app_label, model_name)
            # Filtre société : empêche de résoudre (et donc d'écrire) une cible
            # d'un autre tenant si target_model/target_id venaient à croiser.
            lookup = {'pk': approval.target_id}
            if approval.company_id and _has_company_fk(model):
                lookup['company'] = approval.company
            instance = model.objects.filter(**lookup).first()
        except Exception:  # pragma: no cover
            instance = None
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
    'evaluate', 'run_action', 'run_approved', 'ActionType', 'TriggerType',
]
