"""Le rythme : module PUR (reference/regles.md §6), sans Django ni base.

Chaque fonction reçoit ses données et la date du jour en argument : aucune
horloge vivante. Les énumérations viennent de `apps.taches.choix`.
"""
import math
from dataclasses import dataclass, replace
from datetime import timedelta
from statistics import mean, median

from apps.taches.choix import ModeRythme, ReponseIncitation, SourceObjectif, StatutJour, StatutTache

# --- Constantes nommées (regles.md §6) -------------------------------------
PALIER_DEFAUT = 5  # objectif de démarrage à froid
PALIER_MIN = 1
PALIER_MAX = 12
DEMI = 0.5  # « au plus proche, la demie vers le bas » (A2.3)
PLAFOND_FACTEUR = 2  # chaque jour plafonné à 2 × médiane + 1 (A2.3)
PLAFOND_DECALAGE = 1
MICRO_MAX_MIN = 10  # micro-tâche : estimation <= 10 min
MICRO_MAX_PAR_JOUR = 2  # micro-tâches comptées au plus par jour

BLOC_JOURS = 10  # un bloc = 10 jours évalués au même palier
SEUIL_MONTER = 5  # jours à N ou plus : >= 5/10 -> proposer +1 (A2.2)
SEUIL_BAISSER = 3  # <= 3/10 -> proposer -1
SEUIL_BAISSER_ESSAI = 1  # bloc d'essai : seulement si 0 ou 1 jour tenu
REFUS_SAUT_MAX = 4  # blocs sautés après refus : 1, 2, puis 4
ECHEC_JOURS_PAR_ECHEC = 42  # un palier quitté sans être tenu : 42 j x echec_n
GARDE_TAILLE_RATIO = 0.7  # médiane du bloc < 70 % de la référence
GARDE_TAILLE_MIN_ESTIMEES = 10
BANDE_FACTEUR = 0.2  # b = max(1 ; 0,2 R)
BANDE_MIN = 1
OBJECTIF_INVALIDE = 'Entre 1 et 12.'
DECISION_MONTER = 'monter'
DECISION_BAISSER = 'baisser'
DECISION_TAILLE = 'taille'
CARTE_PREMIER = 'premier'
CARTE_JOURNEE_TYPE = 'journee_type'
SENS_PLUS = 'plus'
SENS_MOINS = 'moins'

# Hors de la première livraison (A18, critique m5) : les champs restent, le
# comportement est éteint ; un test peut l'allumer par `patch.object`.
PLAFOND_MICRO_ACTIF = False
GARDE_TAILLE_ACTIVE = False
MEMOIRE_ECHEC_ACTIVE = False


@dataclass(frozen=True)
class EtatRythme:
    """Valeurs de `ReglagesRythme` utiles au moteur (mêmes noms) + `objectif` en vigueur.

    Extras du moteur : `comptes_bloc` (comptes des jours du bloc en cours),
    `comptes_recents` (jours évalués, chronologiques), `taille_mediane_bloc` et
    `nb_estimees` (garde de taille, éteinte en v1).
    """
    mode: str = ModeRythme.POUSSER
    comprendre_mon_rythme: bool = True
    palier: object = None
    palier_source: str = ''
    bloc_debut: object = None
    refus_montee: int = 0
    blocs_a_sauter: int = 0
    echec_n: int = 0
    baisse_refusee: bool = False
    essai_restant: bool = False
    meilleur_tenu: object = None
    echec_niveau: object = None
    ref_taille_min: object = None
    echec_le: object = None
    tenir_fixee_le: object = None
    tenir_silence_jusquau: object = None
    tenir_reference: object = None
    pauses_sollicitations: tuple = ()
    objectif: object = None
    comptes_bloc: tuple = ()
    comptes_recents: tuple = ()
    taille_mediane_bloc: object = None
    nb_estimees: object = None


class ObjectifInvalide(ValueError):
    """Objectif dit hors 1-12 : la vue répond 400 avec `erreurs`."""

    def __init__(self):
        super().__init__(OBJECTIF_INVALIDE)
        self.erreurs = {'objectif': [OBJECTIF_INVALIDE]}


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


