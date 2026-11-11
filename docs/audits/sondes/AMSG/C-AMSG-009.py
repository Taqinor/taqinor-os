# flake8: noqa  (sonde HÔTE d'audit PF8 « messages envoyés aux clients », groupe AMSG — sans Django, sans base, sans réseau)
"""C-AMSG-009 — e-mail éteint (backend console, l'état de la production) : les VRAIS envois terrain / après-vente / portail
(`send_mail(fail_silently=True)` puis succès) sont joués sur des faux objets ; `send_mail` imite le backend console de Django
(il imprime, rend 1, rien ne quitte la machine). Emplacements exécutés : `installations/tasks.py::rappel_rdv_j1`,
`installations/livraison_client_notify.py::notify_livraison_transition`, `sav/notifications_client.py::notify_ticket_transition`
(réglage SAV client allumé), `portail/services.py::_envoyer_identifiants_portail`,
`stock/services.py::_envoyer_identifiants_portail_fournisseur`. Chaque module est chargé ENTIER (toutes ses fonctions de
premier niveau) et tout autre nom est résolu PARESSEUSEMENT dans le dépôt (`is_email_configured`, `core/checks.py::
backend_email_envoie`, toute fonction auxiliaire qu'un correctif ajouterait) : un correctif n'exige aucune retouche."""
SONDE = {"constat": "C-AMSG-009", "sha": "3acfee471",
         "attendu": "chaque emplacement dit « envoyé » (emails_envoyes=1, email_sent=True, True) alors que rien ne part ; "
                    "le brouillon WhatsApp du rappel J-1 est compté puis jeté"}
import ast, builtins, copy, datetime as dt, importlib, logging, pathlib, sys, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
NS = types.SimpleNamespace


class _SansImport(ast.NodeTransformer):  # imports (même imbriqués) → pass : leurs noms sont résolus par l'Espace
    visit_Import = visit_ImportFrom = lambda s, n: ast.Pass()


class Espace(dict):
    """Globales d'un module RÉEL : toutes ses fonctions de premier niveau (corps réels, décorateurs et imports retirés) ;
    tout autre nom (constante, classe, nom importé — stdlib ou dépôt, suivi à travers les ré-exports) est résolu à la
    première lecture. Les bouchons priment. Un nom introuvable ne lève NameError qu'à l'exécution qui le lit."""
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


class QS(list):
    def filter(s, *a, **k): return s
    select_related = actives = filter


def sonde(ctx=None):
    console = []  # ce que le backend console « imprime » (rien n'est remis)

    def send_mail(subject="", message="", from_email=None, recipient_list=(), fail_silently=False, **k):
        console.append(list(recipient_list)); return 1  # = django.core.mail.send_mail sous console.EmailBackend
    settings = NS(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend", ANYMAIL={}, DEFAULT_FROM_EMAIL="erp@example.invalid",
                  INBOUND_REPLY_EMAIL="")
    co = NS(id=1, pk=1)
    client = NS(id=5, prenom="Karim", nom="Client", email="x@example.invalid", telephone="+212600000000")
    interv = NS(id=3, company=co, installation=NS(id=9, reference="INS-9", client=client), date_prevue=None, rdv_confirme=False)
    b = {"logger": logging.getLogger("sonde"), "settings": settings, "dj_settings": settings, "send_mail": send_mail,
         "resolve_langue_sortie": lambda **k: "fr", "render_message_template": lambda t, c: t.format(**c),
         "build_wa_url": lambda p, m: f"https://wa.me/{p.lstrip('+')}?text=…",
         "MessageTemplate": NS(get_corps=lambda c, cle, lg: "Bonjour {nom}, votre rendez-vous {reference} est demain."),
         "EmailTemplate": NS(render=lambda c, cle, lg, **ctx: {"sujet": "Votre livraison", "corps": "Bonjour"}),
         "casablanca_today": lambda: dt.date(2026, 11, 11), "active_companies": lambda: [co], "Intervention": NS(objects=QS([interv])),
         "_livraison_lien": lambda l, request=None: "https://erp.example.invalid/portail/client/livraisons",
         "SavSlaSettings": NS(get=lambda c: NS(notifications_client_sav=True)),
         "build_ticket_transition_message": lambda t, cle, request=None: ("Bonjour", {"sujet": "Votre ticket", "corps": "Bonjour"}),
         "_build_wa_draft_url": lambda p, m: f"https://wa.me/{p.lstrip('+')}?text=…", "notifier_portail_client": lambda *a, **k: None,
         "marque_portail": lambda c: {"nom_affichage": "Société"}, "_nom_affiche_societe": lambda c: "Société"}
    sortie, compte = {}, NS(email="x@example.invalid", username="client-portail")
    r1 = espace("apps/installations/tasks.py", b)["rappel_rdv_j1"]()  # 1. rappel de pose J-1
    sortie["installations/tasks.py::rappel_rdv_j1"] = {"retour": r1, "brouillon_whatsapp_compte_puis_jete": bool(r1.get("wa_generes")) and "wa.me" not in str(r1)}
    sortie["installations/livraison_client_notify.py::notify_livraison_transition"] = espace(  # 2. avis de livraison
        "apps/installations/livraison_client_notify.py", b)["notify_livraison_transition"](
        NS(pk=4, reference="LIV-4", company=co, installation=NS(client=client)), "livree")
    sortie["sav/notifications_client.py::notify_ticket_transition"] = espace(  # 3. avis SAV (réglage société allumé ; défaut éteint)
        "apps/sav/notifications_client.py", b)["notify_ticket_transition"](NS(pk=6, company=co, client=client), "resolu")
    sortie["portail/services.py::_envoyer_identifiants_portail"] = espace(  # 4-5. identifiants des portails
        "apps/portail/services.py", b)["_envoyer_identifiants_portail"](compte, "Temp-0000", co)
    sortie["stock/services.py::_envoyer_identifiants_portail_fournisseur"] = espace(
        "apps/stock/services.py", b)["_envoyer_identifiants_portail_fournisseur"](compte, "Temp-0000", co)

    def dit_envoye(v):
        if isinstance(v, dict): return bool(v.get("emails_envoyes") or v.get("email_sent") or (v.get("retour") and dit_envoye(v["retour"])))
        return v is True
    faux = sorted(k for k, v in sortie.items() if dit_envoye(v))
    return {"repro": bool(faux), "observe": {
        "methode": "exécution des 5 vraies fonctions d'envoi (modules réels, noms résolus paresseusement, ORM bouchonné), send_mail = backend console",
        "is_email_configured": espace("apps/ventes/email_service.py", b)["is_email_configured"](),
        "messages_imprimes_par_le_backend_console": len(console), "emplacements_qui_disent_envoye": faux, "retours": sortie}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
