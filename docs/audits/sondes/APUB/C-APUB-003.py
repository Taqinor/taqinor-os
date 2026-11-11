"""Rejoue la vraie vue publique apps/sav/public_views.py::equipement_public_signaler (scan QR, sans login) : la clé anti-rejeu dépend du texte et aucun plafond par équipement n'existe — 40 descriptions distinctes = 40 tickets SAV."""
SONDE = {"constat": "C-APUB-003", "sha": "ae5a7ae4c",
         "attendu": "40 POST au même QR, textes p0..p39 → 40 tickets créés (numéros consommés) ; témoin : 40 POST au même texte → 1 ticket"}
import ast, datetime, pathlib, sys, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
CHEMIN = "apps/sav/public_views.py"


class A:  # objet permissif (attributs de bouchon)
    def __init__(s, *a, **k): pass
    def __call__(s, *a, **k): return A()
    def __getattr__(s, n): return A()


class Response:
    def __init__(s, data=None, status=200): s.data, s.status_code, s.entetes = data, status, {}
    def __setitem__(s, k, v): s.entetes[k] = v


class Statut:  # status.HTTP_201_CREATED → 201
    def __getattr__(s, n): return int(n.split("_")[1])


class Tickets(list):  # faux Ticket.objects : create / filter(...).order_by().first()
    def create(s, **kw):
        t = types.SimpleNamespace(pk=len(s) + 1, date_creation=datetime.datetime.now(datetime.timezone.utc), **kw)
        s.append(t); return t
    def filter(s, **kw):
        def ok(t):
            return all((getattr(t, k[:-5]) >= v) if k.endswith("__gte") else getattr(t, k, None) == v for k, v in kw.items())
        return Tickets(t for t in s if ok(t))
    def order_by(s, *a): return Tickets(sorted(s, key=lambda t: t.date_creation, reverse=True))
    def first(s): return s[0] if s else None


def vue():
    """Extrait la vraie fonction (sans ses décorateurs DRF) + ses aides et constantes du module."""
    arbre = ast.parse((DJ / CHEMIN).read_text(encoding="utf-8"))
    noms = {"equipement_public_signaler", "_noindex", "_not_found", "FENETRE_REJEU_SIGNALEMENT_S"}
    garde = []
    for n in arbre.body:
        nom = getattr(n, "name", None) or next((t.id for t in getattr(n, "targets", []) if isinstance(t, ast.Name)), None)
        if nom in noms:
            if isinstance(n, ast.FunctionDef): n.decorator_list = []
            garde.append(n)
    throttle = next((ast.literal_eval(b.value) for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == "SavPublicThrottle"
                     for b in n.body if isinstance(b, ast.Assign) and getattr(b.targets[0], "id", "") == "rate"), None)
    return garde, throttle


def jouer(descriptions):
    garde, _ = vue()
    tickets, vus, numero = Tickets(), set(), [0]
    client = types.SimpleNamespace(pk=7)
    equip = types.SimpleNamespace(pk=11, est_retire=False, company="C", installation=types.SimpleNamespace(client=client),
                                  client_vente=None)
    Ticket = types.SimpleNamespace(objects=tickets, Type=types.SimpleNamespace(CORRECTIF="correctif"))
    Equipement = types.SimpleNamespace(DoesNotExist=LookupError,
                                       objects=types.SimpleNamespace(select_related=lambda *a: types.SimpleNamespace(
                                           get=lambda **kw: equip)))

    def dedupe_event(company, source, event_id):  # sémantique de core.idempotency : True = événement neuf
        cle = (company, source, event_id)
        if cle in vus: return False
        vus.add(cle); return True

    def create_with_reference(modele, prefixe, company, creer):
        numero[0] += 1; return creer(f"{prefixe}-{numero[0]:04d}")

    mods = {"core": types.ModuleType("core"), "core.idempotency": types.ModuleType("core.idempotency"),
            "apps": types.ModuleType("apps"), "apps.sav": types.ModuleType("apps.sav"),
            "apps.sav.services": types.ModuleType("apps.sav.services"), "apps.ventes": types.ModuleType("apps.ventes"),
            "apps.ventes.utils": types.ModuleType("apps.ventes.utils"),
            "apps.ventes.utils.references": types.ModuleType("apps.ventes.utils.references")}
    for m in mods.values(): m.__path__ = []
    mods["core.idempotency"].dedupe_event = dedupe_event
    mods["apps.sav.services"].poser_sla_due_at = lambda t: t
    mods["apps.ventes.utils.references"].create_with_reference = create_with_reference
    ns = {"__name__": "apps.sav.public_views", "__package__": "apps.sav", "Response": Response, "status": Statut(),
          "Equipement": Equipement, "Ticket": Ticket, "timezone": types.SimpleNamespace(localdate=datetime.date.today)}
    vieux = {n: sys.modules.get(n) for n in mods}
    sys.modules.update(mods)
    try:
        exec(compile(ast.Module(body=garde, type_ignores=[]), CHEMIN, "exec"), ns)
        codes = []
        for d in descriptions:
            req = types.SimpleNamespace(data={"description": d, "telephone": "0600000000"}, FILES={})
            codes.append(ns["equipement_public_signaler"](req, "jeton-public-qr").status_code)
    finally:
        for n, m in vieux.items():
            if m is None: sys.modules.pop(n, None)
            else: sys.modules[n] = m
    return len(tickets), numero[0], codes


def sonde(ctx=None):
    _, throttle = vue()
    n_var, num_var, codes_var = jouer([f"panne p{i}" for i in range(40)])
    n_id, num_id, codes_id = jouer(["panne p0"] * 40)
    repro = n_var == 40 and n_id == 1
    return {"repro": repro, "observe": {
        "methode": "exécution (vraie fonction extraite par ast, bouchons ORM/idempotence)",
        "route": "POST /api/django/public/sav/equipement/<token>/signaler/ (AllowAny, sans login)",
        "garde_anti_rejeu": "event_id = equipement.pk + sha256(description)[:16] + fenêtre 5 min",
        "textes_distincts_40": {"tickets_crees": n_var, "numeros_consommes": num_var, "codes_http": sorted(set(codes_var))},
        "temoin_texte_identique_40": {"tickets_crees": n_id, "codes_http": sorted(set(codes_id))},
        "plafond_par_equipement": "aucun" if n_var == 40 else f"oui ({n_var} tickets sur 40)",
        "throttle_django_par_ip": throttle}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
