"""Rejoue l'export de réversibilité core/export_registry.py : l'historique (ExportReversibiliteHistoriqueView) rend le jeton
de téléchargement à des rôles internes livrés qui ne peuvent pas lancer l'export, et la vue publique
telecharger_export_reversibilite (AllowAny) sert tout SignedDownload actif, quel que soit son bucket (export de stock APRF34)."""
SONDE = {"constat": "C-APUB-001", "sha": "ae5a7ae4c",
         "attendu": "10 rôles internes livrés lisent le jeton sans pouvoir lancer l'export ; la vue publique sert un jeton du bucket uploads"}
import ast, logging, pathlib, sys, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"


def noeuds(chemin):
    src = (DJ / chemin).read_text(encoding="utf-8")
    return src, {n.name: n for n in ast.parse(src).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}


def executer(chemin, nom, ns):
    _, d = noeuds(chemin)
    n = d[nom]; n.decorator_list = []
    exec(compile(ast.Module(body=[n], type_ignores=[]), chemin, "exec"), ns)
    return ns[nom]


class Role:
    def __init__(s, nom, perms): s.nom, s.permissions = nom, list(perms)


def sonde(ctx=None):
    reg = {}
    exec(compile((DJ / "apps/roles/permissions_registre.py").read_text(encoding="utf-8"), "registre", "exec"), reg)
    portail = {n for n, _ in reg["CANONICAL_PORTAIL_ROLES"]}
    _, mdl = noeuds("authentication/models.py")
    iar = next(f for f in mdl["CustomUser"].body if isinstance(f, ast.FunctionDef) and f.name == "is_admin_role")
    iar.decorator_list = []; g = {}
    exec(compile(ast.Module(body=[iar], type_ignores=[]), "models.py", "exec"), g)

    class User:
        PORTEE_INTERNE, ROLE_ADMIN, is_authenticated, is_superuser, role_legacy = "interne", "admin", True, False, "normal"
        def __init__(s, role, portee): s.role, s.portee, s.company = role, portee, "C"
        is_admin_role = property(g["is_admin_role"])

    # 1. gardes RÉELLES de la vue historique (noms lus dans permission_classes, classes exécutées)
    src_er, er = noeuds("core/export_registry.py")
    vue = er["ExportReversibiliteHistoriqueView"]
    noms = [e.id if isinstance(e, ast.Name) else ast.unparse(e) for m in vue.body if isinstance(m, ast.Assign)
            and getattr(m.targets[0], "id", "") == "permission_classes" for e in m.value.elts]
    surcharges = [m.name for m in vue.body if isinstance(m, ast.FunctionDef) and m.name in ("get_permissions", "check_permissions")]
    qs_src = ast.get_source_segment(src_er, next(m for m in vue.body if isinstance(m, ast.FunctionDef) and m.name == "get_queryset"))
    filtre_lanceur = any(k in qs_src for k in ("demande_par", "_is_directeur_or_admin", "is_admin_role"))
    _, perms_auth = noeuds("authentication/permissions.py")
    gardes, inconnues = [], []
    for nom in noms:
        for chemin, table in (("authentication/permissions.py", perms_auth), ("core/export_registry.py", er)):
            if nom in table:
                gardes.append(executer(chemin, nom, {"BasePermission": object, "__name__": "x"})); break
        else:
            inconnues.append(nom)  # garde non résolue : comptée comme refus (correctif présumé)
    lance = executer("core/export_registry.py", "_is_directeur_or_admin", {})
    champs = next(ast.literal_eval(m.value) for m in ast.walk(er["ExportReversibiliteRunSerializer"])
                  if isinstance(m, ast.Assign) and getattr(m.targets[0], "id", "") == "fields")
    req = types.SimpleNamespace
    lit_sans_lancer, internes = [], []
    for nom, perms in reg["CANONICAL_SYSTEM_ROLES"]:
        u = User(Role(nom, perms), "portail_client" if nom in portail else "interne")
        lit = (not inconnues and not surcharges and not filtre_lanceur
               and all(G().has_permission(req(user=u), None) for G in gardes))
        if nom not in portail: internes.append(nom)
        if lit and "token" in champs and not lance(u): lit_sans_lancer.append(nom)

    # 2. vue publique RÉELLE exécutée avec SignedDownload en mémoire (resoudre_lien réel)
    class DNE(Exception): pass
    class Lien:
        def __init__(s, b, k, actif=True, expire=False): s.bucket, s.object_key, s.actif, s.expire = b, k, actif, expire
    base = {"tok-revers": Lien("erp-reversibilite", "1/export.zip"), "tok-stock": Lien("erp-uploads", "exports/1/42.xlsx"),
            "tok-expire": Lien("erp-reversibilite", "1/vieux.zip", expire=True)}
    def get(token):
        if token not in base: raise DNE()
        return base[token]
    sd = types.ModuleType("core.signed_download")
    sd.SignedDownload = types.SimpleNamespace(objects=types.SimpleNamespace(get=lambda token: get(token)), DoesNotExist=DNE)
    executer("core/signed_download.py", "resoudre_lien", sd.__dict__)
    lus = []
    class Corps:
        def read(s): return b"PK"
    class Minio:
        def get_object(s, Bucket, Key): lus.append((Bucket, Key)); return {"Body": Corps()}
    bk = types.ModuleType("core.backup"); bk._minio_client = Minio
    tk = types.ModuleType("core.tasks")  # constante réelle du bucket (pour un correctif qui la lirait)
    tk.REVERSIBILITE_BUCKET = next(ast.literal_eval(n.value) for n in ast.parse((DJ / "core/tasks.py").read_text(
        encoding="utf-8")).body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "REVERSIBILITE_BUCKET")
    core = types.ModuleType("core"); core.__path__ = []; core.signed_download, core.backup, core.tasks = sd, bk, tk
    sauve = {n: sys.modules.get(n) for n in ("core", "core.signed_download", "core.backup", "core.tasks")}
    sys.modules.update({"core": core, "core.signed_download": sd, "core.backup": bk, "core.tasks": tk})
    class Http404(Exception): pass
    class Resp(dict):
        def __init__(s, contenu, content_type=None): super().__init__(); s.contenu, s.status_code = contenu, 200
    ns = {"__name__": "core.export_registry", "__package__": "core", "Http404": Http404, "HttpResponse": Resp,
          "logger": logging.getLogger("sonde"),
          "REVERSIBILITE_BUCKET": tk.REVERSIBILITE_BUCKET}
    servis = {}
    try:
        vue_pub = executer("core/export_registry.py", "telecharger_export_reversibilite", ns)
        for tok in base:
            try: servis[tok] = vue_pub(None, tok).status_code
            except Http404: servis[tok] = 404
            except Exception as e: servis[tok] = type(e).__name__  # noqa: BLE001 — refus non-404 = non servi
    finally:
        for n, m in sauve.items():
            if m is None: sys.modules.pop(n, None)
            else: sys.modules[n] = m
    bucket_croise = servis.get("tok-stock") == 200
    return {"repro": bool(lit_sans_lancer) or bucket_croise, "observe": {
        "methode": "exécution (gardes, is_admin_role, _is_directeur_or_admin, resoudre_lien, vue publique extraites par ast)",
        "historique_permission_classes": noms, "gardes_non_resolues": inconnues, "surcharges": surcharges,
        "get_queryset_filtre_lanceur": filtre_lanceur, "serialiseur_expose_token": "token" in champs,
        "roles_internes_livres": len(internes),
        "lisent_le_jeton_sans_pouvoir_lancer": lit_sans_lancer,
        "vue_publique_statut_par_jeton": servis, "objets_lus_minio": lus,
        "vue_publique_sert_autre_bucket": bucket_croise}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
