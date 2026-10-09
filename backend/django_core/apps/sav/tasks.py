"""YSERV5 — Beat Celery quotidien : génération automatique des visites
préventives dues (opt-in par société).

Avant cette tâche, ``apps/sav/maintenance.py generer_visites_dues()``
n'était appelée QUE par le bouton manuel (action ``generer-dus``) — aucun job
beat (vérifié ``erp_agentique/celery.py``). Le sweep FG1 ne fait que
NOTIFIER, jamais matérialiser. Cette tâche ferme cet écart : les sociétés qui
activent ``SavSlaSettings.generation_auto_visites`` voient leurs visites
dues (sous ``visites_avance_jours`` jours) créées chaque nuit sans action
humaine — réutilise EXACTEMENT ``maintenance.generer_visites_dues`` (aucune
logique dupliquée), étendue pour accepter un horizon d'avance.

Autodécouvert par ``erp_agentique.celery`` (``autodiscover_tasks()``), comme
les autres tâches planifiées de l'ERP.

Multi-tenant : boucle par société active, OFF par défaut = no-op total. Une
société qui échoue n'empêche jamais les suivantes (best-effort, journalisé).
"""
import logging
from contextlib import contextmanager
from datetime import timedelta

from celery import shared_task
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)

_EVENT_TYPE = 'sav_visites_auto_generees'

# ── NTSRV38 — verrou d'exclusion des balayages SLA ──────────────────────────
# Les deux balayages SLA tournent au quart d'heure (beat). Une exécution qui
# déborde (beat qui retire, worker relancé, exécution manuelle en parallèle)
# ne doit JAMAIS notifier deux fois le même palier du même ticket : c'est une
# course entre deux lectures de `Ticket.sla_escalade_paliers_notifies` avant
# que l'une n'écrive. Le verrou la ferme.
#
# C'est un VERROU (posé puis RELÂCHÉ), pas une clé d'idempotence à durée fixe
# (`core.idempotent_task`) : un appel SÉQUENTIEL suivant doit pouvoir tourner
# normalement — seul un appel CONCURRENT est court-circuité. Le TTL n'est
# qu'un filet si le processus meurt en cours de balayage.
_VERROU_TTL = 600  # secondes


@contextmanager
def _verrou_scan(nom):
    """Verrou best-effort nommé. Cède ``True`` si CET appel l'a obtenu.

    Cache indisponible (Redis coupé) → on cède ``True`` sans verrou : un
    balayage SLA qui ne tourne plus du tout serait pire que le risque de
    double notification, déjà atténué par l'idempotence sur le ticket.
    """
    cle = f'sav-sla-scan:{nom}'
    try:
        obtenu = bool(cache.add(cle, 1, _VERROU_TTL))
    except Exception:  # pragma: no cover - cache KO → on n'empêche pas le scan
        logger.warning('sav: verrou %s indisponible (cache KO)', nom)
        yield True
        return
    try:
        yield obtenu
    finally:
        if obtenu:
            try:
                cache.delete(cle)
            except Exception:  # pragma: no cover - défensif
                logger.warning('sav: libération du verrou %s KO', nom)


def _responsables(company):
    """Responsables/admins actifs de la société (destinataires de la
    notification). Repli sur tous les actifs si aucun palier trouvé — même
    logique que les autres tâches de notification par défaut de l'ERP."""
    try:
        from authentication.models import CustomUser
        base = list(CustomUser.objects.filter(company=company, is_active=True))
    except Exception:  # pragma: no cover - défensif
        return []
    managers = [
        u for u in base
        if getattr(u, 'is_admin_role', False)
        or getattr(u, 'role_tier', None) in ('admin', 'responsable')
    ]
    return managers or base


