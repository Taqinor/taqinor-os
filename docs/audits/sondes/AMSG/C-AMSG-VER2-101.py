# flake8: noqa  (sonde HÔTE de la contre-visite « vérifie AMSG » du 13/11, PF8 — sans Django, sans base, sans réseau)
"""C-AMSG-VER2-101 — e-mail éteint (clé posée, backend console : l'état de la production) : l'administrateur du portail
client invite un collègue depuis « Mon équipe ». On joue la VRAIE vue `apps/portail/views_client.py::MonEquipePortailViewSet.
create` (corps réel extrait de la classe, décorateurs et imports retirés) sur le VRAI service `apps/portail/services.py::
inviter_membre_portail`, qui appelle le VRAI `_envoyer_invitation_portail` ; la chaîne réelle `notifications/services.py::
_is_email_configured` → `ventes/email_service.py::is_email_configured` → `core/checks.py::backend_email_envoie` décide si
l'e-mail part. ORM, `send_mail`, `timezone`, `marque_portail`, `public_url` bouchonnés. Témoin : même jeu avec un backend qui
envoie (anymail) ⇒ l'envoi part, ce qui prouve que la chaîne réelle est bien traversée. 3ᵉ point, LU (pas exécuté : JSX) :
`frontend/src/features/portail/client/PortailClientEquipe.jsx::inviter` affiche-t-il « Invitation envoyée. » sans lire la
réponse ? Repro = rien n'est parti, la réponse 201 ne le dit pas, et l'écran annonce « envoyée »."""
SONDE = {"constat": "C-AMSG-VER2-101", "sha": "d64fa1e4e",
         "attendu": "e-mail éteint : _envoyer_invitation_portail rend False et send_mail n'est pas appelé, mais la vue répond 201 "
                    "sans aucune clé disant que l'e-mail n'est pas parti, et l'écran affiche « Invitation envoyée. »"}
import ast, builtins, copy, datetime as dt, importlib, pathlib, re, sys, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
NS = types.SimpleNamespace


class _SansImport(ast.NodeTransformer):  # imports (même imbriqués) → pass : leurs noms sont résolus par l'Espace
    visit_Import = visit_ImportFrom = lambda s, n: ast.Pass()


class Espace(dict):
    """Globales d'un module RÉEL (même mécanique que les sondes AMSG du 11/11) : fonctions de premier niveau chargées,
    tout autre nom résolu à la première lecture (stdlib ou dépôt, à travers les ré-exports). Les bouchons priment."""
    def __init__(s, rel, b):
        super().__init__(b, __name__=rel[:-3].replace("/", "."))
        s.b, s.corps, s.imp, pkg = b, ast.parse((DJ / rel).read_text(encoding="utf-8")).body, {}, rel.split("/")[:-1]
        for n in ast.walk(ast.Module(body=s.corps, type_ignores=[])):
            if isinstance(n, ast.ImportFrom) and n.module:
                base = pkg[:len(pkg) - n.level + 1] if n.level else []
                s.imp.update({a.asname or a.name: (".".join(base + [n.module]), a.name) for a in n.names})
            elif isinstance(n, ast.Import):
                s.imp.update({a.asname or a.name.split(".")[0]: (a.name if a.asname else a.name.split(".")[0], None) for a in n.names})
        for n in s.corps:
            if isinstance(n, ast.FunctionDef):
                try: s._charger(n)
                except Exception: pass
        s.update(b)

    def _charger(s, n):
        n = copy.deepcopy(n)
        if hasattr(n, "decorator_list"): n.decorator_list = []
        exec(compile(ast.fix_missing_locations(ast.Module(body=[_SansImport().visit(n)], type_ignores=[])), s["__name__"], "exec"), s)

    def __missing__(s, nom):
        if nom.startswith("__") or hasattr(builtins, nom): raise KeyError(nom)
        try:
            n = next((n for n in s.corps if nom in (getattr(n, "name", None), *(getattr(t, "id", None) for t in getattr(n, "targets", ())))), None)
            if n is not None: s._charger(n); return dict.__getitem__(s, nom)
            mod, orig = s.imp[nom]
            if mod.split(".")[0] in sys.stdlib_module_names:
                v = importlib.import_module(mod) if orig is None else getattr(importlib.import_module(mod), orig)
            else:
                p = mod.replace(".", "/"); v = espace(next(r for r in (p + ".py", p + "/__init__.py") if (DJ / r).is_file()), s.b)[orig]
        except Exception: raise KeyError(nom) from None
        s[nom] = v; return v


def espace(rel, b):
    c = b.setdefault("__espaces__", {})
    return c[rel] if rel in c else c.setdefault(rel, Espace(rel, b))


def methode(rel, classe, nom, glob):
    """Le corps RÉEL d'une méthode de classe, exécuté comme fonction dans `glob` (décorateurs et imports retirés)."""
    arbre = ast.parse((DJ / rel).read_text(encoding="utf-8"))
    cls = next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == classe)
    f = copy.deepcopy(next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == nom))
    f.decorator_list = []
    exec(compile(ast.fix_missing_locations(ast.Module(body=[_SansImport().visit(f)], type_ignores=[])), rel, "exec"), glob)
    return glob[nom]


