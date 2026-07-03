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


def _check_promesses_expirees(today):
    """XFAC5 — marque ``rompue`` toute promesse ``en_cours`` dont la date est
    dépassée SANS encaissement suffisant, et libère la suspension de relance
    (``exclu_relances_jusquau``) de la facture pour que ``relance_reminders``
    reprenne avec un flag « promesse rompue » (priorité haute dans la liste
    des impayés de ``recouvrement.py``). Une promesse tenue (facture réglée
    avant/à la date promise) n'est jamais touchée ici — elle est marquée
    ``tenue`` dès que la facture passe payée (voir ``enregistrer_paiement``
    côté vue, qui referme les promesses en cours à ce moment-là)."""
    from .models import PromessePaiement

    rompues = 0
    en_cours = PromessePaiement.objects.filter(
        statut=PromessePaiement.Statut.EN_COURS,
        date_promise__lt=today,
    ).select_related('facture').prefetch_related(
        'facture__paiements', 'facture__avoirs',
        'facture__retenues_subies', 'facture__affectations_paiement')
    for promesse in en_cours:
        facture = promesse.facture
        if facture.montant_du <= 0:
            promesse.statut = PromessePaiement.Statut.TENUE
            promesse.save(update_fields=['statut'])
            continue
        promesse.statut = PromessePaiement.Statut.ROMPUE
        promesse.save(update_fields=['statut'])
        if facture.exclu_relances_jusquau is not None:
            facture.exclu_relances_jusquau = None
            facture.save(update_fields=['exclu_relances_jusquau'])
        rompues += 1
    return rompues


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
    date pour stopper proprement. Renvoie le nombre de relances déclenchées.

    XFAC5 — avant tout envoi, expire les promesses de paiement dépassées
    (``_check_promesses_expirees``), puis SAUTE toute facture dont
    ``exclu_relances_jusquau`` est encore dans le futur (promesse active en
    cours) : la relance reste suspendue jusqu'à la date promise ou la rupture
    de la promesse."""
    from datetime import timedelta
    from .models import Facture, FollowupLevel, RelanceLog
    from .email_service import send_relance_email

    today = casablanca_today()
    _check_promesses_expirees(today)
    sent = 0
    factures = Facture.objects.filter(
        prochaine_relance__lte=today, exclu_relances=False,
    ).exclude(
        statut__in=['payee', 'annulee', 'brouillon'],
    ).exclude(
        exclu_relances_jusquau__gte=today,
    ).select_related('client', 'company').prefetch_related(
        'lignes', 'paiements', 'avoirs')

    # LITIGE3 — import local pour respecter les contrats d'import CI-enforced
    # (ventes ne doit pas importer les modèles d'une autre app au niveau module).
    from apps.litiges.selectors import relances_suspendues_pour_facture

    for facture in factures:
        # LITIGE3 — sauter si un litige financier bloquant est actif.
        if relances_suspendues_pour_facture(facture.id, facture.company):
            logger.info(
                'relance_reminders: facture %s suspendue (litige actif)', facture.id)
            continue
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
        # DC19 — la date de relance est reportée au prochain JOUR OUVRÉ de la
        # société (week-end/férié → jour ouvré suivant) via le référentiel
        # calendrier partagé : on ne relance jamais un client un jour non ouvré.
        next_idx = idx + 1
        if next_idx < len(levels):
            gap = max(levels[next_idx].delai_jours - niveau.delai_jours, 1)
            cible = today + timedelta(days=gap)
            try:
                from apps.notifications.calendar_utils import prochain_jour_ouvre
                cible = prochain_jour_ouvre(cible, facture.company)
            except Exception:  # noqa: BLE001 — calendrier absent → date brute
                pass
            facture.prochaine_relance = cible
        else:
            facture.prochaine_relance = None
        facture.save(update_fields=['prochaine_relance'])
        sent += 1

    logger.info('relance_reminders: %s relance(s) envoyée(s)', sent)
    return sent


@shared_task(name='crm.appointment_reminders')
def appointment_reminders():
    """QJ20 — Envoie les rappels de visites planifiées arrivant dans l'heure.

    Délègue toute la logique à ``crm.services.send_due_appointment_reminders``
    pour que la logique métier reste testable sans Celery. RAMADAN-AWARE :
    les rappels pendant la plage 18h–21h Casablanca sont différés si le drapeau
    est actif sur la société (voir ``crm.services.dispatch_appointment_reminder``).
    Idempotent : safe à ré-exécuter. Ne touche JAMAIS au statut du Lead ou du
    Devis (rule #4). Renvoie le nombre de rappels envoyés.
    """
    from apps.crm.services import send_due_appointment_reminders
    count = send_due_appointment_reminders()
    logger.info('appointment_reminders: %d rappel(s) envoyé(s)', count)
    return count


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


# XFAC7 — marqueur dédié du rappel de courtoisie pré-échéance, pour
# distinguer son log d'un email de relance classique (idempotence par jour).
PRE_ECHEANCE_MARKER = 'pre_echeance'


@shared_task(name='ventes.pre_echeance_reminders')
def pre_echeance_reminders():
    """XFAC7 — rappel de courtoisie J-N AVANT échéance (jamais après).

    Pour chaque facture ÉMISE (jamais payée/annulée/exclue) dont l'échéance
    tombe dans EXACTEMENT N jours (N = ``CompanyProfile.rappel_pre_echeance_
    jours`` de la société, défaut 5, 0 = désactivé), envoie l'email de
    courtoisie (clé ``EmailTemplate`` ``pre_echeance``, NO-OP réseau sans clé
    d'envoi) avec le lien de paiement FG53 si disponible, et consigne dans
    ``EmailLog``. Idempotent : un log dédié (``reference`` suffixée du
    marqueur) empêche un second envoi pour la même facture. Renvoie le
    nombre de rappels envoyés."""
    from .models import EmailLog, Facture
    from .email_service import send_pre_echeance_email
    from apps.parametres.models_company import CompanyProfile

    today = casablanca_today()
    sent = 0
    candidates = Facture.objects.filter(
        statut=Facture.Statut.EMISE, exclu_relances=False,
        date_echeance__isnull=False,
    ).select_related('client', 'company').prefetch_related(
        'lignes', 'paiements', 'avoirs')

    profiles_cache = {}
    for facture in candidates:
        if facture.montant_du <= 0:
            continue
        company_id = facture.company_id
        if company_id not in profiles_cache:
            profiles_cache[company_id] = CompanyProfile.get(
                company=facture.company)
        profile = profiles_cache[company_id]
        n = getattr(profile, 'rappel_pre_echeance_jours', 5) or 0
        if n <= 0:
            continue
        if facture.date_echeance != today + timedelta(days=n):
            continue
        # Idempotence : un seul rappel par facture (le marqueur reste tant
        # que la facture n'a qu'une échéance figée — pas de doublon possible
        # même si le job tourne plusieurs fois le même jour).
        deja_envoye = EmailLog.objects.filter(
            facture=facture, reference__endswith=f'::{PRE_ECHEANCE_MARKER}',
        ).exists()
        if deja_envoye:
            continue
        log = send_pre_echeance_email(facture, user=None)
        # Marque le log avec le suffixe dédié (idempotence future) sans
        # perdre la référence facture d'origine.
        log.reference = f'{(facture.reference or "")[:70]}::' \
            f'{PRE_ECHEANCE_MARKER}'
        log.save(update_fields=['reference'])
        sent += 1

    logger.info('pre_echeance_reminders: %s rappel(s) envoyé(s)', sent)
    return sent
