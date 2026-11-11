"""Rejoue le lien public du compte-rendu d'intervention (Intervention.lien_rapport_token) : les 3 vues publiques de
apps/installations/public_views.py servent un jeton posé il y a 5 ans (aucune expiration), et le seul écrivain du champ hors
tests/migrations est la pose de ensure_lien_rapport_token (aucune révocation ni rotation ; re-clôture = même jeton)."""
SONDE = {"constat": "C-APUB-004", "sha": "ae5a7ae4c",
         "attendu": "page, photo et PDF rendent 200 sur un jeton de 5 ans ; 1 seule écriture de lien_rapport_token (la pose)"}
import ast, datetime, pathlib, sys, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
MAINTENANT = datetime.datetime(2026, 11, 11, 9, 0)
VIEUX = MAINTENANT - datetime.timedelta(days=5 * 365)
VUES = ("InterventionRapportPublicView", "InterventionRapportPhotoPublicView", "InterventionRapportPdfPublicView")
MODS = ("django", "django.http", "django.utils", "django.utils.timezone", "apps", "apps.installations",
        "apps.installations.selectors", "apps.installations.field_services", "apps.installations.intervention_pdf",
        "apps.records", "apps.records.storage")


def ecrivains():
    """Toute écriture de lien_rapport_token hors tests/migrations (affectation, setattr, update/create)."""
    vus = []
    for p in sorted(DJ.rglob("*.py")):
        s = p.as_posix()
        if "/migrations/" in s or "/tests" in s or p.name.startswith("test"): continue
        try:
            txt = p.read_text(encoding="utf-8")
            if "lien_rapport_token" not in txt: continue
            arbre = ast.parse(txt)
        except (SyntaxError, UnicodeDecodeError): continue
        for n in ast.walk(arbre):
            if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                for c in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                    if isinstance(c, ast.Attribute) and c.attr == "lien_rapport_token":
                        vus.append(f"{p.relative_to(DJ).as_posix()}:{n.lineno} {ast.unparse(n)[:60]}")
            elif isinstance(n, ast.Call):
                f = ast.unparse(n.func)
                if any(k.arg == "lien_rapport_token" for k in n.keywords) and f.endswith(("update", "create", "update_or_create")):
                    vus.append(f"{p.relative_to(DJ).as_posix()}:{n.lineno} {f}(lien_rapport_token=…)")
                if f == "setattr" and len(n.args) > 1 and isinstance(n.args[1], ast.Constant) and n.args[1].value == "lien_rapport_token":
                    vus.append(f"{p.relative_to(DJ).as_posix()}:{n.lineno} setattr")
    return vus