class Obj(NS):
    def get_role_display(s): return {"lecture": "Lecture seule", "ecriture": "Écriture"}.get(s.role, s.role)
    def get_statut_display(s): return "En attente"


def jouer(backend):
    maintenant = dt.datetime(2026, 11, 13, 10, 0, tzinfo=dt.timezone.utc)
    co = NS(id=1, pk=1)
    envois, invitations = [], []
    settings = NS(EMAIL_BACKEND=backend, ANYMAIL={"SENDINBLUE_API_KEY": "cle-factice"},
                  DEFAULT_FROM_EMAIL="erp@exemple.invalid", EMAIL_BACKEND_REEL="")

    def send_mail(**kw):  # imite un backend : rend le nombre de messages remis
        envois.append(kw.get("recipient_list")); return 1

    class _Qs(list):
        def first(s): return s[0] if s else None

    def creer(**kw):
        inv = Obj(id=5, created_at=maintenant, date_acceptation=None, statut="en_attente", **kw); invitations.append(inv); return inv
    base = {"settings": settings, "send_mail": send_mail,
            "timezone": NS(now=lambda: maintenant, localtime=lambda d: d),
            "marque_portail": lambda company: {"nom_affichage": "Société témoin"},
            "ComptePortailClient": NS(objects=NS(filter=lambda **kw: _Qs([NS(id=9, client_id=kw.get("client_id"))]))),
            "InvitationPortail": NS(objects=NS(create=creer),
                                    Role=NS(values=["lecture", "ecriture"], LECTURE="lecture"))}
    svc = espace("apps/portail/services.py", base)
    vrai_envoi, retours = svc["_envoyer_invitation_portail"], []

    def espion(*a, **kw):  # le VRAI _envoyer_invitation_portail, dont on note le résultat
        r = vrai_envoi(*a, **kw); retours.append(r); return r
    svc["_envoyer_invitation_portail"] = espion

    class Response:
        def __init__(s, data=None, status=200): s.data, s.status_code = data, status
    glob = {"services": NS(est_admin_portail_client=lambda u: True, inviter_membre_portail=svc["inviter_membre_portail"]),
            "Response": Response, "status": NS(HTTP_201_CREATED=201, HTTP_400_BAD_REQUEST=400, HTTP_403_FORBIDDEN=403),
            "_scope": lambda request: (co, 42), "public_url": lambda chemin, request=None: "https://erp.exemple.invalid/"}
    ligne = methode("apps/portail/views_client.py", "MonEquipePortailViewSet", "_ligne", dict(glob))
    create = methode("apps/portail/views_client.py", "MonEquipePortailViewSet", "create", glob)
    rep = create(NS(_ligne=ligne), NS(data={"email": "collegue@exemple.invalid", "role": "lecture"}, user=NS()))
    return {"backend": backend, "envoi_reel_rendu": retours, "send_mail_appels": len(envois),
            "statut_http": rep.status_code, "cles_servies": sorted((rep.data or {}).keys()),
            "invitation_creee": bool(invitations)}


def ecran():
    src = (RACINE / "frontend/src/features/portail/client/PortailClientEquipe.jsx").read_text(encoding="utf-8")
    m = re.search(r"const inviter = async.*?\n  }\n", src, re.S)
    corps = m.group(0) if m else ""
    return {"bloc_inviter_trouve": bool(m),
            "message_affiche": re.findall(r"setMessageOk\('([^']*)'\)", corps),
            "reponse_lue": bool(re.search(r"(const|let)\s+\w+\s*=\s*await\s+portailApi\.equipe\.inviter|email_envoye", corps))}


def sonde(ctx=None):
    eteint = jouer("django.core.mail.backends.console.EmailBackend")   # la production (clé posée, backend console)
    temoin = jouer("anymail.backends.brevo.EmailBackend")               # un backend qui envoie : la chaîne réelle est traversée
    vue = ecran()
    faux_envoyee = (eteint["envoi_reel_rendu"] == [False] and eteint["send_mail_appels"] == 0 and eteint["statut_http"] == 201
                    and not any("email" in c and "envoy" in c for c in eteint["cles_servies"])
                    and "Invitation envoyée." in vue["message_affiche"] and not vue["reponse_lue"])
    chaine_ok = temoin["envoi_reel_rendu"] == [True] and temoin["send_mail_appels"] == 1
    return {"repro": faux_envoyee and chaine_ok, "observe": {
        "methode": "exécution de la vraie vue create + vrai inviter_membre_portail + vrai _envoyer_invitation_portail (chaîne "
                   "is_email_configured réelle) ; lecture du bloc inviter de l'écran",
        "emplacements": ["apps/portail/services.py::inviter_membre_portail", "apps/portail/views_client.py::MonEquipePortailViewSet.create",
                         "frontend/src/features/portail/client/PortailClientEquipe.jsx::inviter"],
        "email_eteint": eteint, "temoin_backend_qui_envoie": temoin, "ecran": vue}}


if __name__ == "__main__":
    import json
    r = sonde()
    print(json.dumps(r, ensure_ascii=False, indent=1, default=str))
    print(f"repro: {r['repro']}")
