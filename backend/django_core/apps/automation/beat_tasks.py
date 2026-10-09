"""FG2 — Déclencheurs temporels de l'automation engine via Celery Beat.

`automation/models.py` déclare `WARRANTY_EXPIRING` / `MAINTENANCE_DUE` /
`FACTURE_OVERDUE` comme `TriggerType` et l'UI les offre, mais `signals.py`
ne les wire que sur `post_save` (`_equipement_saved` est un explicit no-op).
Ce module ajoute la tâche beat qui appelle `engine.evaluate(TriggerType.X,
instance, company)` pour chaque instance correspondante, so que les règles
configurables sur ces déclencheurs temporels s'exécutent réellement.

Principes :
  - IDEMPOTENT PAR OCCURRENCE ET PAR OBJET (AUD822 → APAR8) : un marqueur `AutomationRun` est
    posé après chaque évaluation et vérifié avant la suivante — voir la section
    « Marqueur d'idempotence » ci-dessous. Re-lancer la tâche le même jour ne
    ré-exécute jamais une règle déjà tirée pour le même objet.
  - MULTI-TENANT : chaque société est traitée isolément.
  - DÉFENSIF : chaque section est dans son propre try/except ; une erreur sur
    un modèle absent ou une société ne bloque pas les autres.
  - ADDITIF : sans règle `enabled=True`, `engine.evaluate` fait un no-op total.
"""
import logging
from datetime import date, timedelta

from celery import shared_task

logger = logging.getLogger(__name__)

# ── Seuils ────────────────────────────────────────────────────────────────────
WARRANTY_HORIZON_DAYS = 90   # identique à notifications/sweeps.py
OVERDUE_GRACE_DAYS = 0       # facture en retard dès l'échéance dépassée


# ── AUD822 — Marqueur d'idempotence des déclencheurs temporels ────────────────
#
# DÉFAUT CORRIGÉ : `_trigger_warranty_expiring` / `_trigger_maintenance_due` /
# `_trigger_facture_overdue` bouclaient QUOTIDIENNEMENT et appelaient
# `evaluate()` sans jamais vérifier qu'une évaluation avait déjà eu lieu la
# veille — contrairement à `_trigger_date_echeance_champ` (XPLT3) qui posait et
# vérifiait déjà un marqueur. Conséquences réelles : une facture impayée depuis
# 60 jours envoyait au client le MÊME email de relance 60 fois (le preset
# officiel `email_on_facture_overdue` a `requires_approval=False`), et une règle
# `CREATE_SAV_TICKET` sur `MAINTENANCE_DUE` créait un ticket SAV par jour tant
# que le contrat restait dû (`_create_sav_ticket` crée inconditionnellement).
#
# Le marqueur généralise EXACTEMENT le patron XPLT3 : une entrée `AutomationRun`
# NOOP dont le message commence par une clé stable
# `AUD822:<trigger>:<app.model>:<pk>:<jour ISO>`, vérifiée AVANT `evaluate()`.
# `rule` est nul sur ces entrées (le marqueur vaut pour le couple
# déclencheur+objet, pas pour une règle donnée : `evaluate` tire toutes les
# règles activées d'un coup).
#
# Il n'est posé QUE si la société a au moins une règle activée sur ce
# déclencheur : sans règle, il n'y a rien à rendre idempotent, et on n'inonde
# pas le journal des sociétés qui n'automatisent pas.
MARQUEUR_PREFIXE = 'AUD822'

# APAR8 — la clé n'est plus le JOUR du passage mais l'OCCURRENCE MÉTIER : la
# date d'échéance de la facture, la ``prochaine_visite()`` du contrat, la fin
# de garantie de l'équipement. Avant, la clé journalière relançait le client
# CHAQUE JOUR (« 60 e-mails pour 60 jours ») ; désormais une occurrence = une
# relance, et seule une NOUVELLE occurrence (facture rééchelonnée, visite
# suivante) relance de nouveau.
FACTURE_LABEL = 'ventes.facture'


