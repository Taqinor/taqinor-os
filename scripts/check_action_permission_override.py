"""AUD421 — un `get_permissions()` maison ne doit jamais AFFAIBLIR une
`@action(permission_classes=...)`.

CE QUE CETTE GARDE GÈLE. Le sweep RBAC d'AUD403 a rejoué action par action la
trentaine de fichiers combinant un `get_permissions()` local à branchement sur
``self.action`` ET au moins une ``@action(permission_classes=...)`` inline.
Verdict : AUCUN cas où le repli était PLUS FAIBLE que la permission inline
voulue — sauf ``ventes/views/devis.py`` (AUD403), corrigé. Ce négatif prouvé
doit être gelé par une garde mécanique, pas re-audité à la main tous les six
mois.

LE PIÈGE, en une phrase. DRF appelle ``get_permissions()`` pour TOUTE requête,
y compris une ``@action``. Si la méthode branche sur ``self.action`` et REND
une liste par défaut au lieu de déléguer, la ``permission_classes`` déclarée
sur l'action est purement et simplement IGNORÉE : la déclaration inline devient
décorative, et l'action tombe sur le repli — souvent plus permissif.

CE QUI EST EXIGÉ. Toute classe portant à la fois un ``get_permissions()`` local
et une ``@action(permission_classes=...)`` doit satisfaire l'UN des trois
patrons sûrs :

  · PATRON D'OR — appeler ``declared_action_permissions(...)``
    (``apps/ventes/views/paiement.py``) : il lit la déclaration de l'action
    et la rend telle quelle ;
  · REPLI DRF — finir par ``return super().get_permissions()``, qui honore la
    déclaration inline pour toute action non explicitement listée (24 ViewSets
    de ``compta/views.py``, ``innovation/views.py``, ``adsengine/views.py``) ;
  · COUVERTURE EXPLICITE — nommer, dans le branchement, CHAQUE action qui
    déclare une ``permission_classes`` (patron d'``apps/ventes/views/devis.py``
    après AUD403 : le repli n'est jamais atteint pour ces actions, et l'@action
    déclare la MÊME classe « pour ne jamais mentir »). Les noms cherchés sont
    ceux des MÉTHODES Python (c'est ce que vaut ``self.action``), littéraux du
    corps ou membres d'une constante de module (``READ_ACTIONS`` &c.).

Une classe SANS ``get_permissions()`` local n'est jamais concernée : DRF lit
directement la déclaration de l'action.

DB-free, AST-only (mêmes conventions que ``check_tenant_isolation.py`` /
``check_mouvement_stock_service.py`` : pas de Django, pas de base, tourne dans
le job CI rapide ``backend-lint-fast``).

ALLOWLIST (``scripts/action_permission_override_allow.txt``)
------------------------------------------------------------
Une ligne ``chemin/relatif.py::NomDeClasse`` par exception ASSUMÉE, justifiée
en commentaire — vérifiée bénigne par le sweep AUD403.

Usage :
    python scripts/check_action_permission_override.py           # check (CI)
    python scripts/check_action_permission_override.py --list    # tout le
                                                                 # périmètre
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
ALLOWLIST_PATH = ROOT / "scripts" / "action_permission_override_allow.txt"

#: Le helper « patron d'or » : il rend la déclaration de l'action elle-même.
HELPER_DECLARE = "declared_action_permissions"

#: Racines scannées : tout le code Django de production.
SCAN_ROOTS = [
    DJANGO_CORE / "apps",
    DJANGO_CORE / "core",
    DJANGO_CORE / "authentication",
]


def _is_test_path(path: Path) -> bool:
    parts = path.parts
    if any(p in ("tests", "migrations") for p in parts):
        return True
    name = path.name
    return (name.startswith("test_") or name.startswith("tests_")
            or name == "tests.py")


def _iter_source_files():
    for root in SCAN_ROOTS:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if _is_test_path(path):
                continue
            yield path


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _load_allowlist_raisons():
    """{clé: raison}. Ligne ``clé  # raison`` ; clé = ``chemin.py::Classe``
    (toute la classe) ou ``chemin.py::Classe.action`` (une seule action)."""
    if not ALLOWLIST_PATH.exists():
        return {}
    out = {}
    for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cle, _, raison = line.partition("#")
        out[cle.strip()] = raison.strip()
    return out


def _load_allowlist():
    return set(_load_allowlist_raisons())


#: Phrase collective interdite (ACRM48) : chaque ligne porte SA raison.
RAISON_COLLECTIVE = "vérifiées bénignes"
RAISON_MIN = 12

#: Rang de rigueur des permissions de rôle connues (plus grand = plus strict).
RANG = {"IsAnyRole": 1, "IsResponsableOrAdmin": 2, "IsAdminRole": 3}


def _norm_permission(elt):
    """``IsAdminRole()`` / ``IsAdminRole`` -> 'IsAdminRole' ;
    ``HasPermissionOrLegacy('x')()`` / ``HasPermissionOrLegacy('x')`` ->
    ``HasPermissionOrLegacy('x')``."""
    if isinstance(elt, ast.Call) and not elt.args and not elt.keywords:
        elt = elt.func
    return ast.unparse(elt)


def _permissions_liste(node):
    """Ensemble normalisé d'une liste/tuple littérale, sinon None."""
    if isinstance(node, (ast.List, ast.Tuple)):
        return frozenset(_norm_permission(e) for e in node.elts)
    return None


