"""Rejoue le livechat public apps/crm/public_chat_views.py::post_chat_message (AllowAny, sans authentification) et
apps/crm/leads_intake.py::create_lead_from_livechat : un visiteur anonyme qui donne le téléphone d'un lead existant
(ici un lead Signé) écrit son texte libre dans l'historique de ce lead et remplit son e-mail manquant."""
SONDE = {"constat": "C-APUB-007", "sha": "ae5a7ae4c",
         "attendu": "réponse 200 sans compte ; lead Signé : e-mail vide → e-mail du visiteur, note « Transcript livechat » ajoutée"}
import ast, dataclasses, datetime, logging, pathlib, re, runpy, sys, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
MODS = ("core", "core.ai", "core.ai.services", "apps", "apps.crm", "apps.crm.leads_intake", "apps.crm.cadence_reponses",
        "apps.crm.leads_doublons", "apps.crm.leads_meta")
MESSAGE = "Bonjour, je m'appelle Intrus, 0644444444, intrus@exemple.invalid — annulez mon contrat"


def extraire(chemin, noms, ns):
    arbre = ast.parse((DJ / chemin).read_text(encoding="utf-8"))
    pris = [n for n in arbre.body if (isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in noms)
            or (isinstance(n, ast.Assign) and any(getattr(t, "id", None) in noms for t in n.targets))]
    decos = {n.name: [ast.unparse(d) for d in n.decorator_list] for n in arbre.body if isinstance(n, ast.FunctionDef)}
    for n in pris:
        if isinstance(n, ast.FunctionDef): n.decorator_list = []
    exec(compile(ast.Module(body=pris, type_ignores=[]), chemin, "exec"), ns)
    return ns, decos


def module(nom, **a):
    m = types.ModuleType(nom); m.__path__ = []; m.__dict__.update(a); sys.modules[nom] = m; return m


