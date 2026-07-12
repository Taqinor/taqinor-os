"""FG1 — Balayages quotidiens (Celery Beat) pour les EventTypes « morts ».

`CHANTIER_DUE`, `WARRANTY_EXPIRING`, `MAINTENANCE_DUE`, `SAV_TICKET_BREACHING`
étaient déclarés dans `models.py` mais jamais émis. Ces tâches idempotentes les
activent sans rien modifier : elles scannent, notifient, et s'arrêtent là.

Principes :
  - IDEMPOTENT : ne mute aucune donnée métier ; ré-exécuter ne fait que
    ré-émettre des notifications (la préférence in-app peut désactiver).
  - MULTI-TENANT : chaque société est traitée isolément, bornée par company.
  - DÉFENSIF : chaque section est dans son propre try/except — une société en
    erreur n'empêche pas les suivantes. Aucune exception ne remonte.
  - DESTINATAIRE : l'owner/responsable de l'enregistrement si disponible,
    sinon les gérants/staff de la société (même logique que digests.py).
"""
import logging
from datetime import date, timedelta

from celery import shared_task

from .models import EventType
from .services import notify

logger = logging.getLogger(__name__)

# ── Seuils (constants défensives) ────────────────────────────────────────────
WARRANTY_HORIZON_DAYS = 90   # garantie expirant dans les 90 prochains jours
BREACH_OPEN_DAYS = 7         # ticket ouvert depuis ≥ 7 jours sans résolution
CHANTIER_DUE_DAYS = 14      # chantier dont date_pose_prevue arrive dans 14 j
DA_STALE_DAYS = 3            # VX213 — DA soumise sans décision depuis ≥ 3 jours
STOCK_EXPIRATION_HORIZON_DAYS = 30  # VX209(d) — lot expirant dans 30 jours
NOTIFICATION_RETENTION_DAYS = 60    # VX209(c) — purge lues / archive non-lues


def _companies():
    """Toutes les sociétés actives. Vide si erreur."""
    try:
        from authentication.models import Company
        return list(Company.objects.filter(actif=True))
    except Exception:  # pragma: no cover
        logger.warning('sweeps: chargement des sociétés impossible', exc_info=True)
        return []


def _managers(company):
    """Gérants/staff de la société (même logique que digests._recipients)."""
    try:
        from authentication.models import CustomUser
        base = CustomUser.objects.filter(company=company, is_active=True)
        mgrs = [u for u in base if _is_manager(u)]
        return mgrs if mgrs else list(base)
    except Exception:  # pragma: no cover
        return []


def _is_manager(user):
    try:
        if getattr(user, 'is_admin_role', False):
            return True
        return getattr(user, 'role_tier', None) in ('admin', 'responsable')
    except Exception:
        return False


def _notify_user_or_managers(user, company, event_type, title, body, link=''):
    """Notifie `user` s'il est valide, sinon les managers de la société."""
    if user is not None and getattr(user, 'pk', None):
        notify(user, event_type, title, body=body, link=link, company=company)
        return
    for mgr in _managers(company):
        notify(mgr, event_type, title, body=body, link=link, company=company)


# ── WARRANTY_EXPIRING sweep ───────────────────────────────────────────────────

def _owner_of_equipement(eq):
    """VX209(d) — le technicien responsable du chantier de l'équipement,
    s'il en a un (`Installation.technicien_responsable`) ; `None` sinon (les
    équipements vendus au comptoir — `client_vente` — n'ont pas de chantier)."""
    installation = getattr(eq, 'installation', None)
    return getattr(installation, 'technicien_responsable', None) \
        if installation is not None else None


