# flake8: noqa  (sonde HÔTE d'audit PF8 « messages envoyés aux clients », groupe AMSG — sans Django, sans base, sans envoi)
"""C-AMSG-004 — « Anonymiser » sur la fiche client efface le client mais laisse son lead contactable.
Exécute la VRAIE action `apps/crm/clients_views.py::ClientViewSet.anonymize` (corps extrait par ast, décorateurs retirés)
→ VRAI module `apps/crm/dsr_provider.py` (exécuté en entier : `anonymiser_client`, `anonymiser_lead`…), avec les VRAIS
`leads_doublons` et `portee_selectors` ; faux ORM ; seuls les caviardages annexes du lead (chatter, traces, copies brutes),
le Tiers miroir, l'audit et le sérialiseur sont bouchonnés. Client à 1 lead lié (`Lead.client`, related_name `leads`)."""
SONDE = {"constat": "C-AMSG-004", "sha": "3acfee471",
         "attendu": "après POST clients/<id>/anonymize/ le client est anonymisé, mais son lead garde nom, téléphone, WhatsApp et "
                    "e-mail, sans ne_plus_contacter ni empreinte : peut_contacter(lead) reste vrai"}
import ast, pathlib, sys, types
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


def globaux(rel, nom_module, g):  # noms importés au niveau module du vrai fichier, quand leur module est chargé ici
    pkg = nom_module.rsplit(".", 1)[0].split(".")
    for n in ast.parse((DJ / rel).read_text(encoding="utf-8")).body:
        if isinstance(n, ast.ImportFrom):
            base = ".".join(pkg[:len(pkg) - n.level + 1] + ([n.module] if n.module else [])) if n.level else n.module
            for a in n.names:
                if base in sys.modules and hasattr(sys.modules[base], a.name): g.setdefault(a.asname or a.name, getattr(sys.modules[base], a.name))


class Q:  # django.db.models.Q (et, ou, non)
    def __init__(s, *enf, **kw): s.kw, s.op, s.enf = kw, "et", list(enf)
    def _c(s, op, *enf): q = Q(); q.op, q.enf = op, list(enf); return q
    __or__ = lambda s, o: s._c("ou", s, o); __and__ = lambda s, o: s._c("et", s, o); __invert__ = lambda s: s._c("non", s)
    def ok(s, o):
        if s.op == "ou": return any(e.ok(o) for e in s.enf)
        if s.op == "non": return not s.enf[0].ok(o)
        return all(e.ok(o) for e in s.enf) and all((getattr(o, k[:-4], None) in v) if k.endswith("__in") else getattr(o, k, None) == v for k, v in s.kw.items())


class QS(list):
    def filter(s, *q, **kw): return QS(o for o in s if Q(*q, **kw).ok(o))
    def exclude(s, *q, **kw): return QS(o for o in s if not Q(*q, **kw).ok(o))
    def update(s, **kw): [o.__dict__.update(kw) for o in s]; return len(s)
    def exists(s): return bool(s)
    all = select_related = prefetch_related = distinct = lambda s, *a: s
    def bulk_create(s, objs, ignore_conflicts=False): s.extend(objs)


class Fiche:  # crm.Lead / crm.Client (faux) : save() enregistre seulement
    def __init__(s, **kw): s.__dict__.update(kw)
    def save(s, *a, **k): pass


class Lead(Fiche): pass


