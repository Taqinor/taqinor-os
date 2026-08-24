#!/usr/bin/env python3
"""WOW6 / WOW-CI2 — deterministic, DURATION-BALANCED backend-test sharding for CI.

Usage
-----
    python scripts/ci_shard.py <shard_index> <shard_total>   # labels for one shard
    python scripts/ci_shard.py --plan <shard_total>          # human balance table
    python scripts/ci_shard.py --update-timings <log>...     # refresh the timing table

WHY THIS WAS REWRITTEN (18/08/2026, run 32182877239)
----------------------------------------------------
The first version split at APP granularity, round-robin over the sorted app list
(``i % total``). Sorting by name has nothing to do with cost, so the split was
blind: on the 6-way run, ``ci_shard.py 2 6`` handed ONE lane both heavyweights —
``apps.crm`` AND ``apps.ventes`` — plus eleven small apps. That lane was still
running (>9 min of tests) while its siblings had finished in 1 min 44 s to
5 min 48 s. Since wall-clock = setup + the WORST lane, the whole backend gate was
priced by that one accident of alphabetical order.

App granularity could not fix it either: ``apps.ventes`` alone carries ~240 test
modules and is heavier than several entire sibling shards, so no assignment of
whole apps can balance it. Two changes fix that for good:

1. **The unit is a test MODULE, not an app.** Django accepts dotted module labels
   (``apps.ventes.tests.test_pdf``), so a heavy app is spread across lanes
   instead of pinning one. Discovery uses Django's own default pattern
   (``test*.py``, any depth) so the union of the lanes is exactly what an
   unsharded ``test apps authentication core`` would have run — including the
   files that are NOT inside a ``tests/`` package (``apps/ventes/tests_qj9_*.py``)
   and those named ``tests_*.py`` rather than ``test_*.py``.
2. **Placement is LPT (longest-processing-time-first) over MEASURED durations**,
   not round-robin. Units are sorted heaviest-first and each is placed on the
   lane that is currently lightest — the classic greedy makespan heuristic, which
   is provably within 4/3 of optimal and, with units this small, lands much
   closer.

COMPLETENESS IS A TEST, NOT A PROMISE. ``scripts/tests/test_ci_shard.py`` asserts
that the union of every lane equals the full discovered unit set, with no
duplicates and nothing dropped, for several shard totals. A module that silently
fell out of the split would mean tests that no longer run while CI stays green —
the worst possible failure for a gate. That test runs in the ``stage-names`` job.

THE TIMING TABLE — ``scripts/ci_shard_timings.json``
----------------------------------------------------
``{"<dotted label>": <seconds>}``. It is an OPTIMISATION INPUT ONLY: it can never
change WHICH tests run, only which lane they land on. A stale or missing entry
costs balance, never correctness — so it is refreshed manually, on demand, and
never blocks a build.

To refresh it after the suite has grown noticeably, take a green CI run and:

    # one log per backend-tests shard (the ids come from `gh run view <run>`)
    for j in <job-id>...; do \
      gh api repos/Taqinor/taqinor-os/actions/jobs/$j/logs > /tmp/shard-$j.log; done
    python scripts/ci_shard.py --update-timings /tmp/shard-*.log

The parser reads the ``-v 2`` runner output, whose every line carries the runner's
ISO timestamp, and attributes the elapsed wall time between consecutive test lines
to the module that owns the earlier one. Unmeasured modules fall back to a
static weight (their test-method count), which is a decent proxy until measured.
"""
from __future__ import annotations

import argparse
import ast
import functools
import json
import os
import re
import sys
from collections import defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DJANGO_ROOT = os.path.join(REPO_ROOT, "backend", "django_core")
TIMINGS_PATH = os.path.join(REPO_ROOT, "scripts", "ci_shard_timings.json")
# The most recent RAW run, kept beside the planning table so a refresh can take
# max(latest, previous) WITHOUT the value ratcheting upward forever: each refresh
# compares against exactly one prior run, never an accumulated maximum.
RAW_TIMINGS_PATH = os.path.join(REPO_ROOT, "scripts", "ci_shard_timings_raw.json")
# Volet F — durees par CLASSE de test. Sous `--parallel`, la classe est l'unite
# INDIVISIBLE : c'est elle, et non le module, qui fixe le plancher d'une lane.
CLASS_TIMINGS_PATH = os.path.join(REPO_ROOT, "scripts",
                                  "ci_shard_class_timings.json")

# Roots Django is asked to test: every package under apps/, plus the two
# foundation packages that live at the django_core root.
TOP_LEVEL = ("authentication", "core")
# Directories that never carry runnable tests.
SKIP_DIRS = {"__pycache__", "migrations", "node_modules", ".git"}