def _sweep_warranty_expiring(company):
    """Équipements EN SERVICE dont la garantie expire dans WARRANTY_HORIZON_DAYS.

    VX209(d) — notifie le technicien responsable du chantier quand il existe
    (`_owner_of_equipement`), sinon les managers de la société (comportement
    historique préservé pour les équipements sans chantier)."""
    try:
        from apps.sav.models import Equipement
        today = date.today()
        horizon = today + timedelta(days=WARRANTY_HORIZON_DAYS)
        qs = Equipement.objects.filter(
            company=company,
            statut=Equipement.Statut.EN_SERVICE,
            date_fin_garantie__isnull=False,
            date_fin_garantie__gte=today,
            date_fin_garantie__lte=horizon,
        ).select_related('produit', 'installation')
        count = 0
        for eq in qs:
            try:
                produit_nom = (
                    getattr(eq.produit, 'designation', '')
                    or str(eq.produit_id)
                )
                delta = (eq.date_fin_garantie - today).days
                title = 'Garantie bientôt expirée'
                body = (
                    f"L'équipement « {produit_nom} » "
                    f"(n° série : {eq.numero_serie or '—'}) "
                    f"voit sa garantie expirer dans {delta} jours "
                    f"({eq.date_fin_garantie})."
                )
                link = f'/sav/equipements/{eq.pk}'
                owner = _owner_of_equipement(eq)
                if owner is not None:
                    notify(owner, EventType.WARRANTY_EXPIRING, title,
                           body=body, link=link, company=company)
                else:
                    for mgr in _managers(company):
                        notify(mgr, EventType.WARRANTY_EXPIRING, title,
                               body=body, link=link, company=company)
                count += 1
            except Exception:  # pragma: no cover
                logger.warning('sweeps: warranty eq %s échoué', eq.pk,
                               exc_info=True)
        return count
    except Exception:  # pragma: no cover
        logger.warning('sweeps: warranty_expiring société %s échouée',
                       getattr(company, 'pk', None), exc_info=True)
        return 0


# ── MAINTENANCE_DUE sweep ─────────────────────────────────────────────────────

def _sweep_maintenance_due(company):
    """Contrats de maintenance actifs dont une visite est due aujourd'hui.

    Réutilise ContratMaintenance.is_due() (même oracle que le digest).
    VX209(d) — notifie le technicien responsable du chantier rattaché quand
    il existe, sinon les managers (comportement historique préservé pour les
    contrats sans chantier)."""
    try:
        from apps.sav.models import ContratMaintenance
        qs = ContratMaintenance.objects.filter(
            company=company, actif=True
        ).select_related('client', 'installation')
        count = 0
        for contrat in qs:
            try:
                if not contrat.is_due():
                    continue
                client_nom = (
                    getattr(contrat.client, 'nom', '')
                    or str(contrat.client_id)
                )
                title = 'Visite de maintenance due'
                body = (
                    f"Le contrat de maintenance pour « {client_nom} » "
                    f"(périodicité : {contrat.get_periodicite_display()}) "
                    f"a une visite due aujourd'hui."
                )
                link = f'/sav/maintenances/{contrat.pk}'
                owner = getattr(
                    getattr(contrat, 'installation', None),
                    'technicien_responsable', None)
                if owner is not None:
                    notify(owner, EventType.MAINTENANCE_DUE, title,
                           body=body, link=link, company=company)
                else:
                    for mgr in _managers(company):
                        notify(mgr, EventType.MAINTENANCE_DUE, title,
                               body=body, link=link, company=company)
                count += 1
            except Exception:  # pragma: no cover
                logger.warning('sweeps: maintenance contrat %s échoué',
                               contrat.pk, exc_info=True)
        return count
    except Exception:  # pragma: no cover
        logger.warning('sweeps: maintenance_due société %s échouée',
                       getattr(company, 'pk', None), exc_info=True)
        return 0


# ── SAV_TICKET_BREACHING sweep ────────────────────────────────────────────────

