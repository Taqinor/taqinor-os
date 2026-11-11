# flake8: noqa  (sonde HÔTE d'audit PF8 « messages envoyés aux clients », groupe AMSG — sans Django, sans base, sans envoi)
"""C-AMSG-002 — « Relances du jour » prépare un WhatsApp pré-rempli pour le lead opposé, perdu ou archivé d'un devis envoyé.
Exécute le VRAI module `apps/ventes/selectors_cadence.py` en entier (dont `devis_action_requise`, `_ligne_action_requise`,
`_brouillon_relance_engagement`, `declencheurs_actifs`, et le vrai contrat `contract_samples/devis_action_requise.json`)
sur un faux ORM en mémoire : 4 devis ENVOYÉS dont le lien n'a pas été ouvert depuis 24 h (déclencheur `not_opened_24h`
posé par le beat d'engagement), leads opposé / perdu / archivé / témoin. Le VRAI `crm.portee_selectors` est exposé par
le faux `apps.crm.selectors` (ré-export réel)."""
SONDE = {"constat": "C-AMSG-002", "sha": "3acfee471",
         "attendu": "wa_drafts porte un brouillon WhatsApp (et la ligne le numéro) pour les devis des leads opposé, perdu et archivé, "
                    "comme pour le témoin contactable"}
import datetime as dt, pathlib, sys, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ, NS = RACINE / "backend/django_core", types.SimpleNamespace
NOW = dt.datetime(2026, 11, 11, 10, 0, 0)


def mod(nom, **attrs):  # module-bouchon enregistré (parents créés, attribut posé sur le parent)
    m = sys.modules.get(nom) or types.ModuleType(nom); m.__path__ = []; m.__dict__.update(attrs); sys.modules[nom] = m
    if "." in nom: setattr(mod(nom.rsplit(".", 1)[0]), nom.rsplit(".", 1)[1], m)
    return m


def charge(nom, rel):  # VRAI module du dépôt exécuté en entier sous ``nom`` (rien n'est écrit sur disque)
    m = mod(nom, __file__=str(DJ / rel), __package__=nom.rsplit(".", 1)[0])
    exec(compile((DJ / rel).read_text(encoding="utf-8"), str(DJ / rel), "exec"), m.__dict__); return m


def _val(o, chemin):
    for p in chemin:
        o = getattr(o, p, None)
        if o is None: return None
    return o


def _ok(o, cle, v):  # lookups Django usuels : a__b__c, __in, __isnull, __gt…
    parts, op = cle.split("__"), "exact"
    if parts[-1] in ("in", "isnull", "gt", "gte", "lt", "lte", "iexact"): op = parts.pop()
    c = _val(o, ["id" if p == "pk" else p for p in parts])
    if op == "isnull": return (c is None) == v
    if op == "in": return c in v
    if op == "iexact": return c is not None and str(c).lower() == str(v).lower()
    if op == "exact": return c == v
    return c is not None and {"gt": c > v, "gte": c >= v, "lt": c < v, "lte": c <= v}[op]


class QS(list):
    def filter(s, *q, **kw): return QS(o for o in s if all(_ok(o, k, v) for k, v in kw.items()))
    def exclude(s, *q, **kw): return QS(o for o in s if not all(_ok(o, k, v) for k, v in kw.items()))
    def order_by(s, *a): return QS(sorted(s, key=lambda o: o.id))
    def values_list(s, *f, flat=False): return [getattr(o, f[0]) for o in s] if flat else [tuple(getattr(o, x) for x in f) for o in s]
    select_related = prefetch_related = distinct = lambda s, *a: s
    def all(s): return s
    def exists(s): return bool(s)


class Lead:
    def __init__(s, **kw): s.__dict__.update(kw)


def sonde(ctx=None):
    sauve, pyc = dict(sys.modules), sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        societe, devis = NS(id=1, pk=1), QS()
        cas = {"oppose": dict(ne_plus_contacter=True), "perdu": dict(perdu=True), "archive": dict(is_archived=True), "temoin": {}}
        for i, (nom, drapeaux) in enumerate(cas.items()):
            lead = Lead(**{"id": 70 + i, "pk": 70 + i, "company": societe, "company_id": 1, "whatsapp": "+212600000000", "telephone": "+212600000000",
                           "email": "x@example.invalid", "ne_plus_contacter": False, "perdu": False, "is_archived": False, "owner": None, **drapeaux})
            lien = NS(engagement_triggers_fired={"not_opened_24h": (NOW - dt.timedelta(days=1)).isoformat()}, last_viewed_at=None,
                      created_at=NOW - dt.timedelta(days=3))
            devis.append(NS(id=42 + i, pk=42 + i, company=societe, company_id=1, statut="envoye", is_active=True, date_validite=None,
                            date_envoi=NOW - dt.timedelta(days=3), reference=f"DEV-2611-00{42 + i}", lead=lead, lead_id=lead.id,
                            client=NS(prenom="Prénom", nom=nom.capitalize(), telephone="+212600000000"), share_links=QS([lien]),
                            motif_refus="", total_ttc="74800.00", created_by=None, _cas=nom))
        mod("django.utils.timezone", now=lambda: NOW, localdate=lambda: NOW.date())
        mod("core.scoping", scope_queryset=lambda qs, user, champs: qs)
        mod("apps.ventes.models", Devis=NS(objects=devis, Statut=NS(ENVOYE="envoye", REFUSE="refuse", ACCEPTE="accepte")), ShareLink=NS())
        mod("apps.ventes.selectors", devis_en_jeu=lambda qs: qs.filter(is_active=True), devis_avec_totaux=lambda qs: qs)
        mod("apps.ventes.selectors_facturation", devis_a_facturer=lambda *a, **k: [])
        mod("apps.crm.models", Lead=Lead)
        ps = charge("apps.crm.portee_selectors", "apps/crm/portee_selectors.py")
        mod("apps.crm.selectors", prochaine_touche_par_lead=lambda company, ids: {},
            **{k: v for k, v in vars(ps).items() if not k.startswith("__")})
        sc = charge("apps.ventes.selectors_cadence", "apps/ventes/selectors_cadence.py")
        res = sc.devis_action_requise(societe, user=None, today=NOW.date())
    finally:
        for n in set(sys.modules) - set(sauve): sys.modules.pop(n)
        sys.modules.update(sauve); sys.dont_write_bytecode = pyc
    par_cas = {d._cas: {"panier": next((k for k, b in res["buckets"].items() if d.id in b["ids"]), None),
                        "brouillon_whatsapp": res["wa_drafts"].get(d.id),
                        "numero_publie": (res["devis"].get(d.id) or {}).get("client_whatsapp")} for d in devis}
    if not par_cas["temoin"]["brouillon_whatsapp"]:
        raise RuntimeError(f"sonde cassée : le témoin contactable n'a pas de brouillon ({par_cas['temoin']})")
    servis = sorted(c for c in ("oppose", "perdu", "archive") if par_cas[c]["brouillon_whatsapp"])
    return {"repro": bool(servis), "observe": {
        "methode": "exécution du vrai module selectors_cadence (devis_action_requise) sur faux ORM",
        "route": "GET /api/django/ventes/devis/action-requise/ (écran « Relances du jour », DevisActionBoardPage)",
        "leads_clos_avec_brouillon": servis, "par_cas": par_cas}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
