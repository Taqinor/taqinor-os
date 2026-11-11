# flake8: noqa  (sonde ATST, DÉTECTEUR hôte stdlib : lecture + ast, ni base ni Django — rejouable à la main)
"""PF7 / ATST : le balayage « prix d'achat » `test_astk_garde_prix_achat.py::test_aucune_route_ne_sert_de_prix`, seule
preuve revendiquée des routes stock, est AVEUGLE sur deux routes admin-only : (a) `inventaires-annuels` (inventaire légal
valorisé au coût d'achat, `total_valeur` + `donnees` ; `permission_classes = [IsAdminRole]`, garde aussi le POST `figer`) —
le `setUp` ne crée aucun `InventaireAnnuel`, la liste rend `[]`, le détail est sauté ; (b) `produits/valorisation-xlsx`
(repli `IsAdminRole`) — toute réponse non JSON est exemptée. Mutants (vérifiés le 11/11) : `[IsAdminRole]` →
`[LectureDuModule]`, ou `'valorisation_xlsx'` ajouté à la branche `LectureDuModule` → Commercial, Viewer, Utilisateur,
Technicien… lisent la valorisation, le balayage reste vert, et les seuls autres tests de ces routes jouent un ADMIN.
Détecteur : `repro` vrai tant qu'au moins une des deux routes reste aveugle ET sans test qui joue un rôle LIVRÉ non admin."""
SONDE = {"constat": "C-ATST-008", "sha": "ae5a7ae4c",
         "attendu": "setUp du balayage sans InventaireAnnuel + exemption non-JSON ; aucun test de inventaires-annuels ni de valorisation-xlsx ne joue un rôle livré non admin -> repro True ; route seedée/balayée ou test fort ajouté -> False pour cette route"}
import ast, re, runpy
from pathlib import Path

RACINE = Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir():
    RACINE = Path.cwd()
BASE = RACINE / "backend/django_core"
BALAYAGE = BASE / "apps/stock/test_astk_garde_prix_achat.py"
ROUTES = {"inventaires-annuels": re.compile(r"inventaires-annuels|InventaireAnnuelViewSet|inventaireannuel-"),
          "produits/valorisation-xlsx": re.compile(r"valorisation-xlsx|produit-valorisation-xlsx")}


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


def balayage():
    """(setUp seede un InventaireAnnuel ?, réponses non JSON exemptées ?)"""
    if not BALAYAGE.is_file():
        return None, None
    src = BALAYAGE.read_text(encoding="utf-8")
    setup = ""
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.ClassDef) and n.name == "GardePrixAchat":
            for m in n.body:
                if isinstance(m, ast.FunctionDef) and m.name == "setUp":
                    setup = ast.get_source_segment(src, m) or ""
    seede = bool(re.search(r"InventaireAnnuel|figer_inventaire_annuel", setup))
    return seede, "'json' not in" in src.replace('"', "'")


def sonde(ctx=None):
    seede, exempte = balayage()
    if seede is None:
        return {"repro": False, "raison": "balayage test_astk_garde_prix_achat.py absent"}
    livres, consts = registre()
    aveugle_balayage = {"inventaires-annuels": not seede, "produits/valorisation-xlsx": bool(exempte)}
    par_route = {}
    for nom, motif in ROUTES.items():
        touchants, forts = [], []
        for p in fichiers_test():
            if p == BALAYAGE:
                continue
            t = p.read_text(encoding="utf-8", errors="replace")
            if not motif.search(t):
                continue
            for n in touche(t, ast.parse(t), motif):
                if True:
                    rel = p.relative_to(RACINE).as_posix()
                    touchants.append(rel + "::" + n.name)
                    r = sorted(set(raisons_fortes(n, livres, consts)))
                    if r:
                        forts.append({"bloc": rel + "::" + n.name, "raisons": r})
        par_route[nom] = {"balayage_aveugle": aveugle_balayage[nom], "blocs_touchant": touchants,
                          "blocs_forts": forts, "repro": aveugle_balayage[nom] and not forts}
    return {"repro": any(v["repro"] for v in par_route.values()), "routes": par_route,
            "setUp_seede_inventaire": seede, "balayage_exempte_non_json": exempte}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