# Fallback weight for a module absent from the timing table: seconds per test
# method, floored so a module is never weightless. Calibrated on the 18/08 run
# (~27 min of tests over ~2 700 modules).
SECONDS_PER_TEST = 0.55
MIN_UNIT_SECONDS = 0.4

# Nombre de processus que `manage.py test --parallel N` lance dans CHAQUE lane.
# DOIT rester aligne sur le `PARALLEL` de l'etape « Run Django test suite » de
# `.github/workflows/ci.yml` (4, ou 1 si la garde anti-`max_locks` se declenche
# sur ce shard) : le plan est calcule pour ce parallelisme, et un ecart ne
# casserait rien (le decoupage reste complet) mais rendrait l'equilibrage faux.
# Le NOMBRE DE LANES, lui, ne vit pas ici : il est dans `matrix.shard` de ci.yml
# et passe en argument (`ci_shard.py <shard> <total>`) — 6 depuis le volet G.
DEFAULT_PARALLEL = 4

# Seuil au-dessus duquel une CLASSE est retenue dans `ci_shard_class_timings.json`.
# En dessous, elle ne peut pas etre le facteur limitant d'une lane (la charge
# moyenne d'une lane est de l'ordre de 175 s a 6 lanes) : son cout reste compte
# dans le total de son module, seule sa capacite a BORNER disparait — ce qu'elle
# n'a jamais eue.
CLASS_FLOOR_SECONDS = 1.0

# Marqueurs d'une classe « a purge large » — DOIT rester aligne sur le script
# `/tmp/purge_large.py` de l'etape « Run Django test suite » de ci.yml.
PURGE_MARQUEURS = frozenset({"TransactionTestCase", "WideTeardownTimeoutMixin"})

# WOW-CI RONDE 5 / VOLET F (20/08/2026) — LE PARALLELISME CHANGE LE COUT D'UNE
# LANE, ET LE PLANIFICATEUR L'IGNORAIT.
#
# Depuis que le palier tourne en `--parallel 4`, le temps de mur d'une lane
# n'est PLUS la somme de ses modules : Django repartit les CLASSES de test entre
# N processus (`ParallelTestSuite` decoupe par `TestCase`, jamais plus fin), donc
#
#     temps de lane ~ max( travail_total / N , plus grosse CLASSE de la lane )
#
# Une classe est INDIVISIBLE : aucun parallelisme ne la raccourcit. Le
# planificateur, lui, equilibrait le travail TOTAL et s'auto-declarait parfait
# (« desequilibre 1.00x ») pendant que la realite mesurait ~60 % d'ecart entre
# lanes. Les deux affirmations etaient vraies en meme temps, et c'est tout le
# probleme : il optimisait la mauvaise quantite.
#
# Cas reel qui l'a revele : `apps.ventes.tests.test_quote_engine_formats` pese
# 117 s dont UNE classe de ~112 s. La lane qui la recoit ne peut pas finir avant
# 112 s — ses trois autres workers tournent a vide — tandis que les cinq autres
# lanes finissent en 73 s.
#
# DEUX CONSEQUENCES, TOUTES DEUX APPLIQUEES PLUS BAS :
#  1. le cout d'une lane se calcule par un ORDONNANCEMENT de ses classes sur N
#     workers, pas par une somme ;
#  2. une lane qui porte une classe geante a de la CAPACITE LIBRE (ses autres
#     workers) : il faut lui donner PLUS de travail, pas moins. Un equilibrage
#     par somme faisait exactement l'inverse.
#
# Les poids par classe sont deduits du poids MESURE du module, reparti au
# prorata du nombre de methodes `test*` de chaque classe — meme procede que la
# repartition app -> module plus bas. C'est une approximation ; elle ne decide
# que du PLACEMENT, jamais de ce qui s'execute.
_CLASS_RE = re.compile(r"^class\s+(\w+)\s*[(:]", re.MULTILINE)
_TEST_DEF_RE = re.compile(r"^\s+(?:async\s+)?def\s+test", re.MULTILINE)
# A Django -v 2 result line: "name (dotted.path.Class.name) ... ok"
_RESULT_RE = re.compile(r"^\S*\s*\(([\w.]+)\)\s*\.\.\.")
_TS_RE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d+Z)\s?(.*)$")


def _dotted(path: str) -> str:
    """`backend/django_core/apps/x/tests/test_y.py` -> `apps.x.tests.test_y`."""
    rel = os.path.relpath(path, DJANGO_ROOT).replace(os.sep, "/")
    return rel[:-3].replace("/", ".")


def _walk_tests(base: str):
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            # Django's default discovery pattern is `test*.py` — that matches
            # `test_x.py`, `tests.py` AND `tests_x.py`. Keep it identical here,
            # or the shards would run a different set than an unsharded run.
            if name.startswith("test") and name.endswith(".py"):
                yield os.path.join(dirpath, name)


