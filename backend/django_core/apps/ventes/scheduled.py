"""G9 — Tâches planifiées (Celery Beat). DEUX jobs, toute la logique de temps en
Africa/Casablanca :

  1. ``relance_reminders`` — envoie les rappels de relance programmés : pour
     chaque facture impayée dont ``prochaine_relance`` est arrivée à échéance
     (en date Casablanca), envoie l'email de relance via l'intégration N87
     (NO-OP réseau sans clé) et consigne une RelanceLog.
  2. ``check_overdue_factures`` — contrôle quotidien des factures en retard :
     une facture est en retard si son échéance est dépassée ET qu'elle n'est
     pas entièrement réglée. Sans ``date_echeance``, l'échéance par défaut est
     la date d'émission + 30 jours. Le job bascule alors ``statut`` →
     ``en_retard``. Idempotent : une facture déjà ``en_retard`` n'est pas
     re-basculée, une facture réglée/annulée est ignorée.

La planification réelle (cadence) est définie dans ``CELERY_BEAT_SCHEDULE``
(settings) ; ces tâches sont sûres à ré-exécuter (idempotentes).
"""
import logging
from datetime import timedelta

from celery import shared_task

logger = logging.getLogger(__name__)

# Toute la logique de dates de ces jobs raisonne en heure du Maroc.
CASABLANCA_TZ = 'Africa/Casablanca'

# Échéance par défaut quand aucune date d'échéance n'est posée sur la facture.
DEFAULT_ECHEANCE_DAYS = 30


def casablanca_today():
    """Date « aujourd'hui » au fuseau Africa/Casablanca (jamais UTC)."""
    from django.utils import timezone
    try:
        from zoneinfo import ZoneInfo
        return timezone.now().astimezone(ZoneInfo(CASABLANCA_TZ)).date()
    except Exception:  # pragma: no cover - zoneinfo absent (très improbable)
        return timezone.localdate()


def _echeance_effective(facture, today):
    """Échéance retenue : ``date_echeance`` si posée, sinon émission + 30 j."""
    if facture.date_echeance:
        return facture.date_echeance
    base = facture.date_emission or today
    return base + timedelta(days=DEFAULT_ECHEANCE_DAYS)


@shared_task(name='ventes.check_overdue_factures')
def check_overdue_factures():
    """Bascule en ``en_retard`` les factures dues dont l'échéance est dépassée.

    Idempotent : ne touche que les factures encore ``emise`` (ou brouillon
    émis) avec un reste à payer > 0 et une échéance (effective) passée. Renvoie
    le nombre de factures basculées."""
    from .models import Facture

    today = casablanca_today()
    flipped = 0
    # On ne considère que les statuts « ouverts » : émise (déjà en retard exclu
    # car déjà au bon statut → idempotence), jamais payée/annulée.
    candidates = Facture.objects.filter(
        statut=Facture.Statut.EMISE).select_related('client').prefetch_related(
        'lignes', 'paiements', 'avoirs')
    for facture in candidates:
        if facture.montant_du <= 0:
            continue
        echeance = _echeance_effective(facture, today)
        if echeance >= today:
            continue
        facture.statut = Facture.Statut.EN_RETARD
        facture.save(update_fields=['statut'])
        flipped += 1
    logger.info('check_overdue_factures: %s facture(s) basculée(s) en retard',
                flipped)
    return flipped


@shared_task(name='ventes.relance_reminders')
def relance_reminders():
    """Envoie les relances programmées arrivées à échéance (date Casablanca).

    Pour chaque facture impayée non exclue dont ``prochaine_relance`` est
    atteinte, envoie l'email de relance (N87, NO-OP sans clé), consigne une
    RelanceLog, et efface ``prochaine_relance`` pour ne pas re-déclencher
    (idempotence). Renvoie le nombre de relances déclenchées."""
    from .models import Facture, FollowupLevel, RelanceLog

    today = casablanca_today()
    sent = 0
    factures = Facture.objects.filter(
        prochaine_relance__lte=today, exclu_relances=False,
    ).exclude(
        statut__in=['payee', 'annulee', 'brouillon'],
    ).select_related('client', 'company').prefetch_related(
        'lignes', 'paiements', 'avoirs')

    for facture in factures:
        if facture.montant_du <= 0:
            facture.prochaine_relance = None
            facture.save(update_fields=['prochaine_relance'])
            continue
        # Niveau courant : le plus haut seuil de retard atteint.
        levels = list(FollowupLevel.objects.filter(
            company=facture.company).order_by('delai_jours'))
        jr = facture.jours_retard
        niveau = None
        for lvl in levels:
            if jr >= lvl.delai_jours:
                niveau = lvl
        niveau_nom = niveau.nom if niveau else ''
        message = niveau.message if niveau else ''

        from .email_service import send_relance_email
        send_relance_email(
            facture, niveau_nom=niveau_nom, message=message, user=None)
        RelanceLog.objects.create(
            company=facture.company, facture=facture,
            niveau=(niveau.ordre if niveau else None),
            niveau_nom=niveau_nom,
            note='Relance automatique programmée (email).')
        # On consomme la date pour éviter un re-déclenchement quotidien.
        facture.prochaine_relance = None
        facture.save(update_fields=['prochaine_relance'])
        sent += 1

    logger.info('relance_reminders: %s relance(s) envoyée(s)', sent)
    return sent
