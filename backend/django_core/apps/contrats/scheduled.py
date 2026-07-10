"""YSUBS1/YSUBS2 — Beats quotidiens de l'app `contrats` : facturation
récurrente automatique (échéanciers contrats + maintenance SAV) et
reconduction tacite + diffusion des alertes contrat.

Autodécouvert par ``erp_agentique.celery`` (``autodiscover_tasks()``), comme
``apps.ventes.scheduled``/``apps.ged.tasks``. Toute la logique métier vit dans
``services``/``selectors`` (testable sans Celery) ; cette tâche n'est qu'une
fine enveloppe planifiable.

Avant ce module, TOUTE la facturation récurrente était MANUELLE
(``ContratMaintenanceViewSet.facturer`` / l'action ``facturer`` de
``EcheancierContratViewSet`` appelant ``services.facturer_ligne_echeance``) —
``erp_agentique/celery.py`` ``beat_schedule`` ne contenait aucun job de
facturation récurrente.

Multi-tenant : boucle par société (``authentication.Company``, jamais une
lecture de company depuis un corps de requête) ; chaque société — et chaque
échéance/contrat — est isolée : une exception sur l'un n'empêche jamais les
suivants (best-effort, journalisée).
"""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name='contrats.generer_factures_recurrentes_dues')
def generer_factures_recurrentes_dues():
    """YSUBS1 — Facture automatiquement les échéances/contrats dus du jour.

    Par société :

    (a) sélectionne les ``LigneEcheance`` des ``EcheancierContrat``
        ``facturation_active=True`` + ``statut=actif`` dont
        ``date_echeance <= today`` et ``facture_id`` NULL, et appelle
        ``services.facturer_ligne_echeance_journalisee`` (garde
        d'idempotence déjà en place : une ligne facturée porte un
        ``facture_id`` non NULL et n'est plus sélectionnée) ;
    (b) sélectionne les ``sav.ContratMaintenance`` dus
        (``sav.services.contrats_maintenance_dus_facturation``) et appelle
        ``sav.services.facturer_contrat_maintenance_beat`` ;
    (c) SCA44 — sélectionne les ``monitoring.AbonnementMonitoring`` dus
        (``compta.selectors.abonnements_monitoring_dus_facturation``) et
        appelle ``compta.services.facturer_abonnement_monitoring_beat``
        (3e flux de facturation récurrente automatique — jusqu'ici l'unique
        flux encore manuel, un clic humain par période via l'action
        ``facturer`` du ViewSet, qui reste disponible).

    Chaque exception est isolée : une ligne/contrat/abonnement en échec
    n'empêche JAMAIS les suivants (capturée, journalisée, comptée). Renvoie
    un dict de synthèse ``{'echeances_facturees', 'echeances_echecs',
    'maintenances_facturees', 'maintenances_echecs',
    'abonnements_factures', 'abonnements_echecs'}``.
    """
    from authentication.selectors import active_companies

    from . import services
    from .models import EcheancierContrat, LigneEcheance

    today = timezone.localdate()
    total = {
        'echeances_facturees': 0, 'echeances_echecs': 0,
        'maintenances_facturees': 0, 'maintenances_echecs': 0,
        'abonnements_factures': 0, 'abonnements_echecs': 0,
    }

    # SCA19 — source UNIQUE des sociétés balayables : un tenant suspendu/en
    # fermeture (actif=False via le pont SCA18) n'est plus jamais facturé.
    for company in active_companies():
        # (a) Échéancier de contrats — CONTRAT31.
        lignes_dues = (
            LigneEcheance.objects
            .filter(
                company=company,
                facture_id__isnull=True,
                date_echeance__lte=today,
                echeancier__facturation_active=True,
                echeancier__statut=EcheancierContrat.Statut.ACTIF,
            )
            .exclude(statut=LigneEcheance.Statut.ANNULEE)
            .select_related('echeancier', 'echeancier__contrat')
        )
        for ligne in lignes_dues:
            try:
                services.facturer_ligne_echeance_journalisee(ligne)
                total['echeances_facturees'] += 1
            except Exception:  # pragma: no cover - défensif, isolation
                total['echeances_echecs'] += 1
                logger.warning(
                    'contrats.generer_factures_recurrentes_dues: échec '
                    'échéance #%s (société %s)',
                    ligne.pk, company.pk, exc_info=True)

        # (b) Contrats de maintenance SAV — FG40. Frontière cross-app :
        # sélecteur + service dédiés de ``sav`` (jamais un import de ses
        # modèles ici).
        try:
            from apps.sav.services import (
                contrats_maintenance_dus_facturation,
                facturer_contrat_maintenance_beat,
            )
        except Exception:  # pragma: no cover - app sav absente
            contrats_maintenance_dus_facturation = None

        if contrats_maintenance_dus_facturation is not None:
            for contrat_maintenance in contrats_maintenance_dus_facturation(
                    company, today=today):
                try:
                    facturer_contrat_maintenance_beat(contrat_maintenance)
                    total['maintenances_facturees'] += 1
                except Exception:  # pragma: no cover - défensif, isolation
                    total['maintenances_echecs'] += 1
                    logger.warning(
                        'contrats.generer_factures_recurrentes_dues: échec '
                        'maintenance #%s (société %s)',
                        contrat_maintenance.pk, company.pk, exc_info=True)

        # (c) SCA44 — Abonnements de monitoring (revenu récurrent). Frontière
        # cross-app : sélecteur + service dédiés de ``compta`` (jamais un
        # import de ``apps.monitoring.models`` ici).
        try:
            from apps.compta.selectors import (
                abonnements_monitoring_dus_facturation,
            )
            from apps.compta.services import (
                facturer_abonnement_monitoring_beat,
            )
        except Exception:  # pragma: no cover - app compta absente
            abonnements_monitoring_dus_facturation = None

        if abonnements_monitoring_dus_facturation is not None:
            for abonnement in abonnements_monitoring_dus_facturation(
                    company, today=today):
                try:
                    facturer_abonnement_monitoring_beat(abonnement)
                    total['abonnements_factures'] += 1
                except Exception:  # pragma: no cover - défensif, isolation
                    total['abonnements_echecs'] += 1
                    logger.warning(
                        'contrats.generer_factures_recurrentes_dues: échec '
                        'abonnement monitoring #%s (société %s)',
                        abonnement.pk, company.pk, exc_info=True)

    logger.info(
        'contrats.generer_factures_recurrentes_dues: %s échéance(s) '
        'facturée(s) (%s échec(s)), %s maintenance(s) facturée(s) '
        '(%s échec(s)), %s abonnement(s) monitoring facturé(s) '
        '(%s échec(s))',
        total['echeances_facturees'], total['echeances_echecs'],
        total['maintenances_facturees'], total['maintenances_echecs'],
        total['abonnements_factures'], total['abonnements_echecs'])
    return total


