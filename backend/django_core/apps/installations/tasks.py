"""XFSM6 — Rappel client J-1 automatique avec lien de confirmation.

Tâche Celery Beat quotidienne (patron G9/FG1) : pour chaque intervention
planifiée DEMAIN (heure Africa/Casablanca) non confirmée (``rdv_confirme``
False — FG78), génère un brouillon WhatsApp (``wa.me``, jamais d'envoi
automatique — cohérent avec la politique manuel-first existante) pour le
responsable ET envoie un email (Brevo, key-gated, NO-OP sans clé) au client.

Le modèle de message vit dans ``apps.parametres`` (app foundation, exempte de
la règle cross-app selectors/services — cf. CLAUDE.md), clé ``rappel_rdv``
(FR + darija). Idempotent par construction : le sweep ne mute AUCUN champ sur
l'intervention — seule l'action de confirmation existante (``confirmer-rdv``,
FG78) modifie l'état, donc une ré-exécution du sweep avant confirmation
regénère simplement le même brouillon (pas de double « envoi » traçable côté
serveur, cohérent avec le manuel-first : c'est un humain qui clique Envoyer).
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)

CASABLANCA_TZ = 'Africa/Casablanca'


def casablanca_today():
    """Date « aujourd'hui » au fuseau Africa/Casablanca (jamais UTC)."""
    from django.utils import timezone
    try:
        from zoneinfo import ZoneInfo
        return timezone.now().astimezone(ZoneInfo(CASABLANCA_TZ)).date()
    except Exception:  # pragma: no cover - zoneinfo absent (très improbable)
        return timezone.localdate()


def _wa_draft_for_intervention(interv):
    """Brouillon WhatsApp ``wa.me`` pour le RESPONSABLE, réutilisant le
    patron ``apps.ventes.utils.whatsapp`` (rendu de gabarit + normalisation
    téléphone). Renvoie l'URL, ou None si aucun numéro exploitable."""
    from apps.parametres.models import MessageTemplate
    from apps.ventes.utils.whatsapp import (
        build_wa_url, render_message_template)

    installation = interv.installation
    client = getattr(installation, 'client', None)
    nom_client = ''
    if client is not None:
        nom_client = f"{getattr(client, 'prenom', '') or ''} {client.nom}".strip()

    responsable = installation.technicien_responsable
    if responsable is None:
        return None
    phone = getattr(responsable, 'phone_number', None)
    if not phone:
        return None

    tpl = MessageTemplate.get_corps(interv.company, 'rappel_rdv', 'fr')
    message = render_message_template(tpl, {
        'civilite': '', 'nom': nom_client,
        'reference': installation.reference or installation.id,
        'lien': '',
    })
    return build_wa_url(phone, message)


def _envoyer_email_client(interv):
    """Email de rappel J-1 au client (Brevo, key-gated — NO-OP sans clé,
    jamais d'exception propagée). Réutilise directement le backend Django
    configuré (comportement identique à ``apps.ventes.email_service`` :
    sans BREVO_API_KEY, le backend console « envoie » sans appel réseau)."""
    from django.core.mail import send_mail
    from django.conf import settings
    from apps.parametres.models import MessageTemplate
    from apps.ventes.utils.whatsapp import render_message_template

    installation = interv.installation
    client = getattr(installation, 'client', None)
    if client is None or not getattr(client, 'email', None):
        return False
    nom_client = f"{getattr(client, 'prenom', '') or ''} {client.nom}".strip()
    tpl = MessageTemplate.get_corps(interv.company, 'rappel_rdv', 'fr')
    corps = render_message_template(tpl, {
        'civilite': '', 'nom': nom_client,
        'reference': installation.reference or installation.id,
        'lien': '',
    })
    try:
        send_mail(
            subject='Rappel de rendez-vous — demain',
            message=corps,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', '')
            or 'noreply@erp.local',
            recipient_list=[client.email],
            fail_silently=True)
        return True
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('XFSM6 : envoi email rappel RDV échoué : %s', exc)
        return False


@shared_task(name='installations.rappel_rdv_j1')
def rappel_rdv_j1():
    """XFSM6 — sweep quotidien : cible EXACTEMENT les interventions planifiées
    DEMAIN (Africa/Casablanca) non confirmées (``rdv_confirme=False``), génère
    le brouillon WhatsApp responsable + envoie l'email client. NE MUTE aucun
    champ de l'intervention (le brouillon WhatsApp n'est jamais auto-envoyé —
    politique manuel-first). Renvoie un compte {cibles, wa_generes, emails_envoyes}
    pour observabilité/tests."""
    from datetime import timedelta
    from .models import Intervention

    demain = casablanca_today() + timedelta(days=1)
    qs = (Intervention.objects
          .filter(date_prevue=demain, rdv_confirme=False)
          .select_related('installation', 'installation__client',
                          'installation__technicien_responsable'))

    cibles = 0
    wa_generes = 0
    emails_envoyes = 0
    for interv in qs:
        cibles += 1
        try:
            if _wa_draft_for_intervention(interv):
                wa_generes += 1
        except Exception as exc:  # pragma: no cover - défensif
            logger.warning(
                'XFSM6 : brouillon WhatsApp échoué (intervention %s) : %s',
                interv.id, exc)
        if _envoyer_email_client(interv):
            emails_envoyes += 1

    return {
        'jour_cible': str(demain), 'cibles': cibles,
        'wa_generes': wa_generes, 'emails_envoyes': emails_envoyes,
    }


