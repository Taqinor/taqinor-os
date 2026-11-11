# flake8: noqa  (sonde HÔTE d'audit PF8 « messages envoyés aux clients », groupe AMSG — sans Django, sans base, sans envoi)
"""C-AMSG-006 — « Relancer par WhatsApp » est servi pour une facture CONTESTÉE.
Exécute la VRAIE action `apps/facturation/views/facture_documents.py::FactureDocumentsActionsMixin.whatsapp` (corps extrait par
ast) avec les VRAIS modules `apps/ventes/utils/whatsapp.py` et `phone.py` (exécutés en entier) et la VRAIE garde
`apps/facturation/recouvrement.py::facture_relancable` à disposition ; ShareLink, gabarit, chatter et Response bouchonnés.
Un `ConflitEtat` levé compte comme 409. Témoin : la même facture non contestée. Puis lit l'écran `FactureRow.jsx`."""
SONDE = {"constat": "C-AMSG-006", "sha": "3acfee471",
         "attendu": "POST factures/<id>/whatsapp/ modele=relance sur une facture en retard dont contestee_le est posé rend 200 + wa_url "
                    "au lieu d'un 409 ; l'écran offre « Relancer par WhatsApp » sans lire contestee_le"}
import ast, datetime, pathlib, re, sys, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ, NS = RACINE / "backend/django_core", types.SimpleNamespace


def mod(nom, **attrs):  # module-bouchon enregistré (parents créés, attribut posé sur le parent)
    m = sys.modules.get(nom) or types.ModuleType(nom); m.__path__ = []; m.__dict__.update(attrs); sys.modules[nom] = m
    if "." in nom: setattr(mod(nom.rsplit(".", 1)[0]), nom.rsplit(".", 1)[1], m)
    return m


def charge(nom, rel):  # VRAI module du dépôt exécuté en entier sous ``nom`` (rien n'est écrit sur disque)
    m = mod(nom, __file__=str(DJ / rel), __package__=nom.rsplit(".", 1)[0])
    exec(compile((DJ / rel).read_text(encoding="utf-8"), str(DJ / rel), "exec"), m.__dict__); return m