def _sweep_sav_breaching(company):
    """Tickets ouverts depuis ≥ BREACH_OPEN_DAYS jours sans résolution.

    Notifie le technicien responsable ou les managers si absent."""
    try:
        from apps.sav.models import Ticket
        today = date.today()
        breach_date = today - timedelta(days=BREACH_OPEN_DAYS)
        qs = Ticket.objects.filter(
            company=company,
            statut__in=Ticket.OPEN_STATUTS,
            annule=False,
            date_ouverture__isnull=False,
            date_ouverture__lte=breach_date,
        ).select_related('technicien_responsable', 'client')
        count = 0
        for ticket in qs:
            try:
                user = ticket.technicien_responsable
                anciennete = (today - ticket.date_ouverture).days
                client_nom = (
                    getattr(ticket.client, 'nom', '')
                    or str(ticket.client_id)
                )
                title = 'Ticket SAV proche de son délai'
                body = (
                    f"Le ticket SAV « {ticket.reference} » "
                    f"({client_nom}) est ouvert depuis {anciennete} jours "
                    f"sans résolution "
                    f"(priorité : {ticket.get_priorite_display()})."
                )
                link = f'/sav/tickets/{ticket.pk}'
                _notify_user_or_managers(
                    user, company, EventType.SAV_TICKET_BREACHING,
                    title, body, link)
                count += 1
            except Exception:  # pragma: no cover
                logger.warning('sweeps: breach ticket %s échoué', ticket.pk,
                               exc_info=True)
        return count
    except Exception:  # pragma: no cover
        logger.warning('sweeps: sav_breaching société %s échouée',
                       getattr(company, 'pk', None), exc_info=True)
        return 0


# ── CHANTIER_DUE sweep ───────────────────────────────────────────────────────

def _sweep_chantier_due(company):
    """Chantiers dont date_pose_prevue arrive dans CHANTIER_DUE_DAYS jours
    et dont le statut est encore en préparation (signé / matériel / à planifier).

    Notifie les managers (l'Installation n'a pas d'owner FK dédié)."""
    try:
        from apps.installations.models import Installation
        today = date.today()
        horizon = today + timedelta(days=CHANTIER_DUE_DAYS)
        statuts_planif = [
            Installation.Statut.SIGNE,
            Installation.Statut.MATERIEL_COMMANDE,
            Installation.Statut.A_PLANIFIER,
        ]
        qs = Installation.objects.filter(
            company=company,
            statut__in=statuts_planif,
            date_pose_prevue__isnull=False,
            date_pose_prevue__gte=today,
            date_pose_prevue__lte=horizon,
        ).select_related('client')
        count = 0
        for chantier in qs:
            try:
                client_nom = (
                    getattr(chantier.client, 'nom', '')
                    or str(chantier.client_id)
                )
                delta = (chantier.date_pose_prevue - today).days
                title = 'Chantier à installer bientôt'
                body = (
                    f"Le chantier « {chantier.reference} » "
                    f"(client : {client_nom}) est prévu dans {delta} jours "
                    f"({chantier.date_pose_prevue}). "
                    f"Statut : {chantier.get_statut_display()}."
                )
                link = f'/installations/{chantier.pk}'
                for mgr in _managers(company):
                    notify(mgr, EventType.CHANTIER_DUE, title,
                           body=body, link=link, company=company)
                count += 1
            except Exception:  # pragma: no cover
                logger.warning('sweeps: chantier_due %s échoué',
                               chantier.pk, exc_info=True)
        return count
    except Exception:  # pragma: no cover
        logger.warning('sweeps: chantier_due société %s échouée',
                       getattr(company, 'pk', None), exc_info=True)
        return 0


# ── FACTURE_OVERDUE sweep (YEVNT3) ────────────────────────────────────────────

def _already_notified_today(company, event_type, link):
    """True si une notification `event_type` avec ce `link` a déjà été émise
    AUJOURD'HUI pour cette société — idempotence stricte (une notif/jour),
    plus stricte que les autres sweeps de ce fichier (qui tolèrent une
    ré-émission par exécution)."""
    try:
        from .models import Notification
        today = date.today()
        return Notification.objects.filter(
            company=company, event_type=event_type, link=link,
            created_at__date=today,
        ).exists()
    except Exception:  # pragma: no cover - défensif
        return False