@shared_task(name='contrats.reconductions_et_alertes_daily')
def reconductions_et_alertes_daily():
    """YSUBS2 — Reconduction tacite + diffusion des alertes contrat, par
    société, quotidien.

    ``contrats.services.traiter_reconductions_tacites`` (CONTRAT23, idempotent,
    rattrapage borné) et ``declencher_alertes_contrat`` /
    ``semer_alertes_echeances`` (alertes ÉCHÉANCE/préavis) existent et sont
    TESTÉS depuis longtemps mais n'étaient appelés QUE par des actions
    manuelles de ``contrats/views.py`` — SANS ce beat, un contrat tacite
    échu ne se reconduit JAMAIS tout seul et les alertes de préavis/échéance
    ne partent JAMAIS : le contrat expire silencieusement ou se reconduit
    sans que personne ne soit prévenu.

    Par société, appelle DANS L'ORDRE :

    1. ``semer_alertes_echeances`` — sème les nouvelles alertes dues
       (idempotent : pas de doublon pour un même contrat/type/date) ;
    2. ``declencher_alertes_contrat`` — diffuse les alertes ``planifiee`` dues
       (idempotent : une alerte n'est dispatchée qu'une fois) ;
    3. ``traiter_reconductions_tacites`` — reconduit les contrats en tacite
       reconduction échus (idempotent : avance ``date_fin`` au-delà
       d'aujourd'hui, un second passage le même jour ne re-sélectionne plus
       le contrat).

    Chaque société est isolée (une exception n'empêche jamais les
    suivantes). Renvoie un dict de synthèse agrégé ``{'alertes_semees',
    'alertes_envoyees', 'contrats_reconduits'}``.
    """
    from authentication.selectors import active_companies

    from . import services

    total = {
        'alertes_semees': 0, 'alertes_envoyees': 0, 'contrats_reconduits': 0,
    }

    # SCA19 — un tenant non actif n'est plus relancé/reconduit automatiquement.
    for company in active_companies():
        try:
            semis = services.semer_alertes_echeances(company)
            total['alertes_semees'] += semis['nb_creees']

            declenchement = services.declencher_alertes_contrat(company)
            total['alertes_envoyees'] += declenchement['nb_envoyees']

            reconduction = services.traiter_reconductions_tacites(company)
            total['contrats_reconduits'] += reconduction['nb_traites']
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'contrats.reconductions_et_alertes_daily: échec société %s',
                company.pk, exc_info=True)

    logger.info(
        'contrats.reconductions_et_alertes_daily: %s alerte(s) semée(s), '
        '%s alerte(s) envoyée(s), %s contrat(s) reconduit(s)',
        total['alertes_semees'], total['alertes_envoyees'],
        total['contrats_reconduits'])
    return total
