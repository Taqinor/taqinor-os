"""ACAL1987 (D-ACAL-90, renversée le 23/11/2026) — la simulation PART SEULE.

Le fondateur : « Simulation must start by itself ». Quand une pose COMPLÈTE
(toit, panneaux posés, module et onduleur désignés, mode et fenêtre météo
réglés) est enregistrée, la simulation est mise en file d'elle-même, par la
file existante : ``core.jobs.submit`` sur le kind ``calepinage``, nature
``simulation`` — la MÊME tâche que le bouton « Simuler » (``tasks.simuler_calepinage``,
sa borne de livraisons ``LIVRAISONS_MAX`` comprise). Le bouton reste : il relance
à la main.

TROIS GARDES, UN SEUL JOB
-------------------------
* **Aucun changement de conception ⇒ aucun job** : l'appelant
  (``layout.enregistrer_layout``) ne vient ici que si l'empreinte « document »
  a changé ; ici, l'empreinte d'ENTRÉE de la simulation (``hash_entree``,
  réglages et matériel compris) est comparée à celle du résultat déjà
  enregistré : égale ⇒ ``a_jour``, rien n'est lancé.
* **Pas de double** : un job déjà en file ou en cours pour la même empreinte
  (marqueur de cache posé au lancement) ⇒ ``deja_en_file`` ; un job encore EN
  ATTENTE d'une AUTRE empreinte aussi (ACAL2033 : il relit le document à son
  départ, donc simule le dernier état). Dix enregistrements en rafale, un
  seul job.
* **Pas de boucle** : écrire le résultat (``resultat``) ne passe JAMAIS par
  ``enregistrer_layout`` ; la tâche n'appelle donc jamais ce module.

POSE INCOMPLÈTE ⇒ AUCUN JOB, ET ON DIT CE QUI MANQUE
-----------------------------------------------------
``manquants`` reprend les lignes ``{champ, motif, cible}`` de
``services/manquants_simulation.py`` (mot pour mot : mode météo, pan équipé,
épingle…) et y ajoute le module ou l'onduleur non désigné. Rien n'est jamais
supposé.

Un calepinage FIGÉ (devis accepté, verrou ACON85) ne se re-simule pas ; sans
auteur (``user`` absent : commande, import système) rien n'est lancé — le job
de fond exige un utilisateur. Cette fonction ne lève jamais : une conception
enregistrée ne se perd pas parce qu'une simulation n'a pas pu partir.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = ['ETAT_A_JOUR', 'ETAT_EN_FILE', 'ETAT_IGNOREE', 'ETAT_INCOMPLETE',
           'ETAT_LANCEE', 'etat_simulation_automatique',
           'lancer_simulation_automatique', 'relancer_sur_designation', 'simulation_automatique_en_cours']

ETAT_LANCEE = 'lancee'
ETAT_A_JOUR = 'a_jour'
ETAT_EN_FILE = 'deja_en_file'
ETAT_INCOMPLETE = 'incomplete'
ETAT_IGNOREE = 'ignoree'

#: Durée de conservation du marqueur « simulation partie seule » (secondes).
DUREE_MARQUEUR_S = 24 * 3600


def _cle_marqueur(calepinage):
    return 'calepinage:simulation_auto:%s' % calepinage.pk


def _ligne_materiel(champ, motif):
    return {'champ': champ, 'motif': motif, 'cible': None}


def _manquants_du_materiel(contexte):
    """Le module ou l'onduleur non désigné : ils font partie de la pose."""
    manquants = []
    if not contexte.get('fiche_module'):
        manquants.append(_ligne_materiel(
            'materiel.module', "Aucun module n'est désigné pour cette pose : "
            'choisissez le panneau posé.'))
    if not contexte.get('fiche_onduleur'):
        manquants.append(_ligne_materiel(
            'materiel.onduleur', "Aucun onduleur n'est désigné pour cette "
            'pose : choisissez l\'onduleur.'))
    return manquants