@functools.lru_cache(maxsize=None)
def _discover_cached(repo_root: str) -> tuple:
    return tuple(_discover(repo_root))


def discover_units(repo_root: str = REPO_ROOT) -> list[str]:
    """Sorted dotted labels of every discoverable test MODULE (memoised)."""
    return list(_discover_cached(repo_root))


def _discover(repo_root: str) -> list[str]:
    django_root = os.path.join(repo_root, "backend", "django_core")
    global DJANGO_ROOT
    previous, DJANGO_ROOT = DJANGO_ROOT, django_root
    try:
        units: list[str] = []
        apps_dir = os.path.join(django_root, "apps")
        if os.path.isdir(apps_dir):
            for name in sorted(os.listdir(apps_dir)):
                pkg = os.path.join(apps_dir, name)
                if not os.path.isdir(pkg):
                    continue
                if not os.path.exists(os.path.join(pkg, "__init__.py")):
                    continue
                units += [_dotted(p) for p in _walk_tests(pkg)]
        for top in TOP_LEVEL:
            top_dir = os.path.join(django_root, top)
            if os.path.isdir(top_dir):
                units += [_dotted(p) for p in _walk_tests(top_dir)]
        return sorted(set(units))
    finally:
        DJANGO_ROOT = previous


def load_timings(path: str = TIMINGS_PATH) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {k: float(v) for k, v in data.items() if isinstance(v, (int, float))}


@functools.lru_cache(maxsize=None)
def _static_test_count(unit: str, repo_root: str) -> int:
    """How many test methods the module declares (cheap regex, no import)."""
    path = os.path.join(repo_root, "backend", "django_core", *unit.split(".")) + ".py"
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return max(1, len(_TEST_DEF_RE.findall(fh.read())))
    except OSError:
        return 1


@functools.lru_cache(maxsize=None)
def _class_test_counts(unit: str, repo_root: str) -> tuple:
    """((classe, nb_tests), ...) du module — decoupage textuel, aucun import.

    Sert UNIQUEMENT a estimer la plus grosse portion indivisible du module.
    Un module sans classe reconnue est traite comme un bloc unique, ce qui est
    le choix PESSIMISTE : on suppose qu'il ne se parallelise pas.
    """
    path = os.path.join(repo_root, "backend", "django_core", *unit.split(".")) + ".py"
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            src = fh.read()
    except OSError:
        return (("", 1),)
    bornes = [(m.start(), m.group(1)) for m in _CLASS_RE.finditer(src)]
    if not bornes:
        return (("", 1),)
    out = []
    for i, (pos, nom) in enumerate(bornes):
        fin = bornes[i + 1][0] if i + 1 < len(bornes) else len(src)
        n = len(_TEST_DEF_RE.findall(src[pos:fin]))
        if n:
            out.append((nom, n))
    return tuple(out) if out else (("", 1),)


@functools.lru_cache(maxsize=1)
def load_class_timings(path: str = CLASS_TIMINGS_PATH) -> tuple:
    """Durees MESUREES par classe, sous forme hachable (pour le cache)."""
    return tuple(sorted(load_timings(path).items()))


def class_weights(unit: str, weight: float, repo_root: str = REPO_ROOT) -> list:
    """Poids des blocs INDIVISIBLES du module, mesure d'abord.

    1. si des classes de ce module ont ete MESUREES, on rend leurs durees
       telles quelles (plus le reliquat du poids du module reparti sur les
       classes non mesurees) ;
    2. sinon, le poids du module est reparti au prorata du nombre de tests.

    La difference n'est pas cosmetique : `test_gammes_offre` pesait 26 s au
    total dans l'ancienne table alors que sa seule classe `TestAcceptationGamme`
    en consommait 195 — extrapoler au prorata des tests aurait continue de la
    rendre invisible. (Volet G, 21/08/2026 : cette classe a depuis ete eclatee
    en trois modules d'un test — `test_gammes_offre_acceptation`,
    `_acceptation_signature`, `_acceptation_choix` — donc l'exemple est
    historique ; le mecanisme, lui, reste indispensable.)
    """
    return [poids for _nom, poids in class_weight_items(unit, weight, repo_root)]