def _repli_atteint(fonction):
    """Permissions du repli (dernier ``return [..]`` de plus haut niveau)."""
    corps = [n for n in fonction.body
             if not (isinstance(n, ast.Expr)
                     and isinstance(n.value, ast.Constant))]
    if corps and isinstance(corps[-1], ast.Return) and corps[-1].value:
        return _permissions_liste(corps[-1].value)
    return None


def _permissions_declarees(fonction):
    for deco in fonction.decorator_list:
        if not isinstance(deco, ast.Call):
            continue
        if (_nom_appele(deco) or "").split(".")[-1] != "action":
            continue
        for kw in deco.keywords:
            if kw.arg == "permission_classes":
                return _permissions_liste(kw.value)
    return None


def _comparer(declare, repli):
    """'plus strict' | 'plus faible' | 'different' | 'indetermine' | None."""
    if declare is None or repli is None:
        return "indetermine"
    if declare == repli:
        return None
    rd = [RANG.get(n) for n in declare]
    rr = [RANG.get(n) for n in repli]
    if None in rd or None in rr:
        return "different"
    if max(rr) > max(rd):
        return "plus strict"
    if max(rr) < max(rd):
        return "plus faible"
    return "different"


def divergences(path: Path):
    """[(ligne, classe, action, declare, repli, sens)] : actions à découvert
    dont le repli atteint DIFFÈRE de la permission déclarée (ACRM48)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []
    constantes = _constantes_de_module(tree)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        get_perms, actions = None, {}
        for m in node.body:
            if not isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if m.name == "get_permissions":
                get_perms = m
            elif _action_avec_permissions(m):
                actions[m.name] = m
        if get_perms is None or not actions:
            continue
        if _utilise_le_patron_d_or(get_perms) or _delegue_au_repli(get_perms):
            continue
        couvertes = _actions_couvertes(get_perms, constantes)
        repli = _repli_atteint(get_perms)
        for nom, m in sorted(actions.items()):
            if nom in couvertes:
                continue
            declare = _permissions_declarees(m)
            sens = _comparer(declare, repli)
            if sens:
                out.append((node.lineno, node.name, nom, declare, repli, sens))
    return out


def _nom_appele(node: ast.Call):
    """Nom lisible de l'appelé : ``a.b.c(...)`` -> 'a.b.c', sinon None."""
    parts = []
    cur = node.func
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    elif isinstance(cur, ast.Call):
        # ``super().get_permissions`` : la base est elle-même un appel.
        parts.append("super()" if _nom_appele(cur) == "super" else "?")
    else:
        return None
    return ".".join(reversed(parts))


def _action_avec_permissions(fonction: ast.FunctionDef) -> bool:
    """Vrai si la méthode porte ``@action(..., permission_classes=[...])``."""
    for deco in fonction.decorator_list:
        if not isinstance(deco, ast.Call):
            continue
        nom = _nom_appele(deco) or ""
        if nom.split(".")[-1] != "action":
            continue
        if any(kw.arg == "permission_classes" for kw in deco.keywords):
            return True
    return False


def _constantes_de_module(tree: ast.Module):
    """Constantes de module ``NOM = ['a', 'b']`` (listes/tuples de chaînes)."""
    constantes = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        cible = node.targets[0]
        if not isinstance(cible, ast.Name):
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple)):
            continue
        valeurs = {e.value for e in node.value.elts
                   if isinstance(e, ast.Constant) and isinstance(e.value, str)}
        if valeurs:
            constantes[cible.id] = valeurs
    return constantes


def _actions_couvertes(fonction: ast.FunctionDef, constantes) -> set:
    """Noms d'actions NOMMÉS par le branchement de ``get_permissions``.

    Littéraux du corps, plus les membres de toute constante de module citée
    (``self.action in READ_ACTIONS + [...]``).
    """
    noms = set()
    for node in ast.walk(fonction):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            noms.add(node.value)
        elif isinstance(node, ast.Name) and node.id in constantes:
            noms |= constantes[node.id]
    return noms


