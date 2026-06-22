"""Services (écritures/orchestration) de la Gestion de projet.

Point d'entrée des écritures internes au module. ``company`` est toujours
dérivée du ``projet`` (jamais lue d'un corps de requête) ; aucun import
cross-app (on reste dans ``gestion_projet``).
"""
from datetime import timedelta

from django.db import transaction

from .models import (
    BaselinePlanning,
    BaselineTache,
    DependanceTache,
    PhaseProjet,
    Projet,
    Tache,
)


# Décomposition standard d'un projet d'installation solaire (WBS), dans l'ordre
# de réalisation. PROPRE à ce module — ne réutilise aucune clé de STAGES.py.
PHASES_STANDARD = [
    (PhaseProjet.TypePhase.ETUDE, 'Étude'),
    (PhaseProjet.TypePhase.APPRO, 'Approvisionnement'),
    (PhaseProjet.TypePhase.POSE, 'Pose'),
    (PhaseProjet.TypePhase.MES, 'Mise en service'),
    (PhaseProjet.TypePhase.RECEPTION, 'Réception'),
]


def instancier_phases_standard(projet):
    """Crée les 5 phases standard d'un ``Projet``, dans l'ordre — IDEMPOTENT.

    Une phase n'est créée que si elle n'existe pas déjà (clé
    ``(projet, type_phase)``) : un second appel ne duplique rien et laisse
    intactes les phases déjà présentes (statut/dates/avancement édités). La
    société est toujours celle du ``projet`` (jamais lue d'un corps de requête).
    Renvoie la liste complète des phases du projet, ordonnée par ``ordre``.
    """
    if not isinstance(projet, Projet):  # pragma: no cover - garde-fou
        raise TypeError('projet doit être une instance de Projet.')
    existants = set(
        projet.phases.values_list('type_phase', flat=True))
    a_creer = []
    for ordre, (type_phase, libelle) in enumerate(PHASES_STANDARD, start=1):
        if type_phase in existants:
            continue
        a_creer.append(PhaseProjet(
            company=projet.company,
            projet=projet,
            type_phase=type_phase,
            libelle=libelle,
            ordre=ordre,
        ))
    if a_creer:
        PhaseProjet.objects.bulk_create(a_creer)
    return list(projet.phases.order_by('ordre', 'id'))


# ── Drag-reschedule (PROJ11) ─────────────────────────────────────────────────

class RescheduleError(Exception):
    """Erreur métier de re-planification (ex. dates incohérentes, cycle)."""


def _duree_jours(tache):
    """Durée d'une tâche en jours (≥ 1) à partir de ses dates prévues.

    Si la tâche n'a pas encore de dates, retombe sur ``charge_estimee`` arrondie
    au jour supérieur (≥ 1), sinon 1 — même convention que le CPM (``cpm.py``).
    """
    deb = tache.date_debut_prevue
    fin = tache.date_fin_prevue
    if deb is not None and fin is not None:
        return max(1, (fin - deb).days)
    charge = tache.charge_estimee
    if charge is not None and charge > 0:
        import math
        return max(1, int(math.ceil(float(charge))))
    return 1


def _contrainte_debut_min(type_dep, lag, pred_debut, pred_fin, duree_succ):
    """Début AU PLUS TÔT du successeur imposé par UNE arête (en date).

    Renvoie la date de DÉBUT minimale du successeur pour respecter l'arête
    ``type_dep`` (+ ``lag`` jours) sachant le début/fin du prédécesseur et la
    durée du successeur. Mêmes règles que le CPM, transposées en calendrier.
    """
    lag_d = timedelta(days=lag)
    dur = timedelta(days=duree_succ)
    if type_dep == DependanceTache.TypeDependance.FS:
        return pred_fin + lag_d                     # début ≥ fin préd. + lag
    if type_dep == DependanceTache.TypeDependance.SS:
        return pred_debut + lag_d                   # début ≥ début préd. + lag
    if type_dep == DependanceTache.TypeDependance.FF:
        return pred_fin + lag_d - dur               # fin ≥ fin préd. + lag
    # SF : fin ≥ début préd. + lag
    return pred_debut + lag_d - dur