# --- TCH26 : « En faire plus » (POUSSER, §6.5) -----------------------------

def _palier(etat):
    return etat.palier if etat.palier is not None else PALIER_DEFAUT


def _bande(reference):
    """Zone [R - b, R + b] avec b = max(1 ; 0,2 R), à deux décimales."""
    b = max(BANDE_MIN, BANDE_FACTEUR * reference)
    return round(reference - b, 2), round(reference + b, 2)


def objectif_affiche(etat):
    """`(objectif | None, source, zone | None)` ; la zone n'existe qu'en TENIR."""
    if etat.mode == ModeRythme.LIBRE:
        return None, SourceObjectif.LIBRE, None
    if etat.mode == ModeRythme.TENIR:
        reference = etat.tenir_reference
        if reference is None:
            reference = _palier(etat)  # R provisoire = palier courant (ou 5)
        bas, haut = _bande(float(reference))
        return arrondir(float(reference)), SourceObjectif.CALCULE, (arrondir(bas), arrondir(haut))
    if etat.palier is None:
        return PALIER_DEFAUT, SourceObjectif.DEFAUT, None
    return etat.palier, etat.palier_source or SourceObjectif.CALCULE, None


def _maj(etat, **changes):
    """`replace` puis recalcul de `objectif` (en vigueur)."""
    neuf = replace(etat, **changes)
    return replace(neuf, objectif=objectif_affiche(neuf)[0])


def palier_initial(comptes10, dit):
    """Démarrage à froid : `(palier appliqué | None, journée type, carte | None)`.

    Journée type = `arrondir(min(médiane, moyenne))`, plancher 1. Rien n'est
    imposé : sans objectif dit, un type différent de 5 est PROPOSÉ (`premier`) ;
    avec un objectif dit, il est gardé et `journee_type` propose le type.
    """
    comptes = list(comptes10)
    journee_type = max(PALIER_MIN, arrondir(min(median(comptes), mean(comptes))))
    if dit is not None:
        carte = CARTE_JOURNEE_TYPE if journee_type != dit else None
        return dit, journee_type, carte
    carte = CARTE_PREMIER if journee_type != PALIER_DEFAUT else None
    return None, journee_type, carte


def _jours_tenus(etat):
    n = _palier(etat)
    return sum(1 for c in etat.comptes_bloc[-BLOC_JOURS:] if c >= n)


def _echec_bloque(etat, jour):
    """Le palier N+1 a été quitté sans être tenu depuis moins de 42 j x echec_n."""
    n = _palier(etat)
    if etat.echec_niveau != n + 1 or etat.echec_le is None:
        return False
    if (etat.meilleur_tenu or 0) >= n + 1:
        return False
    return (jour - etat.echec_le).days < ECHEC_JOURS_PAR_ECHEC * max(1, etat.echec_n)


def _taille_trop_basse(etat):
    reference, bloc = etat.ref_taille_min, etat.taille_mediane_bloc
    if reference is None or bloc is None:
        return False
    if etat.nb_estimees is not None and etat.nb_estimees < GARDE_TAILLE_MIN_ESTIMEES:
        return False
    return bloc < GARDE_TAILLE_RATIO * reference


def _verdict_monter(etat, jour):
    if _palier(etat) >= PALIER_MAX or etat.blocs_a_sauter > 0:
        return None
    if MEMOIRE_ECHEC_ACTIVE and _echec_bloque(etat, jour):
        return None
    if GARDE_TAILLE_ACTIVE and _taille_trop_basse(etat):
        return DECISION_TAILLE
    return DECISION_MONTER


def _verdict_baisser(etat, tenus):
    if _palier(etat) <= PALIER_MIN or etat.baisse_refusee:
        return None
    if etat.essai_restant and tenus > SEUIL_BAISSER_ESSAI:
        return None
    return DECISION_BAISSER


def evaluer_bloc(etat, jour):
    """Verdict d'un bloc complet : `monter` | `baisser` | `taille` | `None`.

    Jamais imposé, jamais plus d'un cran (pas de double saut, A2.2).
    """
    if len(etat.comptes_bloc) < BLOC_JOURS:
        return None
    tenus = _jours_tenus(etat)
    if tenus >= SEUIL_MONTER:
        return _verdict_monter(etat, jour)
    if tenus <= SEUIL_BAISSER:
        return _verdict_baisser(etat, tenus)
    return None


