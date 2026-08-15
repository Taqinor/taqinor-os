"""NTAI17 — Branchement « dépôt d'une pièce GED → job de traitement IA ».

Le receiver est branché sur ``post_save`` de ``ged.Document`` par une
référence PAR CHAÎNE (``sender='ged.Document'``, résolue paresseusement par
Django) : ``ai_governance`` n'importe JAMAIS les modèles d'une autre app — les
lectures passent par ses ``selectors``/``services`` (règle de frontière du
dépôt), exactement comme une FK déclarée par chaîne.

BEST-EFFORT ABSOLU : la création du job et la mise en file Celery sont
enveloppées ; une panne côté IA ne doit JAMAIS empêcher l'enregistrement d'un
document. La mise en file passe par ``transaction.on_commit`` — le worker ne
peut donc pas lire un job que la transaction n'a pas encore validé.

KEY-GATED, éteint par défaut (``AI_DOCUMENT_JOBS_ENABLED``) : sans le flag,
``creer_document_ai_job`` renvoie None et ce module est un no-op complet.
"""
import logging

from django.db import transaction
from django.db.models.signals import post_save

logger = logging.getLogger(__name__)

#: Identifiant de branchement — garantit qu'un rechargement du module ne
#: connecte pas le receiver deux fois (double job sur un même dépôt).
DISPATCH_UID = 'ai_governance.document_ai_job'


def _enfiler(job_id):
    """Met le job en file Celery, sans jamais lever (broker injoignable…)."""
    try:
        from .tasks import traiter_document_ai_job_task

        traiter_document_ai_job_task.delay(job_id)
    except Exception:  # noqa: BLE001 - best-effort : le job reste « en attente ».
        logger.warning(
            'ai_governance: mise en file du job document %s impossible',
            job_id, exc_info=True)


def on_document_cree(sender, instance, created, **kwargs):
    """Crée un ``DocumentAiJob`` au DÉPÔT d'une pièce (jamais à une mise à jour)."""
    if not created:
        return
    try:
        from .services import creer_document_ai_job

        job = creer_document_ai_job(instance)
    except Exception:  # noqa: BLE001 - ne casse jamais l'écriture documentaire.
        logger.warning('ai_governance: job document non créé', exc_info=True)
        return
    if job is None:
        return
    transaction.on_commit(lambda: _enfiler(job.id))


def connect_receivers():
    """Branche les receivers du module (idempotent via ``dispatch_uid``)."""
    post_save.connect(
        on_document_cree, sender='ged.Document', dispatch_uid=DISPATCH_UID)
