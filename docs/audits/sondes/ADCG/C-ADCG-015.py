"""Rejoue le KPI d'alerte apps/reporting/kpi_alertes.py::_compute_jours_depuis_dernier_drill_reussi + KpiAlerte.est_franchi : 13 exercices échoués et aucun réussi → valeur None → alerte « Drill de restauration périmé » muette."""
SONDE = {"constat": "C-ADCG-015", "sha": "ce4e5fc4f",
         "attendu": "13 drills echec, 0 réussi : valeur None, franchi False ; témoin : réussi il y a 40 j → franchi True"}
import ast, datetime, pathlib, sys, types
from decimal import Decimal
RACINE = pathlib.Path(__file__).resolve().parents[4]
DJ = RACINE / "backend/django_core"
MAINTENANT = datetime.datetime(2026, 11, 10, 9, 0)


class QS(list):
    def _ok(s, r, kw):
        return all((getattr(r, k[:-8]) is None) == v if k.endswith("__isnull") else getattr(r, k) == v for k, v in kw.items())
    def filter(s, **kw): return QS(r for r in s if s._ok(r, kw))
    def exclude(s, **kw): return QS(r for r in s if not s._ok(r, kw))
    def order_by(s, cle): return QS(sorted(s, key=lambda r: getattr(r, cle.lstrip("-")), reverse=cle.startswith("-")))
    def first(s): return s[0] if s else None


def fonction(chemin, nom, classe=None):
    arbre = ast.parse((DJ / chemin).read_text(encoding="utf-8"))
    corps = next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == classe).body if classe else arbre.body
    f = next(n for n in corps if isinstance(n, ast.FunctionDef) and n.name == nom)
    ns = {"Decimal": Decimal}
    exec(compile(ast.Module(body=[f], type_ignores=[]), chemin, "exec"), ns)
    return ns[nom]


def kpi(runs):
    """Valeur du KPI drill + franchissement de l'alerte par défaut (> 35 j) sur la liste ``runs``."""
    BR = types.SimpleNamespace(KIND_RESTORE_DRILL="restore_drill", STATUT_TERMINE="termine", objects=QS(runs))
    vieux = {n: sys.modules.get(n) for n in ("django", "django.utils", "core", "core.models")}
    for n in vieux: sys.modules[n] = types.ModuleType(n)
    sys.modules["django.utils"].timezone = types.SimpleNamespace(now=lambda: MAINTENANT)
    sys.modules["core.models"].BackupRun = BR
    try:
        valeur = fonction("apps/reporting/kpi_alertes.py", "_compute_jours_depuis_dernier_drill_reussi")("C")
    finally:
        for n, m in vieux.items():
            if m is None: sys.modules.pop(n, None)
            else: sys.modules[n] = m
    alerte = types.SimpleNamespace(operateur="sup", seuil=Decimal(35),
                                   Operateur=types.SimpleNamespace(SUP="sup", SUP_EGAL="sup_egal", INF="inf"))
    return valeur, fonction("apps/reporting/models.py", "est_franchi", "KpiAlerte")(alerte, valeur)


def run(**kw):
    base = dict(kind="restore_drill", statut="echec", company=None, purge_is_deleted=False, termine_le=None)
    return types.SimpleNamespace(**{**base, **kw})


def sonde(ctx=None):
    echecs = [run(created_at=MAINTENANT - datetime.timedelta(weeks=i + 5)) for i in range(13)]   # prod : 13/13 en échec (ADEP1)
    v, f = kpi(echecs)
    vt, ft = kpi([run(statut="termine", termine_le=MAINTENANT - datetime.timedelta(days=40))])
    return {"repro": v is None and f is False and ft is True, "observe": (
        f"13 échecs, 0 réussi : valeur={v}, alerte franchie={f} ; témoin réussi il y a 40 j : valeur={vt}, franchie={ft}")}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
