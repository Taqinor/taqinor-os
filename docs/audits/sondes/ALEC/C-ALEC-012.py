"""Rejoue le journal d'audit générique pour Devis.marge_snapshot : VRAIE _diff_from_snapshot (+ VRAIE caviarder), VRAI AuditLogSerializer.get_detail et VRAIE object_history (garde IsAuthenticated + borne propriétaire) pour un rôle livré sans marge_voir, créateur du devis."""
SONDE = {"constat": "C-ALEC-012", "sha": "ae5a7ae4c",
         "attendu": "le créateur du devis (Commercial, sans marge_voir) lit, par object_history, un détail « marge_snapshot : — → 4000.00 » : le diff générique ne rédige que les secrets"}
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
    sig, vw, red = "apps/audit/signals.py", "apps/audit/views.py", "apps/audit/redaction.py"
    rid = {}
    for k in ("MASQUE", "CHAMPS_SECRETS"): exec(ast.unparse(noeud(red, k)), rid)
    for f in ("_est_chiffre", "champs_secrets_du_modele", "caviarder"): reel(red, f, None, rid)
    Devis = type("Devis", (), {"_meta": NS(concrete_fields=[NS(name="marge_snapshot", attname="marge_snapshot")])})
    ns = constantes(sig); ns["caviarder"] = rid["caviarder"]; reel(sig, "_truncate_diff_value", None, ns)
    inst = Devis(); inst.marge_snapshot = "4000.00"
    changes = reel(sig, "_diff_from_snapshot", None, ns)(inst, {"marge_snapshot": None})
    suivi = ("ventes", "Devis") in runpy.run_path(str(DJ / "apps/audit/modeles_suivis.py"))["TRACKED_MODELS"]
    ligne = NS(detail="", changes=changes, content_type_id=1, content_type=NS(model_class=lambda: None))
    detail = reel("apps/audit/serializers.py", "get_detail", "AuditLogSerializer", {"FieldDoesNotExist": KeyError})(None, ligne)
    createur = comptes["Commercial"]; createur.company, createur.company_id = NS(id=1), 1
    devis = NS(company_id=1, owner_id=None, created_by_id=createur.id, assigned_to_id=None)
    table = NS(objects=NS(get=lambda **k: NS(model_class=lambda: NS(_default_manager=NS(filter=lambda **k: NS(first=lambda: devis))))))
    table.DoesNotExist = LookupError
    ns_v = {"ContentType": table, "Response": lambda d, status=200: (status, d), "_limite": lambda p: 50, "str": str,
            "_company_qs": lambda r: NS(filter=lambda **k: NS(order_by=lambda c: [ligne])),
            "AuditLogSerializer": lambda qs, many=False: NS(data=[{"detail": detail} for _ in qs])}
    code, corps = reel(vw, "object_history", None, ns_v)(NS(user=createur, query_params={}), "ventes.devis", 77)
    garde = [ast.unparse(d) for d in noeud(vw, "object_history").decorator_list if ast.unparse(d).startswith("permission_classes")]
    lu = code == 200 and any("marge_snapshot" in r["detail"] for r in corps["results"])
    marge_voir = "marge_voir" in createur.role.permissions
    return {"repro": bool(changes) and suivi and lu and not marge_voir, "observe": {
        "methode": "VRAIES _diff_from_snapshot, caviarder, get_detail et object_history exécutées (ORM bouchonné) ; garde du décorateur lue par ast",
        "route": "GET audit/objets/ventes.devis/<id>/history/", "garde": garde, "diff_enregistre": changes, "Devis_suivi_par_le_journal": suivi,
        "reponse": code, "detail_servi_au_createur": [r["detail"] for r in corps["results"]] if code == 200 else corps, "code_attendu": "marge_voir",
        "role_livre_createur": "Commercial", "porte_marge_voir": marge_voir,
        "roles_livres_ventes_creer_sans_marge_voir": sorted(n for n, c in comptes.items() if "ventes_creer" in c.role.permissions and "marge_voir" not in c.role.permissions)}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