def sonde(ctx=None):
    sauve, pyc = dict(sys.modules), sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        LEADS, EMPREINTES, caviardages = QS(), QS(), []
        mod("django.conf", settings=NS(SECRET_KEY="cle-de-sonde")); mod("django.db.models", Q=Q)
        mod("django.utils", timezone=NS(now=lambda: "2026-11-11T10:00")); mod("django.utils.timezone", now=lambda: "2026-11-11T10:00")
        mod("django.db", transaction=NS(on_commit=lambda f: f())); mod("core.events", lead_erased=NS(send=lambda **k: None))
        Lead.objects = NS(filter=lambda *q, **kw: LEADS.filter(*q, **kw), all=lambda: LEADS)
        Empreinte = type("EmpreinteOpposition", (Fiche,), {"objects": NS(bulk_create=lambda o, **k: EMPREINTES.bulk_create(o),
                                                                          filter=lambda *q, **kw: EMPREINTES.filter(*q, **kw))})
        mod("apps.crm.models", Lead=Lead, Client=NS(objects=NS(filter=lambda *q, **kw: QS())), EmpreinteOpposition=Empreinte)
        charge("apps.crm.leads_doublons", "apps/crm/leads_doublons.py")
        peut_contacter = charge("apps.crm.portee_selectors", "apps/crm/portee_selectors.py").peut_contacter
        mod("apps.crm.cadence_plan", arreter_cadence=lambda le, **k: caviardages.append(f"cadence arrêtée lead {le.pk}"))
        mod("apps.tiers.services", CHAMPS_PERSONNE=(), anonymiser_tiers=lambda *a, **k: None)
        mod("apps.audit.recorder", record=lambda *a, **k: None); mod("apps.audit.models", AuditLog=NS(Action=NS(UPDATE="update")))
        dsr = charge("apps.crm.dsr_provider", "apps/crm/dsr_provider.py")
        for f in ("_caviarder_historique", "_anonymiser_traces_visiteur", "_anonymiser_copies_brutes"):
            setattr(dsr, f, lambda company, le, *a, _f=f, **k: caviardages.append(f"{_f} lead {le.pk}"))
        societe = NS(pk=1, id=1)
        client = Fiche(pk=5, id=5, company=societe, company_id=1, nom="Client", prenom="Prénom", email="x@example.invalid",
                       telephone="+212600000000", adresse="Rue", cin="X", ice=None, if_fiscal=None, rc=None, custom_data=None,
                       is_anonymized=False, anonymized_at=None, tiers_id=None, site_profile=None)
        lead = Lead(pk=9, id=9, company=societe, company_id=1, client=client, client_id=5, nom="Nom du lead", prenom="Prénom",
                    email="x@example.invalid", telephone="+212600000000", whatsapp="+212600000000", ne_plus_contacter=False,
                    perdu=False, is_archived=False, phone_normalise="600000000")
        LEADS.append(lead); client.leads = NS(all=lambda: LEADS.filter(client=client), filter=lambda *q, **kw: LEADS.filter(client=client).filter(*q, **kw))
        g = {"__name__": "apps.crm.clients_views", "__package__": "apps.crm", "status": NS(HTTP_409_CONFLICT=409),
             "Response": lambda data=None, status=200, **k: NS(data=data, status_code=status),
             "ClientSerializer": lambda obj, **k: NS(data={"id": obj.id, "nom": obj.nom})}
        globaux("apps/crm/clients_views.py", "apps.crm.clients_views", g)
        arbre = ast.parse((DJ / "apps/crm/clients_views.py").read_text(encoding="utf-8"))
        f = next(n for c in arbre.body if isinstance(c, ast.ClassDef) and c.name == "ClientViewSet"
                 for n in c.body if isinstance(n, ast.FunctionDef) and n.name == "anonymize")
        f.decorator_list = []; exec(compile(ast.Module(body=[f], type_ignores=[]), "clients_views.py", "exec"), g)
        req = NS(method="POST", user=NS(id=1, pk=1, company=societe, company_id=1), data={})
        r = g["anonymize"](NS(get_object=lambda: client, request=req), req, pk=5)
        etat = {"nom": lead.nom, "telephone": lead.telephone, "whatsapp": lead.whatsapp, "email": lead.email,
                "ne_plus_contacter": lead.ne_plus_contacter, "peut_contacter": peut_contacter(lead)}
    finally:
        for n in set(sys.modules) - set(sauve): sys.modules.pop(n)
        sys.modules.update(sauve); sys.dont_write_bytecode = pyc
    if r.status_code != 200 or not client.is_anonymized:
        raise RuntimeError(f"sonde cassée : le client n'a pas été anonymisé (statut {r.status_code})")
    joignable = etat["peut_contacter"] and any(etat[k] for k in ("telephone", "whatsapp", "email"))
    return {"repro": joignable, "observe": {
        "methode": "exécution de la vraie action anonymize → vrais anonymiser_client/anonymiser_lead (dsr_provider), faux ORM",
        "route": "POST /api/django/crm/clients/<id>/anonymize/ (bouton admin ClientRgpdActions.jsx)",
        "client_apres": {"statut": r.status_code, "nom": client.nom, "telephone": client.telephone, "is_anonymized": client.is_anonymized},
        "lead_lie_apres": etat, "empreintes_opposition_posees": len(EMPREINTES), "scrubs_du_lead": caviardages,
        "lead_reste_joignable": joignable}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
