"""FG2 — Déclencheurs temporels de l'automation engine via Celery Beat.

`automation/models.py` déclare `WARRANTY_EXPIRING` / `MAINTENANCE_DUE` /
`FACTURE_OVERDUE` comme `TriggerType` et l'UI les offre, mais `signals.py`
ne les wire que sur `post_save` (`_equipement_saved` est un explicit no-op).
Ce module ajoute la tâche beat qui appelle `engine.evaluate(TriggerType.X,
instance, company)` pour chaque instance correspondante, so que les règles
configurables sur ces déclencheurs temporels s'exécutent réellement.

Principes :
  - IDEMPOTENT : ne mute aucune donnée hors des actions de règles activées.
    Re-lancer la tâche peut ré-exécuter des règles (c'est voulu et bien
    journalisé dans `AutomationRun`) mais ne casse rien.
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
        for eq in qs:
            try:
                evaluate(TriggerType.WARRANTY_EXPIRING, eq, company)
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
        for contrat in qs:
            try:
                if not contrat.is_due():
                    continue
                evaluate(TriggerType.MAINTENANCE_DUE, contrat, company)
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
        from apps.automation.engine import evaluate
        from apps.automation.models import TriggerType
        from apps.ventes.models import Facture
        today = timezone.localdate()
        qs = Facture.objects.filter(
            company=company,
            date_echeance__lt=today,
        ).exclude(statut='payee')
        count = 0
        for facture in qs:
            try:
                evaluate(TriggerType.FACTURE_OVERDUE, facture, company)
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
        from apps.automation.engine import evaluate
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


# ── ZPAI12 — Alerte de clôture de paie en retard ─────────────────────────────

def _trigger_paie_cloture_retard(company):
    """Notifie (best-effort) les ``PeriodePaie`` en retard de clôture (ZPAI12).

    Délègue entièrement à ``apps.paie.services.notifier_cloture_en_retard``
    (idempotence portée par ``PeriodePaie.date_alerte_cloture_retard``, côté
    paie) — ce module ne fait que la brancher sur le balayage quotidien,
    comme les autres déclencheurs temporels. No-op si l'app paie est absente.
    """
    try:
        from apps.paie.services import notifier_cloture_en_retard

        return len(notifier_cloture_en_retard(company))
    except Exception:  # pragma: no cover
        logger.warning(
            'automation.beat: paie_cloture_retard société %s échouée',
            getattr(company, 'pk', None), exc_info=True)
        return 0


# ── Tâche Celery Beat ─────────────────────────────────────────────────────────

@shared_task(name='automation.time_triggers_daily')
def time_triggers_daily():
    """Balayage quotidien des déclencheurs temporels de l'automation engine (FG2).

    Pour chaque société active : évalue WARRANTY_EXPIRING, MAINTENANCE_DUE,
    FACTURE_OVERDUE et l'alerte de clôture de paie en retard (ZPAI12) afin
    que les règles configurables sur ces déclencheurs s'exécutent réellement.
    Best-effort par société ; renvoie le total d'évaluations déclenchées (pas
    le nombre de règles exécutées)."""
    total = 0
    for company in _companies():
        try:
            total += _trigger_warranty_expiring(company)
            total += _trigger_maintenance_due(company)
            total += _trigger_facture_overdue(company)
            total += _trigger_date_echeance_champ(company)
            total += _trigger_paie_cloture_retard(company)
        except Exception:  # pragma: no cover
            logger.warning('automation.beat: société %s échouée',
                           getattr(company, 'pk', None), exc_info=True)
    logger.info('time_triggers_daily: %s évaluation(s) déclenchée(s)', total)
    return total