def _sweep_facture_overdue(company):
    """Factures en retard (échéance dépassée, non payées) → notifie
    l'auteur (`created_by`) de la facture, sinon les managers.

    Idempotence stricte : une notification par facture par jour (vérifiée via
    `_already_notified_today` sur le lien de la facture) — contrairement aux
    autres sweeps de ce fichier, une facture en retard ne doit pas spammer à
    chaque exécution du sweep si celui-ci tourne plusieurs fois par jour."""
    try:
        from apps.ventes.selectors import factures_echues
        today = date.today()
        qs = factures_echues(company, today=today)
        count = 0
        for facture in qs:
            try:
                link = f'/ventes/factures/{facture.pk}'
                if _already_notified_today(
                        company, EventType.FACTURE_OVERDUE, link):
                    continue
                client_nom = (
                    getattr(facture.client, 'nom', '')
                    or str(facture.client_id)
                )
                delta = (today - facture.date_echeance).days
                title = 'Facture en retard'
                body = (
                    f"La facture « {facture.reference} » "
                    f"(client : {client_nom}) est en retard de {delta} "
                    f"jour(s) (échéance : {facture.date_echeance})."
                )
                _notify_user_or_managers(
                    facture.created_by, company, EventType.FACTURE_OVERDUE,
                    title, body, link)
                count += 1
            except Exception:  # pragma: no cover
                logger.warning('sweeps: facture_overdue %s échouée',
                               facture.pk, exc_info=True)
        return count
    except Exception:  # pragma: no cover
        logger.warning('sweeps: facture_overdue société %s échouée',
                       getattr(company, 'pk', None), exc_info=True)
        return 0


# ── DA_SOUMISE_STALE sweep (VX213) ────────────────────────────────────────────

def _sweep_da_soumise_stale(company):
    """VX213 (d) — réquisitions d'achat (``installations.DemandeAchat``) restées
    SOUMISE au-delà de ``DA_STALE_DAYS`` sans décision → relance les
    approbateurs (managers de la société).

    Miroir de ``_sweep_sav_breaching`` : cross-app lecture seule via le
    sélecteur ``installations.selectors.demandes_achat_soumises_stale`` (jamais
    un import du modèle installations). Idempotence stricte : une relance par DA
    par jour (dédup par ``link`` via ``_already_notified_today``)."""
    try:
        from django.utils import timezone as tz
        from apps.installations.selectors import demandes_achat_soumises_stale
    except Exception:  # pragma: no cover — installations indisponible
        return 0
    try:
        cutoff = tz.now() - timedelta(days=DA_STALE_DAYS)
        qs = demandes_achat_soumises_stale(company, cutoff)
        today = date.today()
        count = 0
        for da in qs:
            try:
                link = f'/installations/demandes-achat?demande={da.pk}'
                if _already_notified_today(
                        company, EventType.DA_SOUMISE_STALE, link):
                    continue
                # Ancienneté depuis la dernière touche (soumission).
                dm = da.date_modification
                if dm is not None:
                    anciennete = (today - tz.localdate(dm)).days
                else:  # pragma: no cover - défensif
                    anciennete = DA_STALE_DAYS
                title = "Demande d'achat en attente d'approbation"
                body = (
                    f"La demande d'achat « {da.reference} » ({da.objet}) est "
                    f"soumise depuis {anciennete} jour(s) sans décision."
                )
                for mgr in _managers(company):
                    notify(mgr, EventType.DA_SOUMISE_STALE, title,
                           body=body, link=link, company=company)
                count += 1
            except Exception:  # pragma: no cover
                logger.warning('sweeps: da_soumise_stale %s échouée',
                               da.pk, exc_info=True)
        return count
    except Exception:  # pragma: no cover
        logger.warning('sweeps: da_soumise_stale société %s échouée',
                       getattr(company, 'pk', None), exc_info=True)
        return 0