def class_weight_items(unit: str, weight: float,
                       repo_root: str = REPO_ROOT) -> list:
    """`class_weights` en gardant le NOM de chaque bloc, pour les diagnostics."""
    mesures = dict(load_class_timings())
    parts = _class_test_counts(unit, repo_root)
    connues = [(nom, mesures[f"{unit}.{nom}"]) for nom, _n in parts
               if f"{unit}.{nom}" in mesures]
    if connues:
        reste = weight - sum(v for _nom, v in connues)
        inconnues = [(nom, n) for nom, n in parts
                     if f"{unit}.{nom}" not in mesures]
        total_inconnu = sum(n for _nom, n in inconnues)
        if reste > 0 and total_inconnu:
            connues += [(nom, reste * n / total_inconnu) for nom, n in inconnues]
        return connues
    total = sum(n for _n, n in parts)
    if not total:
        return [("", weight)]
    return [(nom, weight * n / total) for nom, n in parts]


def makespan(charges, workers: int = 0) -> float:
    """Temps de mur d'une lane portant ces blocs.

    ATTENTION AU SENS DES POIDS — c'est le piege de ce fichier. Les durees de
    `ci_shard_class_timings.json` sont mesurees SUR UN RUN DEJA PARALLELE
    (`--parallel 4`) : ce sont des CONTRIBUTIONS AU TEMPS DE MUR, pas du travail
    processeur. Les rediviser par le nombre de workers reviendrait a compter le
    parallelisme DEUX FOIS, et c'est ce qui produisait un plan absurde (une lane
    a 1 603 modules « pesant » 128 s).

    Le modele juste est donc :

        temps de lane = max( somme des contributions , plus grosse CLASSE )

    Le premier terme dit qu'une lane deux fois moins chargee finit deux fois
    plus vite (les 4 workers restent 4) ; le second dit qu'aucune lane ne
    descend sous sa plus grosse classe, indivisible par construction.

    Verification sur le run 32320058346, les six lanes, sans ajustement :
        shard 0 : somme 131 s, plus grosse classe 73 s -> 131 s (mesure 131 s)
        shard 2 : somme  86 s, plus grosse classe  5 s ->  86 s (mesure  86 s)
        shard 4 : somme 276 s, plus grosse classe 195 s -> 276 s (mesure 276 s)

    `workers` n'est plus utilise dans le calcul ; il reste au prototype pour ne
    pas casser les appels existants et pour documenter que la mesure a ete prise
    a ce parallelisme. Si `--parallel` change dans ci.yml, il faut REMESURER,
    pas rediviser.
    """
    charges = list(charges)
    if not charges:
        return 0.0
    return max(sum(charges), max(charges))


def app_of(unit: str) -> str:
    """`apps.ventes.tests.test_pdf` -> `apps.ventes`; `core.tests.x` -> `core`."""
    parts = unit.split(".")
    return ".".join(parts[:2]) if parts[0] == "apps" and len(parts) > 1 else parts[0]


def weigh(units, timings, repo_root: str = REPO_ROOT) -> dict:
    """Cost per unit, best available source first.

    1. a MEASURED per-module entry (what ``--update-timings`` writes);
    2. else the app's MEASURED total, shared out across its modules in
       proportion to how many test methods each declares — this is what the
       committed table holds today, because the 18/08 run reported per-app
       totals. It captures both effects that matter: how heavy the app is
       (``apps.ventes`` runs at 0.18 s/test, ``apps.ao`` at 0.024 s/test — a 7x
       spread that a flat per-test constant would get badly wrong) and how big
       the module is inside that app;
    3. else a flat per-test-method fallback, for an app nobody has measured yet.

    Weights only decide PLACEMENT. A wrong weight costs balance, never
    correctness: the union of the lanes is asserted complete by
    scripts/tests/test_ci_shard.py whatever the numbers say.
    """
    counts = {u: _static_test_count(u, repo_root) for u in units}
    per_app_counts: dict = defaultdict(int)
    for unit in units:
        per_app_counts[app_of(unit)] += counts[unit]

    weights = {}
    for unit in units:
        measured = timings.get(unit)
        if measured:
            # A MEASURED value is used as-is, with NO floor. The floor exists to
            # stop a static ESTIMATE from reading as weightless; applying it to a
            # measurement would destroy the balance it is meant to protect. Most
            # of the 2 680 modules really do run in hundredths of a second, and
            # flooring them all to the same 0.4 s would make LPT balance module
            # COUNT instead of module TIME — which is the blind split this whole
            # mechanism replaced. (Measured 2026-08-19: the floor inflated an
            # estimated total of 1 457 s to 2 232 s, i.e. 775 s of pure phantom.)
            weights[unit] = float(measured)
            continue
        app = app_of(unit)
        app_total = timings.get(app)
        n_app = per_app_counts.get(app, 0)
        if app_total and n_app:
            share = counts[unit] / n_app
            weights[unit] = max(MIN_UNIT_SECONDS, float(app_total) * share)
        else:
            # UN MODULE NON MESURE COUTE LA MEDIANE, pas une extrapolation par
            # nombre de tests (mesure du 19/08/2026). Ce palier tourne avec
            # `--exclude-tag=pdf --exclude-tag=slow` : 347 des 2 733 modules ne
            # s'executent donc JAMAIS ici et n'ont, par construction, aucune
            # mesure. Les facturer `nb_tests x 0,55 s` gonflait le total estime a
            # 58 min contre 23 min reellement mesurees — LPT equilibrait des
            # fantomes, et le desequilibre affiche a 1,00x etait un mirage. La
            # mediane des modules REELLEMENT mesures est l'estimation neutre :
            # elle ne peut ni dominer une lane ni disparaitre.
            weights[unit] = _fallback_seconds(timings, counts[unit])
    return weights


