"""Classement et Proposé (regles.md §3, §4.2) — code PUR.

Aucune base, aucun ORM, aucune horloge : le jour `J` et l'ensemble des jours
travaillés `travailles` sont toujours des paramètres. Les seules valeurs
techniques viennent de `apps.taches.choix` (source unique des énumérations).
"""
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from apps.taches.choix import (
    CapaciteSource, MotifRevoir, Moment, RaisonPropose, SectionJournee, StatutTache)
from apps.taches.moteur.nombres import arrondir

TACHE = 'tache'
ACTIVITE = 'activite'
HAUTE = 3
OBJECTIF_LIBRE = 5  # mode `libre` : N = 5 (regles.md §3.4)
CAPACITE_DEFAUT = 240
SECTIONS_GARDEES = (SectionJournee.ESSENTIEL, SectionJournee.JOURNEE, SectionJournee.CE_SOIR)


# --- Types d'entrée (regles.md §0.1) ---------------------------------------

@dataclass(frozen=True)
class ItemPur:
    """Une tâche ou une activité ERP, telle que la vue la construit depuis l'ORM."""
    type: str = TACHE
    id: int = 0
    statut: str = StatutTache.A_FAIRE
    priorite: int = 0
    projet_id: int | None = None
    projet_priorite: int | None = None
    projet_rang: int | None = None
    focus: bool = False
    section_id: int | None = None
    parent_id: int | None = None
    rang_projet: int | None = None
    rang_jour: int | None = None
    jour_prevu: date | None = None
    heure_debut: time | None = None
    moment: str = Moment.AUCUN
    echeance: date | None = None
    echeance_heure: time | None = None
    quelque_jour: bool = False
    bloquee_par: int | None = None
    triee_le: datetime | None = None
    estimation_minutes: int | None = None
    duree_reelle_minutes: int | None = None
    reports: int = 0
    reports_tranches: int = 0
    fait_le: datetime | None = None
    routine: bool = False
    recurrente: bool = False
    jalon: bool = False
    confidentielle: bool = False
    created_at: datetime | None = None


@dataclass(frozen=True)
class LignePure:
    """Une ligne du plan du jour (`LignePlanJour`)."""
    tache_id: int | None = None
    activite_id: int | None = None
    prevue_au_plan: bool = False
    faite: bool = False
    reportee: bool = False
    essentielle: bool = False
    creneau: str = ''
    rang: int | None = None


@dataclass(frozen=True)
class PlanPur:
    """Le plan du jour (`PlanJour`)."""
    jour: date | None = None
    planifie_le: datetime | None = None
    cloture_le: datetime | None = None
    allege_le: datetime | None = None
    objectif_du_jour: int | None = None
    lignes: tuple = ()


@dataclass(frozen=True)
class Placement:
    """Résultat de `placer` : la section, et le motif (À revoir) ou la raison (Proposé)."""
    section: str
    code: str | None = None
    essentielle: bool = False


# --- Jours travaillés -------------------------------------------------------

def n_travailles(J, jusqua, travailles):
    """Nombre de jours travaillés d avec J < d ≤ `jusqua` (0 si `jusqua` ≤ J ou nul)."""
    if jusqua is None or jusqua <= J:
        return 0
    return sum(1 for d in travailles if J < d <= jusqua)


def nieme_travaille(J, n, travailles):
    """Le n-ième jour travaillé après J ; à défaut, le dernier connu (J si aucun)."""
    suivants = sorted(d for d in travailles if d > J)
    if not suivants:
        return J
    return suivants[min(n, len(suivants)) - 1]


# --- cle_tri (regles.md §3.2) -----------------------------------------------

def echeance_de(item):
    """Échéance servant au tri : `echeance`, ou pour une activité sa date due."""
    if item.type == ACTIVITE:
        return item.echeance if item.echeance is not None else item.jour_prevu
    return item.echeance


def pmax(item):
    """max(priorité de la tâche, priorité du projet) ; projet de la semaine ⇒ 3 ; activité ⇒ 0."""
    if item.type == ACTIVITE:
        return 0
    if item.focus:
        return HAUTE
    if item.projet_priorite is None:
        return item.priorite
    return max(item.priorite, item.projet_priorite)


def bande(item, J, n_ouvres):
    """k1 : 1, 2 ou 3 (regles.md §3.2)."""
    ech = echeance_de(item)
    p = pmax(item)
    if item.type == ACTIVITE and ech is not None and ech <= J:
        return 1
    if ech == J or (ech is not None and ech < J and p == HAUTE):
        return 1
    if ech is not None and ech > J and (n_ouvres or 0) <= 3:
        return 2
    if p == HAUTE and (ech is None or ech <= J + timedelta(days=14)):
        return 2
    return 3