@transaction.atomic
def reprogrammer_tache(tache, nouvelle_date_debut, nouvelle_date_fin=None):
    """Déplace une tâche (drag) et POUSSE ses successeurs en cascade.

    Pose le nouveau créneau de ``tache`` (``date_debut_prevue`` /
    ``date_fin_prevue``) puis propage en aval : chaque successeur dont le créneau
    actuel VIOLE désormais sa contrainte (FS/SS/FF/SF + lag) est décalé au plus
    tôt admissible, en CONSERVANT sa durée. La propagation ne fait que POUSSER
    (jamais tirer une tâche plus tôt) : un successeur déjà assez tard n'est pas
    touché. Toutes les écritures sont dans une transaction atomique.

    ``nouvelle_date_fin`` est optionnelle : si absente, on conserve la durée
    courante de la tâche (ou 1 jour à défaut). Renvoie la liste ORDONNÉE des
    tâches modifiées (la tâche déplacée d'abord, puis les successeurs décalés).

    Garde-fous : ``nouvelle_date_fin`` doit être ≥ ``nouvelle_date_debut`` ; un
    cycle dans le sous-graphe aval lève ``RescheduleError`` (sécurité, au-delà
    des cycles directs déjà refusés à l'écriture).
    """
    if nouvelle_date_debut is None:
        raise RescheduleError('La nouvelle date de début est obligatoire.')
    if nouvelle_date_fin is None:
        duree = _duree_jours(tache)
        nouvelle_date_fin = nouvelle_date_debut + timedelta(days=duree)
    if nouvelle_date_fin < nouvelle_date_debut:
        raise RescheduleError(
            'La date de fin ne peut pas précéder la date de début.')

    projet = tache.projet
    company = tache.company

    # Charge tout le graphe du projet en mémoire (scopé société).
    taches = {
        t.id: t for t in Tache.objects.filter(
            projet=projet, company=company)
    }
    deps = list(DependanceTache.objects.filter(
        predecesseur__projet=projet, company=company))
    succ_par_pred = {}   # pred_id -> [dep]
    pred_par_succ = {}   # succ_id -> [dep]
    for dep in deps:
        succ_par_pred.setdefault(dep.predecesseur_id, []).append(dep)
        pred_par_succ.setdefault(dep.successeur_id, []).append(dep)

    # Pose le nouveau créneau de la tâche déplacée.
    tache.date_debut_prevue = nouvelle_date_debut
    tache.date_fin_prevue = nouvelle_date_fin
    taches[tache.id].date_debut_prevue = nouvelle_date_debut
    taches[tache.id].date_fin_prevue = nouvelle_date_fin

    modifies = {tache.id: tache}
    ordre_modifies = [tache.id]

    # Propagation BFS en aval avec garde anti-boucle (au plus N² relâches).
    file = [tache.id]
    max_iter = (len(taches) + 1) ** 2 + 1
    iters = 0
    while file:
        iters += 1
        if iters > max_iter:
            raise RescheduleError(
                'Cycle détecté dans le sous-graphe des successeurs.')
        courant = file.pop(0)
        cur = taches[courant]
        if cur.date_debut_prevue is None or cur.date_fin_prevue is None:
            continue
        for dep in succ_par_pred.get(courant, ()):
            succ = taches[dep.successeur_id]
            dur_succ = _duree_jours(succ)
            debut_min = _contrainte_debut_min(
                dep.type_dependance, dep.lag,
                cur.date_debut_prevue, cur.date_fin_prevue, dur_succ)
            debut_actuel = succ.date_debut_prevue
            # Ne POUSSE que si le créneau actuel viole la contrainte (ou est
            # absent) ; ne tire jamais un successeur plus tôt.
            if debut_actuel is not None and debut_actuel >= debut_min:
                continue
            succ.date_debut_prevue = debut_min
            succ.date_fin_prevue = debut_min + timedelta(days=dur_succ)
            if succ.id not in modifies:
                modifies[succ.id] = succ
                ordre_modifies.append(succ.id)
            file.append(succ.id)

    for t in modifies.values():
        t.save(update_fields=['date_debut_prevue', 'date_fin_prevue'])

    return [taches[i] for i in ordre_modifies]


# ── Baseline de planning (PROJ13) ────────────────────────────────────────────

@transaction.atomic
def creer_baseline(projet, libelle='', auteur=None):
    """Crée une BASELINE figée du planning courant d'un ``Projet``.

    Capture, pour CHAQUE tâche du projet, son créneau prévu
    (``date_debut_prevue`` / ``date_fin_prevue``) et sa ``charge_estimee`` dans
    des lignes ``BaselineTache`` (libellé/code WBS figés pour survivre à une
    suppression de tâche). ``company`` est toujours celle du ``projet`` (jamais
    lue d'un corps de requête) ; ``auteur`` est posé côté serveur. Écritures
    atomiques. Renvoie la ``BaselinePlanning`` créée.
    """
    if not isinstance(projet, Projet):  # pragma: no cover - garde-fou
        raise TypeError('projet doit être une instance de Projet.')
    baseline = BaselinePlanning.objects.create(
        company=projet.company,
        projet=projet,
        libelle=libelle or '',
        auteur=auteur,
    )
    taches = Tache.objects.filter(projet=projet, company=projet.company)
    lignes = [
        BaselineTache(
            company=projet.company,
            baseline=baseline,
            tache=t,
            tache_libelle=t.libelle,
            tache_code_wbs=t.code_wbs,
            date_debut_prevue=t.date_debut_prevue,
            date_fin_prevue=t.date_fin_prevue,
            charge_estimee=t.charge_estimee,
        )
        for t in taches
    ]
    if lignes:
        BaselineTache.objects.bulk_create(lignes)
    return baseline
