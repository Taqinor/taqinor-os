# flake8: noqa  (sonde HÔTE d'audit PF8 « messages envoyés aux clients », groupe AMSG — sans Django, sans base, sans réseau)
"""C-AMSG-012 — le rappel avant échéance (beat 07:20) : la VRAIE tâche `apps/ventes/scheduled.py::pre_echeance_reminders`
est jouée sur 4 factures ÉMISES, échéance dans 2 jours : (1) contestée, (2) client en relance MANUELLE, (3) sous promesse de
paiement active, (4) témoin. ORM et e-mail bouchonnés (rien ne part). 2ᵉ emplacement : le VRAI
`apps/automation/engine.py::_motif_facture` (règle « facture en retard ») sur une facture contestée. Chaque module est chargé
ENTIER (fonctions de premier niveau) et tout autre nom est résolu PARESSEUSEMENT dans le dépôt (constantes, garde réelle
`facturation/recouvrement.py::facture_relancable`, toute fonction qu'un correctif importerait) : un correctif n'exige aucune retouche."""
SONDE = {"constat": "C-AMSG-012", "sha": "3acfee471",
         "attendu": "le rappel part aux 4 factures, dont la contestée, celle du client MANUEL et celle sous promesse ; "
                    "_motif_facture ne donne aucun motif d'arrêt pour une facture en retard contestée"}
import ast, builtins, copy, datetime as dt, importlib, logging, pathlib, sys, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
NS = types.SimpleNamespace


class _SansImport(ast.NodeTransformer):  # imports (même imbriqués) → pass : leurs noms sont résolus par l'Espace
    visit_Import = visit_ImportFrom = lambda s, n: ast.Pass()


class Espace(dict):
    """Globales d'un module RÉEL : toutes ses fonctions de premier niveau (corps réels, décorateurs et imports retirés) ;
    tout autre nom (constante, classe, nom importé — stdlib ou dépôt, suivi à travers les ré-exports) est résolu à la
    première lecture. Les bouchons priment. Un nom introuvable ne lève NameError qu'à l'exécution qui le lit."""
    def __init__(s, rel, b):
        super().__init__(b, __name__=rel[:-3].replace("/", "."))
        s.b, s.corps, s.imp, pkg = b, ast.parse((DJ / rel).read_text(encoding="utf-8")).body, {}, rel.split("/")[:-1]
        for n in ast.walk(ast.Module(body=s.corps, type_ignores=[])):
            if isinstance(n, ast.ImportFrom) and n.module:
                base = pkg[:len(pkg) - n.level + 1] if n.level else []
                s.imp.update({a.asname or a.name: (".".join(base + [n.module]), a.name) for a in n.names})
            elif isinstance(n, ast.Import):
                s.imp.update({a.asname or a.name.split(".")[0]: (a.name if a.asname else a.name.split(".")[0], None) for a in n.names})
        for n in s.corps:
            if isinstance(n, ast.FunctionDef):
                try: s._charger(n)
                except Exception: pass
        s.update(b)

    def _charger(s, n):
        n = copy.deepcopy(n)
        if hasattr(n, "decorator_list"): n.decorator_list = []
        exec(compile(ast.fix_missing_locations(ast.Module(body=[_SansImport().visit(n)], type_ignores=[])), s["__name__"], "exec"), s)

    def __missing__(s, nom):
        if nom.startswith("__") or hasattr(builtins, nom): raise KeyError(nom)
        try:
            n = next((n for n in s.corps if nom in (getattr(n, "name", None), *(getattr(t, "id", None) for t in getattr(n, "targets", ())))), None)
            if n is not None: s._charger(n); return dict.__getitem__(s, nom)
            mod, orig = s.imp[nom]
            if mod.split(".")[0] in sys.stdlib_module_names:
                v = importlib.import_module(mod) if orig is None else getattr(importlib.import_module(mod), orig)
            else:
                p = mod.replace(".", "/"); v = espace(next(r for r in (p + ".py", p + "/__init__.py") if (DJ / r).is_file()), s.b)[orig]
        except Exception: raise KeyError(nom) from None
        s[nom] = v; return v


def espace(rel, b):
    c = b.setdefault("__espaces__", {})
    return c[rel] if rel in c else c.setdefault(rel, Espace(rel, b))


_OPS = {"exact": lambda c, v: c == v, "isnull": lambda c, v: (c is None) == v, "in": lambda c, v: c in v,
        "lte": lambda c, v: c is not None and c <= v, "gte": lambda c, v: c is not None and c >= v,
        "lt": lambda c, v: c is not None and c < v, "gt": lambda c, v: c is not None and c > v,
        "endswith": lambda c, v: c is not None and str(c).endswith(v)}


def _cle(o, k, v):  # lookups Django usuels (champ__sous_champ__op)
    parts = k.split("__"); op = parts.pop() if parts[-1] in _OPS else "exact"
    for p in parts: o = getattr(o, p, None)
    return _OPS[op](o, v)