# ── SAV_ACTIVITE_DUE sweep (VX209(d) — ZSAV3 déclarée, jamais émise) ─────────

def _sweep_sav_activite_due(company):
    """Activités planifiées (``sav.TicketActiviteAFaire``) dont l'échéance est
    atteinte ou dépassée et qui ne sont pas encore ``fait`` → notifie l'
    utilisateur ``assigne``, sinon les managers de la société (même politique
    « owner d'abord » que les autres sweeps de ce fichier)."""
    try:
        from apps.sav.models import TicketActiviteAFaire
        today = date.today()
        qs = TicketActiviteAFaire.objects.filter(
            company=company, fait=False, echeance__lte=today,
        ).select_related('ticket', 'assigne')
        count = 0
        for taf in qs:
            try:
                ticket_ref = getattr(taf.ticket, 'reference', '') or str(
                    taf.ticket_id)
                title = 'Activité SAV à échéance'
                body = (
                    f"{taf.get_type_display()} « {taf.titre} » sur le ticket "
                    f"« {ticket_ref} » était due le {taf.echeance}."
                )
                link = f'/sav/tickets/{taf.ticket_id}'
                _notify_user_or_managers(
                    taf.assigne, company, EventType.SAV_ACTIVITE_DUE,
                    title, body, link)
                count += 1
            except Exception:  # pragma: no cover
                logger.warning('sweeps: sav_activite_due %s échouée',
                               taf.pk, exc_info=True)
        return count
    except Exception:  # pragma: no cover
        logger.warning('sweeps: sav_activite_due société %s échouée',
                       getattr(company, 'pk', None), exc_info=True)
        return 0


# ── STOCK_EXPIRATION_SOON sweep (VX209(d) — ZSTK2 déclarée, jamais émise) ────

def _sweep_stock_expiration_soon(company):
    """Lots en entrepôt (``stock.LotEntrepot``) avec un reliquat non nul dont
    la péremption arrive dans ``STOCK_EXPIRATION_HORIZON_DAYS`` jours → notifie
    les managers (un lot n'a pas d'owner dédié, même politique que
    ``STOCK_LOW``)."""
    try:
        from apps.stock.models import LotEntrepot
        today = date.today()
        horizon = today + timedelta(days=STOCK_EXPIRATION_HORIZON_DAYS)
        qs = LotEntrepot.objects.filter(
            company=company,
            quantite_restante__gt=0,
            date_peremption__isnull=False,
            date_peremption__gte=today,
            date_peremption__lte=horizon,
        ).select_related('produit')
        count = 0
        for lot in qs:
            try:
                produit_nom = getattr(lot.produit, 'nom', '') or str(
                    lot.produit_id)
                delta = (lot.date_peremption - today).days
                title = 'Lot bientôt périmé'
                body = (
                    f"Le lot « {lot.numero_lot} » de « {produit_nom} » "
                    f"({lot.quantite_restante} restant(s)) expire dans "
                    f"{delta} jours ({lot.date_peremption})."
                )
                for mgr in _managers(company):
                    notify(mgr, EventType.STOCK_EXPIRATION_SOON, title,
                           body=body, link='/stock', company=company)
                count += 1
            except Exception:  # pragma: no cover
                logger.warning('sweeps: stock_expiration_soon lot %s échoué',
                               lot.pk, exc_info=True)
        return count
    except Exception:  # pragma: no cover
        logger.warning('sweeps: stock_expiration_soon société %s échouée',
                       getattr(company, 'pk', None), exc_info=True)
        return 0


# ── Purge périodique (VX209(c)) ──────────────────────────────────────────────

