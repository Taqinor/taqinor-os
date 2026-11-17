"""Règles du rythme APRÈS (spec-5a-rythme.md) — fonctions PURES, bibliothèque standard seule.
Ce fichier est la maquette exécutable des fonctions que la lane de construction écrira dans
apps/taches/moteur/rythme.py. Données synthétiques seulement dans le banc ; rien ici n'est un fait
sur de vrais utilisateurs."""
import math
import statistics
from dataclasses import dataclass, field, replace

# ---------------------------------------------------------------- constantes (choix de conception)
DEFAUT = 5            # objectif affiché tant qu'aucun palier personnel n'existe (« valeur par défaut »)
JOURS_INITIAUX = 10   # jours évalués avant le premier palier personnel
BLOC = 10             # jours évalués par bloc d'évaluation (≈ 2 semaines ouvrées)
SEUIL_BAISSER = 3     # jours tenus sur 10 (ou moins) pour proposer N-1
PLAFOND = 12          # au-delà, plus de proposition de montée
MICRO_MIN = 10        # une tâche estimée <= 10 min est une micro-tâche
MICRO_COMPTEES = 2    # micro-tâches comptées au plus par jour
TAILLE_MIN = 0.70     # médiane des tailles faites >= 70 % de la référence pour proposer de monter
TAILLE_N_MIN = 10     # tâches estimées nécessaires dans chaque échantillon pour appliquer la garde
ATTENTE_ECHEC = 42    # jours calendaires avant de reproposer un palier jamais tenu puis quitté
ATTENTE_REFUS = (0, 1, 2, 4)   # blocs sautés après 0, 1, 2, >=3 refus de montée consécutifs
TENIR_N = 14          # jours évalués pour la référence et la dérive de TENIR
TENIR_SILENCE = 28    # jours calendaires de silence après une alerte TENIR
# variantes testées par le banc (valeurs retenues ci-dessous)
BORNE = 'aucune'      # 'aucune' | 'p60' : N+1 <= ceil(P60 du bloc). Testé : 'p60' étouffe la montée -> repère affiché
SEUIL_MONTER = 6      # retenu après itération (7 testé : pousse moins le profil qui progresse)
ESSAI = 1             # blocs après une montée acceptée pendant lesquels aucune baisse n'est proposée
INITIAL = 'min_med_moy'   # 'mediane' | 'min_med_moy'
TENU_ESSENTIEL = False    # le jour « à N ou plus » des PALIERS compte les tâches seules (l'essentiel est affiché à part)
BAISSE_MOYENNE = False    # testé (moyenne du bloc < N - 0,5) : aucun effet mesuré -> écarté pour la simplicité


def round_half_down(x):
    return int(math.ceil(x - 0.5))


def round_half_up(x):
    return int(math.floor(x + 0.5))


