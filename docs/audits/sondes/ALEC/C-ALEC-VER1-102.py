"""Contre-visite ALEC (13/11) — ALEC18 : les deux vues des demandes de signature sont restées en `IsAnyRole`.
`backend/django_core/apps/ged/views.py::DemandeSignatureDocumentViewSet.get_permissions` (lecture + `pdf_signe`) et
`SignataireDemandeViewSet.permission_classes` ; leurs sérialiseurs servent `nom`, `email`, `telephone`, `adresse_ip`,
`user_agent` des signataires sans condition `client_pii_voir`. On EXÉCUTE le vrai `get_permissions` (ast, bouchons DRF) et les
VRAIES classes de permission (`authentication/permissions.py`, registre des modules enregistré) contre de faux utilisateurs
portant les codes RÉELS des rôles livrés « Commercial terrain » et « Admin RH » ; témoin : la vue documents (`DocumentViewSet`)
corrigée par ALEC18 refuse le Commercial terrain. Sérialiseurs et sélecteur lus par ast (pas de base, pas de Django)."""
SONDE = {"constat": "C-ALEC-VER1-102", "sha": "d64fa1e4e4",
         "attendu": "Commercial terrain (aucun code ged_*) et Admin RH (sans client_pii_voir) franchissent la lecture des "
                    "demandes de signature et des signataires ; la vue documents refuse le Commercial terrain"}
import ast, pathlib, runpy, sys, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
DJ = RACINE / "backend/django_core"
V, S, SEL = "apps/ged/views.py", "apps/ged/serializers.py", "apps/ged/selectors.py"


def corps(chemin, classe=None):
    b = ast.parse((DJ / chemin).read_text(encoding="utf-8")).body
    return next(n for n in b if isinstance(n, ast.ClassDef) and n.name == classe).body if classe else b


def fonction(chemin, nom, classe=None, ns=None):
    f = next(n for n in corps(chemin, classe) if isinstance(n, ast.FunctionDef) and n.name == nom)
    f.decorator_list = []
    ns = {} if ns is None else ns
    exec(compile(ast.Module([f], []), chemin, "exec"), ns)
    return ns[nom]


def constante(chemin, nom):
    for n in corps(chemin):
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == nom:
            return ast.literal_eval(n.value)


def monde():
    reg = runpy.run_path(str(DJ / "apps/roles/permissions_registre.py"))
    sauve = {k: sys.modules.get(k) for k in ("rest_framework", "rest_framework.permissions")}
    perm = types.ModuleType("rest_framework.permissions")
    perm.SAFE_METHODS = ("GET", "HEAD", "OPTIONS"); perm.BasePermission = type("BasePermission", (), {})
    sys.modules["rest_framework"] = types.ModuleType("rest_framework"); sys.modules["rest_framework.permissions"] = perm
    try:
        g = runpy.run_path(str(DJ / "authentication/permissions.py"))
    finally:
        for k, v in sauve.items():
            sys.modules.pop(k, None) if v is None else sys.modules.__setitem__(k, v)
    g["enregistrer_registre_modules"](reg["PERMISSION_MODULE"], octrois_lecture=reg["OCTROIS_LECTURE"])
    M = "authentication/models.py"
    rgw, adm, resp, hep = (fonction(M, n, "CustomUser") for n in
                           ("_role_grants_write", "is_admin_role", "is_responsable", "has_erp_permission"))

    class FauxUser:
        is_authenticated, is_superuser, company_id, id, portee, role_legacy = True, False, 1, 1, "interne", "normal"
        has_erp_permission = hep

        def __init__(s, nom, perms):
            s.role = types.SimpleNamespace(nom=nom, permissions=list(perms), est_systeme=True); s.role_id = 1
            s._role_grants_write = rgw
            s.is_admin_role, s.is_responsable = adm(s), resp(s)

    roles = dict(reg["CANONICAL_SYSTEM_ROLES"])
    return g, {n: FauxUser(n, roles[n]) for n in ("Commercial terrain", "Admin RH", "Directeur")}


class Req:
    def __init__(s, user, method="GET"):
        s.user, s.method, s.data, s.query_params = user, method, {}, {}


def passe(gardes, user, vue):
    return all(p.has_permission(Req(user), vue) for p in gardes)


