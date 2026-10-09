"""ACHT75 — échéance de calibration des outils (FG80) : notification réelle.

Avant ce module, ``calibrer`` appelait ``notify(event_type=
'outillage_calibration_proche')`` dans un ``try/except: pass`` : le type
d'événement n'existait pas dans ``EventType`` (``notify()`` renvoie ``None`` et
journalise « type d'événement inconnu »), donc AUCUNE notification n'était
jamais créée et l'échec était avalé en silence.

Ici : le type existe (``EventType.OUTILLAGE_CALIBRATION_PROCHE``), l'envoi est
un helper unique (``notifier_calibration_proche``, appelé par ``calibrer`` ET
par la tâche quotidienne), les erreurs sont JOURNALISÉES, et la tâche balaie
``authentication.selectors.active_companies()`` (jamais une société
suspendue). Idempotent : une notification par destinataire, par outil et par
échéance — un 2e passage ne crée aucun doublon.
"""
import datetime
import logging

from celery import shared_task

logger = logging.getLogger(__name__)

#: Horizon d'alerte (jours) avant l'échéance de calibration.
HORIZON_JOURS = 30


def _titre(outil):
    return (f"Calibration proche : {outil.nom} "
            f"({outil.date_prochaine_calibration})")


def notifier_calibration_proche(outil, destinataires):
    """Notifie ``destinataires`` (itérable d'utilisateurs) de l'échéance de
    calibration de ``outil``. Une seule notification par destinataire et par
    échéance (titre = nom + date). Renvoie le nombre de notifications créées.
    Journalise (``logger.warning``) au lieu d'avaler l'exception."""
    from apps.notifications.models import Notification
    from apps.notifications.services import notify
    from apps.notifications.types_evenements import EventType

    if outil.date_prochaine_calibration is None:
        return 0
    titre = _titre(outil)
    crees = 0
    for user in destinataires:
        try:
            if Notification.objects.filter(
                    recipient=user, company=outil.company,
                    event_type=EventType.OUTILLAGE_CALIBRATION_PROCHE,
                    title=titre).exists():
                continue
            notif = notify(
                user, EventType.OUTILLAGE_CALIBRATION_PROCHE, titre,
                body=(f"Prochaine calibration le "
                      f"{outil.date_prochaine_calibration}."),
                company=outil.company)
            if notif is not None:
                crees += 1
        except Exception:  # noqa: BLE001 — jamais bloquant, mais journalisé
            logger.warning(
                'ACHT75: notification de calibration échouée '
                '(outil %s, utilisateur %s)', outil.pk,
                getattr(user, 'pk', '?'), exc_info=True)
    return crees


@shared_task(name='outillage.calibrations_a_echeance')
def calibrations_a_echeance():
    """Balayage quotidien : pour chaque société ACTIVE, notifie les
    destinataires résolus (``resolve_recipients``) de chaque outil soumis à
    calibration dont l'échéance tombe dans les 30 jours (ou est dépassée).
    Renvoie ``{outils, notifications}`` pour l'observabilité."""
    from authentication.selectors import active_companies
    from apps.notifications.services import resolve_recipients
    from apps.notifications.types_evenements import EventType

    from .models import Outillage

    limite = datetime.date.today() + datetime.timedelta(days=HORIZON_JOURS)
    outils = 0
    notifications = 0
    for company in active_companies():
        destinataires = list(resolve_recipients(
            company, EventType.OUTILLAGE_CALIBRATION_PROCHE))
        if not destinataires:
            continue
        for outil in Outillage.objects.filter(
                company=company, intervalle_calibration_mois__gt=0,
                date_prochaine_calibration__isnull=False,
                date_prochaine_calibration__lte=limite):
            outils += 1
            notifications += notifier_calibration_proche(
                outil, destinataires)
    return {'outils': outils, 'notifications': notifications}