def _job_du_marqueur(calepinage, *statuts):
    """Le job du marqueur s'il est dans l'un des ``statuts``, sinon ``None``."""
    from core import cache as cache_tenant
    from core.models import BackgroundJob

    marqueur = cache_tenant.get(calepinage.company_id,
                                _cle_marqueur(calepinage))
    job_id = marqueur.get('job_id') if isinstance(marqueur, dict) else None
    if not job_id:
        return None
    present = BackgroundJob.objects.filter(
        pk=job_id, company_id=calepinage.company_id,
        statut__in=[getattr(BackgroundJob, nom) for nom in statuts]).exists()
    return job_id if present else None


def simulation_automatique_en_cours(calepinage):
    """Le job de simulation PARTI SEUL et encore en file ou en cours pour ce
    calepinage (identifiant), ou ``None`` : de quoi dire « Simulation en
    cours… » sans clic. Lecture pure."""
    return _job_du_marqueur(calepinage, 'STATUT_QUEUED', 'STATUT_RUNNING')


def etat_simulation_automatique(calepinage, empreinte):
    """``{en_cours, job_id, manquants}`` servi par ``GET resultat/`` (clé
    ``simulation_automatique``) : l'écran dit « Simulation en cours… » sans
    clic, ou « Il manque … » quand la dernière pose enregistrée était
    incomplète. ``manquants`` n'est servi que s'il décrit ENCORE ce dossier
    (même empreinte de simulation ``empreinte``) : une saisie faite depuis
    l'efface. Lecture pure (un cache, au plus une requête) ; ne lève jamais."""
    rendu = {'en_cours': False, 'job_id': None, 'manquants': []}
    if (calepinage is None or not getattr(calepinage, 'pk', None)
            or getattr(calepinage, 'company_id', None) is None):
        return rendu
    try:
        from core import cache as cache_tenant

        job_id = simulation_automatique_en_cours(calepinage)
        marqueur = cache_tenant.get(calepinage.company_id,
                                    _cle_marqueur(calepinage))
    except Exception:  # noqa: BLE001 — une lecture d'état ne fait jamais tomber GET resultat/ (D-ENF22-BLE001)
        logger.exception('ACAL1987 : état de la simulation automatique '
                         'illisible (calepinage %s)', calepinage.pk)
        return rendu
    manquants = []
    if (isinstance(marqueur, dict) and empreinte
            and marqueur.get('etat') == ETAT_INCOMPLETE
            and marqueur.get('hash_entree') == empreinte):
        manquants = list(marqueur.get('manquants') or [])
    return dict(rendu, en_cours=job_id is not None, job_id=job_id,
                manquants=manquants)


def lancer_simulation_automatique(calepinage, *, user):
    """Met la simulation en file si la pose est complète et pas déjà simulée.

    Returns:
        ``{etat, job_id, manquants}`` — ``etat`` parmi ``lancee``, ``a_jour``,
        ``deja_en_file``, ``incomplete`` (``manquants`` dit quoi) et
        ``ignoree`` (figé, ou sans auteur). Ne lève jamais.
    """
    rendu = {'etat': ETAT_IGNOREE, 'job_id': None, 'manquants': []}
    if calepinage is None or not getattr(calepinage, 'pk', None) \
            or user is None:
        return rendu
    try:
        return _lancer(calepinage, user, rendu)
    except Exception:  # noqa: BLE001 — un enregistrement ne se perd pas pour une simulation (D-ENF22-BLE001)
        logger.exception('ACAL1987 : simulation automatique en échec '
                         '(calepinage %s)', calepinage.pk)
        return rendu


