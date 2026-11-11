# flake8: noqa  (sonde HÔTE d'audit PF8 « messages envoyés aux clients », groupe AMSG — sans Django, sans base, sans réseau)
"""C-AMSG-011 — envoi par e-mail d'une facture ANNULÉE ou BROUILLON. Exécute la VRAIE action de lot
`apps/facturation/views/facture_lot.py::FactureLotActionsMixin.bulk` (`action=envoyer-email`, « Tout sélectionner → Envoyer
par email ») et la VRAIE action unitaire `facture_documents.py::FactureDocumentsActionsMixin.envoyer_email`, jusqu'au VRAI
`apps/ventes/email_service.py::send_document_email` → VRAI `_send`. Le constat est LATENT (prod en console) : la sonde joue
donc l'e-mail ALLUMÉ — un backend qui envoie, remplacé par une boîte d'envoi en mémoire (rien ne quitte la machine).
Statuts lus dans le vrai `apps/facturation/models.py::Facture.Statut`. Témoin : une facture émise."""
SONDE = {"constat": "C-AMSG-011", "sha": "3acfee471",
         "attendu": "lot et unitaire : la facture annulée et la brouillon partent (EmailLog « envoye », message dans la "
                    "boîte d'envoi, réponse « Email envoyé ») comme la facture émise"}
import ast, copy, logging, pathlib, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
NS = types.SimpleNamespace


class _SansImport(ast.NodeTransformer):  # imports (même imbriqués) → pass : leurs noms viennent de l'espace fourni
    visit_Import = visit_ImportFrom = lambda s, n: ast.Pass()


def _corps(rel, classe=None):
    arbre = ast.parse((DJ / rel).read_text(encoding="utf-8")).body
    return arbre if classe is None else next(n for n in arbre if isinstance(n, ast.ClassDef) and n.name == classe).body


def reel(rel, noms, ns, classe=None):  # exécute les nœuds RÉELS ``noms`` (du module, ou d'une classe) dans ``ns``
    pris = []
    for n in _corps(rel, classe):
        nom = getattr(n, "name", None) or (getattr(n.targets[0], "id", None) if isinstance(n, ast.Assign) else None)
        if nom in noms:
            n = copy.deepcopy(n)
            if hasattr(n, "decorator_list"): n.decorator_list = []
            pris.append(_SansImport().visit(n))
    exec(compile(ast.fix_missing_locations(ast.Module(body=pris, type_ignores=[])), rel, "exec"), ns)
    return ns


def statuts_reels():  # Facture.Statut du vrai modèle : NOM = ('valeur', 'Libellé')
    st = next(n for n in _corps("apps/facturation/models.py", "Facture") if isinstance(n, ast.ClassDef) and n.name == "Statut")
    return {n.targets[0].id: ast.literal_eval(n.value) for n in st.body if isinstance(n, ast.Assign)}


class QS(list):
    def filter(s, id__in=(), **k): return QS(o for o in s if o.id in id__in)