@shared_task(name='sav.generer_visites_dues_quotidien')
def generer_visites_dues_quotidien():
    """YSERV5 — Pour chaque société ayant activé
    ``SavSlaSettings.generation_auto_visites`` : matérialise les visites
    préventives dues sous ``visites_avance_jours`` jours (idempotence déjà
    garantie par ``generer_visites_dues``), puis notifie les responsables
    quand au moins un ticket a été créé. OFF (défaut) = société totalement
    ignorée — aucun effet."""
    from authentication.models import CustomUser
    from authentication.selectors import active_companies

    from apps.notifications.services import notify
    from .maintenance import generer_visites_dues
    from .models import SavSlaSettings

    total_societes = 0
    total_generes = 0

    # SCA19 — restreint aux sociétés opérationnelles via la source unique : un
    # tenant suspendu/en fermeture n'a plus de génération de visites préventives.
    for reglage in SavSlaSettings.objects.filter(
            generation_auto_visites=True, company__isnull=False,
            company__in=active_companies()).select_related('company'):
        company = reglage.company
        try:
            acteur = (
                CustomUser.objects.filter(
                    company=company, is_active=True)
                .order_by('-is_superuser', 'id').first())
            n = generer_visites_dues(
                company, acteur, avance_jours=reglage.visites_avance_jours)
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'sav.generer_visites_dues_quotidien: échec société %s',
                company.pk, exc_info=True)
            continue
        total_societes += 1
        if not n:
            continue
        total_generes += n
        titre = f'{n} visite(s) préventive(s) générée(s) automatiquement'
        corps = (
            f'{n} ticket(s) SAV préventif(s) ont été créés automatiquement '
            f'(avance {reglage.visites_avance_jours} j).')
        for user in _responsables(company):
            try:
                notify(
                    user, _EVENT_TYPE, titre, body=corps,
                    # SAV-LIEN-MORT — la route frontend est `/sav/contrats`
                    # (`frontend/src/features/sav/module.config.jsx`), jamais
                    # `/sav/contrats-maintenance` (ça, c'est le préfixe API
                    # `/api/django/sav/contrats-maintenance/…`, sans rapport).
                    link='/sav/contrats', company=company)
            except Exception:  # pragma: no cover - défensif
                logger.warning(
                    'sav.generer_visites_dues_quotidien: notification '
                    'échouée vers %s', user, exc_info=True)

    logger.info(
        'sav.generer_visites_dues_quotidien: %s société(s) traitée(s), %s '
        'visite(s) générée(s)', total_societes, total_generes)
    return {'societes': total_societes, 'visites_generees': total_generes}


# ── WIR30 — Beat pour XSAV6 (pré-alerte SLA + escalade) ─────────────────────

@shared_task(name='sav.scan_sla_pre_alerts_and_escalations_quotidien')
def scan_sla_pre_alerts_and_escalations_quotidien():
    """WIR30 — Planifie ``apps.sav.views.scan_sla_pre_alerts_and_escalations``
    (XSAV6), bâtie et testée (``tests_xsav6.py``) mais jamais ajoutée au beat
    jusqu'ici. DISTINCT de ``scan_sla_breaches`` (planifiée séparément par
    NTSRV38, ne pas dupliquer ici). OFF par défaut par société
    (``sla_warning_days=0``, ``escalade_activee=False``) : aucun effet tant
    qu'une société n'active pas explicitement l'un des deux réglages.

    NTSRV38 — c'est ICI que vivent les PALIERS d'escalade multi-niveaux
    (NTSRV12, ``_notifier_paliers``), donc c'est cette tâche que le beat
    rappelle toutes les 15 minutes (le nom ``…_quotidien`` est hérité de
    WIR30 et conservé : il est référencé par ``beat_schedule`` et
    ``CELERY_TASK_ROUTES``). Deux exécutions CONCURRENTES sont exclues par le
    verrou ; une exécution séquentielle suivante tourne normalement."""
    with _verrou_scan('pre-alerts') as obtenu:
        if not obtenu:
            logger.info(
                'sav.scan_sla_pre_alerts_and_escalations: exécution '
                'concurrente ignorée (verrou tenu)')
            return {'skipped': True}
        return scan_sla_pre_alerts_and_escalations()


# ── NTSRV38 — Beat au quart d'heure pour FG81 (violation SLA) ───────────────

