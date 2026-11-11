# flake8: noqa  (sonde HÔTE d'audit PF8 « messages envoyés aux clients », groupe AMSG — sans Django, sans base, sans réseau)
"""C-AMSG-008 — sous un backend e-mail qui n'envoie rien (console, l'état de la production), la VRAIE tâche planifiée
`apps/ventes/scheduled.py::relance_reminders` (+ vrais `_dispatch_relance_canal`, `_email_parti`, `_reporter_relance`,
`domain/recouvrement.py::prochain_niveau`, `facturation/recouvrement.py::facture_relancable`) appelle le VRAI
`apps/ventes/email_service.py::send_relance_email` → VRAI `_send` (et le vrai `is_email_configured` + `core/checks.py`
mis à sa portée). La connexion e-mail imite le backend console de Django : elle imprime, rien ne quitte la machine.
Scénario : facture en retard, relance du jour, 3 niveaux. Volet informatif : un niveau au canal WhatsApp."""
SONDE = {"constat": "C-AMSG-008", "sha": "3acfee471",
         "attendu": "EmailLog « envoye » alors que rien ne part ; RelanceLog niveau 1 créée, prochaine_relance avancée "
                    "(niveau consommé) ; is_email_configured() répond pourtant faux"}
import ast, copy, datetime as dt, logging, pathlib, types
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


_OPS = {"exact": lambda c, v: c == v, "isnull": lambda c, v: (c is None) == v, "in": lambda c, v: c in v,
        "lte": lambda c, v: c is not None and c <= v, "gte": lambda c, v: c is not None and c >= v,
        "lt": lambda c, v: c is not None and c < v, "gt": lambda c, v: c is not None and c > v}


class QS(list):  # faux QuerySet
    def _ok(s, o, kw):
        res = []
        for k, v in kw.items():
            parts = k.split("__"); op = parts.pop() if parts[-1] in _OPS else "exact"; c = o
            for p in parts: c = getattr(c, p, None)
            res.append(_OPS[op](c, v))
        return all(res)
    def filter(s, *a, **kw): return QS(o for o in s if s._ok(o, kw))
    def exclude(s, *a, **kw): return QS(o for o in s if not s._ok(o, kw))
    select_related = prefetch_related = order_by = lambda s, *a: s
    def all(s): return s
    def first(s): return s[0] if s else None
    def count(s): return len(s)
    def values_list(s, *ch, flat=False): return QS(getattr(o, ch[0]) if flat else tuple(getattr(o, c) for c in ch) for o in s)


class Obj(NS):
    def save(s, **k): pass


