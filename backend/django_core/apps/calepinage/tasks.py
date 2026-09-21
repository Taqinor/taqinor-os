"""CAL23 — le calcul LOURD en tâche de fond, suivi par ``BackgroundJob``.

AUCUNE file maison : le dispatch passe par ``core.jobs.submit(kind, task,
company=…, user=…)`` — la primitive plateforme (NTPLT29), partagée par tous
les kinds du dépôt. Elle crée le ``BackgroundJob`` (société et
utilisateur FORCÉS côté serveur) et transmet ``job_id`` à la tâche ; la tâche
est responsable de la progression et de l'issue.

UN SEUL KIND, ``calepinage``. Une soumission de PLUSIEURS documents passe par
ce MÊME kind (jamais une seconde file, jamais un second kind) : chaque élément
réussit ou échoue SÉPARÉMENT et NOMMÉMENT, et le job ne ment pas sur
l'ensemble — un lot à moitié réussi se lit comme tel.

LA TÂCHE PREND DES DONNÉES, JAMAIS DES INSTANCES de modèle : une instance
sérialisée puis rejouée après un retry est un risque de correction ET
d'idempotence (garde ``scripts/check_celery_tasks.py``).

IDEMPOTENCE : le résultat est rangé sous une clé DÉRIVÉE de l'empreinte de
l'entrée et de la version du moteur. Rejouer la tâche sur la même entrée écrit
donc la MÊME clé — un seul résultat, jamais deux.
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)

__all__ = ['KIND_CALEPINAGE', 'NATURE_SIMULATION', 'calculer_calepinage',
           'cle_resultat', 'cle_job', 'resultat_du_job',
           'simuler_calepinage']

#: Type logique du job de fond (``BackgroundJob.kind``) — UN SEUL pour tout le
#: module, y compris les soumissions multiples.
KIND_CALEPINAGE = 'calepinage'

#: Durée de conservation d'un résultat en cache (secondes).
DUREE_CACHE_S = 24 * 3600

#: CALX5 / D-CALX 12 — LA SIMULATION EMPRUNTE LE KIND EXISTANT et se
#: discrimine par cette ``nature`` dans la charge utile de ``core.jobs.submit``.
#: Un second kind rendrait ``GET moteur/resultat/<job_id>/`` 404, puisque cette
#: vue filtre sur ``kind=KIND_CALEPINAGE`` (``views/moteur.py``).
NATURE_SIMULATION = 'simulation'


def cle_resultat(hash_entree, version_moteur):
    """La clé de cache d'UN résultat — la version du moteur est DEDANS.

    L'invalidation au bump de version est donc structurelle : les résultats de
    l'ancien moteur deviennent inatteignables, sans purge à ne pas oublier.
    """
    return 'calepinage:resultat:%s:%s' % (hash_entree, version_moteur or '?')


def cle_job(job_id):
    """La clé de cache de la charge utile d'un job (un ou plusieurs calculs)."""
    return 'calepinage:job:%s' % job_id


def resultat_du_job(job):
    """La charge utile d'un job TERMINÉ, ou ``None`` (best-effort).

    ``None`` veut dire « pas (encore) de résultat », jamais « résultat vide » :
    l'écran doit pouvoir distinguer les deux.
    """
    from core import cache as cache_tenant

    if job is None or not job.result_file_key:
        return None
    return cache_tenant.get(job.company_id, job.result_file_key)


