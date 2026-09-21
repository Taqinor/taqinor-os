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


# ─────────────────────────────────────────────────────────────────────────
# AUD730 — quatre producteurs RH DOCUMENTÉS comme automatiques n'avaient ni
# ``@shared_task`` ni entrée ``beat_schedule`` : ils n'ont donc JAMAIS tourné,
# accessibles seulement par une exécution manuelle sur le serveur, alors que
# leurs propres docstrings disent « acquisition mensuelle automatique… Odoo
# Accrual Time Off » et « clôture automatique… Automatic check-out Odoo ».
# C'est le patron déjà tâché AUD231 (jobs orphelins).
#
# CONVENTION DE NOM : ``rh.<nom_de_commande>`` — celle qu'impose
# ``scripts/check_commandes_planifiees.py`` (une commande qui se déclare
# planifiable doit avoir une entrée beat portant ce nom exact).
#
# POLITIQUE D'APPLICATION, alignée sur la maison (GED_PURGE_AUTO_APPLY /
# BACKUP_PURGE_AUTO_APPLY / RETENTION_AUTO_APPLY) :
#   * ce qui est IDEMPOTENT et NON destructif s'applique directement
#     (acquisition de congés, clôture de pointages) ;
#   * ce qui est IRRÉVERSIBLE (anonymisation CNDP des candidatures) ou dont la
#     cadence est une DÉCISION MÉTIER (planification des appréciations) tourne
#     en DRY-RUN tant que le fondateur n'a pas posé la variable d'env dédiée —
#     le balayage SIGNALE alors ce qu'il ferait, au lieu de ne rien faire du
#     tout comme aujourd'hui.
# ─────────────────────────────────────────────────────────────────────────


@shared_task(name='rh.accruer_conges')
def accruer_conges(annee=None, mois=None):
    """AUD730 — acquisition mensuelle des congés payés, par société active.

    Crédite ``SoldeConge.acquis`` du droit du mois pour chaque employé ACTIF
    (``services.accruer_conges_mensuel``, ZRH2). Sans paramètre, cible le mois
    COURANT. IDEMPOTENT par construction : la garde ``mois_acquis`` empêche un
    second crédit pour le même mois, donc ré-exécuter la tâche ne double
    jamais un solde.
    """
    from authentication.selectors import active_companies

    from apps.rh import selectors, services

    today = timezone.localdate()
    annee = annee or today.year
    mois = mois or today.month
    credites = 0
    deja = 0
    # SCA19 — un tenant suspendu n'acquiert pas de congés.
    for company in active_companies():
        for dossier in selectors.dossiers_actifs(company):
            try:
                resultat = services.accruer_conges_mensuel(
                    dossier, annee=annee, mois=mois, apply=True)
            except Exception:  # pragma: no cover - défensif, isolation
                logger.warning(
                    'rh.accruer_conges: échec dossier #%s', dossier.pk,
                    exc_info=True)
                continue
            if resultat['deja_acquis']:
                deja += 1
            else:
                credites += 1
    logger.info(
        'rh.accruer_conges: %s/%s — %s crédité(s), %s déjà acquis',
        mois, annee, credites, deja)
    return {'annee': annee, 'mois': mois,
            'credites': credites, 'deja_acquis': deja}


@shared_task(name='rh.clore_pointages_ouverts')
def clore_pointages_ouverts():
    """AUD730 — clôture automatique des pointages restés ouverts (ZRH5).

    « Automatic check-out » Odoo : un pointage d'arrivée sans départ au-delà du
    seuil société est fermé et tracé par un ``IncidentPresence``. NO-OP tant
    qu'aucune société n'a configuré ``pointage_auto_depart_apres_h`` — le
    service porte lui-même cette garde. Non destructif (il ne touche QUE des
    pointages ``heure_depart__isnull=True``) : appliqué directement.
    """
    from authentication.selectors import active_companies

    from apps.rh import services

    total = 0
    for company in active_companies():  # SCA19
        try:
            total += len(services.clore_pointages_ouverts(
                company, apply=True))
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'rh.clore_pointages_ouverts: échec société %s', company.pk,
                exc_info=True)
    logger.info('rh.clore_pointages_ouverts: %s pointage(s) clôturé(s)', total)
    return {'clotures': total}


