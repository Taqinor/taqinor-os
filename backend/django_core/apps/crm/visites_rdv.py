"""Rendez-vous de visite : prise de RDV, créneaux publics, rappels (SPL7, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
import datetime
import logging as _logging

from core.dates import aujourd_hui_local

from .leads_socle import lead_notification_recipients
from .models import LeadActivity
import logging
from .activity import journal_systeme

logger = logging.getLogger(__name__)


_appt_logger = _logging.getLogger(__name__)

# How many minutes before a scheduled appointment to send the reminder.
APPOINTMENT_REMINDER_MINUTES = 60

# RAMADAN-AWARE PACING : pendant la période de Ramadan SAISIE par la société
# (``horaires.est_en_ramadan``), aucun rappel ne part dans la plage iftar
# (``horaires.PLAGE_IFTAR_DEBUT``–``PLAGE_IFTAR_FIN``, heure de Casablanca)
# pour ne pas déranger les familles au ftour. ACRM42 — un RDV dont la fenêtre
# de rappel tomberait DANS la plage est rappelé AVANT elle (dernière heure
# avant la plage, ``send_due_appointment_reminders``) : il n'est jamais « reporté
# après 21 h » (l'ancien commentaire le prétendait, rien ne le faisait — un RDV
# de 19 h 30 n'était JAMAIS rappelé). Une seule notion de Ramadan : celle de
# ``horaires`` ; les constantes ci-dessous en dérivent (compatibilité).
RAMADAN_AVOID_START_H = 18   # = horaires.PLAGE_IFTAR_DEBUT.hour
RAMADAN_AVOID_END_H = 21     # = horaires.PLAGE_IFTAR_FIN.hour
RAMADAN_TZ = 'Africa/Casablanca'


def _ramadan_pacing_enabled(company) -> bool:
    """True si le drapeau « pacing Ramadan » est actif pour la société.

    MRY8 — ce helper lisait ``CompanyProfile.ramadan_pacing``, un champ qui
    N'A JAMAIS EXISTÉ : il renvoyait donc toujours False et le pacing Ramadan
    (report des rappels de RDV pendant l'iftar) était mort depuis sa création.
    Il s'appuie désormais sur la PÉRIODE réellement saisie par la société
    (``ramadan_debut``/``ramadan_fin``, MRY8) : vrai pendant cette période,
    faux partout ailleurs — et faux tant que la société n'a rien saisi (la
    période n'est jamais devinée). ``ramadan_pacing`` reste honoré s'il est
    un jour ajouté, pour ne pas retirer un interrupteur explicite.
    """
    if company is None:
        return False
    try:
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.objects.filter(company=company).first()
        if bool(getattr(profile, 'ramadan_pacing', False)):
            return True
        from apps.crm import horaires
        return horaires.est_en_ramadan(
            aujourd_hui_local(), company, profil=profile)
    except Exception:
        logger.warning('%s : échec ignoré (dégradé)', '_ramadan_pacing_enabled', exc_info=True)
        return False


def _is_ramadan_iftar_window(dt_utc) -> bool:
    """True si le datetime tombe dans la plage iftar (``horaires``, ACRM42 :
    une seule définition)."""
    try:
        from . import horaires
        return horaires.dans_plage_iftar(dt_utc)
    except Exception:
        logger.warning('%s : échec ignoré (dégradé)', '_is_ramadan_iftar_window', exc_info=True)
        return False


def book_appointment(*, lead, scheduled_at, notes=None, user=None):
    """QJ20 — Planifie un rendez-vous (visite commerciale/technique) sur un lead.

    Crée un ``crm.Appointment`` lié au lead et à sa société (forcé côté serveur —
    jamais lu d'un corps de requête). Écrit une entrée de chatter sur le lead.
    Renvoie l'instance Appointment créée.

    ``scheduled_at`` doit être un datetime timezone-aware (UTC recommandé).
    ``notes`` est optionnel.
    ``user`` est l'utilisateur actif (peut être None pour les appels beat).
    """
    from .models import Appointment

    if scheduled_at is None:
        raise ValueError('scheduled_at est requis pour planifier un rendez-vous.')

    # Company is always forced from the lead (never from request body).
    company = lead.company

    appointment = Appointment.objects.create(
        company=company,
        lead=lead,
        scheduled_at=scheduled_at,
        statut=Appointment.Statut.PLANIFIE,
        notes=notes or '',
        created_by=user,
    )

    # ACVI63 (D-ACVI-8) — ce rendez-vous EST la visite technique : la porte
    # unique crée ou déplace la visite, date la fiche, recale la cadence et pose
    # la note. L'``Appointment`` garde l'heure et le rappel.
    from apps.visites.services import erreur_commercial, planifier_visite
    from . import horaires
    from .activity import log_note
    # ERR-W33-RDV-CHATTER — même garde que le commercial choisi à la main : une
    # réservation publique n'assigne jamais une visite à un compte désactivé.
    assigne = user or lead.owner
    refus_assigne = erreur_commercial(assigne, company.pk) if assigne else None
    local = scheduled_at.astimezone(horaires.CASABLANCA)
    visite, erreurs = planifier_visite(
        lead, user, local.date(), notes=notes or '', replanifier=True,
        assigne_par_defaut=None if refus_assigne else assigne)
    if erreurs:
        logger.warning('ACVI63 : RDV #%s sans visite : %s', appointment.pk, erreurs)
        # La porte des visites n'a rien écrit : la fiche dit ce qui manque.
        motifs = ' '.join(m for messages in erreurs.values() for m in messages)
        log_note(lead, user, (
            f'Rendez-vous du {local:%d/%m/%Y à %H:%M} enregistré sans visite '
            f'technique : {motifs}'))
    elif refus_assigne and visite.commercial_id is None:
        log_note(lead, user, (
            f'Visite technique du {local:%d/%m/%Y} sans assigné : {refus_assigne}'))

    _appt_logger.info(
        'QJ20: RDV #%d créé pour lead %s le %s (company %s)',
        appointment.pk, lead.pk, scheduled_at, getattr(company, 'id', '?'))
    return appointment


def annuler_rendez_vous_du_jour(lead_id, jour):
    """AMSG16 — la visite technique du ``jour`` est annulée : le rendez-vous
    d'agenda qui EST cette visite (D-ACVI-8) passe ANNULÉ, et son rappel ne part
    plus. Seuls les rendez-vous PLANIFIÉ/CONFIRMÉ du lead dont la date locale
    est ``jour``. Renvoie le nombre de rendez-vous annulés."""
    import zoneinfo

    from .models import Appointment

    if jour is None:
        return 0
    debut = datetime.datetime.combine(
        jour, datetime.time.min, tzinfo=zoneinfo.ZoneInfo(RAMADAN_TZ))
    return Appointment.objects.filter(
        lead_id=lead_id, scheduled_at__gte=debut,
        scheduled_at__lt=debut + datetime.timedelta(days=1),
        statut__in=[Appointment.Statut.PLANIFIE, Appointment.Statut.CONFIRME],
    ).update(statut=Appointment.Statut.ANNULE)


# ── VX245(b) — confirmation WhatsApp POST-RDV (aperçu date/heure + .ics) ────

def build_appointment_confirmation_whatsapp(request, appointment):
    """VX245(b) — construit le message de CONFIRMATION WhatsApp d'un rendez-
    vous ; AMSG11 : le gabarit société `visite_confirmation` dans la langue du
    lead, à la date (Africa/Casablanca) du rendez-vous. ACVI45 — le lien `.ics` (route JWT,
    401 pour le client) n'entre plus dans le message ; il reste servi à l'ERP
    (VX245(a), `apps.crm.views.AppointmentViewSet.ics`). N'ENVOIE RIEN — même
    convention que `build_devis_whatsapp`/`build_facture_whatsapp` : ouvre
    WhatsApp avec le message pré-rempli, le commercial appuie lui-même sur
    Envoyer. Renvoie `(message, wa_url, ics_url)` ; `wa_url` est `None` si le
    lead n'a pas de numéro exploitable."""
    import zoneinfo

    from apps.ventes.utils.whatsapp import build_wa_url

    from .cadence_temps import numero_joignable

    lead = appointment.lead
    phone = numero_joignable(lead)  # ACVI50
    local_dt = appointment.scheduled_at.astimezone(zoneinfo.ZoneInfo(RAMADAN_TZ))
    ics_url = request.build_absolute_uri(
        f'/api/django/crm/appointments/{appointment.pk}/ics/')
    # AMSG11 — le gabarit société `visite_confirmation`, dans la langue du lead.
    from .cadence_messages import (
        langue_relance_du_lead, message_visite_pour_lead, refus_rendu_whatsapp)
    rendu = message_visite_pour_lead(
        lead, 'visite_confirmation', user=getattr(request, 'user', None),
        date_visite=local_dt.date())
    langue = 'darija' if langue_relance_du_lead(lead) == 'darija' else 'fr'
    message = rendu[f'corps_{langue}']
    # ACVI111 — aucun lien à un refusé
    return message, (None if refus_rendu_whatsapp(lead) else build_wa_url(phone, message)), ics_url


# ── XSAL17 — Placeholder {lien_rdv} : lien de réservation dans les messages ──

def public_booking_url(lead, *, request=None):
    """XSAL17 — Crée (ou réutilise) un ``BookingLink`` NON expiré/NON utilisé
    pour ``lead`` et renvoie son URL PUBLIQUE complète. Réutilise un lien
    existant tant qu'il n'est ni expiré ni déjà utilisé (évite de multiplier
    les jetons à chaque envoi) ; en crée un nouveau sinon. Company-scopé
    (le lien porte la société du lead, jamais du corps de requête)."""
    from django.conf import settings
    from django.utils import timezone as _timezone

    from .models import BookingLink

    now = _timezone.now()
    link = (
        BookingLink.objects
        .filter(lead=lead, used_at__isnull=True, expires_at__gt=now)
        .order_by('-created_at')
        .first()
    )
    if link is None:
        link = BookingLink.objects.create(company=lead.company, lead=lead)

    # ACVI46 (D-ACVI-9) — UNE base : l'ERP, seul à servir la page `/rdv/<jeton>`
    # (jamais `PUBLIC_SITE_URL`, 404) ; sans base ni requête, '' : phrase omise.
    base = (getattr(settings, 'PUBLIC_BASE_URL', '') or '').strip().rstrip('/')
    if not base and request is not None:
        base = request.build_absolute_uri('/')[:-1]
    return f'{base}/rdv/{link.token}' if base else ''


def resoudre_lien_rdv(text, lead, *, request=None) -> str:
    """XSAL17 — Résout le placeholder ``{lien_rdv}`` dans ``text`` au moment
    de l'ENVOI (jamais généré à l'avance/en masse) : un template SANS le
    placeholder est renvoyé INCHANGÉ (aucun jeton créé — no-op, jamais de
    coût inutile). Best-effort : une erreur de génération de lien ne casse
    jamais l'envoi — le placeholder est alors simplement retiré."""
    if '{lien_rdv}' not in (text or ''):
        return text
    try:
        url = public_booking_url(lead, request=request)
    except Exception:  # noqa: BLE001 — jamais bloquer l'envoi d'un message (D-ENF22-BLE001)
        logger.warning('%s : échec ignoré (dégradé)', 'resoudre_lien_rdv', exc_info=True)
        url = ''
    return text.replace('{lien_rdv}', url)


class BookingLinkUnavailable(Exception):
    """XSAL17 — levée quand un jeton de réservation est invalide, expiré ou
    déjà utilisé (l'appelant — la vue publique — traduit en 404/410 douce)."""


def resolve_booking_link(token):
    """XSAL17 — Résout un jeton de réservation PUBLIC : renvoie le
    ``BookingLink`` s'il existe, n'est ni expiré ni déjà utilisé. Lève
    :class:`BookingLinkUnavailable` sinon (message explicite). Lecture
    seule — ne réserve rien elle-même."""
    from .models import BookingLink

    link = BookingLink.objects.select_related('lead', 'company').filter(
        token=token).first()
    if link is None:
        raise BookingLinkUnavailable('Lien de réservation introuvable.')
    if link.is_used:
        raise BookingLinkUnavailable('Ce créneau a déjà été réservé.')
    if link.is_expired:
        raise BookingLinkUnavailable('Ce lien de réservation a expiré.')
    return link


#: CRX23 — horizon maximal d'une réservation PUBLIQUE, en jours. Sert de
#: borne haute de bon sens : un visiteur (ou un script) ne réserve pas une
#: visite en l'an 9999. Constante de module pour que les tests la patchent.
BOOKING_HORIZON_JOURS = 365


def _valider_creneau_public(scheduled_at):
    """CRX23 — bornes d'un créneau réservé PUBLIQUEMENT.

    Le corps public arrive de ``parse_datetime`` : il rend un datetime NAÏF
    quand la chaîne ne porte pas d'offset, et accepte n'importe quelle année.
    Un naïf serait stocké tel quel (interprétation de fuseau indéterminée) et
    une année absurde polluerait durablement le calendrier du commercial.

    Lève ``ValueError`` (traduit en 400 par la vue publique) si le créneau
    est absent, naïf, déjà passé, ou au-delà de :data:`BOOKING_HORIZON_JOURS`.
    """
    from datetime import timedelta

    from django.utils import timezone as _timezone

    if scheduled_at is None:
        raise ValueError('Date/heure de créneau manquante.')
    if _timezone.is_naive(scheduled_at):
        raise ValueError(
            'Le créneau doit porter son fuseau horaire (date/heure naïve '
            'refusée).')
    now = _timezone.now()
    if scheduled_at <= now:
        raise ValueError('Le créneau demandé est déjà passé.')
    if scheduled_at > now + timedelta(days=BOOKING_HORIZON_JOURS):
        raise ValueError(
            'Le créneau demandé est trop lointain '
            f'(au-delà de {BOOKING_HORIZON_JOURS} jours).')


def reserver_creneau_public(token, *, scheduled_at, notes=None):
    """XSAL17 — Réservation PUBLIQUE d'un créneau via un jeton
    ``BookingLink`` : crée l'``Appointment`` (via ``book_appointment``,
    même logique métier que la création interne — user=None, un visiteur
    anonyme n'est jamais un utilisateur ERP) et marque le lien comme
    UTILISÉ (idempotent : un second appel avec le même jeton lève
    :class:`BookingLinkUnavailable`, jamais un second rendez-vous).
    Le lead atterrit toujours sur SON lead d'origine (booking-to-lead) —
    jamais un autre, jamais choisi par le visiteur.

    CRX23 — l'idempotence est désormais VRAIE sous concurrence. Avant, deux
    requêtes simultanées passaient toutes les deux le ``resolve_booking_link``
    (``used_at`` encore nul pour les deux), créaient DEUX rendez-vous sur le
    même lien, et la seconde écrasait ``link.appointment`` : le commercial
    voyait deux visites pour un seul créneau réservé. Le lien est maintenant
    RÉCLAMÉ par un UPDATE conditionnel (``used_at__isnull=True`` → nombre de
    lignes touchées) DANS la transaction : exactement une requête gagne, la
    perdante reçoit :class:`BookingLinkUnavailable` (410). Le rendez-vous est
    créé APRÈS la réclamation, dans la même transaction — un échec de création
    annule la réclamation (le lien reste utilisable), jamais un lien brûlé
    pour rien.
    """
    from django.db import transaction
    from django.utils import timezone as _timezone

    from .models import BookingLink

    # Le jeton d'abord (404/410 honnête, lecture seule), puis les bornes du
    # créneau — AVANT toute écriture : un créneau invalide ne doit pas
    # consommer le lien (le visiteur doit pouvoir corriger et réessayer).
    link = resolve_booking_link(token)
    _valider_creneau_public(scheduled_at)

    with transaction.atomic():
        maintenant = _timezone.now()
        reclame = BookingLink.objects.filter(
            pk=link.pk, used_at__isnull=True).update(used_at=maintenant)
        if not reclame:
            raise BookingLinkUnavailable('Ce créneau a déjà été réservé.')
        appointment = book_appointment(
            lead=link.lead, scheduled_at=scheduled_at, notes=notes, user=None)
        BookingLink.objects.filter(pk=link.pk).update(appointment=appointment)
        # ACRM41 — une note LISIBLE au chatter, dans la même transaction.
        journal_systeme(
            company=link.lead.company, lead=link.lead,
            kind=LeadActivity.Kind.NOTE,
            body=(f'Le client a réservé sa visite le '
                  f'{_quand_local(scheduled_at)} via le lien de '
                  'réservation.'))
        # ACRM41 (C-ACRM-036) — le responsable (repli : managers) est
        # prévenu APRÈS validation : une réservation annulée ne notifie rien.
        transaction.on_commit(
            lambda: _notifier_reservation_publique(appointment))

    link.used_at = maintenant
    link.appointment = appointment
    return appointment


def _quand_local(instant):
    """« JJ/MM/AAAA à HH:MM », heure de Casablanca."""
    from . import horaires
    return instant.astimezone(horaires.CASABLANCA).strftime(
        '%d/%m/%Y à %H:%M')


def _notifier_reservation_publique(appointment):
    """ACRM41 — une visite réservée par le PROSPECT lui-même (lien public)
    prévient son responsable et le supérieur de celui-ci
    (``lead_notification_recipients`` : repli managers quand l'un manque).
    Best-effort : la réservation est déjà validée."""
    try:
        lead = appointment.lead
        destinataires = lead_notification_recipients(lead)
        if not destinataires:
            return
        from apps.notifications.services import notify_many
        notify_many(
            destinataires, 'appointment_reminder',
            f'Visite réservée — {lead.nom}',
            body=(f'Le client a réservé sa visite le '
                  f'{_quand_local(appointment.scheduled_at)} via le lien '
                  f'de réservation (RDV #{appointment.pk}).'),
            link=f'/crm/leads/{lead.pk}',
            company=appointment.company)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant (D-ENF22-BLE001)
        _appt_logger.warning(
            'ACRM41 : notification de réservation échouée (RDV #%s)',
            getattr(appointment, 'pk', '?'), exc_info=True)


def dispatch_appointment_reminder(appointment) -> bool:
    """QJ20 — Envoie le rappel de visite pour un rendez-vous à venir.

    Canal : notification in-app via notifications.services.notify. AMSG17 —
    plus de brouillon wa.me client (personne ne le lisait ; il écrivait le
    numéro et le texte du client au journal).

    RAMADAN-AWARE PACING : si le drapeau est actif pour la société ET que
    l'heure du rappel tombe dans la plage iftar-sensible (18h–21h Casablanca),
    le rappel est différé (renvoie False sans marquer reminder_sent).

    Idempotent : si reminder_sent est déjà True, renvoie True sans rien envoyer.
    Renvoie True si le rappel a été envoyé, False sinon (différé ou erreur).
    """
    from django.utils import timezone as tz

    if appointment.reminder_sent:
        return True  # already sent — idempotent

    # Ramadan-aware pacing check.
    if _ramadan_pacing_enabled(appointment.company):
        if _is_ramadan_iftar_window(tz.now()):
            _appt_logger.info(
                'QJ20: rappel RDV #%d différé (plage iftar Ramadan)',
                appointment.pk)
            return False

    lead = appointment.lead

    # Notification in-app — ACRM42 : au responsable du lead ET à son
    # supérieur (``lead_notification_recipients`` : repli managers quand l'un
    # manque). Un lead SANS responsable n'est plus un rappel perdu.
    notifies = 0
    try:
        from apps.notifications.services import notify
        import zoneinfo
        local = appointment.scheduled_at.astimezone(
            zoneinfo.ZoneInfo(RAMADAN_TZ))
        date_str = local.strftime('%d/%m/%Y à %H:%M')
        for destinataire in lead_notification_recipients(lead):
            try:
                notify(
                    user=destinataire,
                    event_type='appointment_reminder',
                    title=f'Rappel visite — {lead.nom}',
                    body=(
                        f'Rendez-vous prévu le {date_str} '
                        f'avec {lead.nom} (RDV #{appointment.pk}).'
                    ),
                    link=f'/crm/leads/{lead.pk}',
                    company=appointment.company,
                )
                notifies += 1
            except Exception as exc:  # noqa: BLE001 — journalisé, dégradation propre (D-ENF22-BLE001)
                _appt_logger.warning(
                    'QJ20: notify échec RDV #%d : %s', appointment.pk, exc)
    except Exception as exc:  # noqa: BLE001 — journalisé, dégradation propre (D-ENF22-BLE001)
        _appt_logger.warning(
            'QJ20: notify échec RDV #%d : %s', appointment.pk, exc)

    if not notifies:
        # ACRM42 — personne n'a été prévenu : le rappel n'est PAS marqué
        # envoyé, le passage suivant du beat le retente.
        _appt_logger.warning(
            'QJ20: aucun destinataire pour le rappel du RDV #%d — retenté',
            appointment.pk)
        return False

    # Mark as sent (idempotency guard).
    appointment.reminder_sent = True
    appointment.save(update_fields=['reminder_sent'])

    _appt_logger.info('QJ20: rappel envoyé pour RDV #%d', appointment.pk)
    return True


def send_due_appointment_reminders() -> int:
    """QJ20 — Parcourt les rendez-vous à venir et envoie les rappels dus.

    Un rappel est dû quand :
      - l'appointment est à l'état PLANIFIE ou CONFIRME (pas EFFECTUE / ANNULE) ;
      - ``scheduled_at`` est dans les prochaines APPOINTMENT_REMINDER_MINUTES
        minutes (fenêtre glissante) ;
      - ``reminder_sent`` est False.

    Renvoie le nombre de rappels envoyés.
    """
    from datetime import timedelta
    from django.utils import timezone as tz
    from .models import Appointment

    from . import horaires

    now = tz.now()
    window_end = now + timedelta(minutes=APPOINTMENT_REMINDER_MINUTES)
    # ACRM42 — candidats élargis à la durée de la plage iftar : un RDV dont
    # la fenêtre de rappel tombe DANS la plage est rappelé dans l'heure qui
    # la PRÉCÈDE (sinon un RDV de 19 h 30 n'était jamais rappelé).
    duree_plage = (datetime.datetime.combine(
        datetime.date.min, horaires.PLAGE_IFTAR_FIN) - datetime.datetime.combine(
        datetime.date.min, horaires.PLAGE_IFTAR_DEBUT))
    horizon = window_end + duree_plage

    candidats = Appointment.objects.filter(
        statut__in=[Appointment.Statut.PLANIFIE, Appointment.Statut.CONFIRME],
        scheduled_at__gte=now,
        scheduled_at__lte=horizon,
        reminder_sent=False,
    ).select_related('lead', 'lead__owner', 'company')

    pacing = {}
    due = []
    for appt in candidats:
        if appt.scheduled_at <= window_end:
            due.append(appt)
            continue
        if appt.company_id not in pacing:
            pacing[appt.company_id] = _ramadan_pacing_enabled(appt.company)
        if not pacing[appt.company_id]:
            continue
        rappel_normal = appt.scheduled_at - timedelta(
            minutes=APPOINTMENT_REMINDER_MINUTES)
        debut = horaires.debut_plage_iftar(
            rappel_normal.astimezone(horaires.CASABLANCA).date())
        # Rappel normal DANS la plage et nous sommes dans l'heure qui la
        # précède : c'est le dernier passage avant la plage.
        if (horaires.dans_plage_iftar(rappel_normal)
                and debut - timedelta(minutes=APPOINTMENT_REMINDER_MINUTES)
                <= now < debut):
            due.append(appt)

    sent = 0
    for appt in due:
        try:
            if dispatch_appointment_reminder(appt):
                sent += 1
        except Exception as exc:  # noqa: BLE001 — journalisé, dégradation propre (D-ENF22-BLE001)
            _appt_logger.warning(
                'QJ20: erreur rappel RDV #%d : %s', appt.pk, exc)

    _appt_logger.info('QJ20 send_due_appointment_reminders: %d rappel(s)', sent)
    return sent
