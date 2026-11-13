"""AUD415 — un fan-out beat balaie les sociétés ACTIVES, jamais toutes.

``authentication.selectors.active_companies()`` (SCA19) est la source UNIQUE
des sociétés balayables par une tâche périodique : elle exclut les tenants
``actif=False`` (suspendus, en fermeture — pont bool↔statut SCA18). L'audit
AUD415 a compté **10 sites** de fan-out beat qui itéraient encore
``Company.objects.all()`` en dur, dont un DESTRUCTIF (purge de corbeille GED,
02:30 quotidien avec ``GED_PURGE_AUTO_APPLY=1``) : un tenant suspendu
continuait de recevoir alertes crédit, séquences marketing, réappro stock,
prévisions SCM et relève IMAP réelle. Ils ont convergé ; cette garde empêche
le 11e — et gèle aussi le filtre recopié ``Company.objects.filter(actif=True)``,
qui a la bonne sémantique mais duplique la source unique (elle dérivera le jour
où la définition de « société balayable » bougera).

DB-free, AST-only (mêmes conventions que ``check_mouvement_stock_service.py`` /
``check_tenant_isolation.py`` : pas de Django, pas de base, tourne dans le job
CI rapide ``backend-lint-fast``).

CE QUI EST SCANNÉ
-----------------
Les modules de tâches périodiques UNIQUEMENT : ``apps/*/tasks.py``,
``apps/*/scheduled.py``, ``apps/*/beat_tasks.py`` (y compris en sous-paquet) et,
APFS63, tout module de ``apps/`` ou ``core/`` qui DÉCORE une fonction
``@shared_task`` (AST : ``reporting/scheduled_reports.py``, ``kpi_alertes.py``…).
ACEL5 : plus, à UN saut, les fonctions de la même app qu'une tâche importe et
appelle, et ``Command.handle`` des commandes lancées par ``call_command('<nom>')``.
Le reste du dépôt est hors périmètre : une vue ou un service admin a le droit
de lister TOUTES les sociétés.

CE QUI EST REFUSÉ
-----------------
``Company.objects.all()`` et ``Company.objects.filter(actif=True)`` (ainsi que
``.filter(actif = True)`` écrit autrement — la comparaison est faite sur l'AST,
pas sur le texte).

CLASSE « BALAYAGE GLOBAL NON SCOPÉ » (AFAC44 / AFAC93)
-----------------------------------------------------
Dans un module beat, une requête ``<Modèle>.objects.<méthode>(…)`` sur un modèle
métier à FK ``company`` (``Facture``, ``RelanceLog``, ``PromessePaiement``…) dont la
FONCTION n'appelle pas ``active_companies()`` / ``active_company_ids()`` et ne filtre
aucun QUERYSET ``<Modèle>.objects….filter/exclude/get(company…=)`` (``company``,
``company_id``, ``company__in``… ; un ``create(company=…)`` ou une lecture de profil ne comptent pas) est refusée :
elle balaie les données de TOUTES les sociétés, suspendues comprises. Clé stable
``chemin::fonction`` (jamais un numéro de ligne). Les sites existants sont un PASSIF GELÉ
dans l'allowlist, ligne ``chemin::fonction  # raison / tâche qui la retire`` ; une clé
qui n'apparie plus aucun site (corrigé) FAIT ÉCHOUER la garde — la liste ne fait que
décroître.

ALLOWLIST (``scripts/beat_active_companies_allow.txt``)
-------------------------------------------------------
Une ligne ``chemin/relatif.py`` par exception ASSUMÉE, justifiée en
commentaire. Elle contient les deux exceptions déjà actées par SCA19 (compta,
chat) et les fichiers qui filtrent DÉJÀ ``actif=True`` à la main. Ajouter une
ligne est un choix explicite, revu comme du code.

Usage :
    python scripts/check_beat_active_companies.py           # check (CI)
    python scripts/check_beat_active_companies.py --list    # tous les sites
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
TYPE_DE_CLE = "par_symbole"  # AMET100 — cle de contenu `fichier::symbole` (jamais un numero de ligne)

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
ALLOWLIST_PATH = ROOT / "scripts" / "beat_active_companies_allow.txt"
#: ACEL2 — passif gelé des balayages sans limite de temps effective (ne fait que décroître).
LIMITES_ALLOW_PATH = ROOT / "scripts" / "beat_limites_allow.txt"

#: Le modèle dont le balayage périodique est réservé au sélecteur.
MODEL_NAME = "Company"

#: Le sélecteur qui EST la source unique (SCA19).
SELECTEUR = "authentication.selectors.active_companies()"

#: Noms de fichiers considérés comme des modules de tâches périodiques.
FICHIERS_BEAT = ("tasks.py", "scheduled.py", "beat_tasks.py")

#: Racine scannée : les apps métier (les fan-outs beat vivent tous là).
SCAN_ROOT = DJANGO_CORE / "apps"


def _is_test_path(path: Path) -> bool:
    parts = path.parts
    if any(p in ("tests", "migrations") for p in parts):
        return True
    name = path.name
    return (name.startswith("test_") or name.startswith("tests_")
            or name == "tests.py")


def _decore_shared_task(path: Path) -> bool:
    """APFS63 — le module décore au moins une fonction ``@shared_task``."""
    try:
        texte = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    if "shared_task" not in texte:
        return False
    try:
        tree = ast.parse(texte)
    except SyntaxError:
        return False
    for n in ast.walk(tree):
        for d in getattr(n, "decorator_list", ()):
            d = d.func if isinstance(d, ast.Call) else d
            if getattr(d, "id", getattr(d, "attr", "")) == "shared_task":
                return True
    return False


def _iter_source_files():
    racines = [r for r in (SCAN_ROOT, DJANGO_CORE / "core") if r.is_dir()]
    for path in sorted(p for r in racines for p in r.rglob("*.py")):
        if _is_test_path(path):
            continue
        if path.name in FICHIERS_BEAT or _decore_shared_task(path):
            yield path


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _load_allowlist():
    if not ALLOWLIST_PATH.exists():
        return set()
    out = set()
    for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line)
    return out


def _callee_name(node: ast.Call):
    """Nom lisible de l'appelé : ``A.b.c(...)`` -> 'A.b.c', sinon None."""
    parts = []
    cur = node.func
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    else:
        return None
    return ".".join(reversed(parts))


