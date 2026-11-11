"""En prod, l'origine du site public (taqinor.ma) reçoit l'ERP en CORS AVEC credentials : un script sur le site lit et
écrit l'API avec la session (cookie Lax, même site) de l'employé connecté. Réglages lus et rejoués depuis les fichiers."""
SONDE = {"constat": "C-APUB-038", "sha": "ae5a7ae4c",
         "attendu": "origine https://taqinor.ma → ACAO=origine + ACAC=true sur /api/django/crm/leads/, cookie Lax joint"}
import ast, pathlib, re, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
DJ = RACINE / "backend/django_core"
API = "api.taqinor.ma"  # hôte de l'ERP (CLAUDE.md « Backend production URL »)
CHEMIN = "/api/django/crm/leads/"


def arbre(rel): return ast.parse((DJ / rel).read_text(encoding="utf-8"))


def affectations(a):
    return {t.id: n.value for n in a.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}


def reglages_prod():
    """Rejoue base.py puis prod.py (seules les affectations CORS*/_liste_env), .env prod SANS CORS_ALLOWED_ORIGINS
    (docs/production.md, décision ASEC48)."""
    ns = {"os": types.SimpleNamespace(environ={})}
    for rel in ("erp_agentique/settings/base.py", "erp_agentique/settings/prod.py"):
        corps = [n for n in arbre(rel).body if (isinstance(n, ast.FunctionDef) and n.name == "_liste_env")
                 or (isinstance(n, ast.Assign) and any(getattr(t, "id", "").startswith("CORS_") for t in n.targets))]
        exec(compile(ast.Module(body=corps, type_ignores=[]), rel, "exec"), ns)
    mw = affectations(arbre("erp_agentique/settings/base.py")).get("MIDDLEWARE")
    ns["MIDDLEWARE"] = ast.literal_eval(mw) if mw is not None else []
    return ns


def reponse_cors(r, origine, chemin):
    """Décision de django-cors-headers (CorsMiddleware, doc officielle) : CORS_URLS_REGEX (défaut r'^.*$') sur le
    chemin, origine dans CORS_ALLOWED_ORIGINS ou CORS_ALLOW_ALL_ORIGINS → ACAO ; ACAC si CORS_ALLOW_CREDENTIALS."""
    if "corsheaders.middleware.CorsMiddleware" not in r["MIDDLEWARE"]: return {}
    if not re.match(r.get("CORS_URLS_REGEX", r"^.*$"), chemin): return {}
    if not (r.get("CORS_ALLOW_ALL_ORIGINS") or origine in r.get("CORS_ALLOWED_ORIGINS", [])): return {}
    h = {"Access-Control-Allow-Origin": origine}
    if r.get("CORS_ALLOW_CREDENTIALS"): h["Access-Control-Allow-Credentials"] = "true"
    return h


def meme_site(hote_a, hote_b):  # domaine enregistrable : « .ma » est un suffixe public d'un seul niveau
    return hote_a.split(".")[-2:] == hote_b.split(".")[-2:]


def cookies():
    a = arbre("authentication/views.py")
    samesite = ast.literal_eval(affectations(a)["_COOKIE_SAMESITE"])
    fn = next(n for n in a.body if getattr(n, "name", "") == "_set_auth_cookies")
    appels = [c for c in ast.walk(fn) if isinstance(c, ast.Call) and getattr(c.func, "attr", "") == "set_cookie"]
    return samesite, [ast.literal_eval(c.args[0]) for c in appels], any(k.arg == "domain" for c in appels for k in c.keywords)


def csrf_dans_auth():
    a = arbre("authentication/cookie_auth.py")
    cls = next(n for n in a.body if getattr(n, "name", "") == "CookieJWTAuthentication")
    src = ast.get_source_segment((DJ / "authentication/cookie_auth.py").read_text(encoding="utf-8"), cls) or ""
    return [n.name for n in cls.body if isinstance(n, ast.FunctionDef)], "csrf" in src.lower()


def site_public():
    hdr = (RACINE / "apps/web/worker/headers.mjs").read_text(encoding="utf-8")
    cs = re.search(r"`connect-src([^`]*)`", hdr)
    cred = sum(1 for p in (RACINE / "apps/web/src").rglob("*") if p.suffix in (".astro", ".ts", ".tsx", ".js")
               and ".test." not in p.name and re.search(r"credentials:\s*['\"]include", p.read_text(encoding="utf-8", errors="ignore")))
    return bool(cs and f"https://{API}" in cs.group(1)), cred


def sonde(ctx=None):
    r = reglages_prod()
    origines = list(r.get("CORS_ALLOWED_ORIGINS", []))
    exposees = {}
    for o in origines:
        h = reponse_cors(r, o, CHEMIN)
        if h.get("Access-Control-Allow-Credentials") == "true" and meme_site(o.split("://")[-1], API):
            exposees[o] = h
    samesite, noms_cookies, domain = cookies()
    methodes_auth, csrf = csrf_dans_auth()
    csp_ouverte, nb_cred = site_public()
    cookie_joint = samesite.lower() in ("lax", "none") and "access_token" in noms_cookies
    repro = bool(exposees) and cookie_joint and not csrf
    return {"repro": repro, "observe": {
        "methode": "ast : affectations CORS de base.py+prod.py exécutées (.env sans CORS_ALLOWED_ORIGINS) + modèle "
                   "de décision corsheaders ; cookies et auth lus par ast ; CSP et apps/web par texte",
        "prod CORS_ALLOWED_ORIGINS (défaut)": origines,
        "CORS_ALLOW_CREDENTIALS effectif": r.get("CORS_ALLOW_CREDENTIALS"),
        "CORS_URLS_REGEX": r.get("CORS_URLS_REGEX", "absent (défaut ^.*$ : toute l'API)"),
        f"réponse CORS sur {CHEMIN} par origine même-site": exposees,
        "cookies _set_auth_cookies": {"noms": noms_cookies, "SameSite": samesite, "domain posé": domain},
        "CookieJWTAuthentication": {"méthodes": methodes_auth, "contrôle CSRF": csrf},
        "site : CSP connect-src autorise l'ERP": csp_ouverte,
        "site : fetch credentials:'include' (besoin réel)": nb_cred,
        "effet": "un script exécuté sur taqinor.ma (balise Google Tag, tiers compromis, XSS) lit/écrit l'API avec la "
                 "session de l'employé connecté ; exige un script hostile sur le site (S2)"}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