def champs_meta(classe):
    meta = next(n for n in corps(S, classe) if isinstance(n, ast.ClassDef) and n.name == "Meta")
    a = next(n for n in meta.body if isinstance(n, ast.Assign) and n.targets[0].id == "fields")
    return set(ast.literal_eval(a.value))


def mots(chemin, classe, nom):
    f = next(n for n in corps(chemin, classe) if isinstance(n, ast.FunctionDef) and n.name == nom)
    return ({n.id for n in ast.walk(f) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(f) if isinstance(n, ast.Attribute)}
            | {n.value for n in ast.walk(f) if isinstance(n, ast.Constant) and isinstance(n.value, str)})


def sonde(ctx=None):
    g, users = monde()
    ns = {"READ_ACTIONS": constante(V, "READ_ACTIONS"), "GED_GERER": constante(V, "GED_GERER"),
          "GED_GOUVERNANCE": constante(V, "GED_GOUVERNANCE"), "GOUVERNANCE_ACTIONS": constante(V, "GOUVERNANCE_ACTIONS"),
          "Mapping": dict, "IsAnyRole": g["IsAnyRole"], "HasPermissionOrLegacy": g["HasPermissionOrLegacy"],
          "IsResponsableOrAdmin": g["IsResponsableOrAdmin"], "LectureDuModule": g["LectureDuModule"]}
    gp_dem = fonction(V, "get_permissions", "DemandeSignatureDocumentViewSet", dict(ns))
    gp_doc = fonction(V, "get_permissions", "DocumentViewSet", dict(ns))
    pc = next(n for n in corps(V, "SignataireDemandeViewSet") if isinstance(n, ast.Assign)
              and n.targets[0].id == "permission_classes")
    classes_sig = [ns[e.id] for e in pc.value.elts]
    vue = lambda nom: type(nom, (), {"__module__": "apps.ged.views"})()
    res = {}
    for nom, u in users.items():
        res[nom] = {
            "codes_ged": sorted(c for c in u.role.permissions if c.startswith("ged_")),
            "client_pii_voir": "client_pii_voir" in u.role.permissions,
            "demandes-signature list": passe(gp_dem(types.SimpleNamespace(action="list")), u, vue("DemandeSignatureDocumentViewSet")),
            "demandes-signature pdf_signe": passe(gp_dem(types.SimpleNamespace(action="pdf_signe")), u,
                                                  vue("DemandeSignatureDocumentViewSet")),
            "signataires-demande list": passe([c() for c in classes_sig], u, vue("SignataireDemandeViewSet")),
            "temoin documents list": passe(gp_doc(types.SimpleNamespace(action="list", request=Req(u))), u, vue("DocumentViewSet")),
        }
    pii = {"email", "telephone", "adresse_ip", "user_agent"}
    sig_champs = champs_meta("SignataireDemandeSerializer") & pii
    dem_champs = champs_meta("DemandeSignatureDocumentSerializer") & (pii | {"signataire_email"})
    masque_pii = {c: any("pii" in m for m in mots(S, c, "to_representation"))
                  for c in ("SignataireDemandeSerializer", "DemandeSignatureDocumentSerializer")}
    sel = mots(SEL, None, "documents_visible_to_user")
    ct, rh = res["Commercial terrain"], res["Admin RH"]
    repro = (ct["demandes-signature list"] and ct["signataires-demande list"] and not ct["temoin documents list"]
             and not ct["codes_ged"] and rh["signataires-demande list"] and not rh["client_pii_voir"]
             and {"email", "telephone", "adresse_ip"} <= sig_champs and not any(masque_pii.values()))
    return {"repro": repro, "observe": {
        "methode": "exécution du vrai get_permissions / permission_classes et des vraies classes de permission ; "
                   "sérialiseurs et sélecteur lus par ast",
        "par_role": res,
        "SignataireDemandeSerializer_champs_personnels": sorted(sig_champs),
        "DemandeSignatureDocumentSerializer_champs_personnels": sorted(dem_champs),
        "to_representation_consulte_client_pii": masque_pii,
        "selecteur_ne_retire_aux_sans_pii_que_les_documents_produits": "can_view_client_pii" in sel and "produit" in sel}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
