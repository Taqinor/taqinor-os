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


def main(argv):
    list_mode = "--list" in argv
    allow = _load_allowlist()
    offenders, listed = [], []
    for path in _iter_source_files():
        rel = _rel(path)
        for lineno, classe, verdict, decouvertes in check_file(path):
            listed.append(f"{rel}:{lineno}  {classe}  [{verdict}]"
                          + (f"  à découvert : {', '.join(decouvertes)}"
                             if decouvertes else ""))
            if verdict == "NU" and f"{rel}::{classe}" not in allow:
                offenders.append(
                    f"{rel}:{lineno}  {classe} — action(s) à découvert : "
                    f"{', '.join(decouvertes)}")

    if list_mode:
        for line in listed:
            print(line)
        return 0

    if offenders:
        print("check_action_permission_override : get_permissions() à "
              "branchement brut sur une classe qui déclare pourtant une "
              "@action(permission_classes=...) :")
        for line in offenders:
            print(f"  - {line}")
        print(
            "\nDRF appelle get_permissions() pour TOUTE requête, action "
            "comprise : un branchement qui rend une liste par défaut IGNORE "
            "la permission_classes déclarée sur l'action (motif AUD403, "
            "ventes/views/devis.py). Terminez par "
            "`return super().get_permissions()`, ou passez par "
            f"`{HELPER_DECLARE}(...)` (patron d'or, apps/ventes/views/paiement.py). "
            "Exception assumée et vérifiée : ajouter `chemin.py::Classe` à "
            "scripts/action_permission_override_allow.txt avec sa "
            "justification."
        )
        return 1

    print("check_action_permission_override : OK — aucun get_permissions() à "
          "branchement brut n'affaiblit une @action déclarée "
          "(allowlist respectée).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
