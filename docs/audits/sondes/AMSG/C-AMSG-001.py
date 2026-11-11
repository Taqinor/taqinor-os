# flake8: noqa  (sonde HÔTE d'audit PF8 « messages envoyés aux clients », groupe AMSG — sans Django, sans base, sans envoi)
"""C-AMSG-001 — « Envoyer un questionnaire » vers un lead opposé, perdu ou archivé.
Exécute la VRAIE action `apps/crm/leads_views.py::LeadIntakeActionsMixin.questionnaire_lien` (corps extrait par ast,
décorateurs retirés) avec les VRAIES `questionnaire.mint_lien` / `url_publique` / `lead_clos`, les VRAIES gardes
`cadence_messages.garde_contact_du_lead` / `refus_rendu_whatsapp` et le VRAI module `portee_selectors` à disposition ;
ORM, Response et journal bouchonnés. Un `ConflitEtat` levé compte comme 409 (son statut DRF). Puis lit l'écran
`QuestionnaireDialog.jsx` (lien wa.me assemblé à partir de `url`)."""
SONDE = {"constat": "C-AMSG-001", "sha": "3acfee471",
         "attendu": "POST questionnaire-lien/ sur un lead ne_plus_contacter (et perdu, archivé) rend 200 + url du questionnaire "
                    "au lieu d'un 409 ; l'écran en fait un lien wa.me pré-rempli sans lire l'opposition"}
import ast, datetime, pathlib, sys, types
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


def reel(rel, noms, g, classe=None):  # VRAIES fonctions (corps du dépôt) compilées dans l'espace ``g``
    arbre = ast.parse((DJ / rel).read_text(encoding="utf-8"))
    corps = arbre.body if classe is None else next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == classe).body
    for f in (n for n in corps if isinstance(n, ast.FunctionDef) and n.name in noms):
        f.decorator_list = []; exec(compile(ast.Module(body=[f], type_ignores=[]), str(DJ / rel), "exec"), g)
    return g


def globaux(rel, nom_module, g):  # noms importés au niveau module du vrai fichier, quand leur module est chargé ici
    pkg = nom_module.rsplit(".", 1)[0].split(".")
    for n in ast.parse((DJ / rel).read_text(encoding="utf-8")).body:
        if isinstance(n, ast.ImportFrom):
            base = ".".join(pkg[:len(pkg) - n.level + 1] + ([n.module] if n.module else [])) if n.level else n.module
            for a in n.names:
                if base in sys.modules and hasattr(sys.modules[base], a.name): g.setdefault(a.asname or a.name, getattr(sys.modules[base], a.name))


class ConflitEtat(Exception): status_code = 409


class Lead:
    def __init__(s, **kw): s.__dict__.update(kw)


class Lien:  # crm.QuestionnaireLien (faux)
    objects = NS(filter=lambda **k: NS(order_by=lambda *a: NS(first=lambda: None)))
    def __init__(s, company=None, lead=None, created_by=None):
        s.company, s.lead, s.token, s.token_interne, s.questions = company, lead, "jeton-client", "jeton-interne", None
        s.expires_at = datetime.datetime(2026, 12, 11, 10, 0)
    def save(s, **k): pass
    def question_posee(s, cle): return bool((s.questions or {}).get(cle))