def cle_tri(item, J, n_ouvres):
    """Clé d'un ordre TOTAL strict ; `n_ouvres` = jours travaillés d, J < d ≤ échéance."""
    ech = echeance_de(item)
    priorite = 0 if item.type == ACTIVITE else item.priorite
    return (
        bande(item, J, n_ouvres),
        ech or date.max,
        -pmax(item),
        -priorite,
        (item.rang_jour is None, item.rang_jour),
        (item.created_at is None, item.created_at),
        (0 if item.type == TACHE else 1, item.id),
    )


def cle_tri_pour(J, travailles):
    """Fonction clé prête pour `sorted` : calcule `n_ouvres` de chaque élément."""
    def cle(item):
        return cle_tri(item, J, n_travailles(J, echeance_de(item), travailles))
    return cle


def trier(items, J, travailles):
    """Les éléments dans l'ordre de `cle_tri`."""
    return sorted(items, key=cle_tri_pour(J, travailles))


def cle_section(item, J, travailles):
    """Ordre dans une section du jour (§3.1, inv. 32) : à heure d'abord, puis `rang_jour`, puis `cle_tri`."""
    heure = item.heure_debut
    return (
        heure is None, heure,
        item.rang_jour is None, item.rang_jour,
        cle_tri_pour(J, travailles)(item),
    )


# --- Ce qui presse, candidates, À revoir (regles.md §3.4, §4.2) -------------

def _dans(d, debut, fin):
    return d is not None and debut <= d <= fin


def raison_presse(item, J, travailles):
    """`retard`, `echeance_passee`, `echeance_proche` (dans cet ordre) ou None."""
    if _dans(item.jour_prevu, J - timedelta(days=7), J - timedelta(days=1)):
        return RaisonPropose.RETARD
    if _dans(item.echeance, J - timedelta(days=7), J - timedelta(days=1)):
        return RaisonPropose.ECHEANCE_PASSEE
    limite = nieme_travaille(J, 2, travailles)
    ech = item.echeance
    if ech is not None and J < ech <= limite:
        if item.jour_prevu is None or item.jour_prevu > ech:
            return RaisonPropose.ECHEANCE_PROCHE
    return None


def gardee_aujourdhui(item, J):
    """Tâche gardée du jour : `jour_prevu` = J ou `echeance` = J."""
    return item.jour_prevu == J or item.echeance == J


def reportee_3_fois(item, J):
    """reports ≥ reports_tranches + 3 ∧ jour_prevu ≤ J."""
    return (item.reports >= item.reports_tranches + 3
            and item.jour_prevu is not None and item.jour_prevu <= J)


def motif_revoir(item, J):
    """Motif d'À revoir d'un élément ouvert (§4.2 cas 3, 4, 5 ; activité passée), sinon None."""
    if item.type == ACTIVITE:
        due = echeance_de(item)
        return MotifRevoir.ACTIVITE_PASSEE if due is not None and due < J else None
    if item.statut != StatutTache.A_FAIRE:
        return None
    if reportee_3_fois(item, J):
        return MotifRevoir.REPORTEE_3_FOIS
    if gardee_aujourdhui(item, J):
        return None
    vieux = J - timedelta(days=7)
    if (item.jour_prevu is not None and item.jour_prevu < vieux) or (
            item.echeance is not None and item.echeance < vieux):
        return MotifRevoir.RETARD_ANCIEN
    return None


def dans_prefiltre(item):
    """Préfiltre de la journée (inv. 10) hors statut : parent nul, non bloquée, projet ou triée."""
    if item.parent_id is not None or item.bloquee_par is not None:
        return False
    return item.projet_id is not None or item.triee_le is not None


def est_candidate(item, J):
    """Candidate de Proposé (§3.4) : tâche à faire, éligible, non gardée, sans motif d'À revoir."""
    return (item.type == TACHE and item.statut == StatutTache.A_FAIRE
            and not item.quelque_jour and dans_prefiltre(item)
            and not gardee_aujourdhui(item, J) and motif_revoir(item, J) is None)


# --- placer (regles.md §4.2) ------------------------------------------------

def _ligne_essentielle(item, plan):
    if plan is None:
        return False
    for ligne in plan.lignes:
        cible = ligne.tache_id if item.type == TACHE else ligne.activite_id
        if cible == item.id and ligne.essentielle:
            return True
    return False


