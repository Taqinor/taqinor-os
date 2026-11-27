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

__all__ = ['KIND_CALEPINAGE', 'NATURE_BALAYAGE', 'NATURE_SIMULATION',
           'balayer_calepinage', 'calculer_calepinage', 'cle_resultat',
           'cle_job', 'relancer_moteur_calepinage', 'resultat_du_job', 'simuler_calepinage']

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

#: ACAL468 / ACAL388 — le BALAYAGE d'orientation d'un pan, même kind.
NATURE_BALAYAGE = 'balayage'


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
                        entrees=None, suggestions=True):
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
    motif_livraison = _livraison_de_trop(job)  # ACAL1622 — même borne que la simulation
    if motif_livraison:
        job.marquer_echec(motif_livraison)
        return {'statut': 'failed', 'motif': motif_livraison}
    job.marquer_progression(5)
    for index, document in enumerate(documents):
        repere = document.get('repere') or f'#{index + 1}'
        try:
            resultat = calepinage_json(document, company=company,
                                       user=job.user,
                                       suggestions=suggestions)
        except (entree_invalide, incoherent) as erreur:
            elements.append({'index': index, 'repere': repere,
                             'statut': 'failed', 'motif': str(erreur),
                             'resultat': None})
            continue
        except Exception as erreur:  # un élément ne casse pas le lot
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


#: ACAL1622 — livraisons d'un MÊME job au-delà desquelles le calcul n'est plus
#: relancé. Un processus tué par le système (mémoire : SIGKILL, aucune
#: exception Python) remet son message en file (``CELERY_TASK_ACKS_LATE`` +
#: ``CELERY_TASK_REJECT_ON_WORKER_LOST``) : sans borne, la tâche repartait
#: sans fin et l'écran restait à 5 %. Deux essais tués ⇒ la 3e livraison dit
#: l'échec.
LIVRAISONS_MAX = 2

MOTIF_INTERROMPU = (
    'le calcul a été interrompu par le serveur (mémoire) : réessayez ou '
    'réduisez la fenêtre météo')

#: T4-V1-012 — au-delà de la limite DOUCE de Celery
#: (``CELERY_TASK_SOFT_TIME_LIMIT``, 120 s, ``settings/base.py``) la tâche
#: reçoit ``SoftTimeLimitExceeded`` : publiée par ``str(erreur)``, l'écran
#: affichait « SoftTimeLimitExceeded() ». La durée suit surtout le nombre
#: d'années de la série météo demandée (``parametres.simulation.
#: fenetre_annees``, une requête PVGIS horaire par pan et par base) : c'est le
#: levier nommé, et son champ fait apparaître le lien vers les réglages.
CHAMP_TEMPS_DEPASSE = 'parametres.simulation.fenetre_annees'
MOTIF_TEMPS_DEPASSE = (
    'La simulation a dépassé le temps alloué (2 minutes) : relancez-la ; si '
    'cela se reproduit, réduisez la « Fenêtre d’années météo » dans les '
    'réglages de simulation du calepinage.')
#: T4-V1-012 — toute autre erreur inattendue : jamais le nom ni le texte brut
#: d'une exception à l'écran (ils restent dans le journal du serveur).
MOTIF_ERREUR_INATTENDUE = (
    "La simulation a échoué sur une erreur inattendue du serveur : relancez-"
    "la ; si cela se reproduit, signalez-le à l'administrateur.")


#: ACAL1629 — le balayage Optimiser : le levier d'un dépassement de temps est
#: la GRILLE (nombre d'orientations), pas la fenêtre météo de la simulation.
MOTIF_BALAYAGE_TEMPS_DEPASSE = (
    'Le balayage a dépassé le temps permis : réduisez la grille (moins '
    "d'inclinaisons ou d'orientations) puis relancez-le.")
#: ACAL1629 — table fermée champ de refus météo → phrase de métier : jamais
#: une clé de réglage ni un nom de colonne (« gh_w_m2 ») à l'écran.
MOTIF_BALAYAGE_METEO = (
    "L'optimisation demande une année type ou une série horaire : passez la "
    'fenêtre météo à un an (Réglages simulation).')
CHAMPS_METEO_BALAYAGE = ('meteo.gi_w_m2', 'parametres.simulation.mode_meteo')


