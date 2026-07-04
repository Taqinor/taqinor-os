"""YSUBS1 — Beat quotidien : facturation récurrente automatique (échéanciers
contrats + maintenance SAV).

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
        ``sav.services.facturer_contrat_maintenance_beat``.

    Chaque exception est isolée : une ligne/contrat en échec n'empêche
    JAMAIS les suivants (capturée, journalisée, comptée). Renvoie un dict de
    synthèse ``{'echeances_facturees', 'echeances_echecs',
    'maintenances_facturees', 'maintenances_echecs'}``.
    """
    from authentication.models import Company

    from . import services
    from .models import EcheancierContrat, LigneEcheance

    today = timezone.localdate()
    total = {
        'echeances_facturees': 0, 'echeances_echecs': 0,
        'maintenances_facturees': 0, 'maintenances_echecs': 0,
    }

    for company in Company.objects.filter(actif=True):
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
            continue

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

    logger.info(
        'contrats.generer_factures_recurrentes_dues: %s échéance(s) '
        'facturée(s) (%s échec(s)), %s maintenance(s) facturée(s) '
        '(%s échec(s))',
        total['echeances_facturees'], total['echeances_echecs'],
        total['maintenances_facturees'], total['maintenances_echecs'])
    return total