@functools.lru_cache(maxsize=None)
def _median_measured(frozen_items) -> float:
    values = sorted(v for _k, v in frozen_items if v > 0)
    if not values:
        return 0.0
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2


def _fallback_seconds(timings: dict, n_cases: int) -> float:
    median = _median_measured(tuple(sorted(timings.items()))) if timings else 0.0
    if median > 0:
        return max(MIN_UNIT_SECONDS, median)
    return max(MIN_UNIT_SECONDS, n_cases * SECONDS_PER_TEST)


def assign(units, total: int, weights, parallel: int = DEFAULT_PARALLEL,
           repo_root: str = REPO_ROOT) -> list[list[str]]:
    """LPT greedy sur le TEMPS DE MUR de la lane, pas sur la somme de ses poids.

    Chaque lane est modelisee par l'etat de ses `parallel` workers. Placer un
    module = deposer ses CLASSES sur les workers les plus libres de la lane
    candidate ; on retient la lane dont le temps de mur resultant est le plus
    faible. Une lane bloquee par une classe geante a des workers inoccupes :
    ce modele lui donne donc naturellement plus de travail, ce qu'un
    equilibrage par somme refusait de faire.

    Deterministe : modules ordonnes par (-poids, label) ; a egalite de cout
    resultant, la lane d'indice le plus bas gagne.

    VOLET H (24/08) — CONTRAINTE D'ANTI-AFFINITE « purge large ». Le LPT seul
    n'est pas libre de placer n'importe quoi n'importe ou : la garde `max_locks`
    de ci.yml fait retomber a `--parallel 1` tout shard qui contient DEUX
    classes a purge large. Un plan « equilibre » qui les reunit se fait donc
    punir d'un facteur ~4 sur cette lane. Mesure du 24/08 : le recalage des
    poids seul posait `apps.crm.tests_webhook` ET
    `apps.ventes.tests.test_premium_security` sur la lane 4. Le depot n'en
    compte que DEUX (une classe chacun, 5,7 s et 3,9 s) : les separer ne coute
    rien en equilibre, et les laisser ensemble coutait la lane entiere.
    """
    if total < 1:
        raise ValueError("shard_total must be >= 1")
    lanes: list[list[str]] = [[] for _ in range(total)]
    sommes = [0.0] * total          # contributions cumulees au temps de mur
    plus_gros = [0.0] * total       # plus grosse CLASSE deja posee sur la lane
    purges = [0] * total            # classes a purge large deja posees

    for unit in sorted(units, key=lambda u: (-weights[u], u)):
        blocs = class_weights(unit, weights[unit], repo_root)
        s, g = sum(blocs), (max(blocs) if blocs else 0.0)
        n_purge = wide_purge_classes(unit, repo_root)
        # Une lane est interdite si y poser ce module ferait passer son compte
        # de classes a purge large a 2 ou plus. Si TOUTES le sont (plus de
        # modules a purge large que de lanes), on ne bloque pas le decoupage :
        # on retombe sur le choix non contraint — la garde rendra ce shard lent,
        # jamais rouge, ce qui reste son contrat.
        permises = [i for i in range(total) if purges[i] + n_purge < 2]
        if not permises:
            permises = list(range(total))
        meilleure, meilleur_cout = permises[0], None
        for i in permises:
            cout = max(sommes[i] + s, plus_gros[i], g)
            if meilleur_cout is None or cout < meilleur_cout - 1e-12:
                meilleure, meilleur_cout = i, cout
        lanes[meilleure].append(unit)
        sommes[meilleure] += s
        plus_gros[meilleure] = max(plus_gros[meilleure], g)
        purges[meilleure] += n_purge
    return [sorted(lane) for lane in lanes]


def _bases_de(classe):
    for base in classe.bases:
        if isinstance(base, ast.Name):
            yield base.id
        elif isinstance(base, ast.Attribute):
            yield base.attr