def _marqueur(trigger_type, model_label, obj_pk, occurrence):
    """Clé stable du marqueur : déclencheur + objet + OCCURRENCE métier."""
    occ = (occurrence.isoformat() if hasattr(occurrence, 'isoformat')
           else str(occurrence))
    return f'{MARQUEUR_PREFIXE}:{trigger_type}:{model_label}:{obj_pk}:{occ}'


def marqueur_facture(facture):
    """APAR8 — marqueur de l'occurrence « facture échue à telle échéance »,
    PARTAGÉ par le balayage et le signal ``_facture_saved``."""
    from apps.automation.models import TriggerType
    return _marqueur(TriggerType.FACTURE_OVERDUE, FACTURE_LABEL, facture.pk,
                     facture.date_echeance)


def evaluer_facture_overdue_une_fois(facture, company):
    """APAR8 — évalue FACTURE_OVERDUE pour l'occurrence courante de la
    facture SAUF si elle a déjà été évaluée (signal OU balayage). Renvoie
    True si une évaluation a eu lieu."""
    from apps.automation.engine import evaluate
    from apps.automation.models import TriggerType
    garde = _a_des_regles(company, TriggerType.FACTURE_OVERDUE)
    marqueur = marqueur_facture(facture)
    if garde and _deja_declenche(company, marqueur):
        return False
    evaluate(TriggerType.FACTURE_OVERDUE, facture, company)
    if garde:
        _poser_marqueur(company, marqueur, FACTURE_LABEL, facture.pk)
    return True


def _a_des_regles(company, trigger_type):
    """Vrai si la société a AU MOINS une règle activée sur ce déclencheur."""
    try:
        from apps.automation.models import AutomationRule
        return AutomationRule.objects.filter(
            company=company, enabled=True, trigger_type=trigger_type).exists()
    except Exception:  # pragma: no cover - défensif
        return False


def _deja_declenche(company, marqueur):
    """Vrai si ce couple (déclencheur, objet, jour) a déjà été évalué."""
    try:
        from apps.automation.models import AutomationRun
        return AutomationRun.objects.filter(
            company=company, message__startswith=marqueur).exists()
    except Exception:  # pragma: no cover - défensif
        return False


def _poser_marqueur(company, marqueur, model_label, obj_pk):
    """Journalise le marqueur d'idempotence (entrée NOOP, sans règle)."""
    try:
        from apps.automation.models import AutomationRun
        AutomationRun.objects.create(
            company=company, rule=None,
            target_model=model_label, target_id=obj_pk,
            status=AutomationRun.Status.NOOP,
            message=f'{marqueur} — marqueur idempotence AUD822.')
    except Exception:  # pragma: no cover - défensif
        logger.warning('automation.beat: marqueur %s non posé', marqueur,
                       exc_info=True)


def _companies():
    try:
        # SCA19 — source unique des sociétés balayables : un tenant suspendu/en
        # fermeture (actif=False via le pont SCA18) est exclu des automations.
        from authentication.selectors import active_companies
        return list(active_companies())
    except Exception:  # pragma: no cover
        logger.warning('automation.beat: chargement des sociétés impossible',
                       exc_info=True)
        return []


# ── WARRANTY_EXPIRING ─────────────────────────────────────────────────────────

