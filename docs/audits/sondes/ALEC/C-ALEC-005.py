"""Rejoue stock/views/negoce.py::AccordRFAFournisseurSerializer : VRAIE get_permissions de la liste, puis VRAI MasqueMontantsAchatMixin.to_representation appliqué aux champs réels du sérialiseur (Meta.fields et champs_montants_achat lus par ast) pour chaque rôle livré."""
SONDE = {"constat": "C-ALEC-005", "sha": "ae5a7ae4c",
         "attendu": "le masque retire seuil_ca_achat et montant_fixe mais taux_pct (la remise fournisseur) sort en clair pour les rôles livrés sans prix_achat_voir"}
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


def sonde(ctx=None):
    R, P, comptes = noyau()
    neg = "apps/stock/views/negoce.py"
    lisent = passent(comptes, gardes(P, neg, "AccordRFAFournisseurViewSet", "list"), vue(neg))
    ns = {"BasePermission": P["BasePermission"]}
    reel("apps/stock/permissions.py", "PeutVoirPrixAchat", None, ns)
    Mixin = reel("apps/stock/permissions.py", "MasqueMontantsAchatMixin", None, ns)
    ser = noeud(neg, "AccordRFAFournisseurSerializer")
    champs = ast.literal_eval(next(b for b in noeud(neg, "Meta", "AccordRFAFournisseurSerializer").body if getattr(b.targets[0], "id", "") == "fields").value)
    montants = ast.literal_eval(noeud(neg, "champs_montants_achat", "AccordRFAFournisseurSerializer").value)

    class Base:  # to_representation de ModelSerializer réduit à « tous les champs déclarés »
        def to_representation(self, instance): return {c: 1 for c in champs}

    class Sortie(Mixin, Base):
        champs_montants_achat = montants
        context = {}

    rendu = {}
    for nom in lisent:
        s = Sortie(); s.context = {"request": NS(user=comptes[nom], method="GET")}
        rendu[nom] = s.to_representation(None)
    fuient = [n for n in lisent if "prix_achat_voir" not in comptes[n].role.permissions and "taux_pct" in rendu[n]]
    temoin = [n for n in fuient if "montant_fixe" not in rendu[n] and "seuil_ca_achat" not in rendu[n]]  # le masque joue bien pour les deux autres champs
    return {"repro": bool(fuient) and "MasqueMontantsAchatMixin" in [ast.unparse(b) for b in ser.bases], "observe": {
        "methode": "VRAIE get_permissions + VRAI mixin de masque exécutés ; champs du sérialiseur lus par ast",
        "route": "GET stock/accords-rfa-fournisseur/", "garde": [type(g).__name__ for g in gardes(P, neg, "AccordRFAFournisseurViewSet", "list")],
        "champs_masques": list(montants), "champ_qui_reste": "taux_pct", "code_attendu": "prix_achat_voir",
        "roles_livres_qui_voient_taux_pct_sans_le_code": fuient, "dont_masque_actif_sur_montant_fixe_et_seuil": temoin}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
