"""Rejoue stock/views/entrepot.py::entrepot_cockpit_view : permission_classes du décorateur (lu par ast) exécutée, puis VRAI stock/selectors_entrepot.py::cockpit_entrepot (ORM bouchonné) : expeditions_du_jour[].cout_total = somme des cout_reel (coût de transport, masqué ailleurs)."""
SONDE = {"constat": "C-ALEC-009", "sha": "ae5a7ae4c",
         "attendu": "avec une seule expédition du jour, expeditions_du_jour[0].cout_total = son cout_reel exact, servi à des rôles livrés sans prix_achat_voir"}
import ast, pathlib, runpy, sys, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
NS = types.SimpleNamespace


def noeud(chemin, nom, classe=None):  # nœud AST (fonction, classe, affectation) d'un fichier du dépôt
    arbre = ast.parse((DJ / chemin).read_text(encoding="utf-8"))
    corps = arbre.body if not classe else next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == classe).body
    return next(n for n in corps if getattr(n, "name", None) == nom or (isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == nom))


def reel(chemin, nom, classe=None, ns=None):  # CORPS RÉEL compilé (décorateurs et imports locaux retirés : leurs noms viennent de ns)
    n = noeud(chemin, nom, classe); ns = {} if ns is None else ns; n.decorator_list = []
    class Sans(ast.NodeTransformer):  # imports (même imbriqués) remplacés par pass
        visit_Import = visit_ImportFrom = lambda s, b: ast.Pass()
    n = Sans().visit(n)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[n], type_ignores=[])), chemin, "exec"), ns)
    return ns[nom]


def constantes(chemin):  # constantes littérales de module (READ_ACTIONS…)
    sortie = {}
    for n in ast.parse((DJ / chemin).read_text(encoding="utf-8")).body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
            try: sortie[n.targets[0].id] = ast.literal_eval(n.value)
            except ValueError: pass
    return sortie


def noyau():  # (R, P, comptes) : registre vivant, VRAIES gardes d'authentication/permissions.py, vrais accesseurs de CustomUser, un compte par rôle LIVRÉ interne
    R = runpy.run_path(str(DJ / "apps/roles/permissions_registre.py"))
    rp = types.ModuleType("rest_framework.permissions"); rp.SAFE_METHODS, rp.BasePermission = ("GET", "HEAD", "OPTIONS"), type("BasePermission", (), {})
    avant = {n: sys.modules.get(n) for n in ("rest_framework", "rest_framework.permissions")}
    sys.modules.update({"rest_framework": types.ModuleType("rest_framework"), "rest_framework.permissions": rp})
    try:
        P = {"__name__": "authentication.permissions"}; exec(compile((DJ / "authentication/permissions.py").read_text(encoding="utf-8"), "permissions.py", "exec"), P)
    finally:
        for n, m in avant.items(): sys.modules.pop(n, None) if m is None else sys.modules.update({n: m})
    P["enregistrer_registre_modules"](R["PERMISSION_MODULE"], octrois_lecture=R["OCTROIS_LECTURE"])
    cls = ast.parse("class U:\n    pass").body[0]
    cls.body = [n for n in noeud("authentication/models.py", "CustomUser").body if getattr(n, "name", "") in (
        "is_admin_role", "is_responsable", "_role_grants_write", "has_erp_permission", "can_view_buy_prices", "can_view_marge", "can_view_activity_log")]
    U = {}; exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), "models.py", "exec"), U); U = U["U"]; U.ROLE_ADMIN, U.ROLE_RESPONSABLE = "admin", "responsable"
    comptes = {}
    for nom, perms in R["CANONICAL_SYSTEM_ROLES"]:
        if not nom.startswith("Portail"):
            c = U(); c.__dict__.update(is_superuser=False, is_authenticated=True, portee="interne", role_legacy="normal", role_id=1, id=len(comptes) + 1, role=NS(nom=nom, permissions=list(perms)))
            comptes[nom] = c
    return R, P, comptes


def vue(chemin): return type("Vue", (), {"__module__": chemin[:-3].replace("/", ".")})()  # vue factice : seul le MODULE Python réel compte (module_de_la_vue)


def gardes(P, chemin, classe, action):  # exécute la VRAIE get_permissions de la classe pour ``action``
    return reel(chemin, "get_permissions", classe, {**P, **constantes(chemin)})(NS(action=action))


def passent(comptes, liste, v, methode="GET"):  # rôles LIVRÉS qui franchissent TOUTES les gardes (vraies classes) sur la vue v
    return sorted(n for n, c in comptes.items() if all(g.has_permission(NS(user=c, method=methode), v) for g in liste))


class Chaine(list):  # queryset bouchon : toute méthode de chaînage rend la même liste
    def __getattr__(s, n): return lambda *a, **k: s


def sonde(ctx=None):
    import datetime
    from decimal import Decimal
    R, P, comptes = noyau()
    ent = "apps/stock/views/entrepot.py"; sel = "apps/stock/selectors_entrepot.py"
    deco = next(d for d in noeud(ent, "entrepot_cockpit_view").decorator_list if isinstance(d, ast.Call) and getattr(d.func, "id", "") == "permission_classes")
    noms = [ast.unparse(e) for e in deco.args[0].elts]
    g = [P[n]() for n in noms]
    lisent = passent(comptes, g, vue(ent))
    exp = NS(cout_reel=Decimal("412.50"), transporteur_provider="transporteur-a", statut="x")
    vide = lambda: NS(objects=Chaine())
    ns = {**constantes(sel), "Decimal": Decimal, "timezone": NS(now=lambda: datetime.datetime(2026, 11, 10, 9), localdate=lambda m: m.date()),
          "remplissage_par_zone": lambda *a, **k: [], "zones_en_surcapacite": lambda *a, **k: [], "logger": NS(warning=lambda *a, **k: None), "datetime": datetime,
          "LotEntrepot": vide(), "PlanComptageTournant": vide(), "VaguePicking": NS(objects=Chaine(), Statut=NS(LANCEE="x")),
          "ExpeditionTransporteur": NS(objects=Chaine([exp]), Statut=NS(ANNULE="annule"))}
    reel(sel, "_dec", None, ns); reel(sel, "_fmt_dec", None, ns)
    cockpit = reel(sel, "cockpit_entrepot", None, ns)("societe")
    fuient = [n for n in lisent if "prix_achat_voir" not in comptes[n].role.permissions]
    masque = any(m in ast.unparse(noeud(sel, "cockpit_entrepot")) + ast.unparse(noeud(ent, "entrepot_cockpit_view")) for m in ("can_view_buy_prices", "PeutVoirPrixAchat", "prix_achat_voir"))
    cout = (cockpit["expeditions_du_jour"] or [{}])[0].get("cout_total")
    return {"repro": bool(fuient) and cout == "412.5" and not masque, "observe": {
        "methode": "permission_classes du décorateur lu par ast et exécuté ; VRAI cockpit_entrepot exécuté (ORM bouchonné, 1 expédition à cout_reel=412.50)",
        "route": "GET stock/entrepot/cockpit/", "garde": noms, "expeditions_du_jour": cockpit["expeditions_du_jour"], "masque_dans_la_vue_ou_le_selecteur": masque,
        "code_attendu": "prix_achat_voir", "roles_livres_sans_le_code_qui_lisent": fuient}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