class QS(list):  # faux QuerySet
    def filter(s, *a, **kw): return QS(o for o in s if all(_cle(o, k, v) for k, v in kw.items()))
    def exclude(s, *a, **kw): return QS(o for o in s if not all(_cle(o, k, v) for k, v in kw.items()))
    select_related = prefetch_related = order_by = lambda s, *a: s
    def exists(s): return bool(s)
    def first(s): return s[0] if s else None
    def count(s): return len(s)
    def values_list(s, *ch, flat=False): return QS(getattr(o, ch[0]) if flat else tuple(getattr(o, c) for c in ch) for o in s)


class Obj(NS):
    def save(s, **k): pass
    def get_statut_display(s): return s.statut


def sonde(ctx=None):
    today, co = dt.date(2026, 11, 11), NS(id=1, pk=1)

    def fac(pk, motif, **kw):
        base = dict(pk=pk, id=pk, company=co, company_id=1, client_id=pk, client=Obj(id=pk, email="x@example.invalid"),
                    statut="emise", exclu_relances=False, date_echeance=today + dt.timedelta(days=2), montant_exigible=1200,
                    montant_du=1200, reference=f"FAC-{pk}", contestee_le=None, exclu_relances_jusquau=None, motif=motif,
                    promesses=QS(), relances=QS())
        base.update(kw); return Obj(**base)
    factures = QS([fac(1, "contestée", contestee_le=today - dt.timedelta(days=3)), fac(2, "client en relance MANUELLE"),
                   fac(3, "promesse de paiement active", exclu_relances_jusquau=today + dt.timedelta(days=20)), fac(4, "témoin")])
    Mode = NS(MANUEL="manuel", AUTO="auto")
    parametrages = QS([Obj(company_id=1, client_id=2, client=factures[1].client, company=co, mode=Mode.MANUEL)])
    promesses = QS([Obj(facture=factures[2], facture_id=3, statut="en_cours", date_promise=today + dt.timedelta(days=20),
                        montant_promis=1200, date_creation=None)])
    logs, envois, Statut = QS(), [], NS(ENVOYE="envoye", ECHEC="echec")

    def send_pre_echeance_email(f, user=None):  # l'envoi (bouchon) : on note qui reçoit « Rappel avant échéance »
        envois.append(f.motif); log = Obj(statut=Statut.ENVOYE, reference=f.reference, facture=f); logs.append(log); return log
    base = {"logger": logging.getLogger("sonde"), "casablanca_today": lambda: today, "RELATIONS_MONTANT_DU": (),
            "active_company_ids": lambda: [1], "send_pre_echeance_email": send_pre_echeance_email,
            "EmailLog": NS(objects=NS(filter=lambda **kw: logs.filter(**kw)), Statut=Statut),
            "Facture": NS(objects=factures, Statut=NS(EMISE="emise", EN_RETARD="en_retard", ANNULEE="annulee", PAYEE="payee")),
            "CompanyProfile": NS(get=lambda company: NS(rappel_pre_echeance_jours=5)),
            "ParametrageRelanceClient": NS(objects=parametrages, Mode=Mode),
            "PromessePaiement": NS(objects=promesses, Statut=NS(EN_COURS="en_cours", TENUE="tenue", ROMPUE="rompue")),
            "Paiement": NS(STATUTS_NON_COMPTES=("rejete",)),
            # AMSG29 — le beat lit le backend e-mail : la sonde joue l'e-mail ALLUMÉ (constat latent).
            "settings": NS(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")}
    base["facture_relancable"] = espace("apps/facturation/recouvrement.py", base)["facture_relancable"]  # la garde RÉELLE
    compte = espace("apps/ventes/scheduled.py", base)["pre_echeance_reminders"]()
    a_tort = [m for m in envois if m != "témoin"]
    contestee_retard = Obj(statut="en_retard", montant_exigible=1200, montant_du=1200, contestee_le=today, exclu_relances_jusquau=None)
    motif_auto = espace("apps/automation/engine.py", base)["_motif_facture"](contestee_retard)
    return {"repro": bool(a_tort) or motif_auto is None, "observe": {
        "methode": "exécution de la vraie tâche pre_echeance_reminders + vrai _motif_facture (modules réels, noms résolus paresseusement, ORM bouchonné)",
        "emplacements": ["apps/ventes/scheduled.py::pre_echeance_reminders", "apps/automation/engine.py::_motif_facture"],
        "scenario": "4 factures émises, échéance J+2, rappel J-5 ; aucune n'a encore reçu le rappel",
        "rappels_comptes_envoyes": compte, "destinataires_du_rappel": envois, "recus_a_tort": a_tort, "temoin_recu": "témoin" in envois,
        "automatisation_facture_en_retard_contestee": {"motif_d_arret": motif_auto, "verdict": "relancée" if motif_auto is None else "arrêtée"}}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