def sonde(ctx=None):
    sauve, pyc = dict(sys.modules), sys.dont_write_bytecode
    sys.dont_write_bytecode, notes, sortie = True, [], {}
    try:
        mod("django.conf", settings=NS(PUBLIC_SITE_URL="https://site.example.invalid", SITE_URL=""))
        mod("django.utils.timezone", now=lambda: datetime.datetime(2026, 11, 11, 10, 0))
        mod("core.conflit_etat", ConflitEtat=ConflitEtat)
        mod("apps.crm.models", Lead=Lead, QuestionnaireLien=Lien, LeadActivity=NS())
        charge("apps.crm.portee_selectors", "apps/crm/portee_selectors.py")
        cm = mod("apps.crm.cadence_messages", __package__="apps.crm", RelanceEtape=NS(Statut=NS(ANNULEE="annulee")))
        reel("apps/crm/cadence_messages.py", ("refus_rendu_whatsapp", "garde_rendu_whatsapp", "garde_contact_du_lead"), cm.__dict__)
        class SectionInconnue(Exception): pass
        class SectionHorsSegment(SectionInconnue): pass
        q = mod("apps.crm.questionnaire", __package__="apps.crm", QuestionnaireLien=Lien, Lead=Lead, SectionInconnue=SectionInconnue,
                SectionHorsSegment=SectionHorsSegment, valider_questions=lambda brut, lead=None: brut, LIBELLE_SECTION={"toiture": "Toiture"},
                sections_du_lead=lambda lead: ("toiture",), questions_par_defaut=lambda lead: {"toiture": True}, manquantes=lambda lead: {},
                journal_systeme=lambda *a, **k: None)
        reel("apps/crm/questionnaire.py", ("mint_lien", "url_publique", "lead_clos"), q.__dict__)
        mod("apps.crm.activity", log_note=lambda lead, user, texte: notes.append(texte))
        g = {"__name__": "apps.crm.leads_views", "__package__": "apps.crm", "status": NS(HTTP_409_CONFLICT=409, HTTP_400_BAD_REQUEST=400),
             "Response": lambda data=None, status=200, **k: NS(data=data, status_code=status), "corps_objet": lambda r: r.data or {}}
        globaux("apps/crm/leads_views.py", "apps.crm.leads_views", g)
        vue = reel("apps/crm/leads_views.py", ("questionnaire_lien",), g, classe="LeadIntakeActionsMixin")["questionnaire_lien"]
        cas = {"oppose": dict(ne_plus_contacter=True), "perdu": dict(perdu=True), "archive": dict(is_archived=True), "temoin": {}}
        for nom, drapeaux in cas.items():
            lead = Lead(**{"id": 7, "pk": 7, "company": NS(id=1, pk=1), "company_id": 1, "prenom": "Prénom", "nom": "Nom", "email": "x@example.invalid",
                           "telephone": "+212600000000", "whatsapp": "+212600000000", "perdu": False, "is_archived": False,
                           "ne_plus_contacter": False, "segment": "residentiel", **drapeaux})
            req = NS(method="POST", user=NS(id=1, pk=1, company_id=1, company=lead.company), data={})
            try:
                r = vue(NS(get_object=lambda lead=lead: lead, request=req), req, pk=7)
                sortie[nom] = {"statut": r.status_code, "url_servie": (r.data or {}).get("url")}
            except ConflitEtat as e:
                sortie[nom] = {"statut": 409, "refus": str(e)}
    finally:
        for n in set(sys.modules) - set(sauve): sys.modules.pop(n)
        sys.modules.update(sauve); sys.dont_write_bytecode = pyc
    if sortie["temoin"]["statut"] != 200: raise RuntimeError(f"sonde cassée : le témoin contactable n'obtient pas 200 ({sortie['temoin']})")
    jsx = (RACINE / "frontend/src/features/crm/workspace/QuestionnaireDialog.jsx").read_text(encoding="utf-8")
    ecran = {"lien_wa_assemble_par_l_ecran": "buildWaUrl(waPhone, questionnaireWhatsappText(" in jsx,
             "opposition_lue_par_le_dialogue": any(m in jsx for m in ("ne_plus_contacter", "estOppose", "oppos"))}
    servis = sorted(n for n in ("oppose", "perdu", "archive") if sortie[n]["statut"] == 200 and sortie[n].get("url_servie"))
    return {"repro": "oppose" in servis, "observe": {
        "methode": "exécution de la vraie action questionnaire_lien (+ vrais mint_lien/url_publique, gardes réelles disponibles) ; écran lu",
        "route": "POST /api/django/crm/leads/<id>/questionnaire-lien/", "fiches_closes_servies": servis, "par_cas": sortie,
        "journal_ecrit": notes, "ecran_QuestionnaireDialog": ecran}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