def _placer_activite(item, J):
    due = echeance_de(item)
    if due == J:
        return Placement(SectionJournee.JOURNEE)
    if due is not None and due < J:
        return Placement(SectionJournee.A_DECIDER, MotifRevoir.ACTIVITE_PASSEE)
    return None


def _placer_du_jour(item, plan):
    if _ligne_essentielle(item, plan):
        return Placement(SectionJournee.ESSENTIEL, essentielle=True)
    if item.moment == Moment.SOIR:
        return Placement(SectionJournee.CE_SOIR)
    return Placement(SectionJournee.JOURNEE)


def placer(t, J, plan=None, travailles=frozenset()):
    """Section d'un élément le jour J (premier cas vrai de §4.2) ; None = absent."""
    if t.type == ACTIVITE:
        return _placer_activite(t, J)
    if not dans_prefiltre(t):
        return None
    if t.statut == StatutTache.FAIT:
        if t.fait_le is not None and t.fait_le.date() == J:
            return Placement(SectionJournee.FAITES, essentielle=_ligne_essentielle(t, plan))
        return None
    if t.quelque_jour:
        return None
    if t.statut == StatutTache.EN_ATTENTE:
        date_passee = any(d is not None and d <= J for d in (t.jour_prevu, t.echeance))
        return Placement(SectionJournee.EN_ATTENTE) if date_passee else None
    if t.statut != StatutTache.A_FAIRE:
        return None
    motif = motif_revoir(t, J)
    if motif == MotifRevoir.REPORTEE_3_FOIS:
        return Placement(SectionJournee.A_DECIDER, motif)
    if gardee_aujourdhui(t, J):
        return _placer_du_jour(t, plan)
    if motif is not None:
        return Placement(SectionJournee.A_DECIDER, motif)
    raison = raison_presse(t, J, travailles)
    if raison is not None:
        return Placement(SectionJournee.PROPOSE, raison)
    if t.jour_prevu is None:
        return Placement(SectionJournee.PROPOSE)
    return None


# --- Proposé : prochaine action et tour des projets (regles.md §3.4, inv. 34) ---

@dataclass(frozen=True)
class PlanPropose:
    """Sortie de `proposer_plan` (regles.md §0.1)."""
    pour_objectif: tuple = ()
    reste_nb: int = 0
    suite_par_projet: tuple = ()
    charge: dict = field(default_factory=dict)
    replie: bool = False


def cle_projet(item):
    """Ordre des projets : priorité décroissante, `rang`, `id` ; les sans-projet en dernier."""
    if item.projet_id is None:
        return (1,)
    rang = item.projet_rang
    return (0, -(item.projet_priorite or 0), rang is None, rang, item.projet_id)


def cle_ordre_projet(item):
    """Ordre à l'intérieur d'un projet : `rang_projet`, puis `id`."""
    return (item.rang_projet is None, item.rang_projet, item.id)


def prochaine_action(taches_du_projet):
    """Première tâche `a_faire` non bloquée, hors En réserve, `parent` nul, dans l'ordre du projet."""
    ouvertes = [t for t in taches_du_projet
                if t.type == TACHE and t.statut == StatutTache.A_FAIRE and t.bloquee_par is None
                and not t.quelque_jour and t.parent_id is None]
    return min(ouvertes, key=cle_ordre_projet) if ouvertes else None


def files_par_projet(pool):
    """((projet_id, file triée), …) dans l'ordre des projets ; les sans-projet forment la dernière file."""
    groupes = {}
    for item in sorted(pool, key=lambda i: (cle_projet(i), cle_ordre_projet(i))):
        groupes.setdefault(item.projet_id, []).append(item)
    return tuple((projet, tuple(file)) for projet, file in groupes.items())


def tour_des_projets(pool, n=None):
    """((item, raison), …) : la 1re de chaque file, puis la 2e de chaque file… ; `n` premières si donné."""
    files = [file for _, file in files_par_projet(pool)]
    sortie, rang = [], 0
    while any(rang < len(file) for file in files):
        raison = RaisonPropose.PROCHAINE_ACTION if rang == 0 else RaisonPropose.ACTION_SUIVANTE
        sortie.extend((file[rang], raison) for file in files if rang < len(file))
        rang += 1
    return tuple(sortie if n is None else sortie[:max(0, n)])


def places(objectif, faites, gardees_ouvertes):
    """N = max(0, objectif − faites − gardées ouvertes) ; objectif nul (`libre`) : 5 (IR19)."""
    cible = OBJECTIF_LIBRE if objectif is None else objectif
    return max(0, cible - faites - gardees_ouvertes)


