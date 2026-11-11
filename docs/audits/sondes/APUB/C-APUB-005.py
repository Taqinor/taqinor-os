"""Rejoue la vraie vue publique apps/ventes/public/signature_views.py::proposal_contact_request (« Contacter mon conseiller », lien sans code) : le champ `canal` est libre, chaque valeur neuve ouvre une clé d'idempotence neuve — 10 canaux inventés = 10 notes au chatter du lead + 10 notifications."""
SONDE = {"constat": "C-APUB-005", "sha": "ae5a7ae4c",
         "attendu": "10 POST au même lien, canal c0..c9 → 10 transmissions (notify_client_contact_request) ; témoin canal fixe ×10 → 1"}
import ast, pathlib, sys, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
CHEMIN = "apps/ventes/public/signature_views.py"


class Response:
    def __init__(s, data=None, status=200): s.data, s.status_code = data, status


class Cache:  # sémantique de django.core.cache.cache.add : False si la clé existe déjà
    def __init__(s): s.cles = set()
    def add(s, cle, valeur, timeout=None):
        if cle in s.cles: return False
        s.cles.add(cle); return True


def taux_throttle():
    arbre = ast.parse((DJ / "apps/ventes/public/noyau.py").read_text(encoding="utf-8"))
    return next((ast.literal_eval(b.value) for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == "PublicLinkRateThrottle"
                 for b in n.body if isinstance(b, ast.Assign) and getattr(b.targets[0], "id", "") == "rate"), None)


def jouer(corps):
    """POSTe chaque corps de ``corps`` au même lien ; rend (transmissions, clés de cache posées, réponses « déjà transmise »)."""
    arbre = ast.parse((DJ / CHEMIN).read_text(encoding="utf-8"))
    f = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "proposal_contact_request")
    f.decorator_list = []
    cache, envois = Cache(), []
    lead = types.SimpleNamespace(pk=5)
    devis = types.SimpleNamespace(reference="DV-2026-11-0001", lead=lead, company="C", client_id=1)
    link = types.SimpleNamespace(pk=42, via_interne=False, devis=devis)
    mods = {n: types.ModuleType(n) for n in ("django", "django.core", "django.core.cache", "apps", "apps.crm",
                                              "apps.crm.services", "apps.notifications", "apps.notifications.services")}
    for m in mods.values(): m.__path__ = []
    mods["django.core.cache"].cache = cache
    mods["apps.crm.services"].notify_client_contact_request = lambda ref, ld, **kw: envois.append((ref, ld.pk, kw.get("canal")))
    ns = {"__name__": "apps.ventes.public.signature_views", "__package__": "apps.ventes.public",
          "_resolve_proposal_link": lambda token, refuser_brouillon=False: link, "_not_found": lambda: Response(status=404),
          "_refus_apercu_interne": lambda: Response(status=403), "_refus_brouillon": lambda l: None,
          "_noindex": lambda r: r, "Response": Response,
          "logger": types.SimpleNamespace(warning=lambda *a, **k: None)}
    vieux = {n: sys.modules.get(n) for n in mods}
    sys.modules.update(mods)
    try:
        exec(compile(ast.Module(body=[f], type_ignores=[]), CHEMIN, "exec"), ns)
        deja = 0
        for c in corps:
            r = ns["proposal_contact_request"](types.SimpleNamespace(data=c), "jeton-lien-client")
            deja += bool((r.data or {}).get("already_sent"))
    finally:
        for n, m in vieux.items():
            if m is None: sys.modules.pop(n, None)
            else: sys.modules[n] = m
    return len(envois), sorted(cache.cles), deja


def sonde(ctx=None):
    n_var, cles_var, deja_var = jouer([{"channel": f"c{i}", "message": "rappelez-moi"} for i in range(10)])
    n_fixe, cles_fixe, deja_fixe = jouer([{"channel": "rappel", "message": "rappelez-moi"}] * 10)
    repro = n_var == 10 and n_fixe == 1
    return {"repro": repro, "observe": {
        "methode": "exécution (vraie fonction extraite par ast, cache et services crm bouchonnés)",
        "route": "POST /api/django/ventes/proposal/<token>/contact/ (AllowAny, ouverte sans code : D-ASEC-23-CONTACT)",
        "cle_idempotence_observee": cles_var[:3] + ["…"],
        "canaux_inventes_10": {"transmissions_chatter_et_notifications": n_var, "cles_distinctes": len(cles_var),
                               "reponses_deja_transmise": deja_var},
        "temoin_canal_fixe_10": {"transmissions": n_fixe, "reponses_deja_transmise": deja_fixe},
        "throttle_par_ip_et_jeton": taux_throttle(),
        "liste_blanche_du_canal": "aucune" if n_var == 10 else "présente (canaux inventés refusés ou fusionnés)"}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