def percentile_lineaire(vals, p):
    s = sorted(vals)
    if not s:
        return None
    pos = p * (len(s) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (pos - lo) * (s[hi] - s[lo])


# ---------------------------------------------------------------- 1. compter
def compte_du_jour(taches_faites, activites_closes=0):
    """taches_faites: liste de dicts {estimation: int|None, sous_tache: bool, routine: bool}.
    Retourne (compte, detail). Sous-tâche = 0 (le parent compte 1) ; routine quotidienne = 0
    (affichée à part) ; micro-tâches (<= 10 min) : au plus 2 comptées ; activité ERP close = 1."""
    normales = micro = sous = routines = 0
    for t in taches_faites:
        if t.get('sous_tache'):
            sous += 1
        elif t.get('routine'):
            routines += 1
        elif t.get('estimation') is not None and t['estimation'] <= MICRO_MIN:
            micro += 1
        else:
            normales += 1
    micro_c = min(micro, MICRO_COMPTEES)
    compte = normales + micro_c + activites_closes
    return compte, dict(normales=normales, micro=micro, micro_comptees=micro_c, sous_taches=sous,
                        routines=routines, activites=activites_closes)


# ---------------------------------------------------------------- 2. classer le jour
def statut_jour(ouvre_pour_lui, en_conge, compte, plan_valide, app_ouverte):
    """'conge' | 'non_ouvre' | 'sans_donnees' | 'evalue'. Seul 'evalue' entre dans un bloc.
    ouvre_pour_lui = jour ouvré de la société ET jour de ses jours_travailles déclarés, hors férié."""
    if en_conge:
        return 'conge'
    if not ouvre_pour_lui:
        return 'non_ouvre'          # travail du week-end : montré dans les totaux, jamais évalué
    if compte == 0 and not plan_valide and not app_ouverte:
        return 'sans_donnees'
    return 'evalue'


def jour_tenu(compte, objectif, essentiels_choisis, essentiels_faits):
    """Tenu = compte >= objectif ET (au moins un essentiel fait, ou aucun choisi)."""
    if objectif is None:
        return False
    if not TENU_ESSENTIEL:
        return compte >= objectif
    return journee_reussie(compte, objectif, essentiels_choisis, essentiels_faits)


def journee_reussie(compte, objectif, essentiels_choisis, essentiels_faits):
    """Réussie = objectif atteint ET essentiel fait (au moins un, s'il en a choisi). Sans objectif (LIBRE) : None."""
    if objectif is None:
        return None
    return compte >= objectif and (essentiels_choisis == 0 or essentiels_faits >= 1)


# ---------------------------------------------------------------- 3. POUSSER
@dataclass
class Etat:
    mode: str = 'pousser'            # pousser | tenir | libre
    palier: int = None               # None = démarrage à froid (affiche DEFAUT)
    objectif_dit: int = None         # ce qu'il a DIT (Preference) — prime
    bloc: list = field(default_factory=list)      # jours évalués du bloc courant: (compte, tenu, taille)
    initiaux: list = field(default_factory=list)  # comptes des jours évalués avant le 1er palier
    refus_montee: int = 0
    blocs_a_sauter: int = 0          # montée
    baisse_refusee: bool = False
    meilleur_tenu: int = 0
    echec: tuple = None              # (niveau quitté jamais tenu, jour)
    ref_taille: float = None
    tailles_bloc: list = field(default_factory=list)
    R: float = None                  # référence TENIR
    R_jours: list = field(default_factory=list)
    silence_jusqua: int = -1
    essai_restant: int = 0
    historique: list = field(default_factory=list)  # comptes évalués (tous modes), chronologique


def objectif_affiche(e):
    """(nombre ou None, source) — source ∈ defaut | dit | palier | tenir | libre."""
    if e.mode == 'libre':
        return None, 'libre'
    if e.mode == 'tenir':
        if e.R is None:
            return (e.palier or e.objectif_dit or DEFAUT), 'tenir_provisoire'
        return max(1, round_half_up(e.R)), 'tenir'
    if e.palier is None:
        return (e.objectif_dit or DEFAUT), ('dit' if e.objectif_dit else 'defaut')
    return e.palier, 'palier'


def palier_initial(comptes, objectif_dit=None):
    """Après JOURS_INITIAUX jours évalués : journée type = médiane arrondie à l'inférieur, plancher 1.
    S'il a DIT un objectif, on le garde et on renvoie la journée type comme simple repère."""
    if len(comptes) < JOURS_INITIAUX:
        return None, None
    base = statistics.median(comptes)
    if INITIAL == 'min_med_moy':
        base = min(base, statistics.mean(comptes))   # une journée en rafales ne gonfle pas le départ
    type_ = max(1, round_half_down(base))
    if objectif_dit:
        return objectif_dit, type_
    return type_, type_


def reference_taille(tailles):
    """Médiane des estimations des tâches faites (None si moins de TAILLE_N_MIN tâches estimées)."""
    return statistics.median(tailles) if len(tailles) >= TAILLE_N_MIN else None


def garde_taille(ref, tailles):
    """True si la montée est permise du point de vue de la taille des tâches (ou garde inapplicable)."""
    if ref is None or len(tailles) < TAILLE_N_MIN:
        return True
    return statistics.median(tailles) >= TAILLE_MIN * ref


def evaluer_bloc(e, jour):
    """Appelé quand le bloc compte BLOC jours évalués. Retourne (decision, chiffres) où decision ∈
    'monter' | 'baisser' | 'taille' | None. Ne modifie pas e (pure)."""
    N = e.palier
    tenus = sum(1 for (_, t, _) in e.bloc if t)
    comptes = [c for (c, _, _) in e.bloc]
    ch = dict(palier=N, tenus=tenus, sur=len(e.bloc), p60=math.ceil(percentile_lineaire(comptes, 0.6)),
              mediane=statistics.median(comptes))
    if tenus >= SEUIL_MONTER and N < PLAFOND:
        if e.blocs_a_sauter > 0:
            return None, ch
        if e.echec and e.echec[0] == N + 1 and N + 1 > e.meilleur_tenu and \
                jour - e.echec[1] < ATTENTE_ECHEC * e.echec[2]:
            return None, ch
        if BORNE == 'p60' and N + 1 > ch['p60']:   # borne de vraisemblance (règle publiée WalkIT)
            return None, ch
        if not garde_taille(e.ref_taille, e.tailles_bloc):
            ch['taille_med'] = statistics.median(e.tailles_bloc)
            return 'taille', ch
        return 'monter', ch
    essai_bloque = e.essai_restant > 0 and tenus > 1   # bloc d'essai : baisse seulement si 0 ou 1 jour tenu
    if tenus <= SEUIL_BAISSER and N > 1 and not e.baisse_refusee and not essai_bloque and \
            (not BAISSE_MOYENNE or statistics.mean(comptes) < N - 0.5):
        return 'baisser', ch
    return None, ch


def clore_bloc(e, jour, decision, reponse):
    """Applique la décision et la réponse ('oui' | 'pas_maintenant' | None) ; vide le bloc. Pure."""
    N = e.palier
    tenus = sum(1 for (_, t, _) in e.bloc if t)
    e2 = replace(e, bloc=[], tailles_bloc=[])
    if e2.ref_taille is None and len(e.tailles_bloc) >= TAILLE_N_MIN:
        e2.ref_taille = statistics.median(e.tailles_bloc)   # référence = 1er bloc du mode POUSSER
    if tenus >= SEUIL_MONTER:
        e2.meilleur_tenu = max(e2.meilleur_tenu, N)
    if e2.blocs_a_sauter > 0:
        e2.blocs_a_sauter -= 1
    e2.baisse_refusee = False
    if e2.essai_restant > 0:
        e2.essai_restant -= 1
    if decision == 'monter':
        if reponse == 'oui':
            e2.palier = N + 1
            e2.refus_montee = 0
            e2.essai_restant = ESSAI
        else:
            e2.refus_montee += 1
            e2.blocs_a_sauter = ATTENTE_REFUS[min(e2.refus_montee, 3)]
    elif decision == 'baisser':
        if reponse == 'oui':
            e2.palier = max(1, N - 1)
            if N > e2.meilleur_tenu:
                n_echecs = e.echec[2] + 1 if (e.echec and e.echec[0] == N) else 1
                e2.echec = (N, jour, n_echecs)   # 6 semaines × nombre d'échecs à ce niveau
        else:
            e2.baisse_refusee = True
    return e2


# ---------------------------------------------------------------- 4. TENIR
TENIR_ROGNER = 0      # testé à 2 (moyenne rognée) : gain marginal (1,9 vs 2,4 alertes, profil 7b) -> moyenne simple (socle §6)


def moyenne_rognee(comptes):
    s = sorted(comptes)
    k = TENIR_ROGNER if len(s) > 2 * TENIR_ROGNER else 0
    return statistics.mean(s[k:len(s) - k])


def bande_tenir(R):
    b = max(1.0, 0.2 * R)
    return R - b, R + b


def reference_tenir(comptes):
    """Moyenne rognée non arrondie des TENIR_N derniers jours évalués, ou None s'il en manque."""
    if len(comptes) < TENIR_N:
        return None
    return moyenne_rognee(comptes[-TENIR_N:])


def derive_tenir(R, comptes_depuis_R, jour, silence_jusqua):
    """'sous' | 'au_dessus' | None. Exige TENIR_N jours évalués DEPUIS la fixation de R."""
    if R is None or len(comptes_depuis_R) < TENIR_N or jour < silence_jusqua:
        return None
    m = moyenne_rognee(comptes_depuis_R[-TENIR_N:])
    lo, hi = bande_tenir(R)
    if m < lo:
        return 'sous'
    if m > hi:
        return 'au_dessus'
    return None


# ---------------------------------------------------------------- 5. bascules
def recents(historique, jour, horizon=42):
    """Comptes évalués des `horizon` derniers jours calendaires (historique = [(jour, compte)])."""
    return [c for (j, c) in historique if jour - j <= horizon]


def basculer(e, nouveau, jour):
    """POUSSER <-> TENIR <-> LIBRE. Pure."""
    e2 = replace(e, mode=nouveau, bloc=[], tailles_bloc=[], refus_montee=0, blocs_a_sauter=0,
                 baisse_refusee=False, essai_restant=0)
    rec = recents(e.historique, jour)
    if nouveau == 'tenir':
        e2.R = reference_tenir(rec)   # None -> provisoire (palier ou défaut affiché), fixée après 14 jours
        e2.R_jours = []
        e2.silence_jusqua = -1
    elif nouveau == 'pousser':
        if e.mode == 'tenir' and e.R is not None:
            e2.palier = max(1, round_half_down(e.R))
        elif len(rec) >= JOURS_INITIAUX:
            e2.palier, _ = palier_initial(rec[-JOURS_INITIAUX:], e.objectif_dit)
        e2.ref_taille = None
    return e2


def jour_tenir(e, compte, jour):
    """Un jour évalué en mode TENIR. Retourne (e2, alerte ∈ None|'sous'|'au_dessus', moyenne)."""
    e2 = replace(e, R_jours=e.R_jours + [compte])
    if e2.R is None:
        if len(e2.R_jours) >= TENIR_N:
            e2.R = reference_tenir(e2.R_jours)
            e2.R_jours = []
        return e2, None, None
    a = derive_tenir(e2.R, e2.R_jours, jour, e2.silence_jusqua)
    m = moyenne_rognee(e2.R_jours[-TENIR_N:]) if len(e2.R_jours) >= TENIR_N else None
    if a:
        e2.silence_jusqua = jour + TENIR_SILENCE
    return e2, a, m


# ---------------------------------------------------------------- 6. sollicitations (socle §5)
PRIORITE_RELANCE = ('echeance_du_jour', 'derive_rythme', 'projet_neglige')
PAUSE_APRES = 14


def choisir_relance(candidats):
    """La relance UNIQUE de journée : la première présente dans PRIORITE_RELANCE, sinon None."""
    for k in PRIORITE_RELANCE:
        if k in candidats:
            return k
    return None


def etat_decroissance(ignorees):
    """ignorees = booléens chronologiques des sollicitations ENVOYÉES d'un type (True = ignorée).
    'pause' si les 14 dernières sont toutes ignorées, sinon 'normal'. Une ouverture remet à zéro."""
    run = 0
    for x in reversed(ignorees):
        if not x:
            break
        run += 1
    return 'pause' if run >= PAUSE_APRES else 'normal'


def variante(ordinal_du_jour):
    """Rotation des 3 formulations : 0, 1, 2 selon le jour (date.toordinal() % 3)."""
    return ordinal_du_jour % 3


def derive_pousser_journee(compte_15h, objectif, essentiel_fait):
    """Relance « dérive » en POUSSER à 15 h : moins de la moitié de l'objectif ET essentiel non fait."""
    return objectif is not None and compte_15h < objectif / 2 and not essentiel_fait


def surchauffe_tenir_journee(compte_15h, R):
    """Relance « dérive » en TENIR à 15 h : déjà au haut de la zone ou au-delà."""
    return R is not None and compte_15h >= bande_tenir(R)[1]


def repondre_tenir(e, reponse, moyenne):
    """'garder' (R inchangé) | 'ajuster' (R = moyenne observée, fenêtre repart). Silence déjà posé."""
    if reponse == 'ajuster' and moyenne is not None:
        return replace(e, R=moyenne, R_jours=[])
    return e
