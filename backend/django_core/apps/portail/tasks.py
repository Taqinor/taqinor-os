"""Tâches Celery du module Portail (``apps.portail``).

ACEL65 (C-ACEL-035) — le dépôt GED d'un document téléversé par le client
(WIR94) ne se fait plus dans la requête du client : le récepteur ``post_save``
le confie, après commit, à ``portail.deposer_document_ged``, qui relit les
octets par la clé MinIO et se relance en cas d'échec. Après la dernière
relance, la tâche échoue : le récepteur ``task_failure`` (ADCG18) la consigne
au résumé des problèmes. Idempotent : ``document_ged`` déjà posé ⇒ rien, et
``deposit_document`` est idempotent par ``source_type``/``source_id``.
"""
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded


@shared_task(name='portail.deposer_document_ged', bind=True,
             max_retries=3, default_retry_delay=60)
def deposer_document_ged(self, document_id):
    """Dépose en GED le document portail ``document_id`` ; relance ×3."""
    from .models import DocumentClientPortail
    from .receivers import _capture_depuis_minio, deposer_dans_ged

    instance = DocumentClientPortail.objects.filter(pk=document_id).first()
    if instance is None or instance.document_ged_id:
        return None
    try:
        capture = _capture_depuis_minio(instance)
        if capture is None:
            raise OSError('octets du document portail illisibles par sa clé de stockage')
        return deposer_dans_ged(instance, capture)
    except SoftTimeLimitExceeded:
        raise
    except Exception as exc:  # noqa: BLE001 — relancé puis consigné par task_failure (D-ENF22-BLE001)
        raise self.retry(exc=exc)
