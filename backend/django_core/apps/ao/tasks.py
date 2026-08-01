"""Tâches à la demande du module Appels d'offres (``apps.ao``) — AOF15.

Enveloppes FINES autour de ``apps.ao.services`` : toute la logique métier reste
testable sans Celery. Les tâches prennent des CLÉS PRIMAIRES, jamais des
instances de modèle (une instance sérialisée puis rejouée après un retry est un
risque de correction ET d'idempotence).

Autodécouvert par ``erp_agentique.celery`` (``autodiscover_tasks()``).
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='ao.generer_echeancier')
def generer_echeancier(appel_offre_id):
    """AOF15 — (re)génère l'échéancier d'un AO. IDEMPOTENT.

    Rejouer la tâche sur un dossier inchangé ne crée rien ; après une
    prorogation, elle DÉCALE l'échéance existante au lieu d'en ajouter une.
    Aucun envoi réseau : la tâche calcule et écrit, rien d'autre.
    """
    from .models import AppelOffre
    from .services import generer_echeancier_ao

    appel_offre = AppelOffre.objects.filter(pk=appel_offre_id).first()
    if appel_offre is None:
        logger.info('ao.generer_echeancier : AO #%s introuvable',
                    appel_offre_id)
        return {'creees': 0, 'mises_a_jour': 0, 'inchangees': 0}
    return generer_echeancier_ao(appel_offre)


# AOF61 — le calepinage lourd vit dans son propre module (``calepinage_tasks``)
# pour ne pas grossir ce fichier partagé par trois lanes. L'autodécouverte
# Celery n'importe QUE ``<app>.tasks`` : ce ré-export est ce qui enregistre la
# tâche ``ao.calculer_calepinage`` auprès du worker.
from .calepinage_tasks import calculer_calepinage  # noqa: E402,F401