def _echec_inattendu(erreur, balayage=False):
    """``(champ, motif)`` FRANÇAIS d'une exception non prévue — T4-V1-012 ;
    ``balayage`` (ACAL1629) : le dépassement de temps parle de la grille."""
    from celery.exceptions import SoftTimeLimitExceeded

    if isinstance(erreur, SoftTimeLimitExceeded):
        if balayage:
            return '', MOTIF_BALAYAGE_TEMPS_DEPASSE
        return CHAMP_TEMPS_DEPASSE, MOTIF_TEMPS_DEPASSE
    return '', MOTIF_ERREUR_INATTENDUE


#: Revue lot 6 (ACAL1963) — la base n'a pas pu compter la livraison : le
#: calcul n'est pas lancé et l'échec est DIT, jamais un job bloqué « en cours ».
MOTIF_COMPTE_INDISPONIBLE = (
    "le calcul n'a pas pu démarrer (base momentanément indisponible) : "
    'relancez-le dans un instant')

#: Le préfixe des compteurs de livraison (``core.SequenceCounter.cle``), et
#: leur durée de vie sans nouvelle livraison : au-delà, la ligne est supprimée.
PREFIXE_COMPTEUR_LIVRAISONS = 'calepinage:livraisons:'
HEURES_COMPTEUR_LIVRAISONS = 48


def _livraison_de_trop(job):
    """ACAL1622 — le MOTIF d'échec de cette livraison, ``''`` si elle peut
    calculer : au-delà de :data:`LIVRAISONS_MAX` livraisons d'un même job,
    :data:`MOTIF_INTERROMPU`. ACAL1963 — le compte est DURABLE (une ligne
    ``core.SequenceCounter`` par job, incrémentée sous verrou de ligne) : un
    cache vidé ne le remet plus à 1. Revue lot 6 — une erreur de base pendant
    le compte est un échec DIT (:data:`MOTIF_COMPTE_INDISPONIBLE`) ; et la
    table reste bornée : les compteurs de livraison de la société restés sans
    livraison depuis :data:`HEURES_COMPTEUR_LIVRAISONS` heures sont supprimés
    (seul ce préfixe : jamais une séquence de numérotation)."""
    import datetime

    from django.db import DatabaseError
    from django.utils import timezone

    from core.models import SequenceCounter

    cree = getattr(job, 'created_at', None)
    cle = '%s%s:%s' % (PREFIXE_COMPTEUR_LIVRAISONS, job.pk,
                       int(cree.timestamp()) if cree else '')
    limite = timezone.now() - datetime.timedelta(hours=HEURES_COMPTEUR_LIVRAISONS)
    try:
        rang = SequenceCounter.next(job.company, cle)
    except DatabaseError:
        logger.exception('calepinage : compte des livraisons du job #%s impossible', job.pk)
        return MOTIF_COMPTE_INDISPONIBLE
    try:
        # Revue lot 6 — le ménage a SON try : un verrou ou un interblocage entre
        # deux purges est journalisé et ne change jamais le verdict du compte.
        SequenceCounter.objects.filter(
            company_id=job.company_id, cle__startswith=PREFIXE_COMPTEUR_LIVRAISONS,
            updated_at__lt=limite).delete()
    except DatabaseError:
        logger.exception('calepinage : purge des compteurs de livraison impossible (job #%s)', job.pk)
    return MOTIF_INTERROMPU if rang > LIVRAISONS_MAX else ''


def _publier_echec(job, calepinage, champ, motif):
    """ACAL126 — l'échec d'une simulation, publié comme un succès : la charge
    ``{elements: [{index, repere, statut: 'failed', champ, motif}],
    resultat: None}`` en cache, ``job.message_erreur`` gardant son texte."""
    from core import cache as cache_tenant

    charge = {'elements': [{'index': 0, 'repere': str(calepinage.pk),
                            'statut': 'failed', 'champ': champ or '',
                            'motif': motif or '', 'resultat': None}],
              'resultat': None}
    cache_tenant.set(job.company_id, cle_job(job.pk), charge,
                     timeout=DUREE_CACHE_S)
    job.result_file_key = cle_job(job.pk)
    job.save(update_fields=['result_file_key', 'updated_at'])
    job.marquer_echec('%s : %s' % (champ, motif) if champ else (motif or ''))


