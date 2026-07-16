"""YHIRE8 — Beats Celery quotidiens de l'app `rh` : alertes d'expiration RH
(FG175) et alerte fin de CDD (FG155).

Avant ce module, ``manage.py alertes_expiration_rh`` (FG175) n'était appelée
QUE manuellement — sans exécution planifiée, personne n'était prévenu d'une
habilitation électrique expirée ou d'un CDD à renouveler avant qu'il ne soit
trop tard. L'alerte fin de CDD n'avait même pas de commande dédiée : le
endpoint ``employes/cdd-a-echeance`` (FG155, ``views.py``) n'existait qu'en
LECTURE (l'utilisateur devait ouvrir l'écran lui-même).

Autodécouvert par ``erp_agentique.celery`` (``autodiscover_tasks()``), comme
``apps.contrats.scheduled``/``apps.ged.tasks``. Toute la logique métier
réutilise les sélecteurs existants (``selectors.echeances_rh``) ; ce module
n'est qu'une fine enveloppe planifiable + la diffusion des notifications.

Multi-tenant : boucle par société active (``authentication.Company``, jamais
une lecture de company depuis un corps de requête) ; chaque société — et
chaque échéance/contrat — est isolée : une exception sur l'un n'empêche
jamais les suivants (best-effort, journalisé).

Idempotence (« une seule fois ») : ``apps.notifications.services.notify`` ne
déduplique PAS lui-même — chaque tâche vérifie donc, avant d'émettre, qu'AUCUNE
``Notification`` du même ``event_type`` portant le même ``link`` stable n'a
déjà été créée AUJOURD'HUI (``created_at__date=today``) pour ce destinataire.
Le ``link`` encode la clé stable de l'échéance (type + id + jour d'échéance
pour ``rh.alertes_expiration``, id de contrat pour ``rh.alertes_cdd``) — deux
exécutions le même jour ne notifient donc jamais deux fois la même échéance,
mais une échéance qui progresse d'un jour à l'autre (ex. J-30 puis J-15) peut
re-notifier (comportement voulu : le rappel doit rester visible).
"""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

# Réutilisé de la commande FG175 : pas de nouveau type d'événement.
_EVENT_EXPIRATION = 'warranty_expiring'
# CDD à échéance (FG155) — même famille sémantique (« quelque chose expire »).
_EVENT_CDD = 'warranty_expiring'


def _recipients(company):
    """Responsables/RH actifs de la société (destinataires des alertes).

    Même logique que ``alertes_expiration_rh`` : palier admin/responsable, à
    défaut tous les utilisateurs actifs. Toujours borné à la société.
    """
    try:
        from authentication.models import CustomUser
        base = list(
            CustomUser.objects.filter(company=company, is_active=True))
    except Exception:  # pragma: no cover - défensif
        return []
    managers = []
    for user in base:
        try:
            if getattr(user, 'is_admin_role', False) or getattr(
                    user, 'role_tier', None) in ('admin', 'responsable'):
                managers.append(user)
        except Exception:  # pragma: no cover - défensif
            continue
    return managers or base


def _deja_notifie_aujourdhui(event_type, link, recipient_ids):
    """Vrai si TOUS les destinataires ont déjà reçu ce ``link`` aujourd'hui.

    Renvoie l'ensemble des ids de destinataires déjà notifiés (sous-ensemble
    de ``recipient_ids``) pour permettre de ne notifier QUE les manquants.
    """
    from apps.notifications.models import Notification

    today = timezone.localdate()
    try:
        return set(
            Notification.objects.filter(
                event_type=event_type, link=link,
                recipient_id__in=recipient_ids,
                created_at__date=today,
            ).values_list('recipient_id', flat=True))
    except Exception:  # pragma: no cover - défensif
        return set()