@shared_task(name='sav.scan_sla_breaches_quart_heure')
def scan_sla_breaches_quart_heure():
    """NTSRV38 — Planifie ``apps.sav.views.scan_sla_breaches`` (FG81), qui
    n'avait AUCUNE entrée beat : elle ne tournait qu'à la demande (commande
    de gestion / appel manuel), donc un dépassement de SLA n'était notifié
    que si quelqu'un lançait le balayage.

    Cadence : toutes les 15 minutes, sous le MÊME type de verrou que la
    tâche de pré-alerte/escalade — deux exécutions simultanées n'écrivent
    jamais deux fois ``sla_breach`` ni n'émettent deux notifications pour le
    même ticket. OFF par société tant que ``sla_breach_enabled`` est False
    (défaut) : le balayage ne modifie alors rien."""
    with _verrou_scan('breaches') as obtenu:
        if not obtenu:
            logger.info('sav.scan_sla_breaches: exécution concurrente '
                        'ignorée (verrou tenu)')
            return {'skipped': True}
        return {'skipped': False, 'tickets': scan_sla_breaches()}


# ── ASAV33 — XSAV24 : l'auto-clôture a enfin sa tâche planifiée ─────────────

@shared_task(name='sav.scan_auto_cloture_quotidien')
def scan_auto_cloture_quotidien():
    """ASAV33 — planifie ``scan_auto_cloture_tickets_resolus`` (XSAV24), qui
    n'avait AUCUNE entrée beat : le réglage « auto-clôture après N jours »
    ne clôturait donc jamais rien. Même verrou que les balayages SLA ; OFF par
    société tant que ``auto_cloture_jours`` vaut 0 (défaut)."""
    with _verrou_scan('auto-cloture') as obtenu:
        if not obtenu:
            logger.info('sav.scan_auto_cloture: exécution concurrente '
                        'ignorée (verrou tenu)')
            return {'skipped': True}
        return {'skipped': False,
                'tickets': scan_auto_cloture_tickets_resolus()}


# ── ASAV33 — les balayages SAV (déplacés depuis views.py) ───────────────────

# ── AUD521 — Réglages SLA mis en cache PAR SOCIÉTÉ pour les scans quotidiens ─
# Les trois scans ci-dessous parcourent la queryset Ticket multi-société et
# appelaient ``SavSlaSettings.get(ticket.company)`` DANS la boucle — soit un
# ``get_or_create`` par ticket. Ce helper charge tous les réglages en UNE
# requête et ne retombe sur ``get()`` que pour une société sans réglage
# enregistré (au plus une requête par société distincte, jamais par ticket).

def _reglages_sla_par_ticket(tickets):
    """Renvoie une fonction ``(ticket) -> SavSlaSettings`` sans N+1."""
    from .models import SavSlaSettings

    cache = SavSlaSettings.par_company({t.company_id for t in tickets})

    def _pour(ticket):
        if ticket.company_id in cache:
            return cache[ticket.company_id]
        reglage = SavSlaSettings.get(ticket.company)
        cache[ticket.company_id] = reglage
        return reglage
    return _pour


# ── FG81 — Scan journalier de breach (appelé par Celery-beat ou management cmd) ──

def scan_sla_breaches():
    """FG81 — Parcourt tous les tickets ouverts avec sla_due_at dépassé, met à
    jour sla_breach et notifie le technicien responsable. Idempotent.

    Appelé par le scan journalier (management command ou Celery-beat).
    Aucune modification si sla_breach_enabled est False pour la société."""
    from apps.notifications.services import notify
    from apps.notifications.types_evenements import EventType

    from authentication.selectors import active_company_ids

    from .models import Ticket
    from .selectors import ticket_en_retard_sla

    today = timezone.localdate()
    # ASAV17 — candidats : échéance BRUTE dépassée (l'effective n'est jamais
    # plus tôt) OU drapeau déjà levé (à remettre à False si le retard n'est
    # plus vrai : pause, société au SLA désactivé). La décision vient de
    # ``selectors.ticket_en_retard_sla`` — une seule définition du retard.
    # ASAV33 — un tenant suspendu n'est plus balayé (source unique SCA19).
    candidats = list(Ticket.objects.filter(
        company_id__in=active_company_ids(),
        statut__in=Ticket.OPEN_STATUTS,
        annule=False,
    ).filter(Q(sla_due_at__lt=today) | Q(sla_breach=True))
     .select_related('company', 'technicien_responsable'))
    # AUD521 — réglages chargés UNE fois par société (plus un get_or_create
    # par ticket).
    reglage_pour = _reglages_sla_par_ticket(candidats)

    updated = 0
    for ticket in candidats:
        retard = ticket_en_retard_sla(
            ticket, today, sla_actif=reglage_pour(ticket).sla_breach_enabled)
        if not retard:
            if ticket.sla_breach:
                ticket.sla_breach = False
                ticket.save(update_fields=['sla_breach'])
            continue
        if ticket.sla_breach:
            continue  # déjà signalé — idempotent.
        ticket.sla_breach = True
        ticket.save(update_fields=['sla_breach'])
        updated += 1
        # ASAV57 — l'interrupteur société ne gouverne que la NOTIFICATION.
        if (reglage_pour(ticket).sla_breach_enabled
                and ticket.technicien_responsable_id):
            notify(
                user=ticket.technicien_responsable,
                event_type=EventType.SAV_TICKET_BREACHING,
                title=f'SLA dépassé — {ticket.reference}',
                body=(f'Le ticket {ticket.reference} a dépassé son délai SLA '
                      f'({ticket.sla_due_at.strftime("%d/%m/%Y")}).'),
                link=f'/sav/tickets/{ticket.pk}',
                company=ticket.company,
            )
    return updated