def _sweep_purge_notifications(company):
    """Table ``Notification`` bornée dans le temps par société : les LUES de
    plus de ``NOTIFICATION_RETENTION_DAYS`` jours sont supprimées (historique
    non requis une fois traitées) ; les NON-LUES du même âge sont ARCHIVÉES
    (jamais supprimées — ``archived=True`` les retire de ``list()`` sans
    perdre la trace). Renvoie le nombre de lignes affectées (supprimées +
    archivées)."""
    try:
        from django.utils import timezone as tz
        from .models import Notification
        cutoff = tz.now() - timedelta(days=NOTIFICATION_RETENTION_DAYS)
        deleted, _ = Notification.objects.filter(
            company=company, read=True, created_at__lt=cutoff,
        ).delete()
        archived = Notification.objects.filter(
            company=company, read=False, archived=False,
            created_at__lt=cutoff,
        ).update(archived=True)
        return deleted + archived
    except Exception:  # pragma: no cover
        logger.warning('sweeps: purge_notifications société %s échouée',
                       getattr(company, 'pk', None), exc_info=True)
        return 0


@shared_task(name='notifications.purge_notifications_anciennes')
def purge_notifications_anciennes():
    """VX209(c) — tâche Celery périodique : purge la table ``Notification``
    par société (lues > 60 j supprimées, non-lues > 60 j archivées). Idempotent
    et best-effort par société."""
    total = 0
    for company in _companies():
        try:
            total += _sweep_purge_notifications(company)
        except Exception:  # pragma: no cover
            logger.warning('sweeps: purge_notifications_anciennes société %s échouée',
                           getattr(company, 'pk', None), exc_info=True)
    logger.info('purge_notifications_anciennes: %s ligne(s) affectée(s)', total)
    return total


# ── Annonce sweep (XKB5) ──────────────────────────────────────────────────────

def _sweep_annonces_due(company):
    """Publie les annonces programmées dont l'heure est atteinte (XKB5).

    Idempotent : `publish_annonce` no-op si déjà publiée ; `Annonce.is_due`
    exclut déjà les annonces publiées/non-programmées."""
    try:
        from django.utils import timezone
        from .models import Annonce
        from .services import publish_annonce
        now = timezone.now()
        qs = Annonce.objects.filter(
            company=company, publiee=False,
            date_publication__isnull=False, date_publication__lte=now)
        count = 0
        for annonce in qs:
            try:
                publish_annonce(annonce, now=now)
                count += 1
            except Exception:  # pragma: no cover
                logger.warning('sweeps: annonce %s échouée', annonce.pk,
                               exc_info=True)
        return count
    except Exception:  # pragma: no cover
        logger.warning('sweeps: annonces_due société %s échouée',
                       getattr(company, 'pk', None), exc_info=True)
        return 0


# ── Relance de lecture obligatoire (XKB6) ──────────────────────────────────────

def _sweep_annonce_reminders(company):
    """Relance les non-lecteurs d'annonces à lecture obligatoire (XKB6)."""
    try:
        from .services import sweep_annonce_reminders
        return sweep_annonce_reminders(company)
    except Exception:  # pragma: no cover
        logger.warning('sweeps: annonce_reminders société %s échouée',
                       getattr(company, 'pk', None), exc_info=True)
        return 0


# ── Relance/escalade des approbations en attente (YEVNT9) ──────────────────────

def _sweep_approval_reminders(company):
    """Relance/escalade les approbations en attente au-delà des seuils
    (YEVNT9), pour les deux moteurs (automation + compta)."""
    try:
        from .services import sweep_approval_reminders
        return sweep_approval_reminders(company)
    except Exception:  # pragma: no cover
        logger.warning('sweeps: approval_reminders société %s échouée',
                       getattr(company, 'pk', None), exc_info=True)
        return 0


# ── QX31be — escalade speed-to-lead des leads chauds non contactés ───────────
# Seuils défensifs (surchargables via settings).
HOT_LEAD_SCORE_THRESHOLD = 70   # score ≥ ce seuil = lead « chaud »
HOT_LEAD_UNREAD_MINUTES = 30    # notif d'arrivée non lue depuis ≥ N minutes