@shared_task(name='rh.alertes_expiration')
def alertes_expiration(within_days=30):
    """YHIRE8 — Notifie UNE fois par jour et par échéance les responsables/RH
    des habilitations/certifications/documents/visites/EPI qui expirent sous
    ``within_days`` jours (défaut 30), par société active.

    Réutilise ``selectors.echeances_rh`` (FG175, pur/testable) — cette tâche
    n'ajoute que la diffusion + la déduplication quotidienne par ``link``.
    """
    from authentication.selectors import active_companies

    from apps.notifications.services import notify
    from apps.rh import selectors, services
    from apps.rh.models import Habilitation

    today = timezone.localdate()
    total_echeances = 0
    total_notifs = 0

    # SCA19 — un tenant suspendu ne reçoit plus d'alertes d'échéances RH.
    for company in active_companies():
        try:
            rows = selectors.echeances_rh(
                company, within_days=within_days, today=today)
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'rh.alertes_expiration: échec sélecteur société %s',
                company.pk, exc_info=True)
            continue
        if not rows:
            continue
        total_echeances += len(rows)

        # XRH34 — chaque habilitation ACTIVE mais EXPIRÉE (échéance dépassée)
        # de la société fait naître (idempotent) un BesoinFormation de
        # re-certification SI un quiz actif couvre son type — no-op sinon
        # (``services.generer_besoin_recertification`` porte la garde).
        # Requête directe (pas via les rows agrégées de ``echeances_rh``, qui
        # n'exposent pas l'id de l'habilitation) — même fenêtre de temps.
        habilitations_expirees = Habilitation.objects.filter(
            company=company, actif=True,
            date_validite__isnull=False, date_validite__lt=today)
        for habilitation in habilitations_expirees:
            try:
                services.generer_besoin_recertification(habilitation)
            except Exception:  # pragma: no cover - défensif
                logger.warning(
                    'rh.alertes_expiration: échec re-certification '
                    'habilitation #%s', habilitation.pk, exc_info=True)

        recipients = _recipients(company)
        if not recipients:
            continue
        recipient_ids = [u.pk for u in recipients]

        for row in rows:
            link = (
                f"/rh/echeances?type={row['type']}"
                f"&employe={row['employe_id']}"
                f"&date={row['date_validite'].isoformat()}")
            deja = _deja_notifie_aujourdhui(
                _EVENT_EXPIRATION, link, recipient_ids)
            manquants = [u for u in recipients if u.pk not in deja]
            if not manquants:
                continue
            jours = row['jours_restants']
            if jours < 0:
                quand = f'expiré depuis {abs(jours)} j'
            elif jours == 0:
                quand = "expire aujourd'hui"
            else:
                quand = f'expire dans {jours} j'
            type_label = {
                'habilitation': 'Habilitation',
                'certification': 'Certification',
                'document': 'Document',
                'visite_medicale': 'Visite médicale',
                'dotation_epi': 'Dotation EPI',
                'epi_peremption': 'EPI (péremption)',
                'epi_controle': 'EPI (recontrôle)',
                'fin_essai': "Fin de période d'essai",
                'declaration_entree': "Déclaration d'entrée",
            }.get(row['type'], row['type'])
            titre = (
                f"{type_label} {row['libelle']} — {row['employe']} "
                f"({quand})")[:255]
            corps = (
                f"Échéance : {row['date_validite'].isoformat()} "
                f"({jours} jours).")
            for user in manquants:
                try:
                    notify(
                        user, _EVENT_EXPIRATION, titre, body=corps,
                        link=link, company=company)
                    total_notifs += 1
                except Exception:  # pragma: no cover - défensif
                    logger.warning(
                        'rh.alertes_expiration: notification échouée vers '
                        '%s', user, exc_info=True)

    logger.info(
        'rh.alertes_expiration: %s échéance(s) traitée(s), %s '
        'notification(s) émise(s)', total_echeances, total_notifs)
    return {'echeances': total_echeances, 'notifications': total_notifs}


@shared_task(name='rh.alertes_cdd')
def alertes_cdd(within_days=30):
    """YHIRE8 — Notifie UNE fois (par contrat et par échéance) les
    responsables/RH d'un CDD dont la fin de contrat tombe sous
    ``within_days`` jours (défaut 30, cf. l'action ``cdd-a-echeance``), par
    société active.

    Exclut les CDI/autres types de contrat, les CDD sans date de fin, ceux
    déjà expirés (fin < aujourd'hui) et ceux hors fenêtre — même filtre que
    l'action ``DossierEmployeViewSet.cdd_a_echeance``.
    """
    from datetime import timedelta

    from authentication.selectors import active_companies

    from apps.notifications.services import notify
    from .models import DossierEmploye

    today = timezone.localdate()
    limite = today + timedelta(days=within_days)
    total_contrats = 0
    total_notifs = 0

    # SCA19 — un tenant suspendu ne reçoit plus d'alertes CDD.
    for company in active_companies():
        qs = DossierEmploye.objects.filter(
            company=company,
            type_contrat=DossierEmploye.TypeContrat.CDD,
            contrat_date_fin__isnull=False,
            contrat_date_fin__gte=today,
            contrat_date_fin__lte=limite,
        ).order_by('contrat_date_fin')
        if not qs.exists():
            continue
        recipients = _recipients(company)
        if not recipients:
            continue
        recipient_ids = [u.pk for u in recipients]

        for dossier in qs:
            total_contrats += 1
            link = (
                f"/rh/employes/{dossier.pk}"
                f"?cdd_echeance={dossier.contrat_date_fin.isoformat()}")
            deja = _deja_notifie_aujourdhui(_EVENT_CDD, link, recipient_ids)
            manquants = [u for u in recipients if u.pk not in deja]
            if not manquants:
                continue
            jours = (dossier.contrat_date_fin - today).days
            titre = (
                f'CDD à échéance — {dossier.matricule} — '
                f'{dossier.nom} {dossier.prenom} (J-{jours})')[:255]
            corps = (
                f'Fin de contrat CDD le '
                f'{dossier.contrat_date_fin.isoformat()} ({jours} jours).')
            for user in manquants:
                try:
                    notify(
                        user, _EVENT_CDD, titre, body=corps, link=link,
                        company=company)
                    total_notifs += 1
                except Exception:  # pragma: no cover - défensif
                    logger.warning(
                        'rh.alertes_cdd: notification échouée vers %s',
                        user, exc_info=True)

    logger.info(
        'rh.alertes_cdd: %s contrat(s) traité(s), %s notification(s) '
        'émise(s)', total_contrats, total_notifs)
    return {'contrats': total_contrats, 'notifications': total_notifs}
