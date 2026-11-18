"""Le rythme : module PUR (reference/regles.md §6), sans Django ni base.

Chaque fonction reçoit ses données et la date du jour en argument : aucune
horloge vivante. Les énumérations viennent de `apps.taches.choix`.
"""
import math
from dataclasses import dataclass, replace
from datetime import timedelta
from statistics import mean, median

from apps.taches.choix import ModeRythme, ReponseIncitation, SourceObjectif, StatutJour, StatutTache
from apps.taches.moteur.nombres import arrondir

# --- Constantes nommées (regles.md §6) -------------------------------------
PALIER_DEFAUT = 5  # objectif de démarrage à froid
PALIER_MIN = 1
PALIER_MAX = 12
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


def mettre_a_jour(etat, **changes):
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


def apres_decision(etat, jour, decision, reponse):
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


#: Le nombre écrit sur le bouton « Oui » d'une carte de palier (`Monter à {N1}`, `Descendre à {N_1}`).
CIBLE_DE_LA_CARTE = {DECISION_MONTER: ('N1', 1), DECISION_BAISSER: ('N_1', -1)}


def carte_a_jour(etat, cle, donnees):
    """Vrai si la carte de palier `cle` a été calculée depuis le palier COURANT (§6.5 : jamais plus
    d'un cran). `monter`/`baisser` portent `N` et le nombre de leur bouton (N ± 1), `premier` naît à
    froid (palier nul), `journee_type` porte le palier dit. Une carte périmée ne change rien."""
    if cle in CIBLE_DE_LA_CARTE:
        champ, pas = CIBLE_DE_LA_CARTE[cle]
        n = _palier(etat)
        return donnees.get('N') == n and donnees.get(champ) == n + pas
    if cle == CARTE_PREMIER:
        return etat.palier is None
    if cle == CARTE_JOURNEE_TYPE:
        return etat.palier == donnees.get('dit')
    return True


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
    champs.update(apres_decision(etat, jour, decision, reponse))
    return mettre_a_jour(etat, **champs)


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
    return mettre_a_jour(etat, **champs)


def repondre_premier(etat, journee_type, choix):
    """Réponse à la carte `premier` : `oui` -> palier = type ; `garder` -> palier 5."""
    palier = journee_type if choix == ReponseIncitation.OUI else PALIER_DEFAUT
    return mettre_a_jour(etat, palier=palier, palier_source=SourceObjectif.ACCEPTE)


# --- TCH27 : « Garder ce rythme » et bascules (TENIR, §6.6-§6.7) ------------

JOURS_REFERENCE = 14  # R = moyenne des 14 derniers jours évalués
JOURS_TYPE = 10  # journée type = les 10 derniers jours évalués
SILENCE_TENIR_JOURS = 28  # silence après une dérive, quelle que soit la réponse
DECIMALES_REFERENCE = 2  # `tenir_reference` est un DecimalField(4,2)
DERIVE_SOUS = 'sous'
DERIVE_AU_DESSUS = 'au_dessus'


def moyenne_plafonnee(comptes):
    plafonnes = plafonner_jours(comptes)
    return sum(plafonnes) / len(plafonnes)


def reference_tenir(comptes):
    """R = moyenne (plafonnée) des 14 derniers jours évalués ; `None` s'il en manque."""
    derniers = list(comptes)[-JOURS_REFERENCE:]
    if len(derniers) < JOURS_REFERENCE:
        return None
    return round(moyenne_plafonnee(derniers), DECIMALES_REFERENCE)


def bande_tenir(reference):
    """Zone `(R - b, R + b)` avec `b = max(1 ; 0,2 R)`."""
    return _bande(reference)


def derive_tenir(reference, comptes, jour, silence):
    """`sous` | `au_dessus` | `None` : moyenne plafonnée des 14 derniers jours hors zone.

    Rien pendant le silence (`tenir_silence_jusquau`, 28 jours après une dérive) ;
    `comptes` = jours évalués DEPUIS la fixation de R, il en faut 14.
    """
    if reference is None or (silence is not None and jour <= silence):
        return None
    derniers = list(comptes)[-JOURS_REFERENCE:]
    if len(derniers) < JOURS_REFERENCE:
        return None
    moyenne = moyenne_plafonnee(derniers)
    bas, haut = _bande(float(reference))
    if moyenne < bas:
        return DERIVE_SOUS
    if moyenne > haut:
        return DERIVE_AU_DESSUS
    return None