# ── NTSRV12 — Paliers d'escalade SLA configurables (étend XSAV6) ────────────

def _paliers_escalade_par_company(company_ids):
    """NTSRV12 — ``{company_id: [EscaladeSlaNiveau ordonnés]}`` en UNE requête.

    Dict VIDE pour toute société sans palier configuré : l'appelant garde
    alors le comportement XSAV6 binaire, strictement inchangé."""
    from .models import EscaladeSlaNiveau

    ids = {cid for cid in company_ids if cid is not None}
    if not ids:
        return {}
    par_company = {}
    for palier in (EscaladeSlaNiveau.objects
                   .filter(company_id__in=ids, actif=True)
                   .select_related('notifier_utilisateur')
                   .order_by('ordre', 'seuil_jours_apres_echeance', 'id')):
        par_company.setdefault(palier.company_id, []).append(palier)
    return par_company


def _destinataires_palier(palier, company):
    """NTSRV12 — destinataires d'un palier : l'utilisateur désigné, sinon les
    comptes actifs du rôle visé, sinon les destinataires par défaut de
    l'événement (``resolve_recipients``, mute-aware via ``notify()``)."""
    from apps.notifications.types_evenements import EventType
    from apps.notifications.services import resolve_recipients

    if palier.notifier_utilisateur_id:
        return [palier.notifier_utilisateur]
    role = (palier.notifier_role or '').strip().lower()
    if role:
        from authentication.models import CustomUser
        vises = [
            u for u in CustomUser.objects.filter(
                company=company, is_active=True)
            if (getattr(u, 'role_tier', None) or '').lower() == role
            or (role == 'admin' and getattr(u, 'is_admin_role', False))
        ]
        if vises:
            return vises
    return list(resolve_recipients(company, EventType.SAV_TICKET_BREACHING))


def _notifier_paliers(ticket, paliers, due_effectif, today):
    """NTSRV12 — notifie les paliers ÉCHUS et pas encore notifiés pour ce
    ticket. Renvoie le nombre de paliers déclenchés (0 le plus souvent).

    Un palier ``seuil_jours_apres_echeance=N`` se déclenche à partir de
    ``échéance + N jours`` — JAMAIS avant. IDEMPOTENT : l'id du palier est
    mémorisé sur le ticket (``sla_escalade_paliers_notifies``), donc le
    balayage du lendemain ne le rejoue pas."""
    from apps.notifications.types_evenements import EventType
    from apps.notifications.services import notify

    if due_effectif is None:
        return 0
    deja = ticket.sla_escalade_paliers_notifies or []
    if not isinstance(deja, list):
        deja = []
    declenches = 0
    for palier in paliers:
        if palier.pk in deja:
            continue
        seuil = due_effectif + timedelta(days=palier.seuil_jours_apres_echeance)
        if today < seuil:
            continue  # « jamais avant » — garantie du critère d'acceptation.
        libelle = palier.libelle or f'J+{palier.seuil_jours_apres_echeance}'
        for user in _destinataires_palier(palier, ticket.company):
            notify(
                user=user,
                event_type=EventType.SAV_TICKET_BREACHING,
                title=f'Escalade SLA ({libelle}) — {ticket.reference}',
                body=(f'Le ticket {ticket.reference} a atteint le palier '
                      f'{libelle} après son échéance SLA '
                      f'({due_effectif.strftime("%d/%m/%Y")}).'),
                link=f'/sav/tickets/{ticket.pk}',
                company=ticket.company,
            )
        deja.append(palier.pk)
        declenches += 1
    if declenches:
        ticket.sla_escalade_paliers_notifies = deja
        ticket.save(update_fields=['sla_escalade_paliers_notifies'])
    return declenches


