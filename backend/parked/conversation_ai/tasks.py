"""Tâches Celery du module « conversation_ai » (Groupe NTAI).

Autodécouverte par ``erp_agentique.celery`` (``autodiscover_tasks()``). Les
tâches reçoivent une PK (jamais une instance : elle doit survivre à la
sérialisation du broker et à un rejeu) et ne lèvent jamais — un échec est
capturé dans l'appel lui-même.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='conversation_ai.transcrire_appel')
def transcrire_appel_task(appel_id):
    """NTAI21 — Transcrit l'enregistrement d'un appel (à la demande).

    Déclenchée au TÉLÉVERSEMENT d'un enregistrement, jamais périodique : un
    appel n'existe que si quelqu'un a déposé son audio. No-op propre quand
    aucun fournisseur STT n'est configuré (l'appel reste « non transcrit »).
    """
    from .models import AppelCommercial
    from .services import transcrire_appel

    appel = AppelCommercial.objects.filter(pk=appel_id).first()
    if appel is None:
        return None
    transcrire_appel(appel)
    return appel.statut
