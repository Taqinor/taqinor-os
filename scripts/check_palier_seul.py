"""ADRG79 (C-ADRG-030) — gèle les routes d'ÉCRITURE gardées au seul palier.

Une route d'écriture gardée par ``IsResponsableOrAdmin`` SANS aucun code de la
grille n'exige qu'« un droit d'écriture quelconque du module »
(``CustomUser._role_grants_write``) : décocher « Créer », « Modifier » ou
« Valider » dans l'éditeur de rôles n'y change rien (D-ASEC-VER4-1, D-ASEC-50).
Les ~580 routes existantes forment une DETTE GELÉE (``palier_seul_dette.txt``,
qui ne fait que rétrécir) ; toute NOUVELLE route de ce type fait échouer la CI.

Une route passe si sa garde effective contient ``DroitDeLaGrille``,
``HasPermissionOrLegacy``, ``HasPermissionAndRole``, ``IsAdminRole`` ou une
classe ``Peut*``. Garde effective : ``permission_classes`` de l'``@action``
(sans ``get_permissions`` local, ou patron d'or / repli ``super()``), sinon la
branche de ``get_permissions`` qui nomme l'action, sinon son repli final, sinon
l'attribut ``permission_classes`` de la classe ; vues fonction :
``@permission_classes`` d'un ``@api_view`` d'écriture. Garde non analysable
(héritée, calculée) : hors périmètre.

AST seul, sans Django ni base (job ``backend-lint-fast``). Réutilise les
lecteurs de ``check_action_permission_override.py``.

Usage :
    python scripts/check_palier_seul.py            # check (CI)
    python scripts/check_palier_seul.py --amorcer  # (ré)écrit la dette
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_action_permission_override import (  # noqa: E402 — après sys.path
    _actions_couvertes, _constantes_de_module, _delegue_au_repli, _is_test_path,
    _nom_appele, _permissions_liste, _utilise_le_patron_d_or,
)

TYPE_DE_CLE = "par_symbole"  # cle `fichier::Classe.action` (jamais un numero de ligne)

ROOT = Path(__file__).resolve().parent.parent
DETTE = "scripts/palier_seul_dette.txt"
PALIER = "IsResponsableOrAdmin"
CODES = ("DroitDeLaGrille", "HasPermissionOrLegacy", "HasPermissionAndRole",
         "IsAdminRole")
ECRITURES = {"post", "put", "patch", "delete"}
#: Base de classe (sous-chaîne) -> actions d'écriture standard héritées.
BASES = (("ModelViewSet", {"create", "update", "partial_update", "destroy"}),
         ("CreateModelMixin", {"create"}), ("CreateAPIView", {"create"}),
         ("UpdateModelMixin", {"update", "partial_update"}),
         ("UpdateAPIView", {"update", "partial_update"}),
         ("UpdateDestroyAPIView", {"update", "partial_update", "destroy"}),
         ("DestroyModelMixin", {"destroy"}), ("DestroyAPIView", {"destroy"}))


def _passe(garde) -> bool:
    noms = [g.split("(")[0].split(".")[-1] for g in garde]
    return any(n in CODES or n.startswith("Peut") for n in noms)


def _palier_seul(garde) -> bool:
    return garde is not None and any(
        g.split("(")[0].split(".")[-1] == PALIER for g in garde) and not _passe(garde)


def _methodes_action(fonction):
    """Méthodes HTTP d'un ``@action`` (défaut GET) ; None si pas une action."""
    for deco in fonction.decorator_list:
        if isinstance(deco, ast.Call) and (_nom_appele(deco) or "").endswith("action"):
            for kw in deco.keywords:
                if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                    return {e.value.lower() for e in kw.value.elts if isinstance(e, ast.Constant)}
            return {"get"}
    return None


def _declaree(fonction):
    for deco in fonction.decorator_list:
        if isinstance(deco, ast.Call):
            for kw in deco.keywords:
                if kw.arg == "permission_classes":
                    return _permissions_liste(kw.value)
    return None


def _nomme(test, action, constantes) -> bool:
    noms = _actions_couvertes(ast.Module(body=[ast.Expr(test)], type_ignores=[]), constantes)
    negatif = (isinstance(test, ast.Compare) and len(test.ops) == 1
               and isinstance(test.ops[0], (ast.NotIn, ast.NotEq)))
    return (action not in noms) if negatif else (action in noms)