@shared_task(name='calepinage.calculer')
def calculer_calepinage(job_id=None, company_id=None, entree=None,
                        entrees=None, tiroirs=True, suggestions=True):
    """Calcule un (ou plusieurs) calepinage hors requête et publie l'issue.

    Deux issues, jamais une troisième silencieuse : ``done`` avec la charge
    utile en cache, ou ``failed`` avec un motif FRANÇAIS. Un job qui reste
    « en cours » sans raison est ce qui fait perdre confiance à un écran.

    Sur une soumission MULTIPLE, chaque élément porte SA propre issue
    (``statut`` / ``motif``) : le lot est ``done`` dès qu'un élément a réussi,
    et les échecs restent lisibles un par un.
    """
    from core import cache as cache_tenant
    from core.models import BackgroundJob

    job = BackgroundJob.objects.filter(pk=job_id).first()
    if job is None:
        logger.info('calepinage.calculer : job #%s introuvable', job_id)
        return {'statut': 'inconnu'}

    documents = [d for d in (entrees or ([entree] if entree else []))
                 if isinstance(d, dict) and d]
    if not documents:
        job.marquer_echec("Aucun document de calepinage à calculer.")
        return {'statut': 'failed', 'motif': 'aucun document'}

    from .moteur_service import calepinage_json, erreurs_moteur_calepinage

    entree_invalide, incoherent = erreurs_moteur_calepinage()
    company = job.company
    elements = []
    reussites = 0
    job.marquer_progression(5)
    for index, document in enumerate(documents):
        repere = document.get('repere') or f'#{index + 1}'
        try:
            resultat = calepinage_json(document, company=company,
                                       user=job.user, tiroirs=tiroirs,
                                       suggestions=suggestions)
        except (entree_invalide, incoherent) as erreur:
            elements.append({'index': index, 'repere': repere,
                             'statut': 'failed', 'motif': str(erreur),
                             'resultat': None})
            continue
        except Exception as erreur:  # noqa: BLE001 — un élément ne casse pas le lot
            logger.exception('calepinage.calculer : élément %s en échec',
                             repere)
            elements.append({'index': index, 'repere': repere,
                             'statut': 'failed', 'motif': str(erreur),
                             'resultat': None})
            continue
        reussites += 1
        # IDEMPOTENT : même entrée ⇒ même empreinte ⇒ MÊME clé réécrite.
        cache_tenant.set(
            company.pk,
            cle_resultat(resultat.get('hash_entree'),
                         resultat.get('version_moteur')),
            resultat, timeout=DUREE_CACHE_S)
        elements.append({'index': index, 'repere': repere, 'statut': 'done',
                         'motif': '', 'resultat': resultat})
        job.marquer_progression(5 + int(90 * (index + 1) / len(documents)))

    charge = {'elements': elements,
              'resultat': elements[0]['resultat'] if len(elements) == 1
              else None}
    cache_tenant.set(company.pk, cle_job(job.pk), charge,
                     timeout=DUREE_CACHE_S)
    if not reussites:
        job.result_file_key = cle_job(job.pk)
        job.save(update_fields=['result_file_key', 'updated_at'])
        job.marquer_echec('; '.join(
            f"{e['repere']} : {e['motif']}" for e in elements) or 'échec')
        return {'statut': 'failed', 'elements': len(elements)}
    job.marquer_termine(cle_job(job.pk))
    return {'statut': 'done', 'reussites': reussites,
            'elements': len(elements)}


@shared_task(name='calepinage.simuler')
def simuler_calepinage(job_id=None, company_id=None, calepinage_id=None,
                       nature=NATURE_SIMULATION, forcer=False):
    """CALX5 — la SIMULATION hors requête, sur le kind existant (D-CALX 12).

    Deux issues, jamais une troisième silencieuse : ``done`` avec le résumé du
    calcul en cache, ou ``failed`` avec un motif FRANÇAIS qui NOMME le champ
    fautif (mode météo non saisi, aucun pan équipé, site sans épingle). Le
    calepinage est relu ICI, borné à la société du job : une instance de
    modèle ne voyage jamais dans une charge utile Celery.
    """
    from core import cache as cache_tenant
    from core.models import BackgroundJob

    from .models import Calepinage
    from .services import simulation as service_simulation
    from .services.simulation import SimulationRefusee

    job = BackgroundJob.objects.filter(pk=job_id).first()
    if job is None:
        logger.info('calepinage.simuler : job #%s introuvable', job_id)
        return {'statut': 'inconnu'}

    calepinage = (Calepinage.objects
                  .filter(pk=calepinage_id, company=job.company)
                  .first())
    if calepinage is None:
        job.marquer_echec('Calepinage introuvable : la simulation est '
                          'abandonnée.')
        return {'statut': 'failed', 'motif': 'calepinage introuvable'}

    job.marquer_progression(5)
    try:
        rendu = service_simulation.simuler_calepinage(calepinage,
                                                      forcer=bool(forcer))
    except SimulationRefusee as refus:
        job.marquer_echec('%s : %s' % (refus.champ or 'simulation',
                                       refus.motif))
        return {'statut': 'failed', 'champ': refus.champ}
    except Exception as erreur:  # noqa: BLE001 — l'issue est publiée, pas avalée
        logger.exception('calepinage.simuler : calepinage #%s en échec',
                         calepinage_id)
        job.marquer_echec(str(erreur))
        return {'statut': 'failed', 'motif': str(erreur)}

    resume = {
        'calepinage': calepinage.pk,
        'nature': nature,
        'deja_calcule': rendu['deja_calcule'],
        'hash_entree': rendu.get('hash_entree'),
        'calcule_le': rendu.get('calcule_le'),
        'duree_s': rendu.get('duree_s'),
    }
    charge = {'elements': [{'index': 0, 'repere': str(calepinage.pk),
                            'statut': 'done', 'motif': '',
                            'resultat': resume}],
              'resultat': resume}
    cache_tenant.set(job.company_id, cle_job(job.pk), charge,
                     timeout=DUREE_CACHE_S)
    job.marquer_termine(cle_job(job.pk))
    return {'statut': 'done', 'calepinage': calepinage.pk}