def _vers_tenir(etat, jour):
    reference = reference_tenir(etat.comptes_recents)
    if reference is None:  # R provisoire = palier courant (ou 5), fixée après 14 jours
        return {'tenir_reference': _palier(etat), 'tenir_fixee_le': None}
    return {'tenir_reference': reference, 'tenir_fixee_le': jour}


def _vers_pousser(etat, jour):
    if etat.mode == ModeRythme.TENIR:
        reference = etat.tenir_reference if etat.tenir_reference is not None else _palier(etat)
        palier = max(PALIER_MIN, arrondir(float(reference)))
        return {'palier': palier, 'palier_source': SourceObjectif.CALCULE,
                'bloc_debut': jour + timedelta(days=1)}
    recents = list(etat.comptes_recents)[-JOURS_TYPE:]  # LIBRE -> POUSSER : journée type
    if len(recents) < JOURS_TYPE:
        return {'palier': None, 'palier_source': '', 'bloc_debut': None}  # démarrage à froid
    palier = palier_initial(recents, None)[1]
    return {'palier': palier, 'palier_source': SourceObjectif.CALCULE,
            'bloc_debut': jour + timedelta(days=1)}


def _fenetre_ok(jour, ref, fenetre):
    return 0 <= (jour - ref).days < fenetre


def basculer(etat, mode, jour):
    """Change de mode (§6.7) : remet blocs, refus et essai à zéro ; garde `meilleur_tenu` et les échecs.

    L'abandon de la proposition en attente est affaire de la couche appelante
    (la proposition vit dans `IncitationCoach`, pas dans l'état).
    """
    if mode == etat.mode:
        return etat
    champs = {'mode': mode, 'refus_montee': 0, 'blocs_a_sauter': 0, 'baisse_refusee': False,
              'essai_restant': False, 'comptes_bloc': (), 'tenir_silence_jusquau': None}
    if mode == ModeRythme.TENIR:
        champs.update(_vers_tenir(etat, jour))
    elif mode == ModeRythme.POUSSER:
        champs.update(_vers_pousser(etat, jour))
    return mettre_a_jour(etat, **champs)


# --- TCH28 : constats, retour d'absence, semaine courte, repère (§6.9, §4.8) -

FENETRE_CONSTATS_JOURS = 28  # fenêtre des constats, sauf C3
FENETRE_C3_JOURS = 56  # C3 exige 8 jours d'un même jour de semaine : 28 jours n'en donnent que 4
SILENCE_CONSTAT_JOURS = 28  # un constat refusé se tait 28 jours
CONSTATS_MAX = 8
C1_MIN_LIGNES = 30
C1_ECART = 25  # points
C2_MIN_JOURS = 15
C2_ECART = 30
C3_MIN_JOURS = 8
C3_ECART = 1  # tâches sous la moyenne générale
C4_MIN_PLANS = 10
C4_ECART = 2
C4_PART = 0.6
C5_MIN_TACHES = 30
C5_TRANCHE_HEURES = 2
C6_MIN_TACHES = 5
C6_RATIO_BAS = 0.8
C6_RATIO_HAUT = 1.25
C7_MIN = 1
RETOUR_JOURS_TRAVAILLES = 3  # >= 3 jours travaillés depuis la dernière ouverture
REPERE_JOURS = 9
REPERE_PERCENTILE = 0.6
REPERE_DECIMALES = 1
SEMAINE_COURTE_JOURS = 3  # >= 3 jours `sans_donnees` dans la semaine
POURCENT = 100

# Comme les autres comportements « hors de la première livraison » : C6 est éteint
# faute de durée réelle mesurée (critique m6) ; les champs et la formule restent.
CONSTAT_C6_ACTIF = False

ACTION_ESSENTIEL_MATIN = 'essentiel_le_matin'
ACTION_JOURS_COURTS = 'jours_courts'
ACTION_GARDER_LIMITE = 'garder_limite'
ACTION_DUREE_CORRIGEE = 'duree_corrigee'
ACTION_A_REVOIR = 'a_revoir'
ACTION_PROPOSE_DEMAIN = 'propose_demain'


@dataclass(frozen=True)
class LigneConstat:
    """Une ligne de plan figée (`LignePlanJour`) vue par C1 et C2."""
    jour: object
    creneau: str = ''
    faite: bool = False
    essentielle: bool = False
    rang: object = None


