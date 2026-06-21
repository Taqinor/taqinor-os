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
        from authentication.models import Company
        return list(Company.objects.filter(actif=True))
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


# ── Tâche Celery Beat ─────────────────────────────────────────────────────────

@shared_task(name='automation.time_triggers_daily')
def time_triggers_daily():
    """Balayage quotidien des déclencheurs temporels de l'automation engine (FG2).

    Pour chaque société active : évalue WARRANTY_EXPIRING, MAINTENANCE_DUE et
    FACTURE_OVERDUE afin que les règles configurables sur ces déclencheurs
    s'exécutent réellement. Best-effort par société ; renvoie le total
    d'évaluations déclenchées (pas le nombre de règles exécutées)."""
    total = 0
    for company in _companies():
        try:
            total += _trigger_warranty_expiring(company)
            total += _trigger_maintenance_due(company)
            total += _trigger_facture_overdue(company)
        except Exception:  # pragma: no cover
            logger.warning('automation.beat: société %s échouée',
                           getattr(company, 'pk', None), exc_info=True)
    logger.info('time_triggers_daily: %s évaluation(s) déclenchée(s)', total)
    return total