def _est_filtre_actif_vrai(node: ast.Call) -> bool:
    """Vrai pour ``…filter(actif=True)`` (le filtre recopié à la main)."""
    for kw in node.keywords:
        if kw.arg != "actif":
            continue
        valeur = kw.value
        if isinstance(valeur, ast.Constant) and valeur.value is True:
            return True
    return False


_METHODES_REQUETE = {
    "all", "filter", "exclude", "get", "first", "last", "count", "exists",
    "values", "values_list", "iterator", "annotate", "aggregate", "select_related",
    "prefetch_related", "order_by", "update", "delete", "in_bulk",
}
_SELECTEURS_SOCIETE = {"active_companies", "active_company_ids"}


def modeles_a_company(scan_root: Path = None) -> set:
    """Noms des classes de modèle qui déclarent une FK ``company`` (AST des models)
    ou dont la chaîne de bases atteint ``TenantModel`` (APFS120, fermeture transitive
    sur une table nom → bases lue dans les models et dans ``core/**/*.py``)."""
    scan_root = SCAN_ROOT if scan_root is None else scan_root
    noms, bases = set(), {}
    if not scan_root.is_dir():
        return noms
    modeles = sorted(scan_root.rglob("models*.py")) + sorted(scan_root.rglob("models/*.py"))
    for path in modeles + sorted((scan_root.parent / "core").rglob("*.py")):
        if _is_test_path(path):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for classe in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            bases.setdefault(classe.name, set()).update(
                getattr(b, "id", getattr(b, "attr", "")) for b in classe.bases)
            for stmt in classe.body if path in modeles else ():
                cible = None
                if isinstance(stmt, ast.Assign) and stmt.targets:
                    cible = stmt.targets[0]
                elif isinstance(stmt, ast.AnnAssign):
                    cible = stmt.target
                valeur = getattr(stmt, "value", None)
                if (isinstance(cible, ast.Name) and cible.id == "company"
                        and isinstance(valeur, ast.Call)
                        and isinstance(valeur.func, (ast.Attribute, ast.Name))
                        and getattr(valeur.func, "attr", getattr(valeur.func, "id", ""))
                        == "ForeignKey"):
                    noms.add(classe.name)
    heritiers = {"TenantModel"}
    while True:
        neufs = {n for n, b in bases.items() if b & heritiers} - heritiers
        if not neufs:
            break
        heritiers |= neufs
    return noms | (heritiers - {"TenantModel"})


