"""Rejoue les deux emplacements du tarif de transport : stock/views/wms.py::ExpeditionTransporteurViewSet.tarifs (VRAIES get_permissions et comparer_tarifs_transporteurs) et installations/views/transporteur.py::TransporteurViewSet (garde exécutée, sérialiseur lu par ast). Constat gaté par D-ALEC-1 : la sonde prouve le FAIT (le tarif sort sans masque), pas sa qualification de prix d'achat."""
SONDE = {"constat": "C-ALEC-004", "sha": "ae5a7ae4c",
         "attendu": "des rôles livrés sans prix_achat_voir obtiennent le tarif_base du transporteur (offres[].cout et tarif_base), alors que cout_reel est masqué par le même mécanisme ailleurs"}
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
    from decimal import Decimal
    # Emplacement 1 : stock — GET stock/expeditions/tarifs/
    wms = "apps/stock/views/wms.py"
    g1 = gardes(P, wms, "ExpeditionTransporteurViewSet", "tarifs")
    r1 = passent(comptes, g1, vue(wms))
    transporteur = NS(id=3, nom="Transporteur A", tarif_base=Decimal("350.00"))
    modele = NS(objects=NS(filter=lambda **k: NS(order_by=lambda c: [transporteur])))
    ns = {"Decimal": Decimal, "ExpeditionTransporteur": NS(_meta=NS(get_field=lambda n: NS(related_model=modele))), "providers_configures": lambda company: []}
    offres = reel("apps/stock/selectors_wms.py", "comparer_tarifs_transporteurs", None, ns)(NS(company="c", poids_kg=5, dimensions=""))
    masque1 = any(m in ast.unparse(noeud(wms, "tarifs", "ExpeditionTransporteurViewSet")) + ast.unparse(noeud("apps/stock/selectors_wms.py", "comparer_tarifs_transporteurs"))
                  for m in ("can_view_buy_prices", "PeutVoirPrixAchat", "prix_achat_voir"))
    lisent1 = [n for n in r1 if "prix_achat_voir" not in comptes[n].role.permissions]
    # Emplacement 2 : installations — GET installations/transporteurs/
    ins = "apps/installations/views/transporteur.py"
    r2 = passent(comptes, gardes(P, ins, "TransporteurViewSet", "list"), vue(ins))
    ser = noeud("apps/installations/serializers.py", "TransporteurSerializer")
    champs = ast.literal_eval(next(b for b in noeud("apps/installations/serializers.py", "Meta", "TransporteurSerializer").body if getattr(b.targets[0], "id", "") == "fields").value)
    sert_tarif = "tarif_base" in champs and not any("Masque" in ast.unparse(b) for b in ser.bases) and not any(getattr(b, "name", "") == "to_representation" for b in ser.body)
    lisent2 = [n for n in r2 if "prix_achat_voir" not in comptes[n].role.permissions]
    return {"repro": bool((lisent1 and offres and offres[0]["cout"] == Decimal("350.00") and not masque1) or (lisent2 and sert_tarif)), "observe": {
        "methode": "VRAIES get_permissions + VRAIE comparer_tarifs_transporteurs exécutées (ORM bouchonné) ; sérialiseur Transporteur lu par ast", "emplacements_controles": 2,
        "stock_tarifs": {"route": "GET stock/expeditions/tarifs/?unite_logistique=", "garde": [type(g).__name__ for g in g1], "cout_servi": str(offres[0]["cout"]), "masque_dans_la_vue_ou_le_selecteur": masque1, "roles_livres_sans_le_code_qui_lisent": lisent1},
        "installations_transporteurs": {"route": "GET installations/transporteurs/", "tarif_base_servi_sans_masque": sert_tarif, "roles_livres_sans_le_code_qui_lisent": lisent2},
        "code_attendu": "prix_achat_voir (selon D-ALEC-1 : le tarif est-il un prix d'achat ?)"}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
