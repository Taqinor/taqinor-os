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
                # WIR176 — `/sav/equipements/<pk>` n'existe pas côté front
                # (route réelle : `/equipements`, sans deep-link par id
                # aujourd'hui — jamais un paramètre fabriqué).
                link = '/equipements'
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
                # WIR176 — `/sav/maintenances/<pk>` n'existe pas côté front
                # (route réelle : `/sav/contrats`, sans deep-link par id
                # aujourd'hui — jamais un paramètre fabriqué).
                link = '/sav/contrats'
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
                # WIR176 — `/sav/tickets/<pk>` n'existe pas côté front ;
                # TicketsPage (`/sav`) consomme `?id=<pk>`.
                link = f'/sav?id={ticket.pk}'
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
                # WIR176 — `/installations/<pk>` n'existe pas côté front ;
                # InstallationsPage (`/chantiers`) consomme `?id=<pk>`.
                link = f'/chantiers?id={chantier.pk}'
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
                # WIR176 — `/ventes/factures/<pk>` n'existe pas côté front ;
                # FactureList consomme `?facture=<pk>`.
                link = f'/ventes/factures?facture={facture.pk}'
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
                # WIR176 — `/installations/demandes-achat` n'existe pas côté
                # front (préfixe réel : `/chantiers/…`) ; DemandesAchatList
                # ne consomme pas encore `?demande=` (aucun filtrage
                # fabriqué), mais l'écran cible est le bon.
                link = f'/chantiers/demandes-achat?demande={da.pk}'
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
                # WIR176 — `/sav/tickets/<pk>` n'existe pas côté front ;
                # TicketsPage (`/sav`) consomme `?id=<pk>`.
                link = f'/sav?id={taf.ticket_id}'
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
    (YEVNT9), pour le moteur automation (SOLMVP19 : compta est sorti)."""
    try:
        from .services import sweep_approval_reminders
        return sweep_approval_reminders(company)
    except Exception:  # pragma: no cover
        logger.warning('sweeps: approval_reminders société %s échouée',
                       getattr(company, 'pk', None), exc_info=True)
        return 0


def _sweep_workflow_step_reminders(company):
    """NTWFL5 — relance à mi-SLA des étapes BPM (core.WorkflowStepInstance),
    distinct de YEVNT9 ci-dessus (seuils en jours depuis la création)."""
    try:
        from .services import sweep_workflow_step_reminders
        return sweep_workflow_step_reminders(company)
    except Exception:  # pragma: no cover
        logger.warning(
            'sweeps: workflow_step_reminders société %s échouée',
            getattr(company, 'pk', None), exc_info=True)
        return 0


# ── QX31be / CAD132 — filet speed-to-lead des leads chauds non contactés ─────
# CAD132 (audit L3 du 21/09/2026) — le filet regardait la NOTIFICATION
# d'arrivée, pas le lead : il exigeait un score ≥ 70 qu'un lead Meta ne peut
# pas atteindre, un clic « tout marquer comme lu » l'éteignait sans qu'aucun
# appel ait été passé, et son délai se comptait en minutes de PENDULE sur un
# balayage 24 h/24 (il pouvait sonner à 3 h du matin). Il suit désormais
# EXACTEMENT les règles de l'escalade premier-contact
# (`apps/crm/management/commands/escalader_premier_contact.py`) : condition
# « `first_contacted_at` NULL », minutes OUVRÉES
# (`crm.horaires.minutes_ouvrees_entre`), toutes les sources hors miroir
# Odoo, dossiers perdus/opposés/archivés/clos écartés. Ce qui le distingue
# encore d'elle : il ne vise que les leads CHAUDS, et il remonte aux managers.
#
# Seuil de score UNIQUE : 60, le même que la file « leads chauds non
# contactés » (`apps.crm.selectors.leads_chauds_non_contactes`) — un lead est
# « chaud » partout ou nulle part. À recalibrer sur les scores réels de
# production (CADM7), jamais au jugé.
HOT_LEAD_SCORE_THRESHOLD = 60
#: Minutes OUVRÉES sans premier contact au-delà desquelles le filet escalade.
HOT_LEAD_MINUTES_OUVREES = 30
#: Plafond par passage et par société — appliqué APRÈS le tri (les plus chauds,
#: puis les plus anciens), jamais sur un ordre arbitraire de la base.
HOT_LEAD_LOT_MAX = 500
#: Titre de l'escalade — sert aussi de clé d'idempotence : ``HOT_LEAD_UNREAD``
#: est également émis par l'alerte SLA Meta de l'adsengine (PUB68) sous un
#: autre titre, qui ne doit ni éteindre ni doubler ce filet.
HOT_LEAD_TITRE = 'Lead chaud non contacté'
#: Canal de la première prise de contact du protocole : un MESSAGE (ouvert dès
#: 08:30), comme le défaut de `minutes_ouvrees_entre` — la fenêtre et le
#: décompte se lisent sur la même horloge.
_CANAL_PREMIER_CONTACT = 'whatsapp'


def _lead_id_from_link(link):
    """Extrait ``lead`` d'un deep-link « /crm/leads?lead=42 » (ou None)."""
    if not link:
        return None
    import re
    m = re.search(r'[?&]lead=(\d+)', link)
    return int(m.group(1)) if m else None