def ce_qui_presse(candidates, J, travailles):
    """((item, raison), …) triés par (rang de la raison, `cle_tri`)."""
    rangs = {raison: rang for rang, raison in enumerate(RaisonPropose)}
    cle = cle_tri_pour(J, travailles)
    lignes = [(i, raison_presse(i, J, travailles)) for i in candidates]
    lignes = [(i, r) for i, r in lignes if r is not None]
    return tuple(sorted(lignes, key=lambda ligne: (rangs[ligne[1]], cle(ligne[0]))))


def _tete_et_tour(candidates, J, travailles, inclure):
    """(presse, inclus, tour) : le tour ne porte que les candidates à `jour_prevu` nul (IR25)."""
    presse = ce_qui_presse(candidates, J, travailles)
    deja = {i.id for i, _ in presse}
    tour = tour_des_projets(i for i in candidates if i.id not in deja and i.jour_prevu is None)
    raisons = {i.id: r for i, r in tour}
    inclus = tuple((i, raisons.get(i.id, RaisonPropose.ACTION_SUIVANTE)) for i in candidates
                   if i.id in inclure and i.id not in deja)
    pris_inclus = {i.id for i, _ in inclus}
    return presse, inclus, tuple(ligne for ligne in tour if ligne[0].id not in pris_inclus)


def _suite_par_projet(candidates, pris):
    """Toutes les candidates non prises, prévues plus tard comprises, groupées par projet."""
    return files_par_projet(i for i in candidates if i.id not in pris)


def _charge(gardees, proposees, disponible_minutes):
    """Charge montrée à côté de « Garder ces N » (jamais un filtre, IR24)."""
    taches = list(gardees) + list(proposees)
    minutes = sum(t.estimation_minutes or 0 for t in taches)
    sans = sum(1 for t in taches if t.estimation_minutes is None)
    return {
        'minutes_estimees': minutes,
        'sans_estimation': sans,
        'surcharge': disponible_minutes is not None and minutes > disponible_minutes,
        'non_calculable': 2 * sans > len(taches),
    }


def taches_gardees(items, J, plan=None, travailles=frozenset()):
    """Tâches ouvertes d'Essentiel, Prévu et Ce soir."""
    sortie = []
    for item in items:
        placement = placer(item, J, plan, travailles)
        if item.type == TACHE and placement is not None and placement.section in SECTIONS_GARDEES:
            sortie.append(item)
    return tuple(sortie)


def proposer_plan(items, J, travailles, objectif, faites, gardees_ouvertes,
                  exclure=(), inclure=(), plan=None, disponible_minutes=None):
    """Proposé (regles.md §3.4) : ce qui presse en entier, puis le tour des projets jusqu'à N."""
    exclure, inclure = set(exclure), set(inclure)
    candidates = [i for i in items if est_candidate(i, J) and i.id not in exclure]
    gardees = taches_gardees(items, J, plan, travailles)
    if plan is not None and plan.allege_le is not None:
        return PlanPropose(suite_par_projet=_suite_par_projet(candidates, set()),
                           charge=_charge(gardees, (), disponible_minutes), replie=True)
    presse, inclus, tour = _tete_et_tour(candidates, J, travailles, inclure)
    reste = max(0, places(objectif, faites, gardees_ouvertes) - len(presse) - len(inclus))
    pour_objectif = presse + inclus + tour[:reste]
    return PlanPropose(
        pour_objectif=pour_objectif,
        reste_nb=len(tour) - len(tour[:reste]),
        suite_par_projet=_suite_par_projet(candidates, {i.id for i, _ in pour_objectif}),
        charge=_charge(gardees, (i for i, _ in pour_objectif), disponible_minutes),
    )


# --- « Aide-moi à prioriser » (regles.md §12, A18-M3 b) ---------------------

ESSENTIELS_MAX = 3


@dataclass(frozen=True)
class Priorites:
    """Sortie de `classer_priorites` : (item, raison ou motif) dans l'ordre, et les gestes de la carte."""
    lignes: tuple = ()
    garder_n: int = 0
    plus_tard: date | None = None
    essentiels: tuple = ()


def plus_tard(J, travailles):
    """Prochain jour travaillé après J dans la même semaine (lun.-dim.), sinon le premier qui suit."""
    dimanche = J + timedelta(days=6 - J.weekday())
    suivants = sorted(d for d in travailles if d > J)
    dans_la_semaine = [d for d in suivants if d <= dimanche]
    if dans_la_semaine:
        return dans_la_semaine[0]
    return suivants[0] if suivants else None