def _trigger_warranty_expiring(company):
    """Évalue WARRANTY_EXPIRING pour chaque équipement EN SERVICE dont la
    garantie expire dans WARRANTY_HORIZON_DAYS jours."""
    try:
        from apps.automation.engine import evaluate
        from apps.automation.models import TriggerType
        from apps.sav.models import Equipement
        today = date.today()
        horizon = today + timedelta(days=WARRANTY_HORIZON_DAYS)
        qs = Equipement.objects.filter(
            company=company,
            statut=Equipement.Statut.EN_SERVICE,
            date_fin_garantie__isnull=False,
            date_fin_garantie__gte=today,
            date_fin_garantie__lte=horizon,
        )
        count = 0
        # APAR8 — un équipement est évalué UNE fois par fin de garantie.
        garde = _a_des_regles(company, TriggerType.WARRANTY_EXPIRING)
        for eq in qs:
            marqueur = _marqueur(
                TriggerType.WARRANTY_EXPIRING, 'sav.equipement', eq.pk,
                eq.date_fin_garantie)
            if garde and _deja_declenche(company, marqueur):
                continue
            try:
                evaluate(TriggerType.WARRANTY_EXPIRING, eq, company)
                if garde:
                    _poser_marqueur(
                        company, marqueur, 'sav.equipement', eq.pk)
                count += 1
            except Exception:  # pragma: no cover
                logger.warning('automation.beat: warranty eq %s échoué',
                               eq.pk, exc_info=True)
        return count
    except Exception:  # pragma: no cover
        logger.warning('automation.beat: warranty_expiring société %s échouée',
                       getattr(company, 'pk', None), exc_info=True)
        return 0


# ── MAINTENANCE_DUE ───────────────────────────────────────────────────────────

def _trigger_maintenance_due(company):
    """Évalue MAINTENANCE_DUE pour chaque contrat actif dont is_due() vrai."""
    try:
        from apps.automation.engine import evaluate
        from apps.automation.models import TriggerType
        from apps.sav.models import ContratMaintenance
        qs = ContratMaintenance.objects.filter(company=company, actif=True)
        count = 0
        # AUD822 — sans ce marqueur, une règle CREATE_SAV_TICKET créait un
        # ticket par JOUR tant que le contrat restait dû. APAR8 — clé = la
        # visite due (``prochaine_visite()``), pas le jour du passage.
        garde = _a_des_regles(company, TriggerType.MAINTENANCE_DUE)
        for contrat in qs:
            try:
                if not contrat.is_due():
                    continue
                marqueur = _marqueur(
                    TriggerType.MAINTENANCE_DUE, 'sav.contratmaintenance',
                    contrat.pk, contrat.prochaine_visite())
                if garde and _deja_declenche(company, marqueur):
                    continue
                evaluate(TriggerType.MAINTENANCE_DUE, contrat, company)
                if garde:
                    _poser_marqueur(
                        company, marqueur, 'sav.contratmaintenance',
                        contrat.pk)
                count += 1
            except Exception:  # pragma: no cover
                logger.warning('automation.beat: maintenance contrat %s échoué',
                               contrat.pk, exc_info=True)
        return count
    except Exception:  # pragma: no cover
        logger.warning('automation.beat: maintenance_due société %s échouée',
                       getattr(company, 'pk', None), exc_info=True)
        return 0


# ── FACTURE_OVERDUE ───────────────────────────────────────────────────────────

def _trigger_facture_overdue(company):
    """Évalue FACTURE_OVERDUE pour chaque facture en retard (non réglée,
    échéance dépassée). Le signal post_save déclenche déjà lors d'un save
    mais pas lors d'un glissement naturel de date ; c'est ce balayage qui
    couvre ce cas.

    On exclut les factures déjà avec statut `payee` et celles dont l'échéance
    n'est pas encore dépassée."""
    try:
        from django.utils import timezone
        from apps.automation.engine import (
            FACTURE_STATUTS_RELANCABLES, motif_etat_metier,
        )
        from apps.automation.models import TriggerType
        from apps.ventes.models import Facture
        today = timezone.localdate()
        # APAR7 — seules les factures ÉMISES (ou en retard) sont candidates ;
        # le reste exigible > 0 est vérifié par le prédicat unique ci-dessous.
        qs = Facture.objects.filter(
            company=company,
            date_echeance__lt=today,
            statut__in=FACTURE_STATUTS_RELANCABLES,
        )
        count = 0
        # AUD822/APAR8 — sans ce marqueur, le client recevait le MÊME email de
        # relance chaque jour tant que la facture restait impayée ; il est
        # désormais clé sur l'ÉCHÉANCE (une relance par occurrence) et partagé
        # avec le signal ``_facture_saved``.
        for facture in qs:
            if motif_etat_metier(TriggerType.FACTURE_OVERDUE, facture):
                continue  # APAR7 — soldée : aucune relance, aucun marqueur.
            try:
                if evaluer_facture_overdue_une_fois(facture, company):
                    count += 1
            except Exception:  # pragma: no cover
                logger.warning('automation.beat: facture_overdue %s échouée',
                               facture.pk, exc_info=True)
        return count
    except Exception:  # pragma: no cover
        logger.warning('automation.beat: facture_overdue société %s échouée',
                       getattr(company, 'pk', None), exc_info=True)
        return 0