def _lead_id_from_link(link):
    """Extrait ``lead`` d'un deep-link « /crm/leads?lead=42 » (ou None)."""
    if not link:
        return None
    import re
    m = re.search(r'[?&]lead=(\d+)', link)
    return int(m.group(1)) if m else None


def _sweep_hot_leads(company):
    """QX31be — escalade les leads CHAUDS dont la notif d'arrivée
    (``LEAD_NEW``/``LEAD_ASSIGNED``) reste NON LUE au-delà du seuil minutes.

    In-lane : lit les ``Notification`` (cette app) ; le score du lead est lu via
    le sélecteur crm ``get_company_lead`` (jamais un import de modèle crm).
    Idempotent : une escalade par notif d'origine (déduplication par link).
    Best-effort par société."""
    from django.conf import settings
    from django.utils import timezone as tz
    from .models import Notification

    score_min = getattr(
        settings, 'HOT_LEAD_SCORE_THRESHOLD', HOT_LEAD_SCORE_THRESHOLD)
    minutes = getattr(
        settings, 'HOT_LEAD_UNREAD_MINUTES', HOT_LEAD_UNREAD_MINUTES)
    cutoff = tz.now() - timedelta(minutes=minutes)
    posted = 0
    try:
        from apps.crm.selectors import get_company_lead
    except Exception:  # pragma: no cover — crm indisponible
        return 0

    unread = Notification.objects.filter(
        company=company, read=False,
        event_type__in=[EventType.LEAD_NEW, EventType.LEAD_ASSIGNED],
        created_at__lte=cutoff,
    ).select_related('recipient')[:500]

    for notif in unread:
        lead_id = _lead_id_from_link(notif.link)
        if not lead_id:
            continue
        lead = get_company_lead(company, lead_id)
        score = getattr(lead, 'score', None) if lead is not None else None
        if score is None or score < score_min:
            continue
        esc_link = notif.link or f'/crm/leads?lead={lead_id}'
        # Idempotence : une escalade par lead (dédup par link du jour).
        if _already_notified_today(
                company, EventType.HOT_LEAD_UNREAD, esc_link):
            continue
        title = 'Lead chaud non contacté'
        body = (f'Un lead à fort potentiel (score {score}) attend un premier '
                f'contact depuis plus de {minutes} min. Contactez-le vite '
                '(21× de chances de qualifier si < 5 min).')
        # Escalade aux managers EN PLUS du destinataire initial.
        for mgr in _managers(company):
            notify(mgr, EventType.HOT_LEAD_UNREAD, title, body,
                   link=esc_link, company=company)
            posted += 1
        if notif.recipient_id:
            notify(notif.recipient, EventType.HOT_LEAD_UNREAD, title, body,
                   link=esc_link, company=company)
            posted += 1
    return posted


# ── VX210 — réveil actif des items snoozés (activités VX85 + approbations
# VX210(b)), déclenché par l'échéance OU par un événement métier (VX210(c)).

def _sweep_reveiller_snoozes_activites(company):
    """VX210(a)/(c) — réveille les `records.Activity` snoozées de `company`.

    `records` est une app de FONDATION : ce sweep VIT côté `notifications`
    (satellite) et appelle `records.services.reveiller_snoozes` — jamais
    l'inverse (records n'importe jamais `apps.notifications` pour SA propre
    tâche planifiée)."""
    try:
        from apps.records import services as records_services
        return records_services.reveiller_snoozes(company)
    except Exception:  # pragma: no cover - défensif
        logger.warning('sweeps: reveiller_snoozes (activités) société %s échouée',
                       getattr(company, 'pk', None), exc_info=True)
        return 0