@shared_task(name='installations.meteo_planning_j3')
def meteo_planning_j3():
    """XFSM21 — sweep quotidien : récupère la prévision J+3 (Open-Meteo,
    gratuit, sans clé) aux GPS des interventions de type POSE planifiées ce
    jour-là, et positionne `meteo_risque` selon les seuils (pluie/vent).
    Panne API → SILENCIEUSE (le champ reste inchangé pour cette intervention,
    le sweep continue sur les suivantes). Notifie le responsable du chantier
    quand un risque est détecté (best-effort, jamais bloquant). Renvoie un
    compte {cibles, evaluees, a_risque} pour observabilité/tests."""
    from datetime import timedelta

    from . import weather
    from .models import Intervention

    jour_cible = casablanca_today() + timedelta(days=3)
    qs = (Intervention.objects
          .filter(date_prevue=jour_cible, type_intervention=Intervention.Type.POSE)
          .select_related('installation', 'installation__technicien_responsable'))

    cibles = 0
    evaluees = 0
    a_risque = 0
    for interv in qs:
        cibles += 1
        inst = interv.installation
        lat = getattr(inst, 'gps_lat', None)
        lng = getattr(inst, 'gps_lng', None)
        try:
            forecast = weather.fetch_forecast(lat, lng, jour_cible)
            risque = weather.evaluate_risk(forecast)
        except Exception as exc:  # pragma: no cover - défensif
            logger.warning(
                'XFSM21 : évaluation météo échouée (intervention %s) : %s',
                interv.id, exc)
            continue
        if risque is None:
            continue
        evaluees += 1
        from django.utils import timezone
        interv.meteo_risque = risque
        interv.meteo_verifie_le = timezone.now()
        interv.save(update_fields=['meteo_risque', 'meteo_verifie_le'])
        if risque:
            a_risque += 1
            _notifier_meteo_risque(interv)

    return {
        'jour_cible': str(jour_cible), 'cibles': cibles,
        'evaluees': evaluees, 'a_risque': a_risque,
    }


def _notifier_meteo_risque(interv):
    """XFSM21 — notifie le responsable du chantier d'un risque météo détecté
    sur une pose planifiée (best-effort, ne lève jamais)."""
    try:
        from apps.notifications.services import notify
        from apps.notifications.models import EventType
    except Exception:  # pragma: no cover - défensif
        return
    responsable = getattr(interv.installation, 'technicien_responsable', None)
    if responsable is None:
        return
    try:
        # CHT9 — exclusion EXPLICITE du désenchevêtrement : cette alerte parle
        # bien de la date de POSE du chantier (le fait métier de
        # CHANTIER_DUE), contrairement aux 3 autres sites qui l'empruntaient
        # par facilité — elle reste donc CHANTIER_DUE.
        notify(
            responsable, EventType.CHANTIER_DUE,
            f"Risque météo — pose du {interv.date_prevue}",
            body="Pluie/vent au-delà des seuils prévus J+3 — "
                 "envisager une replanification.",
            company=interv.company)
    except Exception:  # pragma: no cover - défensif
        pass


# ── AUD231 — ZFSM3 : la prestation périodique SANS contrat de maintenance ───
# La commande ``generer_interventions_recurrentes`` annonçait « Pensé pour être
# exécuté à la demande ou par un planificateur (cron / Celery beat) » ; le grep
# sur ``erp_agentique/`` rendait ZÉRO. Aucune occurrence récurrente n'était donc
# générée tant que personne ne lançait la commande à la main.

@shared_task(name='installations.generer_interventions_recurrentes')
def generer_interventions_recurrentes_task():
    """ZFSM3 (AUD231) — génère la prochaine ``Intervention`` de chaque
    récurrence active à échéance, pour toutes les sociétés. Idempotente : deux
    passages le même jour ne créent jamais deux occurrences pour la même
    échéance. Une exception sur une société n'empêche jamais les suivantes.
    Renvoie le nombre total d'interventions créées."""
    from authentication.selectors import active_companies
    from .services import generer_interventions_recurrentes
    total = 0
    for company in active_companies():  # AUD415/SCA19 — pas les suspendus
        try:
            total += len(generer_interventions_recurrentes(company))
        except Exception:  # noqa: BLE001 — société suivante
            logger.warning(
                'installations.generer_interventions_recurrentes: échec '
                'société %s', company.id, exc_info=True)
    return total