@dataclass(frozen=True)
class DonneesConstats:
    """Tout ce que `constats` lit (aucun ORM) ; les fenêtres sont filtrées ici.

    `heures_faits` = `(jour, heure locale de fait_le)` ; `taches_mesurees` =
    `(projet_id, minutes estimées, minutes réelles)` ; `refus` = code -> jour du
    « Pas maintenant » ; `reportees_3` = tâches ouvertes reportées 3 fois ou plus ;
    `projet_neglige_id` = projet de plus haute priorité non vide de `neglige()`.
    """
    jour: object
    comprendre_mon_rythme: bool = True
    jours: tuple = ()
    lignes: tuple = ()
    heures_faits: tuple = ()
    taches_mesurees: tuple = ()
    reportees_3: int = 0
    projet_neglige_id: object = None
    refus: object = None


@dataclass(frozen=True)
class Constat:
    """Un constat : numéro `C<n>`, nombres (ids, jamais de titres) et action proposée."""
    code: str
    donnees: dict
    action: object = None


def _pct(ok, total):
    return POURCENT * ok / total


def lignes_fenetre(d):
    return [x for x in d.lignes if _fenetre_ok(d.jour, x.jour, FENETRE_CONSTATS_JOURS)]


def _constat_c1(d):
    groupes = {}
    for ligne in lignes_fenetre(d):
        if ligne.creneau:
            groupes.setdefault(ligne.creneau, []).append(ligne.faite)
    taux = {c: _pct(sum(v), len(v)) for c, v in groupes.items() if len(v) >= C1_MIN_LIGNES}
    if len(taux) < 2 or max(taux.values()) - min(taux.values()) < C1_ECART:
        return None
    meilleur = max(taux, key=taux.get)
    return Constat('C1', {'taux': taux, 'meilleur': meilleur}, ACTION_ESSENTIEL_MATIN)


def essentiels_classes(lignes):
    """Lignes essentielles `(jour, faite)` : en tête du plan (rang minimal du jour) / ailleurs."""
    rang_min = {}
    for ligne in lignes:
        if ligne.rang is not None:
            rang_min[ligne.jour] = min(rang_min.get(ligne.jour, ligne.rang), ligne.rang)
    en_tete, ailleurs = [], []
    for ligne in lignes:
        if ligne.essentielle and ligne.rang is not None:
            cible = en_tete if ligne.rang == rang_min[ligne.jour] else ailleurs
            cible.append((ligne.jour, ligne.faite))
    return en_tete, ailleurs


def _constat_c2(d):
    en_tete, ailleurs = essentiels_classes(lignes_fenetre(d))
    # 15 jours chacun (un jour compte dans les deux familles s'il a deux essentiels).
    if len({j for j, _ in en_tete}) < C2_MIN_JOURS or len({j for j, _ in ailleurs}) < C2_MIN_JOURS:
        return None
    taux_tete = _pct(sum(f for _, f in en_tete), len(en_tete))
    taux_ailleurs = _pct(sum(f for _, f in ailleurs), len(ailleurs))
    if taux_tete - taux_ailleurs < C2_ECART:
        return None
    return Constat('C2', {'premier': taux_tete, 'ailleurs': taux_ailleurs}, ACTION_ESSENTIEL_MATIN)


def _constat_c3(d):
    evalues = [j for j in d.jours if j.statut_jour == StatutJour.EVALUE
               and _fenetre_ok(d.jour, j.jour, FENETRE_C3_JOURS)]
    if not evalues:
        return None
    generale = mean(j.compte for j in evalues)
    moyennes = {}
    for semaine_jour in range(7):
        comptes = [j.compte for j in evalues if j.jour.weekday() == semaine_jour]
        if len(comptes) >= C3_MIN_JOURS and mean(comptes) <= generale - C3_ECART:
            moyennes[semaine_jour] = mean(comptes)
    if not moyennes:
        return None
    pire = min(moyennes, key=moyennes.get)
    return Constat('C3', {'jour_semaine': pire, 'moyenne': moyennes[pire], 'moyenne_generale': generale},
                   ACTION_JOURS_COURTS)


def _constat_c4(d):
    plans = [j for j in d.jours if j.statut_jour == StatutJour.EVALUE and j.plan_prevues > 0
             and _fenetre_ok(d.jour, j.jour, FENETRE_CONSTATS_JOURS)]
    if len(plans) < C4_MIN_PLANS:
        return None
    trop = sum(1 for j in plans if j.plan_prevues - j.plan_faites >= C4_ECART)
    if trop < C4_PART * len(plans):
        return None
    limite = arrondir(median(j.plan_faites for j in plans)) + 1
    return Constat('C4', {'plans': len(plans), 'limite': limite}, ACTION_GARDER_LIMITE)


