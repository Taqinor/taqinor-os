# flake8: noqa  (sonde HÔTE de la contre-visite de clôture AMSG du 14/11 — sans Django, sans base, sans envoi)
"""C-AMSG-VER3-100 — la fiche SŒUR d'une personne déjà opposée AVANT AMSG3 reste contactable pour toujours.
AMSG3 ne coche les sœurs qu'au moment où une empreinte NEUVE est posée (`poser_empreintes_opposition`, filtre `neuves`) ;
la migration 0154 (ACVI6) a posé les empreintes de tous les leads opposés existants : pour une paire (A opposée, B au même
numéro non opposée) déjà présente au déploiement, aucun geste ne coche plus B (nouveau STOP sur A, enregistrement de A,
enregistrement de B sans changement de contact). Exécute le VRAI `Lead.save` (méthode extraite par ast), les VRAIS modules
`leads_doublons` et `portee_selectors` (exécutés en entier), le VRAI receveur post_save `_empreinte_opposition_lead`
(`receivers.py`) et le VRAI `tracer_opposition_registre` (`cadence_reponses.py`), sur un faux ORM. Témoin : la même paire
créée APRÈS AMSG3 (sans empreinte préalable) ⇒ la sœur est cochée au STOP, ce qui prouve que la chaîne réelle est traversée."""
SONDE = {"constat": "C-AMSG-VER3-100", "sha": "a12f40f82",
         "attendu": "paire existante au déploiement (empreinte de A déjà posée par la migration 0154) : après un nouveau STOP sur A, "
                    "un enregistrement de A et un de B, peut_contacter(B) reste vrai ; témoin (paire neuve) : la sœur est cochée"}
import ast, pathlib, sys, textwrap, types
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


def noeud(rel, nom, classe=None):
    arbre = ast.parse((DJ / rel).read_text(encoding="utf-8"))
    corps = arbre.body if classe is None else next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == classe).body
    f = next(n for n in corps if isinstance(n, ast.FunctionDef) and n.name == nom); f.decorator_list = []; return f


def fonctions(rel, noms, g):  # VRAIES fonctions d'un module exécutées dans ``g`` (décorateurs retirés)
    exec(compile(ast.Module(body=[noeud(rel, n) for n in noms], type_ignores=[]), rel, "exec"), g); return g


class Q:  # django.db.models.Q (et, ou, non)
    def __init__(s, *enf, **kw): s.kw, s.op, s.enf = kw, "et", list(enf)
    def _c(s, op, *enf): q = Q(); q.op, q.enf = op, list(enf); return q
    __or__ = lambda s, o: s._c("ou", s, o); __and__ = lambda s, o: s._c("et", s, o); __invert__ = lambda s: s._c("non", s)
    def ok(s, o):
        if s.op == "ou": return any(e.ok(o) for e in s.enf)
        if s.op == "non": return not s.enf[0].ok(o)
        return all(e.ok(o) for e in s.enf) and all(_ok(o, k, v) for k, v in s.kw.items())


def _ok(o, cle, v):
    parts, op = cle.split("__"), "exact"
    if parts[-1] in ("in", "isnull", "iexact"): op = parts.pop()
    c = getattr(o, "pk" if parts[0] == "pk" else "__".join(parts), None)
    return {"in": lambda: c in v, "isnull": lambda: (c is None) == v, "iexact": lambda: c is not None and str(c).lower() == str(v).lower(),
            "exact": lambda: c == v}[op]()


class QS(list):
    def __init__(s, depot, objets=None): super().__init__(depot if objets is None else objets); s.depot = depot
    def filter(s, *q, **kw): return QS(s.depot, [o for o in s if Q(*q, **kw).ok(o)])
    def exclude(s, *q, **kw): return QS(s.depot, [o for o in s if not Q(*q, **kw).ok(o)])
    def exists(s): return bool(s)
    def first(s): return s[0] if s else None
    def values_list(s, *f, flat=False): return [getattr(o, f[0]) for o in s] if flat else [tuple(getattr(o, x) for x in f) for o in s]
    def bulk_create(s, objs, ignore_conflicts=False):
        for o in objs:
            if not any((e.company_id, e.nature, e.empreinte) == (o.company_id, o.nature, o.empreinte) for e in s.depot): s.depot.append(o)


class Empreinte:  # crm.EmpreinteOpposition (faux)
    def __init__(s, company=None, nature=None, empreinte=None): s.company, s.company_id, s.nature, s.empreinte = company, getattr(company, "pk", company), nature, empreinte


