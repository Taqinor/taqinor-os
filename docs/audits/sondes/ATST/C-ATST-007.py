# flake8: noqa  (sonde ATST, DÉTECTEUR hôte stdlib : lecture + ast, ni base ni Django — rejouable à la main)
"""PF7 / ATST : le PDF INTERNE d'une facture fournisseur (`FactureFournisseurViewSet.pdf`, repli `IsAdminRole` de
`get_permissions` — lignes, HT/TVA/TTC, paiements, acomptes, avoirs) n'est refusé dans les tests qu'avec un compte HÉRITÉ
`role_legacy='normal'` (jamais responsable) et `assertIn(status, [403, 404])`. Mutant (vérifié le 11/11, AUD421 compris) :
`elif self.action == 'pdf': return [IsResponsableOrAdmin()]` → le compte `normal` reste refusé, Commercial, Commercial
responsable, Technicien, Technicien responsable, Responsable et Admin Ventes téléchargent le PDF ; le balayage
`test_astk_garde_prix_achat.py` exempte toute réponse non JSON. Détecteur : `repro` reste vrai tant que le test faible est
présent ET qu'aucun test de la route ne joue un rôle LIVRÉ non administrateur ET que le balayage exempte le non-JSON."""
SONDE = {"constat": "C-ATST-007", "sha": "ae5a7ae4c",
         "attendu": "test_pdf_not_accessible_non_admin joue role_legacy='normal' + assertIn 403/404 ; aucun test de factures-fournisseur/<id>/pdf/ ne joue un rôle livré non admin ; balayage ASTK14 exempte le non-JSON -> repro True ; un test fort ajouté -> False"}
import ast, re, runpy
from pathlib import Path

RACINE = Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir():
    RACINE = Path.cwd()
BASE = RACINE / "backend/django_core"
FAIBLE = BASE / "apps/stock/tests_fg.py"
BALAYAGE = BASE / "apps/stock/test_astk_garde_prix_achat.py"
VUE = BASE / "apps/stock/views/facture_fournisseur.py"
ROUTE = re.compile(r"factures-fournisseur/[^'\"\n]*/pdf/|facturefournisseur-pdf")


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


def touche(t, arbre, motif):
    """Blocs de plus haut niveau qui citent la route, en direct ou via une constante de module (URL = '...')."""
    noms = {c.id for n in arbre.body if isinstance(n, ast.Assign) and motif.search(ast.get_source_segment(t, n) or "")
            for c in n.targets if isinstance(c, ast.Name)}
    for n in arbre.body:
        s = ast.get_source_segment(t, n) or ""
        if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and (motif.search(s) or any(re.search(r"\b%s\b" % x, s) for x in noms)):
            yield n


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
    seg = ""
    for f in ast.walk(ast.parse(src)):
        if isinstance(f, ast.FunctionDef) and f.name == "test_pdf_not_accessible_non_admin":
            seg = (ast.get_source_segment(src, f) or "").replace('"', "'")
    faible = "role_legacy='normal'" in seg and re.search(r"assertIn\(\s*r\.status_code,\s*[\[(]\s*403,\s*404", seg)
    if not faible:
        return {"repro": False, "raison": "le test faible (compte hérité 'normal' + assertIn 403/404) n'existe plus"}
    vue = VUE.read_text(encoding="utf-8") if VUE.is_file() else ""
    pdf_nomme = bool(re.search(r"self\.action\s*(==\s*'pdf'|in\s*\([^)]*'pdf')", vue))
    bal = BALAYAGE.read_text(encoding="utf-8") if BALAYAGE.is_file() else ""
    exempte_non_json = "'json' not in" in bal.replace('"', "'")
    livres, consts = registre()
    touchants, forts = [], []
    for p in fichiers_test():
        t = p.read_text(encoding="utf-8", errors="replace")
        if not ROUTE.search(t):
            continue
        for n in touche(t, ast.parse(t), ROUTE):
            if True:
                rel = p.relative_to(RACINE).as_posix()
                touchants.append(rel + "::" + n.name)
                r = sorted(set(raisons_fortes(n, livres, consts)))
                if r:
                    forts.append({"bloc": rel + "::" + n.name, "raisons": r})
    return {"repro": not forts and (exempte_non_json or not bal), "blocs_touchant_la_route": touchants,
            "blocs_forts": forts, "balayage_exempte_non_json": exempte_non_json,
            "action_pdf_nommee_dans_get_permissions": pdf_nomme, "roles_livres_non_admin": sorted(livres)}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
