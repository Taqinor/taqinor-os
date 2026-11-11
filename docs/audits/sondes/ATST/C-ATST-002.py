# flake8: noqa  (sonde ATST, DÉTECTEUR hôte stdlib : lecture + ast, ni base ni Django — rejouable à la main)
"""PF7 / ATST : `PlanCommissionViewSet` (garde MARGE `HasPermissionOrLegacy('prix_achat_voir')`, plans/taux de commission) n'est
refusé dans `test_wir281_plans_commission_rest.py` qu'avec des rôles FABRIQUÉS nommés « Commercial » portant `['ventes_voir']`
seul (le vrai Commercial écrit sur ventes) ; `test_adev41_garde_portee_ventes.py` EXEMPTE le viewset. Détecteur : `repro`
reste vrai tant que les tests faibles sont présents, que l'exemption adev41 tient ET qu'aucun bloc de test de la route ne
joue un rôle livré avec SES vrais codes (jeu de codes égal ou constante `*_PERMISSIONS` du registre)."""
SONDE = {"constat": "C-ATST-002", "sha": "ae5a7ae4c",
         "attendu": "3 tests wir281 refusent avec un rôle « Commercial » fabriqué ['ventes_voir'] ; adev41 exempte PlanCommissionViewSet ; aucun test de la route ne joue le vrai Commercial du registre -> repro True ; un test fort ajouté -> False"}
import ast, re, runpy
from pathlib import Path

RACINE = Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir():
    RACINE = Path.cwd()
BASE = RACINE / "backend/django_core"
FAIBLE = BASE / "apps/ventes/tests/test_wir281_plans_commission_rest.py"
ADEV41 = BASE / "apps/ventes/tests/test_adev41_garde_portee_ventes.py"
TESTS = ("test_lecture_refusee_sans_prix_achat_voir", "test_ecriture_refusee_sans_prix_achat_voir",
         "test_resoudre_gate_par_prix_achat_voir")
ROUTE = re.compile(r"plans-commission|plan-commission|plancommission-")  # URL seule : le nom du viewset figure aussi dans les listes d exemption


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
    """Ce bloc joue un rôle livré NON admin avec ses VRAIS codes : jeu de codes égal ou constante du registre."""
    out = []
    for n in ast.walk(noeud):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            pass  # le NOM seul ne prouve rien : wir281 nomme déjà « Commercial » un rôle fabriqué
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
    faibles = [f.name for k in arbre.body if isinstance(k, ast.ClassDef) and k.name in ("TestGarde", "TestResoudre")
               for f in k.body if isinstance(f, ast.FunctionDef) and f.name in TESTS]
    if not faibles or "'ventes_voir'" not in src.replace('"', "'"):
        return {"repro": False, "raison": "les tests faibles (rôle fabriqué ['ventes_voir']) n'existent plus"}
    exempte = ADEV41.is_file() and bool(re.search(r"""['"]PlanCommissionViewSet['"]\s*:""",
                                                  ADEV41.read_text(encoding="utf-8")))
    livres, consts = registre()
    fichiers, forts = [], []
    for p in fichiers_test():
        t = p.read_text(encoding="utf-8", errors="replace")
        if not ROUTE.search(t):
            continue
        a = ast.parse(t)  # l'URL est souvent une constante de module : on juge TOUS les blocs du fichier
        rel = p.relative_to(RACINE).as_posix()
        fichiers.append(rel)
        for n in a.body:
            if isinstance(n, (ast.ClassDef, ast.FunctionDef)):
                r = sorted(set(raisons_fortes(n, livres, consts)))
                if r:
                    forts.append({"bloc": rel + "::" + n.name, "raisons": r})
    return {"repro": exempte and not forts, "tests_faibles": faibles, "adev41_exempte": exempte,
            "fichiers_touchant_la_route": fichiers, "blocs_forts": len(forts), "forts": forts}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
