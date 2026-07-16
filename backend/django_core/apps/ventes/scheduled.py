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
    """Échéance retenue : ``date_echeance`` si posée (jamais écrasée — input
    freedom), sinon dérivée des conditions de paiement du client (XFAC23 —
    délai négocié 30/60/90 j, fin de mois), sinon repli émission + 30 j
    (comportement historique inchangé pour un client sans réglage)."""
    if facture.date_echeance:
        return facture.date_echeance
    base = facture.date_emission or today
    from .services import calculer_date_echeance
    derivee = calculer_date_echeance(
        client=getattr(facture, 'client', None), date_emission=base)
    if derivee is not None:
        return derivee
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


def _dispatch_relance_canal(facture, niveau, note, user=None):
    """XFAC8 — route la relance selon ``niveau.canal`` et renvoie un dict
    ``{'canal': …, 'courrier_pdf_key': …}`` à consigner sur la RelanceLog.

    - email (défaut, historique inchangé) : ``send_relance_email``.
    - whatsapp : prépare un brouillon wa.me (jamais d'envoi auto) via le
      ShareLink/MessageTemplate existants — n'échoue jamais le job (best
      effort, ex. téléphone absent).
    - courrier : génère la lettre de relance PDF (file d'attente
      d'impression, jamais d'envoi postal automatisé) et stocke sa clé MinIO.
    - appel : crée une ``records.Activity`` type Appel assignée au owner du
      client, au lieu d'un message.
    """
    from .email_service import send_relance_email
    from .models import FollowupLevel

    canal = getattr(niveau, 'canal', FollowupLevel.Canal.EMAIL) \
        if niveau is not None else FollowupLevel.Canal.EMAIL
    niveau_nom = niveau.nom if niveau is not None else ''
    message = niveau.message if niveau is not None else ''

    if canal == FollowupLevel.Canal.WHATSAPP:
        try:
            from .utils.whatsapp import build_facture_whatsapp_draft
            build_facture_whatsapp_draft(facture, modele='relance')
        except Exception:  # pragma: no cover — best-effort, ex. tél. absent
            logger.warning(
                'relance_reminders: brouillon WhatsApp indisponible pour '
                'facture %s', facture.id)
        return {'canal': canal, 'courrier_pdf_key': ''}

    if canal == FollowupLevel.Canal.COURRIER:
        courrier_key = ''
        try:
            from .utils.pdf import generate_lettre_relance_pdf, _upload_pdf
            pdf_bytes = generate_lettre_relance_pdf(facture, {
                'ordre': getattr(niveau, 'ordre', None), 'nom': niveau_nom,
                'delai_jours': getattr(niveau, 'delai_jours', None),
            } if niveau is not None else None, message)
            courrier_key = (
                f'relances/courrier/{facture.company_id}/'
                f'{facture.reference}-{casablanca_today().isoformat()}.pdf')
            _upload_pdf(pdf_bytes, courrier_key)
        except Exception:  # pragma: no cover — best-effort
            logger.warning(
                'relance_reminders: lettre courrier indisponible pour '
                'facture %s', facture.id)
        return {'canal': canal, 'courrier_pdf_key': courrier_key}

    if canal == FollowupLevel.Canal.APPEL:
        try:
            from django.contrib.contenttypes.models import ContentType
            from apps.records.models import Activity, ActivityType
            ct = ContentType.objects.get_for_model(facture.__class__)
            atype = ActivityType.objects.filter(
                company=facture.company, nom='Appel').first()
            if atype is None:
                atype = ActivityType.objects.create(
                    company=facture.company, nom='Appel', icone='📞',
                    ordre=45, est_systeme=True)
            assigned_to = (
                getattr(facture.client, 'owner', None)
                or getattr(facture.client, 'created_by', None)
                or facture.created_by)
            Activity.objects.create(
                company=facture.company, content_type=ct,
                object_id=facture.id, activity_type=atype,
                summary=f'Relance téléphonique — facture {facture.reference}',
                note=message, due_date=casablanca_today(),
                assigned_to=assigned_to,
            )
        except Exception:  # pragma: no cover — best-effort
            logger.warning(
                'relance_reminders: activité appel indisponible pour '
                'facture %s', facture.id)
        return {'canal': canal, 'courrier_pdf_key': ''}

    # Défaut / email — comportement historique strictement inchangé.
    send_relance_email(facture, niveau_nom=niveau_nom, message=message, user=user)
    return {'canal': FollowupLevel.Canal.EMAIL, 'courrier_pdf_key': ''}


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
    from .models import Facture, FollowupLevel, ParametrageRelanceClient, RelanceLog
    from .email_service import send_relance_email

    today = casablanca_today()
    _check_promesses_expirees(today)
    sent = 0
    # ZFAC8 — un client en mode MANUEL est ignoré par le cron automatique (son
    # responsable le suit via la liste manuelle, pas cet envoi programmé).
    clients_manuels = set(
        ParametrageRelanceClient.objects.filter(
            mode=ParametrageRelanceClient.Mode.MANUEL,
        ).values_list('client_id', flat=True)
    )
    factures = Facture.objects.filter(
        prochaine_relance__lte=today, exclu_relances=False,
    ).exclude(
        statut__in=['payee', 'annulee', 'brouillon'],
    ).exclude(
        exclu_relances_jusquau__gte=today,
    ).exclude(
        client_id__in=clients_manuels,
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

        # XFAC8 — route selon le canal configuré sur CE niveau (email par
        # défaut = comportement historique inchangé).
        dispatch = _dispatch_relance_canal(
            facture, niveau, 'Relance automatique programmée (email).',
            user=None)
        RelanceLog.objects.create(
            company=facture.company, facture=facture, niveau=niveau.ordre,
            niveau_nom=niveau.nom,
            note='Relance automatique programmée (email).',
            canal=dispatch['canal'],
            courrier_pdf_key=dispatch['courrier_pdf_key'])

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


# XFAC25 — marqueur dédié du relevé mensuel automatique, pour l'idempotence
# (un seul envoi par client et par mois, jamais deux).
RELEVE_MENSUEL_MARKER = 'releve_mensuel'


@shared_task(name='ventes.releve_mensuel_reminders')
def releve_mensuel_reminders():
    """XFAC25 — envoi programmé (mensuel, 1er du mois) du relevé de compte.

    Pour chaque client opt-in (``releve_mensuel_auto=True``) AVEC email ET
    encours (montant dû total sur ses factures ouvertes) non nul, envoie le
    relevé PDF existant (``recouvrement._releve_data`` /
    ``email_service.send_releve_email``) et consigne un ``EmailLog``.
    Idempotent : un log dédié (``reference`` suffixée du marqueur + mois
    YYYYMM) empêche un second envoi le même mois même si le job tourne
    plusieurs fois. Solde nul / opt-out / sans email → rien n'est tenté ni
    consigné. Renvoie le nombre de relevés envoyés."""
    from decimal import Decimal
    from .models import EmailLog
    from .email_service import send_releve_email
    from .recouvrement import _releve_data
    from apps.crm.selectors import client_base_qs

    today = casablanca_today()
    mois = today.strftime('%Y%m')
    marker = f'{RELEVE_MENSUEL_MARKER}-{mois}'
    sent = 0

    clients = client_base_qs().filter(
        releve_mensuel_auto=True).exclude(email__isnull=True).exclude(email='')

    for client in clients:
        # Idempotence : un seul envoi par client et par mois.
        deja_envoye = EmailLog.objects.filter(
            client=client, reference=marker,
        ).exists()
        if deja_envoye:
            continue
        data = _releve_data(client, user=None)
        try:
            solde_du = Decimal(data['totaux']['du'])
        except Exception:  # noqa: BLE001 — repli prudent si format inattendu
            solde_du = Decimal('0')
        if solde_du <= 0:
            continue
        log = send_releve_email(client, data, user=None)
        if log is None:
            continue
        log.reference = f'{marker}'[:80]
        log.save(update_fields=['reference'])
        sent += 1

    logger.info('releve_mensuel_reminders: %s relevé(s) envoyé(s)', sent)
    return sent


@shared_task(name='ventes.devis_a_facturer_reminder')
def devis_a_facturer_reminder(jours=7):
    """ZFAC12 — rappel de courtoisie pré-échéance côté DEVIS accepté non
    facturé (backlog à facturer). Pour chaque ``Devis`` ``accepte`` sans
    ``Facture`` liée depuis > ``jours`` jours (défaut 7, réglable), pose une
    entrée SYSTÈME dans son chatter (``DevisActivity``) — NO-OP d'envoi,
    comme les autres rappels (aucun email/SMS). Un devis déjà facturé est
    ignoré. Idempotent : une seule entrée par devis et par jour calendaire
    même si le job tourne plusieurs fois. Renvoie le nombre de rappels posés."""
    from . import activity
    from .selectors import devis_a_facturer
    from authentication.models import Company

    total = 0
    for company in Company.objects.all():
        candidats = devis_a_facturer(company, jours=jours)
        for devis in candidats:
            jours_ecoules = (casablanca_today() - devis.date_acceptation).days
            note = activity.log_devis_a_facturer_reminder(devis, jours_ecoules)
            if note is not None:
                total += 1

    logger.info('devis_a_facturer_reminder: %s rappel(s) posé(s)', total)
    return total


@shared_task(name='ventes.poll_inbound_mailboxes')
def poll_inbound_mailboxes():
    """QX36 — interroge la boîte email entrante de chaque société et dispatche
    aux handlers du bus ``core.email_intake`` (SAV email→ticket, ventes
    réponse→devis). Sans boîte configurée par société, ``poll_mailbox`` est un
    no-op propre (aucune connexion réseau) — donc cette tâche est sûre à
    planifier même quand aucune boîte n'est câblée.

    Multi-tenant : la société est imposée société par société (jamais du corps
    d'une requête). Best-effort par société : un échec n'arrête pas les autres.
    Renvoie le total {fetched, handled}."""
    from core.email_intake import poll_mailbox
    from authentication.models import Company

    fetched = handled = 0
    for company in Company.objects.all():
        try:
            res = poll_mailbox(company)
            fetched += int(res.get('fetched', 0) or 0)
            handled += int(res.get('handled', 0) or 0)
        except Exception:  # noqa: BLE001 — best-effort par société
            logger.warning('ventes.poll_inbound_mailboxes: échec société %s',
                           getattr(company, 'pk', '?'), exc_info=True)
    logger.info('ventes.poll_inbound_mailboxes: %d relevé(s), %d dispatché(s)',
                fetched, handled)
    return {'fetched': fetched, 'handled': handled}


@shared_task(name='ventes.engagement_followup_engine')
def engagement_followup_engine():
    """QX30be — relance déclenchée par le COMPORTEMENT (pas le calendrier).

    Trois déclencheurs, dérivés des données déjà enregistrées (ShareLink
    first_viewed_at/view_count + proposition ENVOYÉE) :
      * ``not_opened_24h`` — devis envoyé, lien JAMAIS ouvert depuis > 24 h ;
      * ``opened_not_signed_48h`` — ouvert mais non signé depuis > 48 h de la
        1ʳᵉ ouverture (46 % des signataires signent < 48 h de l'ouverture) ;
      * ``reopened_3x`` — rouvert ≥ 3 fois (les propositions perdantes sont
        vues 3,5× — « hésite, appelez maintenant »).

    Chaque déclencheur pose une Notification au vendeur, UNE SEULE FOIS par lien
    (idempotence via ``ShareLink.engagement_triggers_fired``). RULE #4 : ne
    touche jamais au statut. Renvoie le nombre de notifications posées."""
    from django.utils import timezone
    from apps.ventes.models import Devis, ShareLink

    now = timezone.now()
    posted = 0

    links = (ShareLink.objects
             .filter(devis__isnull=False,
                     devis__statut=Devis.Statut.ENVOYE,
                     expires_at__gt=now)
             .select_related('devis', 'devis__created_by', 'company'))

    for link in links:
        devis = link.devis
        vendeur = getattr(devis, 'created_by', None)
        if vendeur is None:
            continue
        fired = set(link.engagement_triggers_fired or [])
        to_fire = []

        sent_at = getattr(devis, 'date_envoi', None)
        if (link.view_count == 0 and 'not_opened_24h' not in fired
                and sent_at is not None
                and (now - sent_at).total_seconds() >= 24 * 3600):
            to_fire.append(('not_opened_24h',
                            'Proposition non ouverte depuis 24 h'))
        if (link.first_viewed_at is not None
                and 'opened_not_signed_48h' not in fired
                and (now - link.first_viewed_at).total_seconds() >= 48 * 3600):
            to_fire.append(('opened_not_signed_48h',
                            'Ouverte mais non signée depuis 48 h — appelez'))
        if (link.view_count >= 3 and 'reopened_3x' not in fired):
            to_fire.append(('reopened_3x',
                            'Rouverte 3 fois — le client hésite, appelez'))

        for key, label in to_fire:
            _post_engagement_notification(devis, vendeur, key, label)
            fired.add(key)
            posted += 1
        if to_fire:
            link.engagement_triggers_fired = sorted(fired)
            link.save(update_fields=['engagement_triggers_fired'])

    logger.info('ventes.engagement_followup_engine: %d notification(s)', posted)
    return posted


def _post_engagement_notification(devis, vendeur, key, label):
    """QX30be — pose une Notification d'engagement (best-effort, in-lane)."""
    try:
        from apps.notifications.services import notify
        from apps.notifications.models import EventType
        from apps.ventes.utils.client_links import proposition_url
        from apps.ventes.models import ShareLink
        try:
            token = ShareLink.for_devis(devis).token
            url = proposition_url(token)
        except Exception:  # noqa: BLE001
            url = ''
        notify(
            vendeur, EventType.DEVIS_NUDGE_DUE,
            title=f'{label} — devis {devis.reference}',
            body=(f'Déclencheur d\'engagement : {key}. '
                  f'Proposition : {url or "—"}'),
            link=f'/ventes/devis?devis={devis.id}',
            company=devis.company)
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning('QX30: notification engagement échec devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)