@shared_task(name='rh.purger_candidatures')
def purger_candidatures():
    """AUD730 — rétention CNDP des candidatures rejetées (XRH24).

    Sans exécution périodique, la rétention des CV n'était JAMAIS appliquée —
    enjeu PII, pas seulement opérationnel. DRY-RUN PAR DÉFAUT : l'anonymisation
    est IRRÉVERSIBLE (nom/e-mail/téléphone vidés, CV détruit), donc rien n'est
    modifié tant que ``settings.RH_PURGE_CANDIDATURES_AUTO_APPLY`` n'est pas
    explicitement vrai — même convention que ``GED_PURGE_AUTO_APPLY``. En
    dry-run, le balayage COMPTE et journalise ce qui serait purgé : le signal
    existe enfin, et le fondateur pose une variable d'environnement le jour où
    il veut l'exécution réelle.
    """
    from django.conf import settings

    from authentication.selectors import active_companies

    from apps.rh import services

    apply = bool(getattr(settings, 'RH_PURGE_CANDIDATURES_AUTO_APPLY', False))
    eligibles = 0
    anonymisees = 0
    for company in active_companies():  # SCA19
        try:
            resultat = services.purger_candidatures(company, apply=apply)
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'rh.purger_candidatures: échec société %s', company.pk,
                exc_info=True)
            continue
        eligibles += resultat['eligibles']
        anonymisees += resultat['anonymisees']
    logger.info(
        'rh.purger_candidatures: dry_run=%s, %s éligible(s), %s anonymisée(s)',
        not apply, eligibles, anonymisees)
    return {'dry_run': not apply, 'eligibles': eligibles,
            'anonymisees': anonymisees}


@shared_task(name='rh.planifier_appreciations')
def planifier_appreciations():
    """AUD730 — planification des appréciations dues (ZRH8).

    Crée les ``EvaluationEmploye`` « planifiées » pour chaque jalon
    d'ancienneté franchi (idempotent par marque ``[ZRH8:jalon=<n>]``).
    DRY-RUN PAR DÉFAUT : la CADENCE d'un cycle d'appréciation est une décision
    métier (le fondateur peut vouloir garder la main — c'est la question
    ouverte de la tâche, qu'on ne tranche pas seul), donc rien n'est créé tant
    que ``settings.RH_APPRECIATIONS_AUTO_APPLY`` n'est pas explicitement vrai.
    En dry-run, le balayage journalise ce qui SERAIT planifié : le signal
    manquant, sans décider à la place du fondateur.
    """
    from django.conf import settings

    from authentication.selectors import active_companies

    from apps.rh import services

    apply = bool(getattr(settings, 'RH_APPRECIATIONS_AUTO_APPLY', False))
    concernees = 0
    for company in active_companies():  # SCA19
        try:
            resultat = services.planifier_appreciations_pour_societe(
                company, apply=apply)
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'rh.planifier_appreciations: échec société %s', company.pk,
                exc_info=True)
            continue
        concernees += resultat.get('nb_a_creer', 0) or 0
    logger.info(
        'rh.planifier_appreciations: dry_run=%s, %s évaluation(s) '
        'concernée(s)', not apply, concernees)
    return {'dry_run': not apply, 'nb_a_creer': concernees}


@shared_task(name='rh.rappels_parcours_formation')
def rappels_parcours_formation():
    """NTHCM19 — relance quotidienne des parcours obligatoires non terminés.

    Fine enveloppe planifiable de ``manage.py rappels_parcours_formation`` :
    toute la logique (délai société, dédoublonnage quotidien par ``link``,
    employés sans compte) vit dans la commande, testée là-bas. Non destructif
    (elle n'écrit qu'une notification) : appliqué directement, sans dry-run.
    """
    from django.core.management import call_command

    try:
        call_command('rappels_parcours_formation', verbosity=0)
    except Exception:  # pragma: no cover - défensif
        logger.warning(
            'rh.rappels_parcours_formation: échec du balayage', exc_info=True)
        return {'ok': False}
    logger.info('rh.rappels_parcours_formation: balayage terminé')
    return {'ok': True}


@shared_task(name='rh.notifier_taches_integration_sortie')
def notifier_taches_integration_sortie():
    """NTHCM25 — rappel quotidien des tâches d'on/offboarding en retard.

    Fine enveloppe planifiable de la commande du même nom : la déduplication
    « un rappel par jour et par tâche » vit là-bas, testée là-bas. Non
    destructif (elle n'écrit qu'une notification) : appliqué directement.
    """
    from django.core.management import call_command

    try:
        call_command('notifier_taches_integration_sortie', verbosity=0)
    except Exception:  # pragma: no cover - défensif
        logger.warning(
            'rh.notifier_taches_integration_sortie: échec du balayage',
            exc_info=True)
        return {'ok': False}
    logger.info('rh.notifier_taches_integration_sortie: balayage terminé')
    return {'ok': True}
