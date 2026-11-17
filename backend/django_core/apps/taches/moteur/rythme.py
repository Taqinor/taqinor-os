"""Le rythme : module PUR (reference/regles.md §6), sans Django ni base.

Chaque fonction reçoit ses données et la date du jour en argument : aucune
horloge vivante. Les énumérations viennent de `apps.taches.choix`.
"""
import math
from dataclasses import dataclass
from statistics import median

from apps.taches.choix import StatutJour, StatutTache

# --- Constantes nommées (regles.md §6) -------------------------------------
PALIER_DEFAUT = 5  # objectif de démarrage à froid
PALIER_MIN = 1
PALIER_MAX = 12
DEMI = 0.5  # « au plus proche, la demie vers le bas » (A2.3)
PLAFOND_FACTEUR = 2  # chaque jour plafonné à 2 × médiane + 1 (A2.3)
PLAFOND_DECALAGE = 1
MICRO_MAX_MIN = 10  # micro-tâche : estimation <= 10 min
MICRO_MAX_PAR_JOUR = 2  # micro-tâches comptées au plus par jour

# Hors de la première livraison (A18, critique m5) : les champs restent, le
# comportement est éteint ; un test peut l'allumer par `patch.object`.
PLAFOND_MICRO_ACTIF = False


@dataclass(frozen=True)
class JourCompte:
    """Un jour évalué (regles.md §0.1)."""
    jour: object
    statut_jour: str = StatutJour.EVALUE
    compte: int = 0
    essentiels_choisis: int = 0
    essentiels_faits: int = 0
    plan_prevues: int = 0
    plan_faites: int = 0


def arrondir(x):
    """`ceil(x - 0,5)` : au plus proche, la demie vers le bas (seul arrondi du moteur)."""
    return math.ceil(x - DEMI)


def _est_micro(tache):
    minutes = getattr(tache, 'estimation_minutes', None)
    return minutes is not None and minutes <= MICRO_MAX_MIN


def compte_du_jour(taches, activites):
    """Ce qui compte comme fait un jour local : `(compte, detail)`.

    Seules les tâches `fait` comptent (rouverte = retirée, abandonnée = 0) ;
    sous-tâche = 0 (le parent compte), routine = 0.
    """
    detail = {'etapes': 0, 'routines': 0, 'micro_non_comptees': 0, 'activites_closes': 0}
    compte = 0
    micro = 0
    for tache in taches:
        if tache.statut != StatutTache.FAIT:
            continue
        if getattr(tache, 'parent_id', None) is not None:
            detail['etapes'] += 1
        elif getattr(tache, 'routine', False):
            detail['routines'] += 1
        elif PLAFOND_MICRO_ACTIF and _est_micro(tache) and micro >= MICRO_MAX_PAR_JOUR:
            detail['micro_non_comptees'] += 1
        else:
            micro += 1 if _est_micro(tache) else 0
            compte += 1
    detail['activites_closes'] = len(list(activites))
    return compte + detail['activites_closes'], detail


def statut_jour(ouvre, conge, compte, plan, app):
    """Statut posé sur la journée de la veille (regles.md §6.2)."""
    if conge:
        return StatutJour.CONGE
    if not ouvre:
        return StatutJour.NON_OUVRE
    if compte == 0 and not plan and not app:
        return StatutJour.SANS_DONNEES
    return StatutJour.EVALUE


def journee_reussie(compte, objectif, choisis, faits):
    """Compte >= objectif ET (aucun essentiel choisi OU >= 1 fait) ; `None` sans objectif."""
    if objectif is None:
        return None
    return compte >= objectif and (choisis == 0 or faits >= 1)


def plafonner_jours(comptes):
    """Chaque jour de la fenêtre plafonné à `2 × médiane(fenêtre) + 1` (A2.3)."""
    comptes = list(comptes)
    if not comptes:
        return comptes
    plafond = PLAFOND_FACTEUR * median(comptes) + PLAFOND_DECALAGE
    return [min(c, plafond) for c in comptes]