# ── DATE_ECHEANCE_CHAMP (XPLT3) ───────────────────────────────────────────────

def _trigger_date_echeance_champ(company):
    """Évalue le déclencheur générique « champ date ± N jours » (XPLT3) pour
    chaque règle DATE_ECHEANCE_CHAMP activée de la société.

    ``trigger_config`` attendu : {'model': 'ventes.devis',
    'champ': 'date_validite', 'offset_jours': -3}. Un ``offset_jours``
    négatif signifie « N jours AVANT l'échéance » (le cas le plus courant :
    relancer avant l'expiration) ; positif = après.

    IDEMPOTENCE : un marqueur ``AutomationRun`` (message préfixé par la date
    d'échéance exacte) est vérifié avant d'évaluer — re-lancer la tâche le
    même jour pour la même règle+objet+échéance ne tire jamais deux fois.
    """
    try:
        from django.apps import apps as django_apps
        from django.utils import timezone
        from apps.automation.engine import evaluate, motif_etat_metier
        from apps.automation.models import (
            AutomationRule, AutomationRun, DATE_TRIGGER_TARGETS, TriggerType,
        )

        today = timezone.localdate()
        count = 0
        rules = AutomationRule.objects.filter(
            company=company, enabled=True,
            trigger_type=TriggerType.DATE_ECHEANCE_CHAMP)
        for rule in rules:
            cfg = rule.trigger_config or {}
            model_label = cfg.get('model', '')
            champ = cfg.get('champ')
            try:
                offset = int(cfg.get('offset_jours', 0))
            except (TypeError, ValueError):
                continue
            try:
                app_label, model_name = str(model_label).split('.', 1)
            except ValueError:
                continue
            allowed_fields = DATE_TRIGGER_TARGETS.get(
                (app_label, model_name))
            if not allowed_fields or champ not in allowed_fields:
                continue  # whitelist fermée : modèle/champ non autorisé
            model = django_apps.get_model(app_label, model_name)
            if model is None:
                continue
            # offset=-3 ("3 jours AVANT l'échéance") doit matcher une échéance
            # qui tombe 3 jours DANS LE FUTUR (today - offset), pas dans le
            # passé : `today + offset` donnait `today - 3`, l'inverse de
            # l'intention documentée ci-dessus (et ne tirait jamais pour une
            # échéance à venir).
            target_date = today - timedelta(days=offset)
            filter_kwargs = {'company': company, f'{champ}': target_date}
            try:
                qs = model.objects.filter(**filter_kwargs)
            except Exception:  # pragma: no cover - champ FK-incompatible
                continue
            for obj in qs:
                # APAR7 — seul un devis ENVOYÉ (lead non perdu) est relancé.
                if motif_etat_metier(TriggerType.DATE_ECHEANCE_CHAMP, obj):
                    continue
                marker = (
                    f'XPLT3:{rule.pk}:{model_label}:{obj.pk}:'
                    f'{target_date.isoformat()}')
                already = AutomationRun.objects.filter(
                    company=company, rule=rule,
                    message__startswith=marker).exists()
                if already:
                    continue
                try:
                    evaluate(
                        TriggerType.DATE_ECHEANCE_CHAMP, obj, company,
                        context={
                            'model': model_label, 'champ': champ,
                            'offset_jours': offset,
                            'echeance': target_date.isoformat(),
                        })
                    # Journalise le marqueur d'idempotence (même si
                    # `evaluate` a déjà journalisé un run pour cette règle —
                    # on ajoute une entrée dédiée pour ne jamais confondre le
                    # marqueur avec un run ordinaire d'une autre exécution).
                    AutomationRun.objects.create(
                        company=company, rule=rule,
                        target_model=model_label, target_id=obj.pk,
                        status=AutomationRun.Status.NOOP,
                        message=f'{marker} — marqueur idempotence XPLT3.')
                    count += 1
                except Exception:  # pragma: no cover
                    logger.warning(
                        'automation.beat: date_echeance_champ %s/%s échoué',
                        rule.pk, obj.pk, exc_info=True)
        return count
    except Exception:  # pragma: no cover
        logger.warning(
            'automation.beat: date_echeance_champ société %s échouée',
            getattr(company, 'pk', None), exc_info=True)
        return 0