def _branche(corps, action, constantes, repli_classe):
    """Garde rendue pour ``action`` par une suite d'instructions ; None si non
    analysable, ``False`` si la suite ne rend rien (on continue)."""
    for stmt in corps:
        if isinstance(stmt, ast.If):
            suite = stmt.body if _nomme(stmt.test, action, constantes) else stmt.orelse
            garde = _branche(suite, action, constantes, repli_classe)
            if garde is not False:
                return garde
        elif isinstance(stmt, ast.Return):
            if isinstance(stmt.value, ast.Call) and _nom_appele(stmt.value) == "super().get_permissions":
                return repli_classe
            return _permissions_liste(stmt.value) if stmt.value is not None else None
    return False


def _routes_de_classe(classe, constantes):
    attr = None
    get_perms, methodes = None, {}
    for m in classe.body:
        if isinstance(m, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "permission_classes" for t in m.targets):
            attr = _permissions_liste(m.value)
        elif isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if m.name == "get_permissions":
                get_perms = m
            methodes[m.name] = m
    actions = {}
    bases = " ".join(ast.unparse(b) for b in classe.bases)
    if "ReadOnly" not in bases:
        for motif, noms in BASES:
            if motif in bases:
                actions.update({n: None for n in noms})
    for nom, m in methodes.items():
        meth = _methodes_action(m)
        if meth is not None and meth & ECRITURES:
            actions[nom] = m
        elif nom in ECRITURES or nom in {"create", "update", "partial_update", "destroy"}:
            actions[nom] = None
    for nom, m in sorted(actions.items()):
        declare = _declaree(m) if m is not None else None
        if get_perms is None:
            garde = declare if declare is not None else attr
        elif declare is not None and (_utilise_le_patron_d_or(get_perms)
                                      or _delegue_au_repli(get_perms)):
            garde = declare
        else:
            garde = _branche(get_perms.body, nom, constantes, attr)
            garde = None if garde is False else garde
        yield nom, garde


def routes_palier_seul(path: Path, rel: str):
    """Clés ``rel::Classe.action`` / ``rel::fonction`` des routes au seul palier."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []
    constantes = _constantes_de_module(tree)
    cles = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            cles += [f"{rel}::{node.name}.{nom}" for nom, garde in _routes_de_classe(node, constantes)
                     if _palier_seul(garde)]
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            meth, garde = set(), None
            for deco in node.decorator_list:
                nom = _nom_appele(deco) if isinstance(deco, ast.Call) else None
                if nom and nom.endswith("api_view") and deco.args:
                    meth = {e.value.lower() for e in getattr(deco.args[0], "elts", [])
                            if isinstance(e, ast.Constant)}
                elif nom and nom.endswith("permission_classes") and deco.args:
                    garde = _permissions_liste(deco.args[0])
            if meth & ECRITURES and _palier_seul(garde):
                cles.append(f"{rel}::{node.name}")
    return cles


def inventaire(root: Path):
    cles = set()
    base = root / "backend" / "django_core"
    for sous in ("apps", "core", "authentication"):
        for path in sorted((base / sous).rglob("*.py")) if (base / sous).is_dir() else []:
            if not _is_test_path(path):
                rel = str(path.relative_to(root)).replace("\\", "/")
                cles.update(routes_palier_seul(path, rel))
    return cles


def lire_dette(root: Path):
    chemin = root / DETTE
    if not chemin.exists():
        return set()
    return {ligne.split("#")[0].strip() for ligne in chemin.read_text(encoding="utf-8").splitlines()
            if ligne.split("#")[0].strip()}


def main(argv=None, root: Path = ROOT) -> int:
    argv = sys.argv[1:] if argv is None else argv
    trouvees = inventaire(root)
    if "--amorcer" in argv:
        (root / DETTE).write_text(
            "# ADRG79 — routes d'écriture au seul palier (IsResponsableOrAdmin, aucun code de\n"
            "# grille), gelées : ne fait que rétrécir. Régénérer : --amorcer.\n"
            + "".join(f"{c}\n" for c in sorted(trouvees)), encoding="utf-8", newline="\n")
        print(f"check_palier_seul : dette amorcée ({len(trouvees)} routes).")
        return 0
    dette = lire_dette(root)
    neuves, perimees = sorted(trouvees - dette), sorted(dette - trouvees)
    for cle in neuves:
        print(f"  - {cle} — route d'écriture au seul palier : ajoutez un code de la "
              "grille (DroitDeLaGrille / HasPermissionOrLegacy) ou IsAdminRole")
    for cle in perimees:
        print(f"  - {cle} — dette périmée (route corrigée ou disparue) : retirez la ligne de {DETTE}")
    if neuves or perimees:
        print(f"check_palier_seul : {len(neuves)} route(s) neuve(s), {len(perimees)} dette(s) périmée(s).")
        return 1
    print(f"check_palier_seul : OK ({len(dette)} routes en dette gelée).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
