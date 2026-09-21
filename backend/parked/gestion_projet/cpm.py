"""Calcul du chemin critique (CPM) d'un projet — PROJ8.

Méthode du chemin critique (Critical Path Method) en JOURS sur le graphe des
tâches d'un ``Projet`` et de leurs ``DependanceTache`` (FS/SS/FF/SF + lag).
Lecture seule : on ne MODIFIE aucune donnée — on calcule des dates au plus tôt
/ au plus tard et les MARGES (totale/libre), puis on en déduit l'ensemble des
tâches CRITIQUES (marge totale nulle).

Modèle de durée d'une tâche
---------------------------
La tâche n'a pas de champ « durée » propre : on la DÉRIVE, dans cet ordre,
- si ``date_debut_prevue`` ET ``date_fin_prevue`` sont posées : le nombre de
  jours entre les deux (au moins 1) ;
- sinon, ``charge_estimee`` (jours-homme) arrondie au jour supérieur (au moins
  1 si > 0) ;
- sinon : durée par défaut de 1 jour.

Repère temporel
---------------
Le CPM travaille en JOURS RELATIFS (entiers ≥ 0) à partir d'un instant 0 — pas
en dates calendaires : le calendrier ouvré/fériés (PROJ12) viendra par-dessus.
Seules les tâches FEUILLES (sans sous-tâches) entrent dans le réseau : une tâche
parente est un conteneur WBS, sa durée/avancement se déduit de ses enfants
(PROJ9) et ne porte pas de planning propre. Les dépendances pointant vers/depuis
un conteneur sont ignorées du réseau (rare en pratique).

Garde-fou cycles
----------------
Le tri topologique détecte un éventuel cycle (au-delà des cycles directs déjà
refusés à l'écriture) : en cas de cycle, on renvoie ``has_cycle=True`` et des
marges vides plutôt que de boucler indéfiniment.
"""
import math

from .models import DependanceTache, Tache


def duree_jours(tache):
    """Durée d'une tâche en JOURS (entier ≥ 1), dérivée comme décrit ci-dessus."""
    deb = tache.date_debut_prevue
    fin = tache.date_fin_prevue
    if deb is not None and fin is not None:
        return max(1, (fin - deb).days)
    charge = tache.charge_estimee
    if charge is not None and charge > 0:
        return max(1, int(math.ceil(float(charge))))
    return 1


def _leaf_taches(projet):
    """Tâches FEUILLES du projet (celles sans sous-tâche), indexées par id."""
    taches = list(
        Tache.objects.filter(projet=projet, company=projet.company))
    avec_enfant = set(
        t.parent_id for t in taches if t.parent_id is not None)
    return {t.id: t for t in taches if t.id not in avec_enfant}


def _aretes(projet, ids_valides):
    """Arêtes de dépendance du projet restreintes aux tâches feuilles."""
    qs = DependanceTache.objects.filter(
        predecesseur__projet=projet, company=projet.company)
    out = []
    for dep in qs:
        if dep.predecesseur_id in ids_valides \
                and dep.successeur_id in ids_valides:
            out.append(dep)
    return out


def _tri_topologique(ids, succ_par_pred):
    """Tri topologique (Kahn). Renvoie (ordre, has_cycle)."""
    indeg = {i: 0 for i in ids}
    for pred, succs in succ_par_pred.items():
        for s in succs:
            indeg[s] += 1
    file = [i for i in ids if indeg[i] == 0]
    ordre = []
    while file:
        n = file.pop(0)
        ordre.append(n)
        for s in succ_par_pred.get(n, ()):  # successeurs de n
            indeg[s] -= 1
            if indeg[s] == 0:
                file.append(s)
    has_cycle = len(ordre) != len(ids)
    return ordre, has_cycle