def reel(rel, noms, g, classe=None):  # VRAIES fonctions / constantes du dépôt compilées dans l'espace ``g``
    arbre = ast.parse((DJ / rel).read_text(encoding="utf-8"))
    corps = arbre.body if classe is None else next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == classe).body
    for f in (n for n in corps if (getattr(n, "name", None) in noms) or (isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") in noms)):
        if hasattr(f, "decorator_list"): f.decorator_list = []
        exec(compile(ast.Module(body=[f], type_ignores=[]), str(DJ / rel), "exec"), g)
    return g


def globaux(rel, nom_module, g):  # noms importés au niveau module du vrai fichier, quand leur module est chargé ici
    pkg = nom_module.rsplit(".", 1)[0].split(".")
    for n in ast.parse((DJ / rel).read_text(encoding="utf-8")).body:
        if isinstance(n, ast.ImportFrom):
            base = ".".join(pkg[:len(pkg) - n.level + 1] + ([n.module] if n.module else [])) if n.level else n.module
            for a in n.names:
                if base in sys.modules and hasattr(sys.modules[base], a.name): g.setdefault(a.asname or a.name, getattr(sys.modules[base], a.name))


class ConflitEtat(Exception): status_code = 409


def sonde(ctx=None):
    sauve, pyc = dict(sys.modules), sys.dont_write_bytecode
    sys.dont_write_bytecode, chatter, sortie = True, [], {}
    try:
        mod("core.conflit_etat", ConflitEtat=ConflitEtat)
        mod("apps.ventes.models", ShareLink=NS(for_facture=lambda f: NS(token="jeton-public")), EmailLog=NS())
        mod("apps.parametres.models", MessageTemplate=NS(get_corps=lambda company, cle, langue: "Bonjour {nom}, " + cle + " de la facture {reference} : {lien}"))
        mod("apps.parametres.selectors", company_identity=lambda company: {"nom": "Société de sonde"})
        mod("apps.ventes.domain.encaissements", public_url=lambda chemin, request=None: "https://erp.example.invalid" + chemin)
        mod("apps.ventes.activity", log_facture_whatsapp=lambda facture, user, modele: chatter.append(f"{facture.reference} : {modele}"))
        charge("apps.ventes.utils.phone", "apps/ventes/utils/phone.py"); charge("apps.ventes.utils.whatsapp", "apps/ventes/utils/whatsapp.py")
        rc = mod("apps.facturation.recouvrement", __package__="apps.facturation", logger=NS(warning=print))
        reel("apps/facturation/recouvrement.py", ("STATUTS_NON_RELANCABLES", "STATUTS_HORS_RELEVE", "facture_relancable", "montant_exigible"), rc.__dict__)
        mod("apps.facturation.selectors", facture_relancable=rc.facture_relancable)
        g = {"__name__": "apps.facturation.views.facture_documents", "__package__": "apps.facturation.views", "logger": NS(warning=print),
             "status": NS(HTTP_409_CONFLICT=409, HTTP_400_BAD_REQUEST=400), "D": NS(FactureWhatsappRequest=NS()),
             "Response": lambda data=None, status=200, **k: NS(data=data, status_code=status),
             "valider_corps": lambda request, schema: dict(request.data)}
        globaux("apps/facturation/views/facture_documents.py", "apps.facturation.views.facture_documents", g)
        vue = reel("apps/facturation/views/facture_documents.py", ("whatsapp",), g, classe="FactureDocumentsActionsMixin")["whatsapp"]
        for nom, contestee in (("contestee", datetime.date(2026, 11, 2)), ("temoin_non_contestee", None)):
            facture = NS(id=3, pk=3, reference="FAC-2611-0003", statut="en_retard", montant_du=12000, montant_exigible=12000,
                         contestee_le=contestee, motif_contestation="travaux non terminés" if contestee else "", company=NS(id=1, nom="Société"),
                         client_id=4, client=NS(nom="Client", telephone="+212600000000"), get_statut_display=lambda: "En retard")
            req = NS(method="POST", user=NS(id=1, pk=1, company_id=1), data={"modele": "relance", "langue": "fr"})
            try:
                r = vue(NS(get_object=lambda f=facture: f, request=req), req, pk=3)
                sortie[nom] = {"statut": r.status_code, "wa_url": (r.data or {}).get("wa_url"), "detail": (r.data or {}).get("detail")}
            except ConflitEtat as e:
                sortie[nom] = {"statut": 409, "refus": str(e)}
        garde = rc.facture_relancable(NS(statut="en_retard", contestee_le=datetime.date(2026, 11, 2), montant_exigible=12000))
    finally:
        for n in set(sys.modules) - set(sauve): sys.modules.pop(n)
        sys.modules.update(sauve); sys.dont_write_bytecode = pyc
    if sortie["temoin_non_contestee"]["statut"] != 200: raise RuntimeError(f"sonde cassée : le témoin n'obtient pas 200 ({sortie})")
    jsx = (RACINE / "frontend/src/pages/ventes/factureList/FactureRow.jsx").read_text(encoding="utf-8")
    bloc = jsx[max(0, jsx.find("handleWhatsApp(f,") - 600): jsx.find("Relancer par WhatsApp") + 200]
    ecran = {"bouton_relancer_par_whatsapp": "Relancer par WhatsApp" in jsx and "'relance'" in bloc,
             "contestee_lue_pres_du_bouton": bool(re.search(r"contest", bloc))}
    c = sortie["contestee"]
    return {"repro": c["statut"] == 200 and bool(c.get("wa_url")), "observe": {
        "methode": "exécution de la vraie action whatsapp (+ vrais whatsapp.py/phone.py ; garde facture_relancable réelle disponible) ; écran lu",
        "route": "POST /api/django/ventes/factures/<id>/whatsapp/ {modele: relance}", "par_cas": sortie, "chatter": chatter,
        "facture_relancable_sur_la_contestee": garde, "ecran_FactureRow": ecran}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