def _lancer(calepinage, user, rendu):
    from core import cache as cache_tenant
    from core.jobs import submit

    from ..tasks import (
        KIND_CALEPINAGE, NATURE_SIMULATION,
        simuler_calepinage as tache_de_simulation)
    from .manquants_simulation import manquants_de_simulation
    from .simulation import (
        CLE_SIMULATION, SimulationRefusee, construire_contexte,
        fichier_meteo_depose)
    from .verrou import est_verrouille

    if est_verrouille(calepinage):  # ACON85 — figé : jamais re-simulé
        return rendu
    try:
        contexte, meta = construire_contexte(calepinage)
        manquants = manquants_de_simulation(
            contexte, meta, fichier_depose=fichier_meteo_depose(calepinage))
        manquants += _manquants_du_materiel(contexte)
    except SimulationRefusee as refus:
        return dict(rendu, etat=ETAT_INCOMPLETE, manquants=(
            refus.manquants or [_ligne_materiel(
                refus.champ or 'simulation', refus.motif)]))
    empreinte = meta['hash_entree']
    cle = _cle_marqueur(calepinage)
    if manquants:
        # Rangés pour ``GET resultat/`` (« Il manque … »), avec l'empreinte :
        # servis seulement tant qu'ils décrivent ce dossier.
        cache_tenant.set(calepinage.company_id, cle,
                         {'hash_entree': empreinte, 'etat': ETAT_INCOMPLETE,
                          'manquants': manquants},
                         timeout=DUREE_MARQUEUR_S)
        return dict(rendu, etat=ETAT_INCOMPLETE, manquants=manquants)

    entete = ((calepinage.resultat or {}).get(CLE_SIMULATION)
              if isinstance(calepinage.resultat, dict) else None)
    if (empreinte and isinstance(entete, dict)
            and entete.get('hash_entree') == empreinte):
        return dict(rendu, etat=ETAT_A_JOUR)

    marqueur = cache_tenant.get(calepinage.company_id, cle)
    if (isinstance(marqueur, dict) and empreinte
            and marqueur.get('hash_entree') == empreinte
            and simulation_automatique_en_cours(calepinage)):
        return dict(rendu, etat=ETAT_EN_FILE, job_id=marqueur.get('job_id'))
    # ACAL2033 — un job encore EN ATTENTE (pas démarré) relira le document à
    # son départ : il simulera cet état-ci. Aucun second job ; le marqueur
    # porte la dernière empreinte. Un job EN COURS ne compte pas ici.
    en_file = _job_du_marqueur(calepinage, 'STATUT_QUEUED')
    if en_file:
        cache_tenant.set(calepinage.company_id, cle,
                         {'hash_entree': empreinte, 'job_id': en_file},
                         timeout=DUREE_MARQUEUR_S)
        return dict(rendu, etat=ETAT_EN_FILE, job_id=en_file)

    job = submit(KIND_CALEPINAGE, tache_de_simulation,
                 company=calepinage.company, user=user,
                 calepinage_id=calepinage.pk, nature=NATURE_SIMULATION,
                 forcer=False)
    cache_tenant.set(calepinage.company_id, cle,
                     {'hash_entree': empreinte, 'job_id': job.pk},
                     timeout=DUREE_MARQUEUR_S)
    return dict(rendu, etat=ETAT_LANCEE, job_id=job.pk)


#: ACAL2013 — les désignations de l'étape Électrique qui sont des ENTRÉES imposées du moteur.
DESIGNATIONS_IMPOSEES = ('module_produit', 'onduleur_produit')


def relancer_sur_designation(calepinage, avant, apres):
    """ACAL2013 (D-ACAL-97) — un module ou un onduleur désigné (ou retiré) À LA MAIN
    relance le moteur unique de son porteur : ``pose_enregistree`` part après validation
    (même chemin qu'une pose changée, file dédupliquée ADEV139) ; le moteur relit la
    désignation comme entrée IMPOSÉE (``relancer`` → ``designations_du_calepinage``) et
    range une nouvelle version avec sa phrase « pourquoi »."""
    if not any((avant or {}).get(cle) != (apres or {}).get(cle) for cle in DESIGNATIONS_IMPOSEES):
        return False
    # Un calepinage sans identité rangée (pivot en mémoire, jamais enregistré) n'a ni porteur ni
    # conception : rien à relancer.
    if not getattr(calepinage, 'pk', None) or not getattr(calepinage, 'company_id', None):
        return False
    from .layout import _emettre_pose_enregistree

    _emettre_pose_enregistree(calepinage, getattr(calepinage, 'layout_hash', '') or '')
    return True
