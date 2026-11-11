# flake8: noqa  (sonde HÔTE d'audit PF8 « messages envoyés aux clients », groupe AMSG — sans Django, sans base, sans réseau)
"""C-AMSG-009 — e-mail éteint (backend console, l'état de la production) : les VRAIS envois terrain / après-vente / portail
(`send_mail(fail_silently=True)` puis succès) sont joués sur des faux objets ; `send_mail` imite le backend console de Django
(il imprime, rend 1, rien ne quitte la machine). Emplacements exécutés : `installations/tasks.py::rappel_rdv_j1`
(+ vrais `_envoyer_email_client`, `_wa_draft_for_intervention`, `_rendre_rappel`), `installations/livraison_client_notify.py::
notify_livraison_transition`, `sav/notifications_client.py::notify_ticket_transition` (réglage SAV client allumé),
`portail/services.py::_envoyer_identifiants_portail`, `stock/services.py::_envoyer_identifiants_portail_fournisseur`.
Les prédicats réels `is_email_configured` / `backend_email_envoie` sont mis à portée (un correctif peut les lire)."""
SONDE = {"constat": "C-AMSG-009", "sha": "3acfee471",
         "attendu": "chaque emplacement dit « envoyé » (emails_envoyes=1, email_sent=True, True) alors que rien ne part ; "
                    "le brouillon WhatsApp du rappel J-1 est compté puis jeté"}
import ast, copy, datetime as dt, logging, pathlib, re, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
NS = types.SimpleNamespace


class _SansImport(ast.NodeTransformer):  # imports (même imbriqués) → pass : leurs noms viennent de l'espace fourni
    visit_Import = visit_ImportFrom = lambda s, n: ast.Pass()


def reel(rel, noms, ns):  # exécute les nœuds RÉELS ``noms`` (fonctions, affectations de module) du fichier dans ``ns``
    pris = []
    for n in ast.parse((DJ / rel).read_text(encoding="utf-8")).body:
        nom = getattr(n, "name", None) or (getattr(n.targets[0], "id", None) if isinstance(n, ast.Assign) else None)
        if nom in noms:
            n = copy.deepcopy(n)
            if hasattr(n, "decorator_list"): n.decorator_list = []
            pris.append(_SansImport().visit(n))
    exec(compile(ast.fix_missing_locations(ast.Module(body=pris, type_ignores=[])), rel, "exec"), ns)
    return ns


class QS(list):
    def filter(s, *a, **k): return s
    select_related = actives = filter


def sonde(ctx=None):
    console = []  # ce que le backend console « imprime » (rien n'est remis)

    def send_mail(subject="", message="", from_email=None, recipient_list=(), fail_silently=False, **k):
        console.append(list(recipient_list)); return 1  # = django.core.mail.send_mail sous console.EmailBackend
    settings = NS(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend", ANYMAIL={}, DEFAULT_FROM_EMAIL="erp@example.invalid",
                  INBOUND_REPLY_EMAIL="")
    base = {"logger": logging.getLogger("sonde"), "settings": settings, "dj_settings": settings, "send_mail": send_mail, "re": re}
    reel("core/checks.py", {"BACKENDS_NON_ENVOYEURS", "CLES_ENVOI", "backend_email_envoie", "cles_envoi_posees"}, base)
    reel("apps/ventes/email_service.py", {"is_email_configured"}, base)
    co = NS(id=1, pk=1)
    client = NS(id=5, prenom="Karim", nom="Client", email="x@example.invalid", telephone="+212600000000")
    commun = {"resolve_langue_sortie": lambda **k: "fr", "render_message_template": lambda t, c: t.format(**c),
              "build_wa_url": lambda p, m: f"https://wa.me/{p.lstrip('+')}?text=…",
              "MessageTemplate": NS(get_corps=lambda c, cle, lg: "Bonjour {nom}, votre rendez-vous {reference} est demain."),
              "EmailTemplate": NS(render=lambda c, cle, lg, **ctx: {"sujet": "Votre livraison", "corps": "Bonjour"})}
    sortie = {}
    # 1. rappel de pose J-1
    interv = NS(id=3, company=co, installation=NS(id=9, reference="INS-9", client=client), date_prevue=None, rdv_confirme=False)
    ns = reel("apps/installations/tasks.py", {"_rendre_rappel", "_wa_draft_for_intervention", "_envoyer_email_client", "rappel_rdv_j1"},
              {**base, **commun, "timedelta": dt.timedelta, "casablanca_today": lambda: dt.date(2026, 11, 11),
               "active_companies": lambda: [co], "Intervention": NS(objects=QS([interv]))})
    r1 = ns["rappel_rdv_j1"]()
    sortie["installations/tasks.py::rappel_rdv_j1"] = {"retour": r1, "brouillon_whatsapp_compte_puis_jete": bool(r1.get("wa_generes")) and "wa.me" not in str(r1)}
    # 2. avis de livraison au client
    ns = reel("apps/installations/livraison_client_notify.py", {"STATUT_TO_CLE", "_nom_complet", "notify_livraison_transition"},
              {**base, **commun, "_livraison_lien": lambda l, request=None: "https://erp.example.invalid/portail/client/livraisons"})
    sortie["installations/livraison_client_notify.py::notify_livraison_transition"] = ns["notify_livraison_transition"](
        NS(pk=4, reference="LIV-4", company=co, installation=NS(client=client)), "livree")
    # 3. avis SAV au client (réglage société notifications_client_sav allumé ; défaut éteint)
    ns = reel("apps/sav/notifications_client.py", {"STATUT_TO_CLE", "notify_ticket_transition"},
              {**base, **commun, "SavSlaSettings": NS(get=lambda c: NS(notifications_client_sav=True)),
               "build_ticket_transition_message": lambda t, cle, request=None: ("Bonjour", {"sujet": "Votre ticket", "corps": "Bonjour"}),
               "_build_wa_draft_url": lambda p, m: f"https://wa.me/{p.lstrip('+')}?text=…", "notifier_portail_client": lambda *a, **k: None})
    sortie["sav/notifications_client.py::notify_ticket_transition"] = ns["notify_ticket_transition"](
        NS(pk=6, company=co, client=client), "resolu")
    # 4-5. identifiants des portails client et fournisseur
    compte = NS(email="x@example.invalid", username="client-portail")
    ns = reel("apps/portail/services.py", {"_envoyer_identifiants_portail"}, {**base, "marque_portail": lambda c: {"nom_affichage": "Société"}})
    sortie["portail/services.py::_envoyer_identifiants_portail"] = ns["_envoyer_identifiants_portail"](compte, "Temp-0000", co)
    ns = reel("apps/stock/services.py", {"_envoyer_identifiants_portail_fournisseur"}, {**base, "_nom_affiche_societe": lambda c: "Société"})
    sortie["stock/services.py::_envoyer_identifiants_portail_fournisseur"] = ns["_envoyer_identifiants_portail_fournisseur"](compte, "Temp-0000", co)

    def dit_envoye(v):
        if isinstance(v, dict): return bool(v.get("emails_envoyes") or v.get("email_sent") or (v.get("retour") and dit_envoye(v["retour"])))
        return v is True
    faux = sorted(k for k, v in sortie.items() if dit_envoye(v))
    return {"repro": bool(faux), "observe": {
        "methode": "exécution des 5 vraies fonctions d'envoi (ast, ORM bouchonné), send_mail = backend console",
        "is_email_configured": base["is_email_configured"](), "messages_imprimes_par_le_backend_console": len(console),
        "emplacements_qui_disent_envoye": faux, "retours": sortie}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