@shared_task(name='calepinage.simuler')
def simuler_calepinage(job_id=None, company_id=None, calepinage_id=None,
                       nature=NATURE_SIMULATION, forcer=False,
                       variante_id=None):
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

    # ACAL112 — la variante est relue ICI, bornée au calepinage du job.
    variante = None
    if variante_id:
        variante = calepinage.variantes.filter(pk=variante_id).first()
        if variante is None:
            job.marquer_echec('Variante introuvable : la simulation est '
                              'abandonnée.')
            return {'statut': 'failed', 'motif': 'variante introuvable'}

    motif_livraison = _livraison_de_trop(job)
    if motif_livraison:
        _publier_echec(job, calepinage, '', motif_livraison)
        return {'statut': 'failed', 'motif': motif_livraison}
    job.marquer_progression(5)
    try:
        rendu = service_simulation.simuler_calepinage(
            calepinage, forcer=bool(forcer), variante=variante)
    except SimulationRefusee as refus:
        # ACAL126 — l'échec est STRUCTURÉ comme un succès : la charge du
        # cache porte ``elements[0] = {statut, champ, motif}`` que
        # ``GET moteur/resultat/<job>/`` sert, et l'écran pointe le champ.
        _publier_echec(job, calepinage, refus.champ or 'simulation',
                       refus.motif)
        return {'statut': 'failed', 'champ': refus.champ}
    except Exception as erreur:  # l'issue est publiée, pas avalée
        logger.exception('calepinage.simuler : calepinage #%s en échec',
                         calepinage_id)
        champ, motif = _echec_inattendu(erreur)  # T4-V1-012
        _publier_echec(job, calepinage, champ, motif)
        return {'statut': 'failed', 'champ': champ, 'motif': motif}

    resume = {
        'calepinage': calepinage.pk,
        'variante': variante.pk if variante is not None else None,
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


#: ACAL2019 — le moteur unique n'a rien rangé (dossier hors moteur, porteur introuvable).
MOTIF_RELANCE_REFUSEE = "Le moteur n'a pas pu recalculer cette conception : %s"


@shared_task(name='calepinage.relancer_moteur')
def relancer_moteur_calepinage(job_id=None, company_id=None, calepinage_id=None,
                               nature=NATURE_SIMULATION):
    """ACAL2019 (niveau de règles 15) — le bouton « Relancer le moteur » hors requête :
    UNE relance FORCÉE du moteur unique (``services.layout.relancer_le_moteur``), qui
    exécute la simulation de la pose (ADEV149) et écrit ``Calepinage.resultat`` ; le job
    publie la même charge que ``simuler_calepinage`` (``elements[0]`` + ``resultat``)."""
    from core import cache as cache_tenant
    from core.models import BackgroundJob

    from .models import Calepinage
    from .services.layout import relancer_le_moteur
    from .services.simulation import CLE_SIMULATION

    job = BackgroundJob.objects.filter(pk=job_id).first()
    if job is None:
        logger.info('calepinage.relancer_moteur : job #%s introuvable', job_id)
        return {'statut': 'inconnu'}
    calepinage = Calepinage.objects.filter(pk=calepinage_id, company=job.company).first()
    if calepinage is None:
        job.marquer_echec('Calepinage introuvable : la relance est abandonnée.')
        return {'statut': 'failed', 'motif': 'calepinage introuvable'}
    motif_livraison = _livraison_de_trop(job)
    if motif_livraison:
        _publier_echec(job, calepinage, '', motif_livraison)
        return {'statut': 'failed', 'motif': motif_livraison}
    job.marquer_progression(5)
    try:
        relance = relancer_le_moteur(calepinage, user=job.user)
    except Exception as erreur:  # l'issue est publiée, pas avalée
        logger.exception('calepinage.relancer_moteur : calepinage #%s en échec', calepinage_id)
        champ, motif = _echec_inattendu(erreur)
        _publier_echec(job, calepinage, champ, motif)
        return {'statut': 'failed', 'champ': champ, 'motif': motif}
    refus = getattr(relance, 'refus', None)
    if refus:
        motif = MOTIF_RELANCE_REFUSEE % (refus.get('message') or refus.get('code') or 'refus')
        _publier_echec(job, calepinage, refus.get('champ') or 'conception', motif)
        return {'statut': 'failed', 'motif': motif}
    calepinage.refresh_from_db(fields=['resultat'])
    entete = (calepinage.resultat or {}).get(CLE_SIMULATION) if isinstance(calepinage.resultat, dict) else None
    entete = entete if isinstance(entete, dict) else {}
    resume = {'calepinage': calepinage.pk, 'variante': None, 'nature': nature, 'deja_calcule': False,
              'hash_entree': entete.get('hash_entree'), 'calcule_le': entete.get('calcule_le'),
              'duree_s': entete.get('duree_s')}
    charge = {'elements': [{'index': 0, 'repere': str(calepinage.pk), 'statut': 'done', 'motif': '',
                            'resultat': resume}],
              'resultat': resume}
    cache_tenant.set(job.company_id, cle_job(job.pk), charge, timeout=DUREE_CACHE_S)
    job.marquer_termine(cle_job(job.pk))
    return {'statut': 'done', 'calepinage': calepinage.pk}


@shared_task(name='calepinage.balayer')
def balayer_calepinage(job_id=None, company_id=None, calepinage_id=None,
                       corps=None, nature=NATURE_BALAYAGE):
    """ACAL468 — le BALAYAGE d'orientation hors requête (``nature`` =
    ``balayage``, même kind que la simulation, D-CALX 12).

    Prend des DONNÉES (``corps`` = ``{pan, axes}``), jamais une instance : le
    calepinage est relu ICI, borné à la société du job. Rien n'est écrit au
    calepinage ; le résultat vit dans le cache du job (``cle_job``, 24 h).
    Un refus est publié comme celui d'une simulation (champ nommé).
    """
    from core import cache as cache_tenant
    from core.models import BackgroundJob

    from .models import Calepinage
    from .services.balayage import BalayageInvalide, balayer, balayer_objectif
    from .services.simulation import SimulationRefusee

    job = BackgroundJob.objects.filter(pk=job_id).first()
    if job is None:
        logger.info('calepinage.balayer : job #%s introuvable', job_id)
        return {'statut': 'inconnu'}

    calepinage = (Calepinage.objects
                  .filter(pk=calepinage_id, company=job.company)
                  .first())
    if calepinage is None:
        job.marquer_echec('Calepinage introuvable : le balayage est '
                          'abandonné.')
        return {'statut': 'failed', 'motif': 'calepinage introuvable'}

    motif_livraison = _livraison_de_trop(job)  # ACAL1622 — même borne que la simulation
    if motif_livraison:
        _publier_echec(job, calepinage, '', motif_livraison)
        return {'statut': 'failed', 'motif': motif_livraison}
    job.marquer_progression(5)
    try:
        # ACAL835 : un objectif de couverture cherche N sur la série stockée.
        cherche = balayer_objectif if 'objectif' in (corps or {}) else balayer
        resultat = cherche(calepinage, corps,
                           progression=job.marquer_progression)
    except BalayageInvalide as refus:
        _publier_echec(job, calepinage, refus.champ or 'balayage', str(refus))
        return {'statut': 'failed', 'champ': refus.champ}
    except SimulationRefusee as refus:
        _publier_echec(job, calepinage, refus.champ or 'simulation',
                       MOTIF_BALAYAGE_METEO
                       if refus.champ in CHAMPS_METEO_BALAYAGE
                       else refus.motif)  # ACAL1629
        return {'statut': 'failed', 'champ': refus.champ}
    except Exception as erreur:  # l'issue est publiée, pas avalée
        logger.exception('calepinage.balayer : calepinage #%s en échec',
                         calepinage_id)
        champ, motif = _echec_inattendu(erreur, balayage=True)  # T4-V1-012
        _publier_echec(job, calepinage, champ, motif)
        return {'statut': 'failed', 'champ': champ, 'motif': motif}

    charge = {'elements': [{'index': 0, 'repere': str(calepinage.pk),
                            'statut': 'done', 'motif': '',
                            'resultat': resultat}],
              'resultat': resultat}
    cache_tenant.set(job.company_id, cle_job(job.pk), charge,
                     timeout=DUREE_CACHE_S)
    job.marquer_termine(cle_job(job.pk))
    return {'statut': 'done', 'calepinage': calepinage.pk}