# ── XSAV6 — Pré-alerte SLA (J-x) + escalade à la violation ────────────────────

def scan_sla_pre_alerts_and_escalations():
    """XSAV6 — Pré-alerte à J-x + escalade au tier responsable à la violation.

    DISTINCT de ``scan_sla_breaches`` (FG81, notifie le technicien À la
    violation) et de ``notifications.sweeps._sweep_sav_breaching`` (âge du
    ticket, repli managers). Ici : pré-alerte configurable AVANT l'échéance
    (``sla_warning_days`` jours avant ``sla_due_at_effectif``), puis escalade
    au tier responsable/direction (``resolve_recipients``, mute-aware via
    ``notify()``) une fois l'échéance dépassée — si ``escalade_activee``.

    IDEMPOTENT : un ticket déjà notifié pour un niveau (pré-alerte ou
    escalade) ne l'est plus les jours suivants — flag posé sur le ticket.
    OFF par défaut (``sla_warning_days=0`` et ``escalade_activee=False``) :
    aucun effet, aucune notification supplémentaire.

    NTSRV12 — quand une société configure des ``EscaladeSlaNiveau``, ces
    PALIERS remplacent pour elle l'escalade binaire ci-dessus (plusieurs
    notifications ordonnées, ex. J+0 → responsable, J+1 → direction), chacune
    idempotente via ``Ticket.sla_escalade_paliers_notifies``. AUCUN palier
    configuré = comportement XSAV6 strictement inchangé.
    """
    from authentication.selectors import active_company_ids

    from apps.notifications.services import notify, resolve_recipients
    from apps.notifications.types_evenements import EventType
    from .models import Ticket

    today = timezone.localdate()
    # ASAV33 — bornée aux sociétés actives (tenant suspendu ignoré).
    qs = list(Ticket.objects.filter(
        company_id__in=active_company_ids(),
        statut__in=Ticket.OPEN_STATUTS,
        annule=False,
        sla_due_at__isnull=False,
    ).select_related('company', 'technicien_responsable'))
    # AUD521 — réglages chargés UNE fois par société.
    reglage_pour = _reglages_sla_par_ticket(qs)

    # NTSRV12 — paliers d'escalade chargés UNE fois par société (jamais une
    # requête par ticket).
    paliers_par_company = _paliers_escalade_par_company(
        {t.company_id for t in qs})

    def paliers_pour(company_id):
        return paliers_par_company.get(company_id, [])

    pre_alerts = 0
    escalations = 0
    for ticket in qs:
        sla = reglage_pour(ticket)
        # ASAV57 — interrupteur OFF : aucune pré-alerte ni escalade.
        if not sla.sla_breach_enabled:
            continue
        due_effectif = ticket.sla_due_at_effectif(today=today)

        # ── Pré-alerte J-x au technicien assigné ──
        if (sla.sla_warning_days > 0
                and not ticket.sla_pre_alert_notifiee
                and not ticket.sla_escalade_notifiee
                and ticket.technicien_responsable_id
                and due_effectif is not None):
            seuil = due_effectif - timedelta(days=sla.sla_warning_days)
            if today >= seuil and today <= due_effectif:
                notify(
                    user=ticket.technicien_responsable,
                    event_type=EventType.SAV_TICKET_BREACHING,
                    title=f'SLA bientôt dépassé — {ticket.reference}',
                    body=(f'Le ticket {ticket.reference} approche son '
                          f'échéance SLA ({due_effectif.strftime("%d/%m/%Y")}).'),
                    link=f'/sav/tickets/{ticket.pk}',
                    company=ticket.company,
                )
                ticket.sla_pre_alert_notifiee = True
                ticket.save(update_fields=['sla_pre_alert_notifiee'])
                pre_alerts += 1

        # ── NTSRV12 — Paliers d'escalade configurables (remplacent le
        # binaire XSAV6 POUR LA SOCIÉTÉ QUI EN CONFIGURE). Aucun palier =
        # aucun changement : on retombe sur le bloc XSAV6 ci-dessous.
        paliers = paliers_pour(ticket.company_id)
        if paliers:
            escalations += _notifier_paliers(ticket, paliers, due_effectif,
                                             today)
            continue

        # ── Escalade au tier responsable/direction à la violation ──
        if (sla.escalade_activee
                and not ticket.sla_escalade_notifiee
                and due_effectif is not None
                and today > due_effectif):
            recipients = resolve_recipients(
                ticket.company, EventType.SAV_TICKET_BREACHING)
            for user in recipients:
                notify(
                    user=user,
                    event_type=EventType.SAV_TICKET_BREACHING,
                    title=f'Escalade SLA — {ticket.reference}',
                    body=(f'Le ticket {ticket.reference} a dépassé son '
                          f'échéance SLA ({due_effectif.strftime("%d/%m/%Y")}) '
                          'et requiert une attention immédiate.'),
                    link=f'/sav/tickets/{ticket.pk}',
                    company=ticket.company,
                )
            ticket.sla_escalade_notifiee = True
            ticket.save(update_fields=['sla_escalade_notifiee'])
            escalations += 1

    return {'pre_alerts': pre_alerts, 'escalations': escalations}


