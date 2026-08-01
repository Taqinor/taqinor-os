"""NTAI29 — Tâche Celery mensuelle de surveillance de dérive (drift).

Autodécouverte par ``erp_agentique.celery`` (``autodiscover_tasks()``), comme
``apps.stock.tasks``/``apps.rh.tasks``. Boucle PAR société (jamais une société
lue d'une requête) ; une exception sur l'une n'arrête jamais les suivantes.

Purement OFFLINE : aucun appel LLM, aucun coût. Sans fournisseur de
distribution enregistré (``drift.register_distribution_provider``), la tâche
est un no-op propre — elle n'invente aucune donnée.
"""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name='ai_governance.surveiller_drift_mensuel')
def surveiller_drift_mensuel_task():
    """Calcule, pour chaque société et chaque scorer déclaré, le PSI du mois
    courant vis-à-vis de la baseline, et notifie au-dessus du seuil.

    Renvoie ``{company_id: {modele: psi}}`` (dict vide si aucun fournisseur
    n'est déclaré).
    """
    from authentication.models import Company

    from .drift import distribution_providers, enregistrer_snapshot

    providers = distribution_providers()
    if not providers:
        return {}

    premier_du_mois = timezone.localdate().replace(day=1)
    resultat = {}
    for company in Company.objects.all():
        par_modele = {}
        for modele, fournisseur in providers.items():
            try:
                distribution = fournisseur(company)
            except Exception:  # noqa: BLE001 — un scorer en échec n'arrête pas
                logger.warning(
                    'ai_governance.drift: distribution indisponible '
                    '(société %s, modèle %s)', company.id, modele,
                    exc_info=True)
                continue
            try:
                snapshot = enregistrer_snapshot(
                    company=company, modele=modele,
                    distribution=distribution, date=premier_du_mois)
            except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
                logger.warning(
                    'ai_governance.drift: snapshot non enregistré '
                    '(société %s, modèle %s)', company.id, modele,
                    exc_info=True)
                continue
            par_modele[modele] = snapshot.psi
        if par_modele:
            resultat[company.id] = par_modele
    return resultat