def _est_filtre_societe_queryset(n: ast.Call, modeles: set, par_ligne: bool = False) -> bool:
    """``<Modèle>.objects[…].filter/exclude/get(company…=)`` sur un modèle à FK company."""
    f = n.func
    if not (isinstance(f, ast.Attribute) and f.attr in ("filter", "exclude", "get")):
        return False
    # ACEL5 — ``par_ligne`` : ``company=plan.company`` (lue sur la ligne balayée) ne borne rien.
    if not any((kw.arg or "").startswith("company")
               and not (par_ligne and isinstance(kw.value, ast.Attribute)) for kw in n.keywords):
        return False
    cur = f.value
    while isinstance(cur, (ast.Attribute, ast.Call)):
        if isinstance(cur, ast.Attribute) and cur.attr == "objects":
            return isinstance(cur.value, ast.Name) and cur.value.id in modeles
        cur = cur.value if isinstance(cur, ast.Attribute) else cur.func
    return False


def _fonction_filtre_societe(fonction: ast.AST, modeles: set, par_ligne: bool = False) -> bool:
    """La fonction itère active_companies*() ou borne un QUERYSET par ``company…``
    (un ``objects.create(company=…)`` ou une lecture de profil ne bornent aucun balayage)."""
    for n in ast.walk(fonction):
        if isinstance(n, ast.Call):
            nom = _callee_name(n) or ""
            if nom.split(".")[-1] in _SELECTEURS_SOCIETE:
                return True
            if _est_filtre_societe_queryset(n, modeles, par_ligne):
                return True
    return False


def _chaines_par_pk(fonction: ast.AST) -> set:
    """ids des appels d'une chaîne bornée par ``.filter/.get(pk=…|id=…)`` : lecture d'UNE
    ligne par clé primaire, jamais un balayage (``pk__in`` reste un balayage)."""
    ids = set()
    for c in ast.walk(fonction):
        if (isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                and c.func.attr in ("filter", "get")
                and any(kw.arg in ("pk", "id") for kw in c.keywords)):
            ids.update(id(x) for x in ast.walk(c))
    return ids