# ── XSAV24 — Auto-clôture des tickets résolus dormants ───────────────────────

def scan_auto_cloture_tickets_resolus():
    """XSAV24 — Clôture automatiquement les tickets RÉSOLU sans activité
    depuis ``SavSlaSettings.auto_cloture_jours`` jours (0 = OFF, comportement
    actuel inchangé — AUCUN ticket n'est jamais touché tant qu'une société ne
    fixe pas explicitement une valeur > 0).

    « Sans activité » = aucun ``TicketActivity`` (note ou changement de champ
    suivi, y compris le passage à RÉSOLU lui-même) depuis N jours — donc un
    ticket tout juste résolu, ou avec un échange récent, n'est jamais fermé
    par erreur. IDEMPOTENT : un ticket déjà CLÔTURÉ n'est plus repris par le
    sweep suivant (il ne filtre que sur ``statut=RESOLU``).

    Notification client optionnelle réutilisée via XSAV4
    (``notify_ticket_transition``, best-effort, n'envoie rien sans le toggle
    société ``notifications_client_sav`` — indépendant du toggle
    ``auto_cloture_jours``)."""
    from authentication.selectors import active_company_ids

    from . import activity
    from .models import Ticket, TicketActivity
    from .services import TransitionTicketRefusee, appliquer_transition_ticket

    today = timezone.localdate()
    cloture = 0

    # ASAV33 — bornée aux sociétés actives (tenant suspendu ignoré).
    tickets = list(Ticket.objects
                   .filter(company_id__in=active_company_ids(),
                           statut=Ticket.Statut.RESOLU, annule=False)
                   .select_related('company'))
    # AUD521 — réglages chargés UNE fois par société.
    reglage_pour = _reglages_sla_par_ticket(tickets)

    for ticket in tickets:
        sla = reglage_pour(ticket)
        if not sla.auto_cloture_jours:
            continue

        derniere_activite = (
            TicketActivity.objects.filter(ticket=ticket)
            .order_by('-created_at').values_list('created_at', flat=True)
            .first())
        reference_dt = derniere_activite or ticket.date_modification
        if reference_dt is None:
            continue
        jours_ecoules = (today - timezone.localtime(reference_dt).date()).days
        if jours_ecoules < sla.auto_cloture_jours:
            continue

        # ASAV33 — la clôture passe par LE service gardé (graphe, garde
        # YSERV2 des interventions ouvertes, suiveurs, ARC34, notification
        # client XSAV4) ; un refus laisse le ticket résolu.
        try:
            appliquer_transition_ticket(ticket, Ticket.Statut.CLOTURE, None)
        except TransitionTicketRefusee as exc:
            logger.info(
                'sav.auto_cloture: ticket %s non clôturé (%s)',
                ticket.reference, exc)
            continue
        activity.log_note(
            ticket, None,
            f'Clôturé automatiquement après {sla.auto_cloture_jours} jours '
            "sans activité.")
        cloture += 1

    return cloture