@functools.lru_cache(maxsize=None)
def wide_purge_classes(unit: str, repo_root: str = REPO_ROOT) -> int:
    """Nombre de CLASSES a purge large declarees par le module.

    Miroir EXACT de la garde `max_locks` de l'etape « Run Django test suite »
    (`.github/workflows/ci.yml`) : meme detection par AST, memes marqueurs, meme
    exclusion de `test_rls` (sans `POSTGRES_RLS_ENABLED` sa classe est sautee
    dans ce job). Si cette garde compte >= 2 classes dans UN shard, ce shard
    retombe a `--parallel 1` — c'est-a-dire qu'il quadruple. Le planificateur
    doit donc connaitre la contrainte, sinon il peut « equilibrer » vers un plan
    que la garde punit aussitot.
    """
    if "test_rls" in unit:
        return 0
    path = os.path.join(repo_root, "backend", "django_core", *unit.split(".")) + ".py"
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            arbre = ast.parse(fh.read(), path)
    except (OSError, SyntaxError, ValueError):
        return 0
    return sum(
        1 for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.ClassDef) and PURGE_MARQUEURS & set(_bases_de(noeud))
    )


def lane_makespan(lane, weights, parallel: int = DEFAULT_PARALLEL,
                  repo_root: str = REPO_ROOT) -> float:
    """Temps de mur attendu d'une lane : ses CLASSES sur `parallel` workers."""
    blocs = []
    for unit in lane:
        blocs.extend(class_weights(unit, weights[unit], repo_root))
    return makespan(blocs, parallel)


def theoretical_floor(units, weights, total: int,
                      parallel: int = DEFAULT_PARALLEL,
                      repo_root: str = REPO_ROOT) -> float:
    """Plancher qu'AUCUN decoupage ne peut franchir.

    C'est le plus grand des deux : le travail total divise par tous les workers
    disponibles, et la plus grosse CLASSE indivisible de toute la suite. Quand
    c'est la seconde qui domine, ajouter des lanes ne sert plus a rien — seul
    scinder cette classe ferait descendre le gate.
    """
    travail = sum(weights[u] for u in units)
    plus_grosse = 0.0
    for unit in units:
        for bloc in class_weights(unit, weights[unit], repo_root):
            plus_grosse = max(plus_grosse, bloc)
    return max(travail / total, plus_grosse)


def plan(total: int, repo_root: str = REPO_ROOT,
         parallel: int = DEFAULT_PARALLEL):
    units = discover_units(repo_root)
    weights = weigh(units, load_timings(), repo_root)
    lanes = assign(units, total, weights, parallel, repo_root)
    return units, weights, lanes


# --------------------------------------------------------------------------
# --update-timings: rebuild the table from CI job logs
# --------------------------------------------------------------------------
def parse_log_durations(lines) -> dict:
    """Duree par CLASSE de test, lue sur les journaux `-v 2`.

    DEUX CORRECTIONS DE FOND (volet F, 20/08/2026) — l'ancienne version se
    trompait de sens ET de granularite, et c'est ce qui a rendu le planificateur
    aveugle pendant quatre rondes.

    1. LE SENS. La sortie `-v 2` n'est PAS ecrite au fil de l'eau : Python
       tamponne, et le runner horodate les lignes AU MOMENT DU VIDAGE. Mesure
       sur le run 32320058346 : 15 lignes de tests consecutives portent le meme
       horodatage a 23 ms pres, et l'ecart entre deux lignes de la MEME classe
       est nul dans 100 % des cas. Les horodatages ne datent donc pas les
       tests — ils datent les rafales. Le seul signal exploitable est le TROU
       entre deux rafales, et ce trou mesure le travail accompli JUSTE AVANT
       d'etre vide, c'est-a-dire celui de la ligne QUI SUIT. L'ancienne version
       l'imputait a la ligne PRECEDENTE : un decalage d'un cran qui attribuait
       systematiquement le cout d'une classe lente a sa voisine rapide.
       Consequence mesuree : `test_gammes_offre` etait pesee 25,9 s alors que sa
       classe `TestAcceptationGamme` en consommait 194,8 s a elle seule — 70 %
       du shard le plus lent, invisible dans la table. (Volet G, 21/08/2026 :
       la relecture des journaux de trois runs verts a montre que meme 194,8 s
       etait la MOITIE de la realite — 348,8 / 405,4 / 384,0 s — et que ces
       trois tests valaient 99,5 a 99,7 % du module. Le module a ete scinde,
       la classe eclatee en trois, et la table recalee sur ces mesures. Ce que
       ce parser rend est donc juste, mais il faut le REJOUER : une table qui
       n'est jamais rafraichie derive silencieusement d'un facteur deux.)

    2. LA GRANULARITE. On mesure desormais la CLASSE, pas le module. Sous
       `--parallel`, la classe est l'unite indivisible : c'est elle qui fixe le
       plancher d'une lane (cf. l'en-tete de ce fichier). Le poids du module en
       decoule par simple somme, donc rien n'est perdu.

    Retourne ``{"<module>.<Classe>": secondes}``.
    """
    from datetime import datetime

    durations: dict = defaultdict(float)
    prev_time = None
    for raw in lines:
        m = _TS_RE.match(raw.rstrip("\n"))
        if not m:
            continue
        stamp, body = m.group(1), m.group(2)
        hit = _RESULT_RE.match(body)
        if not hit:
            continue
        dotted = hit.group(1)
        # "apps.ventes.tests.test_pdf.ClassName.test_method" -> drop the method
        classe = ".".join(dotted.split(".")[:-1]) or dotted
        now = datetime.strptime(stamp[:26] + "Z", "%Y-%m-%dT%H:%M:%S.%fZ")
        if prev_time is not None:
            delta = (now - prev_time).total_seconds()
            if 0 <= delta < 3600:  # ignore clock jumps / inter-shard gaps
                durations[classe] += delta
        prev_time = now
    return dict(durations)


