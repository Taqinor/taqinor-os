# flake8: noqa  (sonde HÔTE d'audit PF8 « messages envoyés aux clients », groupe AMSG — sans Django, sans base, sans envoi)
"""C-AMSG-003 — un STOP sur la fiche A ne protège pas la fiche B DÉJÀ existante au même numéro.
Exécute le VRAI `Lead.save` (`apps/crm/models.py`, méthode extraite par ast), les VRAIS modules `leads_doublons` et
`portee_selectors` (exécutés en entier) et le VRAI chemin du STOP de `cadence_reponses.py`
(`_marquer_lead_ne_plus_contacter` puis `tracer_opposition_registre` → `poser_empreintes_opposition`), sur un faux ORM
(Q, filter/exclude/update/bulk_create) ; registre de consentement et chatter bouchonnés. Puis `peut_contacter(B)`."""
SONDE = {"constat": "C-AMSG-003", "sha": "3acfee471",
         "attendu": "après le STOP sur A, peut_contacter(B) reste vrai pour la fiche B existante au même numéro, et un numéro opposé "
                    "recollé sur une fiche existante la laisse contactable ; seule une fiche CRÉÉE après naît opposée"}
import ast, copy, pathlib, sys, textwrap, types
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
    def values_list(s, *f, flat=False): return [getattr(o, f[0]) for o in s] if flat else [tuple(getattr(o, x) for x in f) for o in s]
    def update(s, **kw): [o.__dict__.update(kw) for o in s]; return len(s)
    def delete(s): [s.depot.remove(o) for o in list(s)]
    def bulk_create(s, objs, ignore_conflicts=False):
        for o in objs:
            if not any((e.company_id, e.nature, e.empreinte) == (o.company_id, o.nature, o.empreinte) for e in s.depot): s.depot.append(o)
    all = lambda s: s


class Empreinte:  # crm.EmpreinteOpposition (faux)
    def __init__(s, company=None, nature=None, empreinte=None): s.company, s.company_id, s.nature, s.empreinte = company, getattr(company, "pk", company), nature, empreinte


def sonde(ctx=None):
    sauve, pyc = dict(sys.modules), sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        LEADS, EMPREINTES = [], []
        Empreinte.objects = NS(filter=lambda *q, **kw: QS(EMPREINTES).filter(*q, **kw), bulk_create=lambda o, **k: QS(EMPREINTES).bulk_create(o))
        mod("django.conf", settings=NS(SECRET_KEY="cle-de-sonde")); mod("django.db.models", Q=Q)
        class Base:
            def save(s, *a, **k):
                if s not in LEADS: LEADS.append(s)
                s._state.adding = False
        g = {"__name__": "apps.crm.models", "__package__": "apps.crm", "Base": Base}
        exec("class Lead(Base):\n" + textwrap.indent(ast.unparse(noeud("apps/crm/models.py", "save", "Lead")), "    "), g)
        Lead = g["Lead"]; Lead.objects = NS(filter=lambda *q, **kw: QS(LEADS).filter(*q, **kw), all=lambda: QS(LEADS))
        mod("apps.crm.models", Lead=Lead, EmpreinteOpposition=Empreinte)
        charge("apps.crm.leads_doublons", "apps/crm/leads_doublons.py")
        peut_contacter = charge("apps.crm.portee_selectors", "apps/crm/portee_selectors.py").peut_contacter
        cr = {"__name__": "apps.crm.cadence_reponses", "__package__": "apps.crm", "copy": copy, "BASE_LEGALE_OPPOSITION": "art. 9 loi 09-08",
              "activity": NS(log_changes=lambda *a, **k: None), "_ecrire_registre_contact": lambda *a, **k: None, "logger": NS(warning=print)}
        for f in ("_marquer_lead_ne_plus_contacter", "tracer_opposition_registre"):
            exec(compile(ast.Module(body=[noeud("apps/crm/cadence_reponses.py", f)], type_ignores=[]), "cadence_reponses.py", "exec"), cr)
        societe, ids = NS(pk=1, id=1), iter(range(1, 99))

        def fiche(nom, tel):
            le = Lead(); le.__dict__.update(pk=next(ids), nom=nom, company=societe, company_id=1, telephone=tel, email=None, whatsapp=None,
                                            ne_plus_contacter=False, perdu=False, is_archived=False, _state=NS(adding=True))
            le.id = le.pk; le.save(); return le
        A, B = fiche("A (site)", "0600000000"), fiche("B (Meta)", "+212 6 00 00 00 00")
        D = fiche("D (autre numéro)", "+447700900123")  # numéro de fiction (plage Ofcom réservée)
        avant = {"A": peut_contacter(A), "B": peut_contacter(B)}
        cr["_marquer_lead_ne_plus_contacter"](A, NS(id=1, pk=1))  # STOP : la case puis le registre (CAD5, CAD91)
        cr["tracer_opposition_registre"](A, source="réponse « Ne plus me contacter »")
        B.nom = "B (Meta) modifiée"; B.save()  # une modification quelconque de B après le STOP
        C = fiche("C (créée après le STOP)", "00212600000000")
        D.telephone = "0600000000"; D.save()  # numéro opposé recollé sur une fiche existante
        apres = {"A": peut_contacter(A), "B_existante": peut_contacter(B), "C_creee_apres": peut_contacter(C), "D_numero_recolle": peut_contacter(D)}
    finally:
        for n in set(sys.modules) - set(sauve): sys.modules.pop(n)
        sys.modules.update(sauve); sys.dont_write_bytecode = pyc
    if apres["A"] or not EMPREINTES or not C.ne_plus_contacter:
        raise RuntimeError("sonde cassée : le STOP de A, son empreinte ou l'héritage de la fiche créée après n'ont pas été rejoués")
    return {"repro": apres["B_existante"] or apres["D_numero_recolle"], "observe": {
        "methode": "exécution du vrai Lead.save, des vrais leads_doublons/portee_selectors et du vrai chemin du STOP (cadence_reponses)",
        "scenario": "A et B au même numéro ; STOP sur A ; B modifiée ; C créée après ; D recolle le numéro opposé",
        "contactable_avant_stop": avant, "contactable_apres_stop": apres, "empreintes_posees": len(EMPREINTES),
        "ne_plus_contacter": {"A": A.ne_plus_contacter, "B": B.ne_plus_contacter, "C": C.ne_plus_contacter, "D": D.ne_plus_contacter},
        "fonction_lue_a_l_envoi": "apps/crm/portee_selectors.py::peut_contacter"}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