def _sweep_reveiller_snoozes_approbations(company):
    """VX210(b) — réveille les `SnoozedItem` (approbations snoozées depuis
    « Ma file ») échus : supprime la ligne (redevient visible immédiatement)
    et notifie légèrement le propriétaire. Idempotent (une ligne supprimée ne
    peut plus matcher au prochain passage)."""
    try:
        from django.utils import timezone

        from .models import SnoozedItem
        today = timezone.now().date()
        rows = list(SnoozedItem.objects.filter(
            company=company, snoozed_until__lte=today).select_related('user'))
        for item in rows:
            try:
                notify(
                    item.user, EventType.SNOOZE_REVEIL,
                    '⏰ De retour : approbation en attente',
                    link='/approbations', company=company)
            except Exception:  # pragma: no cover - défensif
                pass
        if rows:
            SnoozedItem.objects.filter(id__in=[r.id for r in rows]).delete()
        return len(rows)
    except Exception:  # pragma: no cover - défensif
        logger.warning('sweeps: reveiller_snoozes (approbations) société %s échouée',
                       getattr(company, 'pk', None), exc_info=True)
        return 0


@shared_task(name='notifications.reveiller_snoozes')
def reveiller_snoozes():
    """VX210 — sweep dédié (cadence propre, comme `sweep_hot_leads`) : réveille
    les items snoozés (activités VX85/VX210(c) + approbations VX210(b)) de
    TOUTES les sociétés, échéance ou déclencheur métier. Best-effort par
    société ; renvoie le nombre total d'items réveillés."""
    total = 0
    for company in _companies():
        try:
            total += _sweep_reveiller_snoozes_activites(company)
            total += _sweep_reveiller_snoozes_approbations(company)
        except Exception:  # pragma: no cover
            logger.warning('sweeps: reveiller_snoozes société %s échouée',
                           getattr(company, 'pk', None), exc_info=True)
    logger.info('reveiller_snoozes: %s item(s) réveillé(s)', total)
    return total


@shared_task(name='notifications.sweep_hot_leads')
def sweep_hot_leads():
    """QX31be — balayage rapide (cadence minutes) : escalade les leads chauds
    dont la notif d'arrivée reste non lue. Best-effort par société."""
    total = 0
    for company in _companies():
        try:
            total += _sweep_hot_leads(company)
        except Exception:  # pragma: no cover
            logger.warning('sweeps: hot_leads société %s échouée',
                           getattr(company, 'pk', None), exc_info=True)
    logger.info('sweep_hot_leads: %s escalade(s)', total)
    return total


# ── Tâche Celery Beat ─────────────────────────────────────────────────────────

@shared_task(name='notifications.sweep_daily')
def sweep_daily():
    """Balayage quotidien des EventTypes « morts » (FG1).

    Pour chaque société active : garanties expirantes, maintenances dues,
    tickets SAV en rupture de délai, chantiers à venir, factures en retard
    (YEVNT3), annonces programmées à publier (XKB5), relances de lecture
    obligatoire en retard (XKB6), relances/escalades d'approbations en
    attente (YEVNT9), demandes d'achat soumises non décidées (VX213),
    activités SAV à échéance et lots bientôt périmés (VX209(d)).
    Best-effort par société ; renvoie le total de notifications émises."""
    total = 0
    for company in _companies():
        try:
            total += _sweep_warranty_expiring(company)
            total += _sweep_maintenance_due(company)
            total += _sweep_sav_breaching(company)
            total += _sweep_chantier_due(company)
            total += _sweep_facture_overdue(company)
            total += _sweep_annonces_due(company)
            total += _sweep_annonce_reminders(company)
            total += _sweep_approval_reminders(company)
            total += _sweep_da_soumise_stale(company)
            total += _sweep_sav_activite_due(company)
            total += _sweep_stock_expiration_soon(company)
        except Exception:  # pragma: no cover
            logger.warning('sweeps: société %s échouée globalement',
                           getattr(company, 'pk', None), exc_info=True)
    logger.info('sweep_daily: %s notification(s) émise(s)', total)
    return total
