"""AOF61 — le calepinage LOURD en tâche de fond, suivi par ``BackgroundJob``.

Aucune file maison : le dispatch passe par ``core.jobs.submit(kind, task,
company=…, user=…)``, qui crée le ``BackgroundJob`` (société et utilisateur
FORCÉS côté serveur) et transmet ``job_id`` à la tâche. La tâche est
responsable de la progression et de l'issue — c'est le contrat NTPLT29.

La tâche prend des CLÉS PRIMAIRES, jamais des instances de modèle : une
instance sérialisée puis rejouée après un retry est un risque de correction ET
d'idempotence (garde ``scripts/check_celery_tasks.py``).

Autodécouverte : ``erp_agentique.celery`` n'importe que ``<app>.tasks`` — ce
module est donc ré-exporté depuis ``apps/ao/tasks.py``.
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)

__all__ = ['calculer_calepinage']


@shared_task(name='ao.calculer_calepinage')
def calculer_calepinage(job_id=None, company_id=None, toiture_id=None,
                        params=None, entree=None, persister=False,
                        nom='', role='', user_id=None):
    """Calcule un calepinage hors requête et publie son résultat.

    Issue possible unique par exécution : ``done`` avec le résultat en cache
    (clé ``ao:calepinage:<hash>:<version>``, société scopée), ou ``failed``
    avec un motif FRANÇAIS. Aucune troisième issue silencieuse : un job qui
    reste ``running`` sans raison est ce qui fait perdre confiance à l'écran.

    IDEMPOTENTE : rejouer la tâche sur la même entrée redonne le même hash,
    donc écrit la même clé de cache, et — si ``persister`` — met à jour LA
    variante existante au lieu d'en créer une seconde.
    """
    from core.models import BackgroundJob

    from . import calepinage_io, calepinage_service
    from .models import ToitureAO, VarianteCalepinage

    job = BackgroundJob.objects.filter(pk=job_id).first()
    if job is None:
        logger.info('ao.calculer_calepinage : job #%s introuvable', job_id)
        return {'statut': 'inconnu'}

    try:
        job.marquer_progression(5)
        company = job.company
        toiture = None
        if toiture_id is not None:
            toiture = ToitureAO.objects.filter(
                pk=toiture_id, company=company).select_related(
                    'batiment', 'batiment__appel_offre').first()
            if toiture is None:
                raise calepinage_service.EntreeInvalide(
                    "Toiture introuvable dans cette société.")
            document = calepinage_io.document_entree(toiture, params=params)
        else:
            document = dict(entree or {})

        job.marquer_progression(25)
        resultat = calepinage_service.calepiner(document, company=company)
        job.marquer_progression(80)
        calepinage_service.mettre_en_cache(company.pk, resultat)

        variante_id = None
        if persister and toiture is not None:
            existante = VarianteCalepinage.objects.filter(
                company=company, toiture=toiture,
                entree_hash=resultat['hash_entree'],
                role=role or VarianteCalepinage.Role.RETENUE).first()
            variante = calepinage_service.calculer_variante(
                toiture, params=params, nom=nom,
                role=role or VarianteCalepinage.Role.RETENUE,
                variante=existante)
            variante.job = job
            variante.save(update_fields=['job', 'updated_at'])
            variante_id = variante.pk

        job.marquer_termine(calepinage_service.cle_cache(
            resultat['hash_entree']))
        return {'statut': 'done', 'hash_entree': resultat['hash_entree'],
                'modules': resultat['total_modules'],
                'variante': variante_id}
    except Exception as erreur:  # noqa: BLE001 — toute panne = échec PROPRE
        logger.exception('ao.calculer_calepinage : échec du job #%s', job_id)
        job.marquer_echec(str(erreur))
        return {'statut': 'failed', 'motif': str(erreur)}