def scenario():
    tz = types.ModuleType("django.utils.timezone"); tz.now = lambda: MAINTENANT; tz.localdate = lambda: MAINTENANT.date()
    class HttpResponse(dict):
        def __init__(s, contenu=b"", content_type=None): super().__init__(); s.status_code, s.contenu = 200, contenu
    def mod(nom, **a):
        m = types.ModuleType(nom); m.__path__ = []; m.__dict__.update(a); sys.modules[nom] = m; return m
    mod("django"); mod("django.http", HttpResponse=HttpResponse); mod("django.utils", timezone=tz); sys.modules["django.utils.timezone"] = tz
    att = types.SimpleNamespace(file_key="k/photo.jpg", mime="image/jpeg")
    class QS(list):
        def filter(s, **k): return QS(s)
        def select_related(s, *a): return s
        def first(s): return s[0] if s else None
    sel = mod("apps.installations.selectors", intervention_rapport_public_payload=lambda i, r: {"photos": 3, "signataire": "X"})
    fs = mod("apps.installations.field_services", intervention_photos=lambda i: QS([att]))
    pdf = mod("apps.installations.intervention_pdf", compte_rendu_pdf=lambda i: b"%PDF")
    mod("apps"); mod("apps.installations", selectors=sel, field_services=fs, intervention_pdf=pdf)
    mod("apps.records"); mod("apps.records.storage", fetch_attachment=lambda k: (b"JPG", None))

    src = (DJ / "apps/installations/models_intervention.py").read_text(encoding="utf-8")
    cls = next(n for n in ast.parse(src).body if isinstance(n, ast.ClassDef) and n.name == "Intervention")
    corps = [f for f in cls.body if isinstance(f, ast.FunctionDef) and "rapport" in f.name]  # dont toute expiration future
    Statut = types.SimpleNamespace(TERMINEE="terminee", VALIDEE="validee")
    nsm = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(
        name="Base", bases=[], keywords=[], body=corps, decorator_list=[], type_params=[])], type_ignores=[])), "models", "exec"), nsm)
    class Interv(nsm["Base"]):
        def __init__(s):
            s.id = s.pk = 7; s.statut, s.annulee, s.lien_rapport_token = Statut.VALIDEE, False, None
            s.cloturee_notifiee_le = s.signe_le = s.date_creation = VIEUX; s.date_prevue = s.date_realisee = VIEUX.date()
            s.ecritures = 0
        def save(s, update_fields=None): s.ecritures += 1
    iv = Interv()
    jeton = iv.ensure_lien_rapport_token(); jeton2 = iv.ensure_lien_rapport_token()  # 2e appel (re-clôture) : même jeton
    base = [iv]
    Intervention = types.SimpleNamespace(Statut=Statut, objects=types.SimpleNamespace(
        select_related=lambda *a: types.SimpleNamespace(filter=lambda **k: QS(i for i in base if i.lien_rapport_token == k.get("lien_rapport_token"))),
        filter=lambda **k: QS(i for i in base if i.lien_rapport_token == k.get("lien_rapport_token"))))
    class Response(dict):
        def __init__(s, data=None, status=200): super().__init__(); s.data, s.status_code = data, status
    vsrc = (DJ / "apps/installations/public_views.py").read_text(encoding="utf-8")
    arbre = ast.parse(vsrc)
    ns = {"__name__": "apps.installations.public_views", "__package__": "apps.installations", "Intervention": Intervention,
          "Response": Response, "status": types.SimpleNamespace(HTTP_404_NOT_FOUND=404, HTTP_410_GONE=410), "timezone": tz}
    morceaux = [n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "_rapport_publiable"]
    gardes = {}
    for n in arbre.body:
        if isinstance(n, ast.ClassDef) and n.name in VUES:
            gardes[n.name] = [ast.unparse(m.value) for m in n.body if isinstance(m, ast.Assign)
                              and getattr(m.targets[0], "id", "") in ("permission_classes", "authentication_classes")]
            meth = [m for m in n.body if isinstance(m, ast.FunctionDef)]
            for m in meth: m.decorator_list = []
            morceaux.append(ast.ClassDef(name=n.name, bases=[], keywords=[], body=meth, decorator_list=[], type_params=[]))
    exec(compile(ast.fix_missing_locations(ast.Module(body=morceaux, type_ignores=[])), "public_views.py", "exec"), ns)
    statuts = {}
    for nom in VUES:
        args = (jeton, 1) if "Photo" in nom else (jeton,)
        try: statuts[nom] = ns[nom]().get(types.SimpleNamespace(), *args).status_code
        except Exception as e: statuts[nom] = type(e).__name__  # noqa: BLE001 — un refus levé = non servi
    return {"jeton_stable_a_la_recloture": jeton == jeton2, "ecritures_save": iv.ecritures,
            "pose_il_y_a": "5 ans (statut validée)", "statut_par_vue": statuts, "gardes_vues": gardes}


def sonde(ctx=None):
    sauve = {n: sys.modules.get(n) for n in MODS}
    try:
        o = scenario()
    finally:
        for n, m in sauve.items():
            if m is None: sys.modules.pop(n, None)
            else: sys.modules[n] = m
    ecr = ecrivains()
    hors_pose = [e for e in ecr if "models_intervention.py" not in e or "= token" not in e]
    servi = all(v == 200 for v in o["statut_par_vue"].values())
    return {"repro": servi or not hors_pose, "observe": {
        "methode": "exécution (3 vues get, _rapport_publiable, ensure_lien_rapport_token extraits par ast) + ast (écrivains)",
        **o, "servi_apres_5_ans": servi, "ecrivains_lien_rapport_token": ecr, "revocation_ou_rotation": hors_pose}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