def _leads_deja_escalades(company):
    """Ids des leads dont le filet a DÉJÀ sonné (une escalade par lead, comme
    le marqueur de l'escalade premier-contact) — lus sur les notifications
    elles-mêmes, lues ou non : leur état de lecture ne décide plus de rien."""
    from .models import Notification

    liens = Notification.objects.filter(
        company=company, event_type=EventType.HOT_LEAD_UNREAD,
        title=HOT_LEAD_TITRE,
    ).values_list('link', flat=True)
    return {i for i in (_lead_id_from_link(lien) for lien in liens) if i}


def _sweep_hot_leads(company, now=None):
    """QX31be / CAD132 — escalade les leads CHAUDS jamais contactés au-delà du
    seuil de minutes OUVRÉES, aux managers ET au responsable du dossier.

    * condition : ``first_contacted_at`` NULL — le LEAD, plus la notification
      (« tout marquer comme lu » n'éteint plus rien) ;
    * toutes les sources (Meta, CTWA, site, saisie) sauf le miroir Odoo, dont
      les leads importés ne sont pas des demandes à rappeler ;
    * le balayage écarte LUI-MÊME les leads perdus, « ne plus contacter »,
      archivés et clos (clés de ``STAGES.py``) ;
    * rien ne part hors de la fenêtre ouvrée : le décompte est en minutes
      ouvrées ET l'instant du balayage doit lui-même être ouvré (un lead
      arrivé à 19 h franchit le seuil la nuit, il sonne à l'ouverture) ;
    * tri (score décroissant, puis le plus ancien) AVANT la troncature, et
      les leads déjà escaladés sortent avant elle : jamais un lot de 500
      saturé par des dossiers déjà signalés.

    Idempotent : une escalade par lead. ``now`` fixe l'horloge (tests).
    ``notifications`` est une app satellite, pas l'un des cinq domaines cœur :
    elle lit ``crm.Lead`` directement, comme ``signals.py`` (import local).
    Best-effort par société."""
    from django.conf import settings
    from django.utils import timezone as tz

    try:
        from apps.crm import horaires
        from apps.crm.models import Lead
        from apps.crm.stages import COLD, SIGNED
    except Exception:  # pragma: no cover — crm indisponible
        return 0

    maintenant = now or tz.now()
    if not horaires.est_dans_fenetre(
            maintenant, company, canal=_CANAL_PREMIER_CONTACT):
        return 0
    score_min = getattr(
        settings, 'HOT_LEAD_SCORE_THRESHOLD', HOT_LEAD_SCORE_THRESHOLD)
    minutes = getattr(
        settings, 'HOT_LEAD_MINUTES_OUVREES', HOT_LEAD_MINUTES_OUVREES)

    candidats = Lead.objects.filter(
        company=company, first_contacted_at__isnull=True,
        perdu=False, ne_plus_contacter=False, is_archived=False,
        score__gte=score_min,
        # Une minute ouvrée n'est jamais plus longue qu'une minute de pendule :
        # un lead arrivé depuis moins de `minutes` ne peut pas être en retard.
        date_creation__lte=maintenant - timedelta(minutes=minutes),
    ).exclude(
        source=Lead.Source.ODOO_IMPORT_TEST,
    ).exclude(
        stage__in=[SIGNED, COLD],
    ).exclude(
        pk__in=_leads_deja_escalades(company),
    ).select_related('owner').order_by(
        '-score', 'date_creation', 'pk')[:HOT_LEAD_LOT_MAX]

    posted = 0
    managers = None
    with horaires.cache_local():
        for lead in candidats:
            try:
                ecoulees = horaires.minutes_ouvrees_entre(
                    lead.date_creation, maintenant, company,
                    canal=_CANAL_PREMIER_CONTACT)
            except Exception:  # noqa: BLE001 — un lead en échec n'arrête rien
                logger.warning('sweeps: hot_leads calcul échoué (lead %s)',
                               lead.pk, exc_info=True)
                continue
            if ecoulees <= minutes:
                continue
            if managers is None:
                managers = _managers(company)
            destinataires = list(managers)
            owner = getattr(lead, 'owner', None)
            if owner is not None and owner.pk not in {
                    u.pk for u in destinataires}:
                destinataires.append(owner)
            body = (f'Un lead à fort potentiel (score {lead.score}) attend un '
                    f'premier contact depuis {ecoulees} minute(s) ouvrée(s) '
                    f'(seuil : {minutes}). Contactez-le vite.')
            lien = f'/crm/leads?lead={lead.pk}'
            for utilisateur in destinataires:
                notify(utilisateur, EventType.HOT_LEAD_UNREAD, HOT_LEAD_TITRE,
                       body, link=lien, company=company)
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
def sweep_hot_leads(now=None):
    """QX31be / CAD132 — balayage rapide (toutes les 15 min) : escalade les
    leads chauds jamais contactés au-delà du seuil de minutes OUVRÉES — et
    seulement pendant la fenêtre ouvrée de chaque société, même si le beat
    tourne 24 h/24. Best-effort par société."""
    total = 0
    for company in _companies():
        try:
            total += _sweep_hot_leads(company, now=now)
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
    attente (YEVNT9), relances à mi-SLA des étapes BPM (NTWFL5), demandes
    d'achat soumises non décidées (VX213), activités SAV à échéance et lots
    bientôt périmés (VX209(d)).
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
            total += _sweep_workflow_step_reminders(company)
            total += _sweep_da_soumise_stale(company)
            total += _sweep_sav_activite_due(company)
            total += _sweep_stock_expiration_soon(company)
        except Exception:  # pragma: no cover
            logger.warning('sweeps: société %s échouée globalement',
                           getattr(company, 'pk', None), exc_info=True)
    logger.info('sweep_daily: %s notification(s) émise(s)', total)
    return total