def _deja_notifie_aujourdhui(event_type, titre, recipient=None):
    """Vrai si CETTE notification (même événement, même titre, même
    destinataire) a déjà été créée aujourd'hui.

    ``stock.tasks._deja_notifie_aujourdhui`` clé sur le ``link`` parce que
    là-bas le lien EST une clé de dédoublonnage stable, passée telle quelle à
    ``notify_many``. Ici le lien posé est la ROUTE RÉELLE de l'écran (WIR176 —
    ``/chantiers/consultations``), donc identique pour toutes les relances et
    jamais égal à la clé calculée : la garde ne trouvait rien et chaque passage
    re-notifiait. Le TITRE, lui, nomme la RFQ ET le fournisseur — c'est-à-dire
    exactement la consultation relancée."""
    from apps.notifications.models import Notification
    today = casablanca_today()
    try:
        qs = Notification.objects.filter(
            event_type=event_type, title=titre, created_at__date=today)
        if recipient is not None:
            qs = qs.filter(recipient=recipient)
        return qs.exists()
    except Exception:  # pragma: no cover - défensif
        return False


@shared_task(name='installations.relancer_rfq_en_attente')
def relancer_rfq_en_attente_task():
    """NTP2P33 — pour CHAQUE société active, notifie l'acheteur (créateur de
    la RFQ, repli managers) des ``RFQConsultation`` non répondues
    (``a_repondu`` False, i.e. ``offre`` non posée) dont la RFQ approche sa
    ``date_limite_reponse`` (J-2) ET n'est pas révoquée.

    Réutilise le pattern ``stock.tasks.relancer_bcf_en_retard_task`` (même
    garde d'idempotence par lien) — EMPRUNTE l'``EventType`` achats existant
    ``BCF_RELANCE_PROPOSEE`` (« brouillon de relance proposé ») plutôt que
    d'ajouter une valeur ``EventType`` non déclarée : ``apps.notifications``
    est hors périmètre de cette lane (même choix que
    ``stock.alerter_surcapacite_zones_task``, qui emprunte ``STOCK_LOW``).
    Le libellé de la notification, lui, nomme explicitement la RFQ.

    Idempotent : au plus une notification par jour par consultation. Best-
    effort par société et par consultation. Renvoie
    ``{company_id: nb_consultations_notifiees}``."""
    from datetime import timedelta

    from authentication.selectors import active_companies

    from .models_rfq import RFQ, RFQConsultation

    today = casablanca_today()
    cible = today + timedelta(days=2)
    result = {}
    for company in active_companies():  # AUD415/SCA19 — pas les suspendus
        try:
            consultations = list(
                RFQConsultation.objects.filter(
                    company=company, revoque=False, offre__isnull=True,
                    rfq__statut=RFQ.Statut.ENVOYEE,
                    rfq__date_limite_reponse=cible,
                ).select_related('rfq', 'rfq__created_by', 'fournisseur'))
        except Exception:  # noqa: BLE001 — société suivante
            logger.warning(
                'installations.relancer_rfq_en_attente: échec calcul '
                'société %s', company.id, exc_info=True)
            continue
        count = 0
        for consultation in consultations:
            acheteur = consultation.rfq.created_by
            if acheteur is None:
                continue
            fournisseur_nom = (
                consultation.fournisseur.nom
                if consultation.fournisseur_id else '')
            titre = (f'RFQ {consultation.rfq.reference} — '
                     f'{fournisseur_nom} n\'a pas répondu')
            # Idempotence du jour : la clé est le TITRE (RFQ + fournisseur =
            # la consultation), pas le lien — celui-ci est la route réelle de
            # l'écran, la même pour toutes les relances (cf. la garde).
            if _deja_notifie_aujourdhui(
                    'bcf_relance_proposee', titre, recipient=acheteur):
                continue
            try:
                from apps.notifications.models import EventType
                from apps.notifications.services import notify
                notify(
                    acheteur, EventType.BCF_RELANCE_PROPOSEE,
                    title=titre,
                    body=(f'La date limite de réponse de la RFQ '
                          f'{consultation.rfq.reference} approche (J-2) et '
                          f'{fournisseur_nom or "ce fournisseur"} n\'a pas '
                          'encore répondu. Une relance est recommandée.'),
                    # WIR176 — route réelle du module (`RFQ.jsx`), pas un
                    # chemin `/installations/...` fabriqué.
                    link='/chantiers/consultations',
                    company=company)
                count += 1
            except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
                logger.warning(
                    'installations.relancer_rfq_en_attente: notification '
                    'échouée (consultation %s)', consultation.pk,
                    exc_info=True)
        result[company.id] = count
    return result