def _a_revoir(items, J, travailles):
    """Tâches d'À revoir avec leur motif, dans l'ordre de `cle_tri` (§3.1)."""
    lignes = []
    for item in items:
        placement = placer(item, J, None, travailles)
        if item.type == TACHE and placement is not None and placement.section == SectionJournee.A_DECIDER:
            lignes.append((item, placement.code))
    cle = cle_tri_pour(J, travailles)
    return tuple(sorted(lignes, key=lambda ligne: cle(ligne[0])))


def _essentiels_suggeres(premieres, plan):
    """Au plus 3 essentielles en tout : les premières lignes à garder, moins celles déjà choisies."""
    deja = sum(1 for ligne in (plan.lignes if plan is not None else ()) if ligne.essentielle)
    return tuple(i.id for i, _ in premieres[:max(0, ESSENTIELS_MAX - deja)])


def classer_priorites(items, J, travailles, objectif, faites, gardees_ouvertes, plan=None):
    """Toutes les tâches ouvertes non gardées : ce qui presse, le tour SANS limite, puis À revoir."""
    candidates = [i for i in items if est_candidate(i, J)]
    presse, _, tour = _tete_et_tour(candidates, J, travailles, set())
    propose = proposer_plan(items, J, travailles, objectif, faites, gardees_ouvertes, plan=plan)
    garder_n = len(propose.pour_objectif)
    lignes = presse + tour + _a_revoir(items, J, travailles)
    return Priorites(
        lignes=lignes,
        garder_n=garder_n,
        plus_tard=plus_tard(J, travailles),
        essentiels=_essentiels_suggeres(lignes[:garder_n], plan),
    )


# --- Explication des lignes hors Proposé (regles.md §3.5) -------------------

def _fait_de_date(item, J, travailles):
    """Le fait daté d'une ligne : état, puis échéance, puis jour prévu (premier vrai)."""
    ech = echeance_de(item)
    if reportee_3_fois(item, J):
        return ('reportee_3_fois', None)
    if item.statut == StatutTache.EN_ATTENTE:
        return ('en_attente', None)
    if item.type == ACTIVITE:
        return ('activite_du_jour', None) if ech == J else None
    if ech == J:
        return ('echeance_aujourdhui', None)
    if ech is not None and ech < J:
        return ('echeance_depassee', ech)
    if ech is not None:
        n = n_travailles(J, ech, travailles)
        return ('echeance_proche', (ech, n)) if n <= 3 else ('echeance_lointaine', ech)
    if item.jour_prevu == J:
        return ('prevue_ce_soir', None) if item.moment == Moment.SOIR else ('prevue_aujourdhui', None)
    if item.jour_prevu is not None and item.jour_prevu < J:
        return ('prevue_passee', item.jour_prevu)
    return None


def _fait_de_priorite(item):
    """Le fait de priorité : projet de la semaine, projet prioritaire, priorité haute ou moyenne."""
    if item.type == ACTIVITE:
        return None
    if item.focus:
        return ('projet_de_la_semaine', item.projet_id)
    if (item.projet_priorite or 0) == HAUTE and item.priorite < HAUTE:
        return ('projet_prioritaire', item.projet_id)
    if item.priorite == HAUTE:
        return ('priorite_haute', None)
    if item.priorite == 2:
        return ('priorite_moyenne', None)
    return None


def explication(item, J, travailles=frozenset()):
    """≤ 3 faits (code, valeur), dans l'ordre de textes.md §2.2 ; le texte est rendu par les gabarits."""
    faits = [f for f in (_fait_de_date(item, J, travailles), _fait_de_priorite(item)) if f is not None]
    if not faits:
        faits.append(('dans_projet', item.projet_id) if item.projet_id is not None else ('sans_projet', None))
    return tuple(faits[:3])


# --- Capacité et temps disponible (regles.md §3.6, inv. 35) -----------------

def capacite(reglage, minutes_9j, jours_28, comprendre=True):
    """(minutes, source) : réglage, sinon médiane des 9 derniers jours travaillés, sinon 240."""
    if reglage is not None:
        return reglage, CapaciteSource.REGLAGE
    if comprendre and jours_28 >= 5 and minutes_9j:
        return arrondir(statistics.median(minutes_9j[-9:])), CapaciteSource.HISTORIQUE
    return CAPACITE_DEFAUT, CapaciteSource.DEFAUT


def temps_disponible(capacite_minutes, rendez_vous_minutes):
    """`disponible_minutes` = max(0, capacité − rendez-vous)."""
    return max(0, capacite_minutes - rendez_vous_minutes)
