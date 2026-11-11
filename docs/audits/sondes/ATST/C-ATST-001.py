# flake8: noqa  (sonde ATST, DÉTECTEUR hôte stdlib : lecture + ast, ni base ni Django — rejouable à la main)
"""PF7 / ATST : `RevalorisationStockViewSet` (`permission_classes = [IsAdminRole]`, coût du stock valorisé) n'est refusée
dans les tests qu'avec un rôle FABRIQUÉ `permissions=['stock_voir']` (jamais responsable : le 403 vient de
`IsResponsableOrAdmin`, pas de la garde administrateur). Détecteur : `repro` reste vrai tant que le test faible est
présent ET qu'aucun test de la route ne joue un rôle LIVRÉ non administrateur (registre `CANONICAL_SYSTEM_ROLES`)."""
SONDE = {"constat": "C-ATST-001", "sha": "ae5a7ae4c",
         "attendu": "test_endpoint_admin_only refuse avec ['stock_voir'] fabriqué ; aucun test de la route revalorisations-stock ne joue un rôle livré non admin (Commercial responsable, Technicien responsable…) -> repro True ; un test fort ajouté -> False"}
import ast, re, runpy
from pathlib import Path

RACINE = Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir():
    RACINE = Path.cwd()
BASE = RACINE / "backend/django_core"
FAIBLE = BASE / "apps/stock/test_xstk14_revalorisation_stock.py"
ROUTE = re.compile(r"revalorisations-stock|RevalorisationStockViewSet|revalorisationstock-")


def registre():
    g = runpy.run_path(str(BASE / "apps/roles/permissions_registre.py"))
    r = g["CANONICAL_SYSTEM_ROLES"]
    admin = {n for n, p in r if "roles_gerer" in p}
    livres = {n: frozenset(p) for n, p in r if n not in admin}
    consts = {k: frozenset(v) for k, v in g.items() if k.endswith("_PERMISSIONS") and isinstance(v, (list, tuple))
              and any(frozenset(v) == j for j in livres.values())}
    return livres, consts


def fichiers_test():
    for p in sorted(BASE.rglob("*.py")):
        s = p.as_posix()
        if "/migrations/" not in s and (p.name.startswith("test") or "/tests/" in s):
            yield p


def raisons_fortes(noeud, livres, consts):
    """Pourquoi ce bloc joue un rôle livré NON admin : nom, jeu de codes égal, constante du registre, init_roles."""
    out = []
    for n in ast.walk(noeud):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            if n.value in livres:
                out.append("nom:" + n.value)
            elif n.value == "init_roles":
                out.append("init_roles")
        elif isinstance(n, (ast.List, ast.Tuple, ast.Set)) and n.elts and all(
                isinstance(e, ast.Constant) and isinstance(e.value, str) for e in n.elts):
            jeu = frozenset(e.value for e in n.elts)
            out += ["codes==" + k for k, v in livres.items() if v == jeu]
        else:
            i = n.id if isinstance(n, ast.Name) else n.attr if isinstance(n, ast.Attribute) else None
            if i in consts:
                out.append("registre." + i)
    return out


def sonde(ctx=None):
    if not FAIBLE.is_file():
        return {"repro": False, "raison": "fichier de test absent : " + FAIBLE.relative_to(RACINE).as_posix()}
    src = FAIBLE.read_text(encoding="utf-8")
    arbre = ast.parse(src)
    faible = [f for f in ast.walk(arbre) if isinstance(f, ast.FunctionDef) and f.name == "test_endpoint_admin_only"
              and "'stock_voir'" in (ast.get_source_segment(src, f) or "").replace('"', "'")
              or isinstance(f, ast.ClassDef) and f.name == "ValiderRevalorisationTests"
              and "permissions=['stock_voir']" in (ast.get_source_segment(src, f) or "").replace('"', "'")]
    if not faible:
        return {"repro": False, "raison": "le test faible (rôle fabriqué ['stock_voir']) n'existe plus"}
    livres, consts = registre()
    touchants, forts = [], []
    for p in fichiers_test():
        t = p.read_text(encoding="utf-8", errors="replace")
        if not ROUTE.search(t):
            continue
        a = ast.parse(t)
        for n in a.body:
            seg = ast.get_source_segment(t, n) or ""
            if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and ROUTE.search(seg):
                rel = p.relative_to(RACINE).as_posix()
                touchants.append(rel + "::" + n.name)
                r = sorted(set(raisons_fortes(n, livres, consts)))
                if r:
                    forts.append({"bloc": rel + "::" + n.name, "raisons": r})
    return {"repro": not forts, "blocs_touchant_la_route": len(touchants), "blocs_forts": len(forts),
            "forts": forts, "touchants": touchants, "roles_livres_non_admin": sorted(livres)}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
