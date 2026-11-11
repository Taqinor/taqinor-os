# flake8: noqa  (sonde HÔTE d'audit PF8 « messages envoyés aux clients », groupe AMSG — sans Django, sans base, sans envoi)
"""C-AMSG-005 — une demande d'effacement par e-mail ne trouve pas la fiche sœur qui ne porte que le téléphone.
Exécute le VRAI module `apps/crm/dsr_provider.py` en entier et appelle sa VRAIE entrée `erase_crm` (← `core/dsr.py::effacer`)
→ VRAI `_matcher`, avec le VRAI module `leads_doublons` (normalisation) ; seuls les scrubs `anonymiser_lead` /
`anonymiser_client` sont remplacés par des enregistreurs (on observe QUI serait effacé), sur un faux ORM (Q, filter/exclude)."""
SONDE = {"constat": "C-AMSG-005", "sha": "3acfee471",
         "attendu": "erase_crm('x@example.invalid') n'efface que la fiche qui porte l'e-mail ; la fiche sœur au même téléphone "
                    "(sans e-mail) garde son identité et reste contactable"}
import pathlib, sys, types
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
    c = getattr(o, "__".join(parts), None)
    return {"in": lambda: c in v, "isnull": lambda: (c is None) == v, "iexact": lambda: c is not None and str(c).lower() == str(v).lower(),
            "exact": lambda: c == v}[op]()


class QS(list):
    def filter(s, *q, **kw): return QS(o for o in s if Q(*q, **kw).ok(o))
    def exclude(s, *q, **kw): return QS(o for o in s if not Q(*q, **kw).ok(o))
    def exists(s): return bool(s)
    def values_list(s, *f, flat=False): return [getattr(o, f[0]) for o in s] if flat else [tuple(getattr(o, x) for x in f) for o in s]
    distinct = select_related = prefetch_related = lambda s, *a: s
    all = lambda s: s


class Lead:
    def __init__(s, **kw): s.__dict__.update(kw)


def sonde(ctx=None):
    sauve, pyc = dict(sys.modules), sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        mod("django.conf", settings=NS(SECRET_KEY="cle-de-sonde")); mod("django.db.models", Q=Q)
        mod("django.utils", timezone=NS(now=lambda: "2026-11-11T10:00")); mod("django.utils.timezone", now=lambda: "2026-11-11T10:00")
        LEADS, CLIENTS = QS(), QS()
        mod("apps.crm.models", Lead=NS(objects=NS(filter=lambda *q, **kw: LEADS.filter(*q, **kw), all=lambda: LEADS)),
            Client=NS(objects=NS(filter=lambda *q, **kw: CLIENTS.filter(*q, **kw), all=lambda: CLIENTS)), EmpreinteOpposition=NS())
        ld = charge("apps.crm.leads_doublons", "apps/crm/leads_doublons.py")
        societe = NS(pk=1, id=1)
        for i, (nom, email, tel) in enumerate((("Fiche site (e-mail + téléphone)", "x@example.invalid", "0600000000"),
                                                ("Fiche sœur Meta (téléphone seul)", None, "+212600000000"),
                                                ("Témoin : autre personne", "y@example.invalid", "+447700900123")), start=1):  # numéro de fiction (plage Ofcom réservée)
            LEADS.append(Lead(pk=i, id=i, nom=nom, company=societe, company_id=1, email=email, telephone=tel, whatsapp=None,
                              email_normalise=ld.normalize_email(email), phone_normalise=ld.normalize_phone(tel)[:20], whatsapp_normalise="",
                              ne_plus_contacter=False, client_id=None))
        dsr = charge("apps.crm.dsr_provider", "apps/crm/dsr_provider.py")
        effaces = []
        dsr.anonymiser_lead = lambda company, le, **k: effaces.append(le.nom) or 1
        dsr.anonymiser_client = lambda company, cl, **k: effaces.append(f"client {cl.pk}") or 1
        par_email = (dsr.erase_crm(societe, "x@example.invalid"), list(effaces)); effaces.clear()
        par_tel = (dsr.erase_crm(societe, "+212600000000"), list(effaces))
    finally:
        for n in set(sys.modules) - set(sauve): sys.modules.pop(n)
        sys.modules.update(sauve); sys.dont_write_bytecode = pyc
    soeur, site = LEADS[1].nom, LEADS[0].nom
    if site not in par_email[1] or sorted(par_tel[1]) != sorted([site, soeur]):
        raise RuntimeError(f"sonde cassée : la recherche de référence n'a pas été rejouée ({par_email}, {par_tel})")
    return {"repro": soeur not in par_email[1], "observe": {
        "methode": "exécution du vrai dsr_provider.erase_crm → _matcher (vrais leads_doublons), scrubs remplacés par des enregistreurs",
        "chemin": "Paramètres › Confidentialité → core/dsr.py::effacer → crm erase_crm",
        "demande_par_email": {"identifiant": "x@example.invalid", "fiches_effacees": par_email[1]},
        "demande_par_telephone_temoin": {"identifiant": "+212600000000", "fiches_effacees": par_tel[1]},
        "fiche_soeur_oubliee_par_l_email": soeur not in par_email[1]}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