# ── Tâche Celery Beat ─────────────────────────────────────────────────────────

@shared_task(name='automation.time_triggers_daily')
def time_triggers_daily():
    """Balayage quotidien des déclencheurs temporels de l'automation engine (FG2).

    Pour chaque société active : évalue WARRANTY_EXPIRING, MAINTENANCE_DUE et
    FACTURE_OVERDUE afin que les règles configurables sur ces déclencheurs
    s'exécutent réellement. Best-effort par société ; renvoie le total
    d'évaluations déclenchées (pas le nombre de règles exécutées).

    AUD822 — le total ne compte que les évaluations NOUVELLES : un objet déjà
    évalué le même jour est ignoré (marqueur d'idempotence), donc deux passages
    dans la journée ne relancent pas deux fois les mêmes envois."""
    total = 0
    for company in _companies():
        try:
            total += _trigger_warranty_expiring(company)
            total += _trigger_maintenance_due(company)
            total += _trigger_facture_overdue(company)
            total += _trigger_date_echeance_champ(company)
        except Exception:  # pragma: no cover
            logger.warning('automation.beat: société %s échouée',
                           getattr(company, 'pk', None), exc_info=True)
    logger.info('time_triggers_daily: %s évaluation(s) déclenchée(s)', total)
    return total


# ── NTEXT7 — reprise des séquences suspendues par une étape « Attendre » ─────

#: Borne par passage : une reprise ne doit jamais monopoliser le worker.
MAX_REPRISES_PAR_PASSAGE = 200


@shared_task(name='automation.process_due_automation_steps')
def process_due_automation_steps():
    """Reprend les séquences d'automatisation dont l'échéance est atteinte.

    Sans Celery beat déployé, cette tâche n'est simplement jamais appelée : les
    échéances restent ``en attente`` et rien ne casse (dégradation propre).
    Best-effort par échéance, idempotent (une échéance déjà reprise est
    ignorée), borné à :data:`MAX_REPRISES_PAR_PASSAGE` par passage.
    """
    try:
        from django.utils import timezone

        from apps.automation.engine import resume_scheduled_step
        from apps.automation.models import AutomationScheduledStep
    except Exception:  # pragma: no cover - défensif
        logger.warning('automation.beat: reprise indisponible', exc_info=True)
        return 0

    dues = list(AutomationScheduledStep.objects.filter(
        statut=AutomationScheduledStep.Statut.EN_ATTENTE,
        run_at__lte=timezone.now(),
    ).order_by('run_at', 'id')[:MAX_REPRISES_PAR_PASSAGE])
    total = 0
    for echeance in dues:
        try:
            resume_scheduled_step(echeance)
            total += 1
        except Exception:  # pragma: no cover - best-effort par échéance
            logger.warning('automation.beat: reprise %s échouée',
                           echeance.pk, exc_info=True)
    if total:
        logger.info('process_due_automation_steps: %s reprise(s)', total)
    return total