def scenario(canal):
    today, co = dt.date(2026, 11, 11), NS(id=1, pk=1)
    console, emaillogs, relancelogs, brouillons = [], QS(), QS(), []
    class Connexion:  # = django.core.mail.backends.console.EmailBackend : écrit sur la sortie, n'envoie rien
        def send_messages(s, msgs): console.extend(m.to for m in msgs); return len(msgs)
    class EmailMultiAlternatives:
        def __init__(s, subject="", body="", from_email=None, to=None, connection=None, reply_to=None): s.to, s.c = to, connection
        def attach_alternative(s, *a): pass
        def attach(s, *a): pass
        def send(s, fail_silently=False): return s.c.send_messages([s])
    class EmailLog(Obj):
        Statut, Direction = NS(ENVOYE="envoye", ECHEC="echec"), NS(SORTANT="sortant")
        objects = NS(filter=lambda **kw: emaillogs.filter(**kw))
        def save(s, **k): s.created_at = today; s in emaillogs or emaillogs.append(s)
    niveaux = [Obj(ordre=i, nom=n, delai_jours=d, canal=canal if i == 1 else "email", message="")
               for i, n, d in ((1, "Rappel courtois", 7), (2, "Relance", 15), (3, "Mise en demeure", 30))]
    facture = Obj(pk=7, id=7, company=co, company_id=1, client_id=7, client=Obj(email="x@example.invalid", owner=None),
                  statut="en_retard", prochaine_relance=today, exclu_relances=False, exclu_relances_jusquau=None,
                  contestee_le=None, montant_exigible=1200, reference="FAC-7", created_by_id=None, created_by=None, relances=QS())
    def creer_relance(**kw): r = Obj(compte_dans_cadence=True, **kw); relancelogs.append(r); facture.relances.append(r); return r
    ns = {"logger": logging.getLogger("sonde"), "timedelta": dt.timedelta, "casablanca_today": lambda: today,
          "settings": NS(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend", ANYMAIL={},
                         DEFAULT_FROM_EMAIL="erp@example.invalid", INBOUND_REPLY_EMAIL=""),
          "get_connection": lambda fail_silently=False: Connexion(), "EmailMultiAlternatives": EmailMultiAlternatives,
          "EmailLog": EmailLog, "PDF_FACTURE_INDISPONIBLE": "PDF indisponible", "_branded_html": lambda c, s, b: "",
          "composer_relance_email": lambda f, niveau_nom="", message="": (f"Relance facture {f.reference}", "Bonjour…"),
          "_document_pdf": lambda f: (b"%PDF-1.4", "FAC-7.pdf"), "RELATIONS_MONTANT_DU": (), "active_company_ids": lambda: [1],
          "Facture": NS(objects=QS([facture])), "RelanceLog": NS(objects=NS(create=creer_relance)),
          "ParametrageRelanceClient": NS(objects=QS(), Mode=NS(MANUEL="manuel")), "PromessePaiement": NS(objects=QS(), Statut=NS(EN_COURS="en_cours")),
          "ensure_default_followup_levels": lambda c: None, "niveaux_cadence": lambda c: niveaux,
          "rendre_message_relance": lambda n, f: "Sauf erreur de notre part…", "prochain_jour_ouvre": lambda d, c: d,
          "FollowupLevel": NS(Canal=NS(EMAIL="email", WHATSAPP="whatsapp", COURRIER="courrier", APPEL="appel")),
          "build_facture_whatsapp_draft": lambda f, modele="": brouillons.append(modele) or "https://wa.me/212600000000?text=…"}
    reel("core/checks.py", {"BACKENDS_NON_ENVOYEURS", "CLES_ENVOI", "backend_email_envoie", "cles_envoi_posees"}, ns)
    reel("apps/facturation/recouvrement.py", {"STATUTS_NON_RELANCABLES", "facture_relancable", "montant_exigible"}, ns)
    reel("apps/ventes/domain/recouvrement.py", {"prochain_niveau"}, ns)
    reel("apps/ventes/email_service.py", {"is_email_configured", "_from_email", "_reply_to_address", "_send",
                                          "_refuser_sans_pdf_facture", "send_relance_email"}, ns)
    reel("apps/ventes/public/payload_conditions.py", {"EMAIL_BACKENDS_SANS_ENVOI"}, ns)  # AMSG29 — prédicat du correctif
    reel("apps/ventes/scheduled.py", {"_dispatch_relance_canal", "_email_parti", "_reporter_relance", "_promesse_honoree",
                                      "_check_promesses_expirees", "relance_reminders", "_email_sans_envoi",
                                      "_activite_relance", "_clients_manuels"}, ns)
    compte = ns["relance_reminders"]()
    return {"is_email_configured": ns["is_email_configured"](), "relances_comptees": compte,
            "messages_imprimes_par_le_backend_console": len(console), "emaillog_statuts": [l.statut for l in emaillogs],
            "relancelog_niveaux": [r.niveau for r in relancelogs], "prochaine_relance": f"{today} → {facture.prochaine_relance}",
            "prochain_niveau_apres": getattr(ns["prochain_niveau"](facture, niveaux)[0], "nom", None),
            "brouillons_whatsapp_calcules_puis_jetes": len(brouillons)}


def sonde(ctx=None):
    mail, wa = scenario("email"), scenario("whatsapp")
    faux_envoye = "envoye" in mail["emaillog_statuts"] or bool(mail["relancelog_niveaux"])
    return {"repro": faux_envoye, "observe": {
        "methode": "exécution de la vraie tâche relance_reminders → vrai send_relance_email → vrai _send (ast, ORM bouchonné)",
        "backend": "django.core.mail.backends.console.EmailBackend (aucun envoi réel)",
        "canal_email": mail, "volet_informatif_canal_whatsapp": wa}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