def _delegue_au_repli(fonction: ast.FunctionDef) -> bool:
    """Vrai si ``get_permissions`` finit par ``return super().get_permissions()``."""
    corps = [n for n in fonction.body
             if not (isinstance(n, ast.Expr)
                     and isinstance(n.value, ast.Constant))]
    if not corps:
        return False
    dernier = corps[-1]
    if not isinstance(dernier, ast.Return) or dernier.value is None:
        return False
    if not isinstance(dernier.value, ast.Call):
        return False
    return _nom_appele(dernier.value) == "super().get_permissions"


def _utilise_le_patron_d_or(fonction: ast.FunctionDef) -> bool:
    for node in ast.walk(fonction):
        if isinstance(node, ast.Call):
            nom = _nom_appele(node) or ""
            if nom.split(".")[-1] == HELPER_DECLARE:
                return True
    return False


def check_file(path: Path):
    """Renvoie [(ligne, classe, verdict, découvertes)] pour le périmètre.

    ``verdict`` vaut ``'or'`` (patron d'or), ``'repli'`` (super() final),
    ``'couvert'`` (toute action déclarée est nommée par le branchement) ou
    ``'NU'`` — le motif refusé : une action déclare une ``permission_classes``
    que le branchement ne nomme pas et qui tombe donc sur le repli brut.
    ``découvertes`` liste les actions à découvert (vide sauf pour ``NU``).
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []
    constantes = _constantes_de_module(tree)
    resultats = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        get_perms = None
        actions_declarees = []
        for membre in node.body:
            if not isinstance(membre, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if membre.name == "get_permissions":
                get_perms = membre
            elif _action_avec_permissions(membre):
                actions_declarees.append(membre.name)
        if get_perms is None or not actions_declarees:
            continue
        decouvertes = []
        if _utilise_le_patron_d_or(get_perms):
            verdict = "or"
        elif _delegue_au_repli(get_perms):
            verdict = "repli"
        else:
            couvertes = _actions_couvertes(get_perms, constantes)
            decouvertes = sorted(a for a in actions_declarees
                                 if a not in couvertes)
            verdict = "NU" if decouvertes else "couvert"
        resultats.append((node.lineno, node.name, verdict, decouvertes))
    return resultats


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
    raisons = _load_allowlist_raisons()
    allow = set(raisons)
    offenders, listed = [], []
    offenders += _morts_offenders(allow)
    for cle, raison in sorted(raisons.items()):
        if len(raison) < RAISON_MIN or RAISON_COLLECTIVE in raison.lower():
            offenders.append(
                f"allowlist : la ligne `{cle}` n'a pas sa raison propre "
                f"(ni vide, ni « {RAISON_COLLECTIVE} » collectif)")
    for path in _iter_source_files():
        rel = _rel(path)
        for lineno, classe, verdict, decouvertes in check_file(path):
            listed.append(f"{rel}:{lineno}  {classe}  [{verdict}]"
                          + (f"  à découvert : {', '.join(decouvertes)}"
                             if decouvertes else ""))
        for lineno, classe, nom, declare, repli, sens in divergences(path):
            cle = f"{rel}::{classe}"
            if cle in allow or f"{cle}.{nom}" in allow:
                continue
            offenders.append(
                f"{rel}:{lineno}  {classe}.{nom} — repli {sens} que la "
                f"déclaration (déclaré {sorted(declare or [])}, repli "
                f"{sorted(repli) if repli is not None else 'non analysable'})")

    if list_mode:
        for line in listed:
            print(line)
        return 0

    if offenders:
        print("check_action_permission_override : la permission atteinte "
              "par une @action n'est pas celle qu'elle déclare "
              "(get_permissions() à branchement brut) :")
        for line in offenders:
            print(f"  - {line}")
        print(
            "\nDRF appelle get_permissions() pour TOUTE requête, action "
            "comprise : un branchement qui rend une liste par défaut IGNORE "
            "la permission_classes déclarée sur l'action (motif AUD403, "
            "ventes/views/devis.py). Terminez par "
            "`return super().get_permissions()`, ou passez par "
            f"`{HELPER_DECLARE}(...)` (patron d'or, apps/ventes/views/paiement.py). "
            "Exception assumée : ajouter `chemin.py::Classe[.action]  # raison` "
            "à scripts/action_permission_override_allow.txt (une raison propre "
            "par ligne)."
        )
        return 1

    print("check_action_permission_override : OK — aucun get_permissions() à "
          "branchement brut n'affaiblit une @action déclarée "
          "(allowlist respectée).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