def calculer_cpm(projet):
    """Calcule le CPM du projet. Renvoie un dict prêt à sérialiser.

    Structure renvoyée ::

        {
          'duree_projet': int,          # durée totale (jours) du chemin critique
          'has_cycle': bool,            # True si un cycle empêche le calcul
          'chemin_critique': [id, ...], # ids des tâches critiques (ordre topo)
          'taches': [                   # une entrée par tâche feuille
             {'tache': id, 'libelle': str, 'code_wbs': str,
              'duree': int, 'es': int, 'ef': int, 'ls': int, 'lf': int,
              'marge_totale': int, 'marge_libre': int, 'critique': bool},
             ...
          ],
        }

    ``es/ef`` = early start/finish, ``ls/lf`` = late start/finish (jours relatifs).
    Une tâche est CRITIQUE quand sa ``marge_totale`` (ls − es) est nulle.
    """
    feuilles = _leaf_taches(projet)
    ids = list(feuilles.keys())
    if not ids:
        return {'duree_projet': 0, 'has_cycle': False,
                'chemin_critique': [], 'taches': []}

    aretes = _aretes(projet, set(ids))
    # Index des arêtes : par successeur (pour le forward pass) et par
    # prédécesseur (pour le backward pass + tri topo).
    entrantes = {i: [] for i in ids}   # successeur -> [dep]
    sortantes = {i: [] for i in ids}   # prédécesseur -> [dep]
    succ_par_pred = {i: [] for i in ids}
    for dep in aretes:
        entrantes[dep.successeur_id].append(dep)
        sortantes[dep.predecesseur_id].append(dep)
        succ_par_pred[dep.predecesseur_id].append(dep.successeur_id)

    ordre, has_cycle = _tri_topologique(ids, succ_par_pred)
    if has_cycle:
        return {'duree_projet': 0, 'has_cycle': True,
                'chemin_critique': [], 'taches': []}

    duree = {i: duree_jours(feuilles[i]) for i in ids}
    es = {i: 0 for i in ids}
    ef = {i: 0 for i in ids}

    # ── Forward pass : early start/finish selon le type de contrainte ────────
    for i in ordre:
        start = 0
        for dep in entrantes[i]:
            p = dep.predecesseur_id
            lag = dep.lag
            t = dep.type_dependance
            if t == DependanceTache.TypeDependance.FS:
                cand = ef[p] + lag            # début ≥ fin du préd. + lag
            elif t == DependanceTache.TypeDependance.SS:
                cand = es[p] + lag            # début ≥ début du préd. + lag
            elif t == DependanceTache.TypeDependance.FF:
                cand = ef[p] + lag - duree[i]  # fin ≥ fin du préd. + lag
            else:  # SF : fin ≥ début du préd. + lag
                cand = es[p] + lag - duree[i]
            if cand > start:
                start = cand
        if start < 0:
            start = 0
        es[i] = start
        ef[i] = start + duree[i]

    duree_projet = max(ef.values()) if ef else 0

    # ── Backward pass : late finish/start ────────────────────────────────────
    lf = {i: duree_projet for i in ids}
    ls = {i: duree_projet for i in ids}
    for i in reversed(ordre):
        finish = duree_projet
        if sortantes[i]:
            finish = None
            for dep in sortantes[i]:
                s = dep.successeur_id
                lag = dep.lag
                t = dep.type_dependance
                if t == DependanceTache.TypeDependance.FS:
                    cand = ls[s] - lag                 # fin ≤ début succ. − lag
                elif t == DependanceTache.TypeDependance.SS:
                    cand = ls[s] - lag + duree[i]      # début ≤ début succ. − lag
                elif t == DependanceTache.TypeDependance.FF:
                    cand = lf[s] - lag                 # fin ≤ fin succ. − lag
                else:  # SF : début ≤ fin succ. − lag
                    cand = lf[s] - lag + duree[i]
                finish = cand if finish is None else min(finish, cand)
        lf[i] = finish
        ls[i] = finish - duree[i]

    # ── Marges ───────────────────────────────────────────────────────────────
    # Marge totale = ls − es. Marge libre = (min ES des successeurs FS/SS,
    # ajusté du lag) − EF de la tâche, jamais négative.
    out = []
    critiques = []
    for i in ordre:
        marge_totale = ls[i] - es[i]
        # Marge libre : combien la tâche peut glisser sans décaler le premier
        # successeur (en ES). Si aucun successeur : marge libre = marge totale.
        if sortantes[i]:
            libre = None
            for dep in sortantes[i]:
                s = dep.successeur_id
                lag = dep.lag
                t = dep.type_dependance
                if t == DependanceTache.TypeDependance.FS:
                    slack = es[s] - lag - ef[i]
                elif t == DependanceTache.TypeDependance.SS:
                    slack = es[s] - lag - es[i]
                elif t == DependanceTache.TypeDependance.FF:
                    slack = ef[s] - lag - ef[i]
                else:  # SF
                    slack = ef[s] - lag - es[i]
                libre = slack if libre is None else min(libre, slack)
            marge_libre = max(0, libre)
        else:
            marge_libre = max(0, marge_totale)
        critique = marge_totale <= 0
        if critique:
            critiques.append(i)
        t = feuilles[i]
        out.append({
            'tache': i,
            'libelle': t.libelle,
            'code_wbs': t.code_wbs,
            'duree': duree[i],
            'es': es[i],
            'ef': ef[i],
            'ls': ls[i],
            'lf': lf[i],
            'marge_totale': marge_totale,
            'marge_libre': marge_libre,
            'critique': critique,
        })

    return {
        'duree_projet': duree_projet,
        'has_cycle': False,
        'chemin_critique': critiques,
        'taches': out,
    }