def check_balayage_global(path: Path, modeles: set):
    """[(cle_fonction, ligne, expression)] : requête sur un modèle à company, fonction non scopée."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []
    sorties = []
    fonctions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for fonction in fonctions:
        site = _balayage_de(fonction, modeles)
        if site:
            sorties.append((fonction.name, *site))
    return sorties


def _balayage_de(fonction: ast.AST, modeles: set, par_ligne: bool = False):
    """(ligne, expression) du 1er balayage non scopé de la fonction, sinon None."""
    # Seules les requêtes DIRECTEMENT de cette fonction (pas celles d'une fonction imbriquée).
    imbriquees = {id(x) for f in ast.walk(fonction) if f is not fonction
                  and isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
                  for x in ast.walk(f)}
    if _fonction_filtre_societe(fonction, modeles, par_ligne):
        return None
    par_pk = _chaines_par_pk(fonction)
    for n in ast.walk(fonction):
        if id(n) in imbriquees or id(n) in par_pk or not isinstance(n, ast.Call):
            continue
        nom = _callee_name(n)
        if not nom:
            continue
        seg = nom.split(".")
        if (len(seg) >= 3 and seg[-2] == "objects" and seg[-3] in modeles
                and seg[-1] in _METHODES_REQUETE):
            return n.lineno, f"{nom}()"
    return None


def _racine_app(path: Path):
    """``apps/<app>`` ou ``core``/``authentication`` contenant ``path``."""
    rel = path.relative_to(DJANGO_CORE).parts
    return DJANGO_CORE.joinpath(*rel[:2]) if rel[0] == "apps" else DJANGO_CORE / rel[0]


def _module_vers_fichier(base: Path):
    for cand in (base.with_suffix(".py"), base / "__init__.py"):
        if cand.is_file():
            return cand
    return None


def fonctions_appelees_d_un_saut(path: Path):
    """ACEL5 — [(fichier, nom)] des fonctions importées dans l'app (``from .x import f``,
    ``from apps.<même app>.x import f``) et appelées par le module de tâches : un seul saut."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []
    racine, importes = _racine_app(path), {}
    for imp in (n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)):
        if imp.level:
            base = path.parents[imp.level - 1].joinpath(*(imp.module or "").split("."))
        else:
            base = DJANGO_CORE.joinpath(*(imp.module or "").split("."))
        cible = _module_vers_fichier(base)
        if cible and racine in cible.parents and not _is_test_path(cible):
            for alias in imp.names:
                importes[alias.asname or alias.name] = (cible, alias.name)
    appeles = {c.func.id for c in ast.walk(tree)
               if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    return sorted({importes[n] for n in appeles if n in importes})


def commandes_lancees(path: Path):
    """ACEL5 — [(fichier, 'Command.handle')] des ``call_command('<nom>')`` littéraux."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []
    noms = {c.args[0].value for c in ast.walk(tree)
            if isinstance(c, ast.Call) and (_callee_name(c) or "").endswith("call_command")
            and c.args and isinstance(c.args[0], ast.Constant) and isinstance(c.args[0].value, str)}
    return sorted((p, "Command.handle") for nom in noms
                  for p in DJANGO_CORE.rglob(f"management/commands/{nom}.py") if not _is_test_path(p))


def _fonction_nommee(path: Path, nom: str):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return None
    *classe, fn = nom.split(".")
    corps = tree.body
    if classe:
        corps = next((c.body for c in tree.body if isinstance(c, ast.ClassDef) and c.name == classe[0]), [])
    return next((f for f in corps if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and f.name == fn), None)


def check_un_saut(path: Path, modeles: set, deja_lus: set):
    """ACEL5 — [(cle_rel, expression)] : service ou commande lancé par une tâche, qui balaie."""
    sorties = []
    for cible, nom in fonctions_appelees_d_un_saut(path) + commandes_lancees(path):
        fonction = None if cible in deja_lus else _fonction_nommee(cible, nom)
        if fonction is None:
            continue
        companies = [_site_company(n) for n in ast.walk(fonction) if isinstance(n, ast.Call)
                     and _site_company(n)]
        site = (None, companies[0]) if companies else _balayage_de(fonction, modeles, par_ligne=True)
        if site:
            sorties.append((f"{_rel(cible)}::{nom}", site[1]))
    return sorties


_LARGES = {"Exception", "BaseException"}


def _noms_types(h: ast.ExceptHandler) -> set:
    t = h.type
    elts = t.elts if isinstance(t, ast.Tuple) else ([t] if t is not None else [])
    return {getattr(e, "id", getattr(e, "attr", "")) for e in elts}


def _releve(h: ast.ExceptHandler) -> bool:
    return any(isinstance(x, ast.Raise) for x in ast.walk(h))


def _limite_douce_avalee(fonction: ast.AST) -> bool:
    """Un ``except`` large (nu, Exception, BaseException) sans relève, que ne précède
    aucun ``except SoftTimeLimitExceeded: raise`` du même ``try``."""
    for t in (n for n in ast.walk(fonction) if isinstance(n, ast.Try)):
        douce_relevee = False
        for h in t.handlers:
            noms = _noms_types(h)
            if "SoftTimeLimitExceeded" in noms and _releve(h):
                douce_relevee = True
            elif (h.type is None or noms & _LARGES) and not douce_relevee and not _releve(h):
                return True
    return False


def check_limites_balayage(path: Path):
    """ACEL2 — [(fonction, raison)] : ``@shared_task`` qui balaie les sociétés sans
    ``soft_time_limit`` ET ``time_limit``, ou dont un ``except`` large avale la limite douce."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []
    sorties = []
    for f in (n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
        decos = [d for d in f.decorator_list
                 if getattr(d.func if isinstance(d, ast.Call) else d, "id",
                            getattr(d.func if isinstance(d, ast.Call) else d, "attr", "")) == "shared_task"]
        if not decos:
            continue
        noms = [(_callee_name(c) or "") for c in ast.walk(f) if isinstance(c, ast.Call)]
        if not any(n.split(".")[-1] in _SELECTEURS_SOCIETE or f"{MODEL_NAME}.objects" in n for n in noms):
            continue
        kws = {kw.arg for d in decos if isinstance(d, ast.Call) for kw in d.keywords}
        if not {"soft_time_limit", "time_limit"} <= kws:
            sorties.append((f.name, "sans soft_time_limit ET time_limit au décorateur"))
        elif _limite_douce_avalee(f):
            sorties.append((f.name, "except large qui avale SoftTimeLimitExceeded"))
    return sorties


def _load_limites_allow():
    if not LIMITES_ALLOW_PATH.exists():
        return set()
    lignes = LIMITES_ALLOW_PATH.read_text(encoding="utf-8").splitlines()
    return {ligne.split("#")[0].strip() for ligne in lignes if ligne.split("#")[0].strip()}


def check_file(path: Path):
    """Renvoie [(ligne, expression)] des balayages non scopés trouvés."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            expr = _site_company(node)
            if expr:
                findings.append((node.lineno, expr))
    return findings


def _site_company(node: ast.Call):
    """``Company.objects.all()`` ou ``….filter(actif=True)`` recopié : expression, sinon None."""
    name = _callee_name(node)
    segments = name.split(".") if name else []
    if MODEL_NAME not in segments:
        return None
    reste = segments[segments.index(MODEL_NAME) + 1:]
    if reste[:1] != ["objects"] or len(reste) < 2:
        return None
    if reste[1] == "all":
        return f"{name}()"
    if reste[1] == "filter" and _est_filtre_actif_vrai(node):
        return f"{name}(actif=True)"
    return None


def fichiers_morts(cles, root=None):
    """ADEP26 — clés d'allowlist dont le fichier n'existe plus (app sortie
    du périmètre) : une ligne morte est un faux acquis, la garde la refuse."""
    root = ROOT if root is None else root
    morts = []
    for cle in sorted(cles):
        chemin = cle.split("#")[0].split("|")[0].split("::")[0].strip()
        if chemin and not (root / chemin).exists():
            morts.append(cle)
    return morts


def _morts_offenders(cles):
    return [f"{c} — ligne d'allowlist morte (fichier absent) : retirez-la"
            for c in fichiers_morts(cles)]


def main(argv):
    list_mode = "--list" in argv
    allow = _load_allowlist()
    offenders, listed = [], []
    offenders += _morts_offenders(allow)
    modeles = modeles_a_company()
    cles_vues, limites_vues, allow_limites = set(), set(), _load_limites_allow()
    beat = list(_iter_source_files())
    for path in beat:
        # ACEL5 — services et commandes qu'une tâche lance (un saut), mêmes règles.
        for cle, expr in check_un_saut(path, modeles, set(beat)):
            cles_vues.add(cle)
            listed.append(f"{cle}  {expr}")
            if cle not in allow:
                offenders.append(f"{cle}  {expr} — appelé par {_rel(path)} : balayage sans "
                                 f"{SELECTEUR} ni filtre company")
    for path in beat:
        rel = _rel(path)
        for lineno, expr in check_file(path):
            listed.append(f"{rel}:{lineno}  {expr}")
            if rel not in allow:
                offenders.append(f"{rel}:{lineno}  {expr}")
        # AFAC44/93 — balayage global non scopé : clé stable `fichier::fonction`.
        for fonction, lineno, expr in check_balayage_global(path, modeles):
            cle = f"{rel}::{fonction}"
            cles_vues.add(cle)
            listed.append(f"{cle}  {expr}")
            if cle not in allow and rel not in allow:
                offenders.append(
                    f"{cle}  {expr} — requête sur un modèle à FK company sans "
                    f"{SELECTEUR} ni filtre company/company__in")
        # ACEL2 — limite de temps effective des balayages planifiés.
        for fonction, raison in check_limites_balayage(path):
            cle = f"{rel}::{fonction}"
            limites_vues.add(cle)
            listed.append(f"{cle}  # limites : {raison}")
            if cle not in allow_limites:
                offenders.append(
                    f"{cle}  — {raison} : posez soft_time_limit + time_limit et placez "
                    "`except SoftTimeLimitExceeded: raise` avant tout except large "
                    "(patron : apps/ventes/coherence/moteur.py)")
    for cle in sorted(allow_limites - limites_vues):
        offenders.append(f"{cle}  — clé morte de scripts/beat_limites_allow.txt : retirez la ligne")
    mortes = sorted(c for c in allow if "::" in c and c not in cles_vues)
    for cle in mortes:
        offenders.append(f"{cle}  — clé morte de l'allowlist (site corrigé ou disparu) : "
                         "retirez la ligne (la liste ne fait que décroître)")

    if list_mode:
        for line in listed:
            print(line)
        return 0

    if offenders:
        print("check_beat_active_companies : fan-out beat qui balaie des "
              "sociétés NON actives :")
        for line in offenders:
            print(f"  - {line}")
        print(
            f"\nItérez sur {SELECTEUR} (SCA19) : un tenant suspendu ou en "
            "fermeture ne doit plus être facturé, relancé ni balayé — et pour "
            "la GED, sa corbeille ne doit surtout pas être purgée "
            "DÉFINITIVEMENT (AUD415, 10 sites corrigés). Un "
            "Company.objects.filter(actif=True) recopié à la main est refusé "
            "pour la même raison : il duplique la source unique et dérivera. "
            "Exception assumée : ajouter le chemin à "
            "scripts/beat_active_companies_allow.txt avec sa justification."
        )
        return 1

    print("check_beat_active_companies : OK — tout fan-out beat passe par "
          "active_companies() (allowlist respectée).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
