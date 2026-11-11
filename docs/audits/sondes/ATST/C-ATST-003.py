# flake8: noqa  (sonde ATST, DÉTECTEUR hôte stdlib : lecture + ast, ni base ni Django — rejouable à la main)
"""PF7 / ATST : `DevisViewSet.variante_config` (PUT) est gardé PAR NOM de rôle (tuple `role_nom in ('Directeur',
'Commercial responsable')` de `views/devis.py`). `test_qg9_variante_pct.py::VarianteConfigEndpointTests` fabrique ses rôles
(`['ventes_voir']`) et n'y joue jamais « Commercial » (2 comptes en prod) : retirer ou ajouter ce nom au tuple ne rougit rien.
Détecteur : `repro` reste vrai tant que le test faible est présent ET qu'aucun bloc de test de la route ne crée un rôle nommé
« Commercial » (ou ne joue ses vrais codes : constante du registre / jeu de codes égal)."""
SONDE = {"constat": "C-ATST-003", "sha": "ae5a7ae4c",
         "attendu": "test_viewer_forbidden est le seul refus de variante-config ; aucun test ne crée/joue un rôle « Commercial » sur cette action -> repro True ; un test Commercial ajouté -> False"}
import ast, re, runpy
from pathlib import Path

RACINE = Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir():
    RACINE = Path.cwd()
BASE = RACINE / "backend/django_core"
FAIBLE = BASE / "apps/ventes/tests/test_qg9_variante_pct.py"
DEVIS = BASE / "apps/ventes/views/devis.py"
ROUTE = re.compile(r"variante-config|variante_config")


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
            if n.value == "Commercial":
                out.append("nom:Commercial")
        elif isinstance(n, (ast.List, ast.Tuple, ast.Set)) and n.elts and all(
                isinstance(e, ast.Constant) and isinstance(e.value, str) for e in n.elts):
            jeu = frozenset(e.value for e in n.elts)
            out += ["codes==" + k for k, v in livres.items() if v == jeu and k == "Commercial"]
        else:
            i = n.id if isinstance(n, ast.Name) else n.attr if isinstance(n, ast.Attribute) else None
            if i in consts and consts[i] == livres["Commercial"]:
                out.append("registre." + i)
    return out


def sonde(ctx=None):
    if not FAIBLE.is_file():
        return {"repro": False, "raison": "fichier de test absent : " + FAIBLE.relative_to(RACINE).as_posix()}
    src = FAIBLE.read_text(encoding="utf-8")
    arbre = ast.parse(src)
    faible = [f for k in ast.walk(arbre) if isinstance(k, ast.ClassDef) and k.name == "VarianteConfigEndpointTests"
              for f in k.body if isinstance(f, ast.FunctionDef) and f.name == "test_viewer_forbidden"]
    if not faible:
        return {"repro": False, "raison": "VarianteConfigEndpointTests.test_viewer_forbidden n'existe plus"}
    garde = None  # tuple de noms de la garde par nom dans views/devis.py
    for n in ast.walk(ast.parse(DEVIS.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Compare) and isinstance(n.ops[0], ast.In) and isinstance(n.comparators[0], ast.Tuple):
            t = [e.value for e in n.comparators[0].elts if isinstance(e, ast.Constant)]
            if "Directeur" in t:
                garde = t
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
    return {"repro": not forts, "garde_par_nom": garde, "blocs_touchant_la_route": len(touchants), "blocs_forts": len(forts),
            "forts": forts, "touchants": touchants, }


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