def sonde(ctx=None):
    sauve, pyc = dict(sys.modules), sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        LEADS, EMPREINTES, CHATTER = [], [], []
        Empreinte.objects = NS(filter=lambda *q, **kw: QS(EMPREINTES).filter(*q, **kw), bulk_create=lambda o, **k: QS(EMPREINTES).bulk_create(o))
        mod("django.conf", settings=NS(SECRET_KEY="cle-de-sonde")); mod("django.db.models", Q=Q)
        mod("apps.crm.activity", log_changes=lambda avant, apres, user: CHATTER.append(apres.nom))
        rec = {"__name__": "apps.crm.receivers", "__package__": "apps.crm"}

        class Base:
            def save(s, *a, **k):
                if s not in LEADS: LEADS.append(s)
                s._state.adding = False
                rec["_empreinte_opposition_lead"](sender=None, instance=s)  # post_save réel (receivers.py)
        g = {"__name__": "apps.crm.models", "__package__": "apps.crm", "Base": Base}
        exec("class Lead(Base):\n" + textwrap.indent(ast.unparse(noeud("apps/crm/models.py", "save", "Lead")), "    "), g)
        Lead = g["Lead"]
        Lead.objects = NS(filter=lambda *q, **kw: QS(LEADS).filter(*q, **kw))
        Lead.all_objects = Lead.objects
        mod("apps.crm.models", Lead=Lead, EmpreinteOpposition=Empreinte)
        ld = charge("apps.crm.leads_doublons", "apps/crm/leads_doublons.py")
        peut_contacter = charge("apps.crm.portee_selectors", "apps/crm/portee_selectors.py").peut_contacter
        fonctions("apps/crm/receivers.py", ["_empreinte_opposition_lead"], rec)
        cr = fonctions("apps/crm/cadence_reponses.py", ["tracer_opposition_registre"], {
            "__name__": "apps.crm.cadence_reponses", "__package__": "apps.crm", "BASE_LEGALE_OPPOSITION": "art. 9 loi 09-08",
            "_ecrire_registre_contact": lambda *a, **k: None, "logger": NS(warning=print)})
        ids = iter(range(1, 99))

        def fiche(societe, nom, tel):
            le = Lead(); le.__dict__.update(pk=next(ids), nom=nom, company=societe, company_id=societe.pk, telephone=tel, email=None,
                                            whatsapp=None, ne_plus_contacter=False, perdu=False, is_archived=False, ville="", _state=NS(adding=True))
            le.id = le.pk; le.save(); return le

        def stop(le):  # chemin réel du STOP : la case (CAD5) puis le registre (CAD91 → ACVI43 → AMSG3)
            ld._marquer_lead_ne_plus_contacter(le, None); cr["tracer_opposition_registre"](le, source="réponse « Ne plus me contacter »")

        # 1) Paire EXISTANTE au déploiement : A opposée avant AMSG3, empreinte posée par la migration 0154 (sans sœurs).
        s1 = NS(pk=1, id=1)
        A, B = fiche(s1, "A (opposée avant AMSG3)", "0600000000"), fiche(s1, "B (même numéro)", "+212 6 00 00 00 00")
        A.__dict__["ne_plus_contacter"] = True  # état laissé par l'ancien code (case cochée, sœur non touchée)
        EMPREINTES.extend(Empreinte(company=s1, nature=n, empreinte=e) for n, e in ld.empreintes_contact(A.email, A.telephone, A.whatsapp))
        avant = peut_contacter(B)
        stop(A)                       # la personne répond STOP une nouvelle fois
        A.ville = "Rabat"; A.save()   # un enregistrement quelconque de A (receveur post_save)
        B.nom = "B modifiée"; B.save()  # un enregistrement quelconque de B (relecture : aucun contact changé)
        apres = peut_contacter(B)
        # 2) Témoin : même paire créée APRÈS AMSG3 (aucune empreinte préalable) dans une autre société.
        s2 = NS(pk=2, id=2)
        A2, B2 = fiche(s2, "A2 (témoin)", "0600000000"), fiche(s2, "B2 (témoin)", "+212 6 00 00 00 00")
        stop(A2)
        temoin = peut_contacter(B2)
    finally:
        for n in set(sys.modules) - set(sauve): sys.modules.pop(n)
        sys.modules.update(sauve); sys.dont_write_bytecode = pyc
    if temoin or not B2.ne_plus_contacter or "B2 (témoin)" not in CHATTER:
        raise RuntimeError("sonde cassée : le témoin (paire neuve) n'a pas été coché par la vraie chaîne STOP → empreinte → sœurs")
    return {"repro": bool(avant and apres), "observe": {
        "methode": "vrai Lead.save, vrais leads_doublons/portee_selectors, vrai receveur post_save et vrai tracer_opposition_registre",
        "scenario": "paire (A opposée, B même numéro) présente au déploiement, empreinte de A déjà posée (migration 0154) ; "
                    "nouveau STOP sur A, enregistrement de A, enregistrement de B",
        "B_contactable_avant": avant, "B_contactable_apres_stop_et_enregistrements": apres,
        "B_ne_plus_contacter": B.ne_plus_contacter, "empreintes_societe_1": sum(1 for e in EMPREINTES if e.company_id == 1),
        "temoin_paire_neuve": {"B2_contactable_apres_stop": temoin, "B2_ne_plus_contacter": B2.ne_plus_contacter,
                               "ligne_de_chatter_B2": "B2 (témoin)" in CHATTER},
        "fonction_lue_a_l_envoi": "apps/crm/portee_selectors.py::peut_contacter"}}


if __name__ == "__main__":
    import json
    r = sonde()
    print(json.dumps(r, ensure_ascii=False, indent=1, default=str))
    print("repro:", r["repro"])