def sonde(ctx=None):
    boite, emaillogs = [], []
    reels = statuts_reels()
    Statut = NS(**{k: v[0] for k, v in reels.items()})
    libelles = {v[0]: v[1] for v in reels.values()}

    class Connexion:  # backend qui ENVOIE (e-mail allumé), remplacé par une boîte d'envoi en mémoire
        def send_messages(s, msgs): boite.extend(m.to[0] for m in msgs); return len(msgs)
    class EmailMultiAlternatives:
        def __init__(s, subject="", body="", from_email=None, to=None, connection=None, reply_to=None): s.to, s.c = to, connection
        def attach_alternative(s, *a): pass
        def attach(s, *a): pass
        def send(s, fail_silently=False): return s.c.send_messages([s])
    class EmailLog(NS):
        Statut, Direction = NS(ENVOYE="envoye", ECHEC="echec"), NS(SORTANT="sortant")
        def save(s, **k): s.id = len(emaillogs) + 1; s in emaillogs or emaillogs.append(s)
    class Facture(NS):
        def get_statut_display(s): return libelles.get(s.statut, s.statut)
    class Devis(NS): pass
    Facture.Statut = Statut
    co = NS(id=1, pk=1)
    factures = QS(Facture(id=i, pk=i, company=co, client=NS(nom=n, prenom="", email=f"facture{i}@example.invalid"),
                          reference=f"FAC-{i}", statut=s, contestee_le=None, montant_exigible=1200, libelle="x",
                          lignes=NS(exists=lambda: True))
                  for i, n, s in ((1, "Annulée", Statut.ANNULEE), (2, "Brouillon", Statut.BROUILLON), (3, "Témoin", Statut.EMISE)))
    ns = {"logger": logging.getLogger("sonde"),
          "settings": NS(EMAIL_BACKEND="anymail.backends.sendinblue.EmailBackend", ANYMAIL={"SENDINBLUE_API_KEY": "cle-fictive"},
                         DEFAULT_FROM_EMAIL="erp@example.invalid", INBOUND_REPLY_EMAIL=""),
          "get_connection": lambda fail_silently=False: Connexion(), "EmailMultiAlternatives": EmailMultiAlternatives,
          "EmailLog": EmailLog, "Facture": Facture, "Devis": Devis, "PDF_FACTURE_INDISPONIBLE": "PDF indisponible",
          "_branded_html": lambda c, s, b: "", "_modele_email_personnalise": lambda *a, **k: {}, "_signature": lambda c, **k: "L'équipe",
          "_document_pdf": lambda d: (b"%PDF-1.4", f"{d.reference}.pdf"), "_chatter_note": lambda *a: None,
          "Response": lambda data=None, status=200, **k: NS(data=data, status_code=status),
          "status": NS(HTTP_400_BAD_REQUEST=400, HTTP_409_CONFLICT=409, HTTP_202_ACCEPTED=202, HTTP_403_FORBIDDEN=403),
          "PeutEncaisser": lambda: NS(has_permission=lambda r, v: True), "MOTIF_SANS_ENCAISSER": "encaisser requis",
          "valider_corps": lambda r, schema: dict(r.data), "D": NS(EnvoyerEmailFactureRequest=None)}
    reel("core/checks.py", {"BACKENDS_NON_ENVOYEURS", "CLES_ENVOI", "backend_email_envoie", "cles_envoi_posees"}, ns)
    reel("apps/facturation/recouvrement.py", {"STATUTS_NON_RELANCABLES", "facture_relancable", "montant_exigible"}, ns)
    reel("apps/ventes/email_service.py", {"is_email_configured", "_from_email", "_reply_to_address", "_send",
                                          "_refuser_sans_pdf_facture", "send_document_email"}, ns)
    reel("apps/facturation/views/facture_lot.py", {"bulk"}, ns, "FactureLotActionsMixin")
    reel("apps/facturation/views/facture_documents.py", {"envoyer_email"}, ns, "FactureDocumentsActionsMixin")
    user = NS(id=1, is_authenticated=True, company=co)
    vue = NS(get_queryset=lambda: factures)
    lot = ns["bulk"](vue, NS(user=user, data={"action": "envoyer-email", "ids": [1, 2, 3]})).data
    unitaire = {}
    for f in factures:
        r = ns["envoyer_email"](NS(get_object=lambda f=f: f), NS(user=user, data={}), pk=f.id)
        unitaire[f.reference] = {"statut_http": r.status_code, "detail": r.data.get("detail")}
    parties = {f.reference: boite.count(f.client.email) for f in factures}
    a_tort = sorted(f.reference for f in factures if f.statut in (Statut.ANNULEE, Statut.BROUILLON) and parties[f.reference])
    return {"repro": bool(a_tort), "observe": {
        "methode": "exécution des vraies actions bulk (envoyer-email) et envoyer_email → vrai send_document_email → vrai _send (ast)",
        "routes": ["POST …/factures/bulk/ {action: envoyer-email}", "POST …/factures/<id>/envoyer-email/"],
        "factures": {f.reference: f.statut for f in factures}, "reponse_du_lot": {k: v["detail"] for k, v in lot.items()},
        "reponse_unitaire": unitaire, "messages_partis_par_facture": parties,
        "emaillog_envoye": sum(1 for l in emaillogs if l.statut == "envoye"), "envoyees_a_tort": a_tort,
        "temoin_emise_partie": bool(parties["FAC-3"])}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