def _constat_c5(d):
    heures = [h for jour, h in d.heures_faits if _fenetre_ok(d.jour, jour, FENETRE_CONSTATS_JOURS)]
    if len(heures) < C5_MIN_TACHES:
        return None
    tranches = {}
    for heure in heures:
        debut = heure - heure % C5_TRANCHE_HEURES
        tranches[debut] = tranches.get(debut, 0) + 1
    return Constat('C5', {'tranches': {k: _pct(v, len(heures)) for k, v in sorted(tranches.items())}}, None)


def _constat_c6(d):
    if not CONSTAT_C6_ACTIF:
        return None
    par_projet = {}
    for projet_id, estime, reel in d.taches_mesurees:
        if estime and reel is not None:
            par_projet.setdefault(projet_id, []).append(reel / estime)
    hors = {p: median(r) for p, r in par_projet.items()
            if len(r) >= C6_MIN_TACHES and not C6_RATIO_BAS <= median(r) <= C6_RATIO_HAUT}
    if not hors:
        return None
    pire = max(hors, key=lambda p: abs(math.log(hors[p])))
    return Constat('C6', {'projet_id': pire, 'ratio': hors[pire]}, ACTION_DUREE_CORRIGEE)


def _constat_c7(d):
    if d.reportees_3 < C7_MIN:
        return None
    return Constat('C7', {'nb': d.reportees_3}, ACTION_A_REVOIR)


def _constat_c8(d):
    if d.projet_neglige_id is None:
        return None
    return Constat('C8', {'projet_id': d.projet_neglige_id}, ACTION_PROPOSE_DEMAIN)


_CONSTATS = (_constat_c1, _constat_c2, _constat_c3, _constat_c4,
             _constat_c5, _constat_c6, _constat_c7, _constat_c8)


def constats(donnees):
    """Les constats calculables, de C1 à C8 (8 au plus), `[]` si « comprendre mon rythme » est éteint.

    Un constat refusé (« Pas maintenant ») se tait 28 jours. Le choix de celui
    qu'on montre au bilan du soir (un seul) appartient à la couche appelante.
    """
    if not donnees.comprendre_mon_rythme:
        return []
    refus = donnees.refus or {}
    sortie = []
    for calcul in _CONSTATS:
        constat = calcul(donnees)
        if constat is None:
            continue
        refuse_le = refus.get(constat.code)
        if refuse_le is not None and (donnees.jour - refuse_le).days < SILENCE_CONSTAT_JOURS:
            continue
        sortie.append(constat)
    return sortie[:CONSTATS_MAX]


def retour_absence(jours, taches, jour=None):
    """Donnees de la carte `retour` (§4.8), ou `None` si ce n'est pas un retour.

    `jours` = `JourCompte` chronologiques depuis la dernière ouverture (incluse)
    jusqu'à la veille de J ; `taches` = ids des tâches `a_faire` prévues dans
    cette période. Retour = fin d'un congé OU >= 3 jours travaillés strictement
    après la dernière ouverture. `jour` (J) vaut le lendemain du dernier jour lu.
    """
    jours = list(jours)
    if not jours:
        return None
    apres = jours[1:]
    travailles = sum(1 for j in apres if j.statut_jour in (StatutJour.SANS_DONNEES, StatutJour.EVALUE))
    en_conge = any(j.statut_jour == StatutJour.CONGE for j in apres)
    if travailles < RETOUR_JOURS_TRAVAILLES and not en_conge:
        return None
    jour = jour if jour is not None else jours[-1].jour + timedelta(days=1)
    return {'jours': (jour - jours[0].jour).days, 'taches': list(taches)}


def semaine_courte(statuts):
    """Vrai si la semaine compte >= 3 jours `sans_donnees` (revue sans chiffres, A16-N9)."""
    return sum(1 for s in statuts if s == StatutJour.SANS_DONNEES) >= SEMAINE_COURTE_JOURS


def repere_p60(comptes):
    """Repère P60 (§6.5 point 8) : percentile 60 linéaire des 9 derniers jours, 1 décimale.

    `None` s'il y a moins de 9 jours. Affiché, jamais un objectif.
    """
    derniers = sorted(list(comptes)[-REPERE_JOURS:])
    if len(derniers) < REPERE_JOURS:
        return None
    position = REPERE_PERCENTILE * (len(derniers) - 1)
    bas = math.floor(position)
    haut = min(bas + 1, len(derniers) - 1)
    valeur = derniers[bas] + (position - bas) * (derniers[haut] - derniers[bas])
    return round(valeur, REPERE_DECIMALES)