def scenario():
    S = types.SimpleNamespace(**runpy.run_path(str(RACINE / "STAGES.py")))
    stages = types.SimpleNamespace(COLD=S.COLD, STAGES=S.STAGES)
    signe = S.CONVERSION_STAGE  # étape « signé » lue dans STAGES.py
    journal, recontacts = [], []
    dbl, _ = extraire("apps/crm/leads_doublons.py", {"normalize_phone"}, {"_re": re})
    dbl["poser_empreintes_opposition"] = lambda c, d: None
    meta, _ = extraire("apps/crm/leads_meta.py", {"_froid_a_reprendre"}, {"normalize_phone": dbl["normalize_phone"], "stages": stages})
    module("apps"); crm = module("apps.crm")
    crm.leads_doublons = module("apps.crm.leads_doublons", **dbl); crm.leads_meta = module("apps.crm.leads_meta", **meta)
    cr = module("apps.crm.cadence_reponses", stages=stages, __package__="apps.crm",
                enregistrer_recontact=lambda f, u, canal=None: recontacts.append(f.pk))
    extraire("apps/crm/cadence_reponses.py", {"doublon_a_reprendre"}, cr.__dict__); crm.cadence_reponses = cr

    class Lead:
        Canal = types.SimpleNamespace(AUTRE="autre")
        def __init__(s, pk, stage, telephone, email=None):
            s.pk, s.stage, s.telephone, s.email, s.company, s.date_creation = pk, stage, telephone, email, "TAQINOR", 1
            s.phone_normalise, s.whatsapp_normalise = dbl["normalize_phone"](telephone), ""
            s.is_archived = s.perdu = s.ne_plus_contacter = False; s.saves = 0
        def save(s, update_fields=None): s.saves += 1
    existant = Lead(41, signe, "+212 6 44 44 44 44")
    crees = []
    def creer(**k): crees.append(k); return Lead(99, "neuf", k.get("telephone") or "", k.get("email"))
    Lead.objects = types.SimpleNamespace(create=creer)
    def doublons(company, phone=None, email=None):  # bouchon de la requête : même téléphone normalisé, même société
        return [l for l in [existant] if phone and l.phone_normalise == dbl["normalize_phone"](phone)]
    activite = types.SimpleNamespace(log_creation=lambda l, u: None,
                                     journal_systeme=lambda **k: journal.append((k["lead"].pk, k["body"][:60])))
    li = module("apps.crm.leads_intake", __package__="apps.crm", Lead=Lead, activity=activite, logger=logging.getLogger("sonde"),
                LeadActivity=types.SimpleNamespace(Kind=types.SimpleNamespace(NOTE="note")),
                find_duplicates_by_contact=doublons, default_responsable_for=lambda c: None, notify_new_lead=lambda l: None,
                enregistrer_base_legale_lead=lambda *a, **k: None, CONSENT_SOURCE_LIVECHAT="livechat",
                BASE_LEGALE_SOLLICITATION="sollicitation", demarrer_cadence_contact=lambda *a, **k: None,
                recompute_lead_score=lambda l: None)
    extraire("apps/crm/leads_intake.py", {"create_lead_from_livechat"}, li.__dict__); crm.leads_intake = li

    ia = module("core.ai.services", dataclass=dataclasses.dataclass, re=re,
                qualify_livechat_reply=lambda t: types.SimpleNamespace(available=False, draft=""))
    extraire("core/ai/services.py", {"LivechatQualificationExtract", "extract_livechat_qualification"}, ia.__dict__)
    module("core", ai=module("core.ai", services=ia))

    St = types.SimpleNamespace(ACTIVE="active", QUALIFIEE="qualifiee", FERMEE="fermee")
    session = types.SimpleNamespace(token="tok", statut=St.ACTIVE, company="TAQINOR", lead_id=None, lead=None, transcript=[],
                                    save=lambda update_fields=None: None)
    class Response(dict):
        def __init__(s, data=None, status=200): super().__init__(); s.data, s.status_code = data, status
    ns = {"__name__": "apps.crm.public_chat_views", "__package__": "apps.crm", "Response": Response,
          "status": types.SimpleNamespace(HTTP_404_NOT_FOUND=404, HTTP_410_GONE=410, HTTP_400_BAD_REQUEST=400),
          "timezone": types.SimpleNamespace(now=datetime.datetime.now),
          "ChatSessionPublique": types.SimpleNamespace(Statut=St, objects=types.SimpleNamespace(
              filter=lambda token=None: types.SimpleNamespace(first=lambda: session if token == "tok" else None)))}
    _, fonctions = extraire("apps/crm/public_chat_views.py", {"post_chat_message", "_append_transcript", "DEFAULT_AWAY_MESSAGE"}, ns)
    decorateurs = [d for d in fonctions["post_chat_message"] if "classes" in d]
    rep = ns["post_chat_message"](types.SimpleNamespace(data={"message": MESSAGE}, user=None), "tok")
    return {"decorateurs": decorateurs, "statut_http": rep.status_code, "lead_created_repondu": (rep.data or {}).get("lead_created"),
            "lead_existant": {"pk": existant.pk, "etape": existant.stage, "email_apres": existant.email, "saves": existant.saves},
            "notes_ecrites_sur": journal, "leads_crees": len(crees), "session_rattachee_au_lead": getattr(session.lead, "pk", None)}


def appelants():
    vus = []
    for racine in ("frontend/src", "apps/web/src"):
        for p in (RACINE / racine).rglob("*"):
            if p.suffix in (".js", ".jsx", ".ts", ".tsx", ".astro") and "public/chat" in p.read_text(encoding="utf-8", errors="ignore"):
                vus.append(p.relative_to(RACINE).as_posix())
    return vus


def sonde(ctx=None):
    sauve = {n: sys.modules.get(n) for n in MODS}
    try:
        o = scenario()
    finally:
        for n, m in sauve.items():
            if m is None: sys.modules.pop(n, None)
            else: sys.modules[n] = m
    ecrit = any(pk == o["lead_existant"]["pk"] for pk, _ in o["notes_ecrites_sur"])
    repro = o["statut_http"] == 200 and (ecrit or o["lead_existant"]["email_apres"] == "intrus@exemple.invalid")
    return {"repro": repro, "observe": {
        "methode": "exécution (post_chat_message, _append_transcript, create_lead_from_livechat, doublon_a_reprendre, "
                   "_froid_a_reprendre, normalize_phone, extract_livechat_qualification extraits par ast)",
        "route": "POST /api/django/crm/public/chat/sessions/<token>/messages/", **o,
        "historique_du_lead_existant_ecrit": ecrit, "ecrans_ou_site_appelants": appelants()}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