def _apres_decision(etat, jour, decision, reponse):
    """Champs changés par la réponse à la proposition du bloc."""
    n = _palier(etat)
    if decision == DECISION_MONTER and reponse == ReponseIncitation.OUI:
        return {'palier': min(PALIER_MAX, n + 1), 'palier_source': SourceObjectif.ACCEPTE,
                'essai_restant': True, 'refus_montee': 0}
    if decision == DECISION_MONTER and reponse == ReponseIncitation.PAS_MAINTENANT:
        refus = etat.refus_montee + 1
        return {'refus_montee': refus, 'blocs_a_sauter': min(REFUS_SAUT_MAX, 2 ** (refus - 1))}
    if decision == DECISION_BAISSER and reponse == ReponseIncitation.OUI:
        champs = {'palier': max(PALIER_MIN, n - 1), 'palier_source': SourceObjectif.ACCEPTE,
                  'refus_montee': 0}
        if n > (etat.meilleur_tenu or 0):
            champs.update(echec_niveau=n, echec_le=jour,
                          echec_n=etat.echec_n + 1 if etat.echec_niveau == n else 1)
        return champs
    if decision == DECISION_BAISSER and reponse == ReponseIncitation.GARDER:
        return {'baisse_refusee': True}
    return {}


def clore_bloc(etat, jour, decision, reponse):
    """Clôture d'un bloc : `meilleur_tenu`, réponse appliquée, bloc remis à zéro.

    `decision` = le verdict proposé (ou `None`), `reponse` = `oui`, `pas_maintenant`,
    `garder` ou `None` (sans réponse en 7 jours : expirée, ce n'est pas un refus).
    """
    n = _palier(etat)
    champs = {}
    if _jours_tenus(etat) >= SEUIL_MONTER:
        champs['meilleur_tenu'] = max(etat.meilleur_tenu or 0, n)
    champs.update(blocs_a_sauter=max(0, etat.blocs_a_sauter - 1), baisse_refusee=False,
                  essai_restant=False, comptes_bloc=(), bloc_debut=jour + timedelta(days=1))
    champs.update(_apres_decision(etat, jour, decision, reponse))
    return _maj(etat, **champs)


def objectif_dit(etat, nombre=None, sens=None, jour=None):
    """L'objectif déclaré prime et s'applique tout de suite (A2.1).

    `nombre` 1-12 (sinon `ObjectifInvalide`, 400) ou `sens` `plus`/`moins` depuis
    l'objectif affiché (plancher 1, plafond 12). Le mode passe à `pousser`. Avec
    `jour`, un nouveau bloc démarre le lendemain (sauf démarrage à froid).
    """
    if nombre is not None:
        if not PALIER_MIN <= nombre <= PALIER_MAX:
            raise ObjectifInvalide()
        palier = nombre
    elif sens in (SENS_PLUS, SENS_MOINS):
        base = objectif_affiche(etat)[0]
        base = _palier(etat) if base is None else base
        palier = max(PALIER_MIN, min(PALIER_MAX, base + (1 if sens == SENS_PLUS else -1)))
    else:
        raise ObjectifInvalide()
    champs = {'mode': ModeRythme.POUSSER, 'palier': palier, 'palier_source': SourceObjectif.DIT,
              'refus_montee': 0, 'blocs_a_sauter': 0, 'baisse_refusee': False,
              'essai_restant': False, 'comptes_bloc': ()}
    if jour is not None and etat.bloc_debut is not None:
        champs['bloc_debut'] = jour + timedelta(days=1)
    return _maj(etat, **champs)


def repondre_premier(etat, journee_type, choix):
    """Réponse à la carte `premier` : `oui` -> palier = type ; `garder` -> palier 5."""
    palier = journee_type if choix == ReponseIncitation.OUI else PALIER_DEFAUT
    return _maj(etat, palier=palier, palier_source=SourceObjectif.ACCEPTE)
