"""G9/QJ4 — Tâches planifiées (Celery Beat). TROIS jobs, toute la logique de
temps en Africa/Casablanca :

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
  3. ``devis_followup_nudges`` (QJ4) — relance automatique cadencée pour les
     devis « envoyés » toujours en attente de validation. Paliers j+2 / j+5 /
     j+10 après date_envoi (configurable via DEVIS_NUDGE_DAYS). Surface un
     draft wa.me au vendeur (ou email si configuré). Idempotent via
     DevisNudgeLog. S'arrête dès que le devis passe « accepté » / « refusé ».

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

    ERR36 — séquence de relance multi-niveaux NON destructive. Pour chaque
    facture impayée non exclue dont ``prochaine_relance`` est atteinte, on
    envoie le PROCHAIN niveau non encore relancé (et non le plus dur d'emblée),
    on consigne une RelanceLog, puis on AVANCE ``prochaine_relance`` à la date
    d'échéance du niveau suivant (au lieu de la nullifier) — la séquence
    progresse donc niveau par niveau au lieu de ne tirer qu'une fois. Quand le
    dernier niveau a été envoyé (ou s'il n'existe aucun niveau), on efface la
    date pour stopper proprement. Renvoie le nombre de relances déclenchées."""
    from datetime import timedelta
    from .models import Facture, FollowupLevel, RelanceLog
    from .email_service import send_relance_email

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
        levels = list(FollowupLevel.objects.filter(
            company=facture.company).order_by('delai_jours', 'ordre'))
        if not levels:
            # Aucun niveau configuré : envoi générique unique, puis stop.
            send_relance_email(facture, niveau_nom='', message='', user=None)
            RelanceLog.objects.create(
                company=facture.company, facture=facture, niveau=None,
                niveau_nom='', note='Relance automatique programmée (email).')
            facture.prochaine_relance = None
            facture.save(update_fields=['prochaine_relance'])
            sent += 1
            continue

        # Niveau courant = PROCHAIN non encore envoyé (séquence niveau par
        # niveau). On compte les relances automatiques déjà consignées pour
        # cette facture afin de reprendre où la séquence s'est arrêtée — pas de
        # saut direct au niveau le plus dur.
        deja = facture.relances.filter(
            note='Relance automatique programmée (email).').count()
        idx = min(deja, len(levels) - 1)
        niveau = levels[idx]

        send_relance_email(
            facture, niveau_nom=niveau.nom, message=niveau.message, user=None)
        RelanceLog.objects.create(
            company=facture.company, facture=facture, niveau=niveau.ordre,
            niveau_nom=niveau.nom,
            note='Relance automatique programmée (email).')

        # Avance vers le niveau suivant : prochaine_relance = aujourd'hui +
        # (délai du niveau suivant − délai du niveau courant). Dernier niveau
        # atteint → on efface la date (séquence terminée).
        next_idx = idx + 1
        if next_idx < len(levels):
            gap = max(levels[next_idx].delai_jours - niveau.delai_jours, 1)
            facture.prochaine_relance = today + timedelta(days=gap)
        else:
            facture.prochaine_relance = None
        facture.save(update_fields=['prochaine_relance'])
        sent += 1

    logger.info('relance_reminders: %s relance(s) envoyée(s)', sent)
    return sent


@shared_task(name='ventes.expire_stale_devis')
def expire_stale_devis():
    """QJ5 — Expiration automatique des devis dépassés + hygiène du funnel CRM.

    Bascule ``envoye → expire`` pour tout devis dont la date de validité effective
    est dépassée (via ``services.expire_stale_devis``, même logique que
    l'indicateur à la volée — cohérence garantie). Avance ensuite l'étape funnel
    du lead lié : QUOTE_SENT → FOLLOW_UP, puis FOLLOW_UP → COLD si inactif
    depuis 30 jours. Ne touche JAMAIS un devis ``accepte`` / ``refuse`` (rule #4),
    ne recule JAMAIS un lead déjà plus avancé (SIGNED), ignore les leads perdus.
    Idempotent et safe à ré-exécuter.
    """
    from .services import expire_stale_devis as _expire
    result = _expire()
    logger.info(
        'expire_stale_devis: %d expiré(s), %d → FOLLOW_UP, %d → COLD',
        result['expired'], result['funnel_followup'], result['funnel_cold'])
    return result


@shared_task(name='ventes.devis_followup_nudges')
def devis_followup_nudges():
    """QJ4 — Relance automatique cadencée des devis envoyés toujours en attente.

    Délègue toute la logique à ``services.send_devis_followup_nudges`` pour que
    la logique métier reste testable sans Celery. Renvoie le nombre de nudges
    déclenchés.

    Idempotent : safe à ré-exécuter. Ne touche JAMAIS au statut du Devis
    (RULE #4). Toute la logique de temps raisonne en Africa/Casablanca.
    """
    from .services import send_devis_followup_nudges
    count = send_devis_followup_nudges()
    logger.info('devis_followup_nudges: %d nudge(s) déclenchés', count)
    return count