def module_of_class(dotted: str) -> str:
    """`apps.x.tests.test_y.MaClasse` -> `apps.x.tests.test_y`."""
    parts = dotted.split(".")
    return ".".join(parts[:-1]) if len(parts) > 1 else dotted


def update_timings(log_paths, out_path: str = TIMINGS_PATH,
                   raw_path: str = RAW_TIMINGS_PATH,
                   class_path: str = CLASS_TIMINGS_PATH) -> int:
    merged: dict = defaultdict(float)
    for path in log_paths:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                for cls, secs in parse_log_durations(fh).items():
                    merged[cls] = max(merged[cls], secs)
        except OSError as exc:
            sys.stderr.write(f"ci_shard: log illisible {path} ({exc})\n")
            return 2
    if not merged:
        sys.stderr.write(
            "ci_shard: aucune durée reconnue dans ces journaux — la suite "
            "tourne-t-elle bien en -v 2 ?\n"
        )
        return 2

    # La table par CLASSE est le nouveau produit principal : c'est l'unite
    # indivisible sous `--parallel`, donc celle qui fixe le plancher d'une lane.
    #
    # ON N'Y GARDE QUE CE QUI PEUT CHANGER UNE DECISION. Une classe ne borne une
    # lane que si elle pese plus que la charge moyenne d'une lane (~160 s a 5
    # lanes) ; en dessous de CLASS_FLOOR_SECONDS elle ne peut jamais etre le
    # facteur limitant, et son cout reste compte dans le total du module. Sans
    # ce seuil la table faisait 473 Ko pour 6 529 entrees dont 99 % sous la
    # seconde — illisible en revue, et couteux a versionner a chaque mesure.
    classes = {k: round(v, 2) for k, v in sorted(merged.items())
               if v >= CLASS_FLOOR_SECONDS}
    with open(class_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(classes, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"ci_shard: {len(classes)} classe(s) chronometree(s) -> {class_path}")

    # Le poids d'un module est la SOMME de ses classes mesurees — plus aucune
    # extrapolation par nombre de tests quand la mesure existe.
    par_module: dict = defaultdict(float)
    for cls, secs in merged.items():
        par_module[module_of_class(cls)] += secs
    merged = par_module

    # GARDE DE VARIANCE (round 4). Une seule mesure est BRUITEE : entre deux runs,
    # l'etat du cache de base de test, le bruit du runner et le voisinage dans le
    # meme processus font bouger le cout d'un module. Le round 3 a equilibre sur un
    # seul echantillon et la pire lane est repartie a 1,24x la moyenne. Le poids de
    # planification est donc le MAX des DEUX derniers runs — pessimiste, donc une
    # lane ne peut pas etre sous-estimee deux fois de suite. Borne : on ne garde
    # qu'UN run brut precedent, donc le max ne monte pas indefiniment.
    # Depart du tableau de planification EXISTANT, pas d'une page blanche : une
    # lane qui n'a pas demarre (plafond de creneaux) ou un module simplement non
    # joue ce jour-la n'a AUCUNE mesure dans ces journaux. Repartir de zero
    # supprimerait son poids et le renverrait a l'estimation statique — c'est
    # arrive le 19/08 avec les modules du shard 5, jamais demarre. On conserve
    # donc l'ancien poids pour tout ce que ce run n'a pas mesure.
    previous_raw = load_timings(raw_path)
    weights = dict(load_timings(out_path))
    for key in set(merged) | set(previous_raw):
        weights[key] = max(merged.get(key, 0.0), previous_raw.get(key, 0.0),
                           weights.get(key, 0.0) if key not in merged else 0.0)
    previous = previous_raw

    if previous:
        drifted = [
            (k, previous[k], merged[k])
            for k in set(merged) & set(previous)
            if previous[k] >= 1.0 and abs(merged[k] - previous[k]) / previous[k] > 0.20
        ]
        drifted.sort(key=lambda r: -abs(r[2] - r[1]))
        print(f"ci_shard: {len(drifted)} module(s) au-dela de 20 % d'ecart entre "
              f"les deux runs (poids = max des deux) ; 10 plus gros ecarts :")
        for key, before, after in drifted[:10]:
            print(f"    {key}: {before:.2f}s -> {after:.2f}s")

    with open(raw_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({k: max(0.01, round(v, 2)) for k, v in sorted(merged.items())},
                  fh, indent=1, sort_keys=True)
        fh.write("\n")
    merged = weights
    # Floor AFTER rounding, not before: a module measured at 0.004 s rounds to
    # 0.0, and a 0.0 entry is FALSY — `weigh()` would silently ignore the
    # measurement and fall back to the static estimate, which for a
    # sub-millisecond module over-weighs it by two orders of magnitude. The
    # well-formedness test in scripts/tests/test_ci_shard.py pins this.
    table = {k: max(0.01, round(v, 2)) for k, v in sorted(merged.items()) if v > 0}
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(table, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"ci_shard: {len(table)} module(s) chronometre(s) -> {out_path}")
    return 0


def main(argv):
    parser = argparse.ArgumentParser(add_help=True, description=__doc__)
    parser.add_argument("index", nargs="?", type=int)
    parser.add_argument("total", nargs="?", type=int)
    parser.add_argument("--plan", type=int, metavar="TOTAL",
                        help="print the balance table for TOTAL lanes")
    parser.add_argument("--update-timings", nargs="+", metavar="LOG",
                        help="rebuild scripts/ci_shard_timings.json from CI logs")
    parser.add_argument("--parallel", type=int, default=DEFAULT_PARALLEL,
                        metavar="N",
                        help="processus par lane (doit refleter ci.yml ; "
                             f"defaut {DEFAULT_PARALLEL})")
    args = parser.parse_args(argv[1:])

    if args.update_timings:
        return update_timings(args.update_timings)

    if args.plan:
        p = args.parallel
        units, weights, lanes = plan(args.plan, parallel=p)
        total_w = sum(weights.values())
        print(f"{len(units)} modules, travail total estime {total_w / 60:.1f} min, "
              f"--parallel {p} par lane")
        murs = [lane_makespan(lane, weights, p) for lane in lanes]
        print(f"  {'lane':>4}  {'modules':>7}  {'travail':>8}  {'temps de mur':>12}")
        for i, lane in enumerate(lanes):
            load = sum(weights[u] for u in lane)
            print(f"  {i:4d}  {len(lane):7d}  {load:7.0f}s  {murs[i]:11.0f}s")
        sol = theoretical_floor(units, weights, args.plan, p)
        ecart = (max(murs) - min(murs)) / max(murs) if max(murs) else 0.0
        print(f"\n  pire lane {max(murs):.0f}s / plancher theorique {sol:.0f}s "
              f"({max(murs) / sol:.2f}x)")
        print(f"  ecart (max-min)/max = {100 * ecart:.0f} %")

        # Nommer CE QUI BORNE : si la plus grosse classe depasse le travail
        # total divise par tous les workers, ajouter des lanes ne sert plus a
        # rien — c'est cette classe qu'il faut scinder.
        pire_bloc, pire_nom = 0.0, ""
        for unit in units:
            for nom, poids in class_weight_items(unit, weights[unit]):
                if poids > pire_bloc:
                    pire_bloc, pire_nom = poids, f"{unit}.{nom}"
        capacite = total_w / args.plan
        if pire_bloc > capacite:
            print(f"\n  BORNE PAR UNE CLASSE INDIVISIBLE : {pire_nom} "
                  f"~{pire_bloc:.0f}s")
            print(f"  (capacite par lane a {args.plan} lanes x {p} workers = "
                  f"{capacite:.0f}s)")
            n_utile = max(1, int(round(total_w / pire_bloc)))
            print(f"  => au-dela de ~{n_utile} lane(s), une lane de plus ne "
                  f"raccourcit RIEN ; seul un decoupage de cette classe le ferait.")
        return 0

    if args.index is None or args.total is None:
        parser.print_usage(sys.stderr)
        return 2
    if not (0 <= args.index < args.total):
        sys.stderr.write("shard_index must be in [0, shard_total)\n")
        return 2
    _units, _weights, lanes = plan(args.total, parallel=args.parallel)
    sys.stdout.write(" ".join(lanes[args.index]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
