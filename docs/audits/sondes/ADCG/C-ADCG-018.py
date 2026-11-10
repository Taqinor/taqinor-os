"""Rejoue le sérialiseur/vue BackupRun (AST) et le KPI drill : un admin de société crée un run kind=restore_drill, la vue le passe « termine », et le KPI système le prend pour un exercice réussi."""
SONDE = {"constat": "C-ADCG-018", "sha": "ce4e5fc4f",
         "attendu": "kind écrivable, sans validate_kind ; _executer le termine via executer_sauvegarde ; KPI = 0 j au lieu de None"}
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
    ser = ast.parse((DJ / "core/serializers.py").read_text(encoding="utf-8"))
    cls = next(n for n in ser.body if isinstance(n, ast.ClassDef) and n.name == "BackupRunSerializer")
    meta = next(n for n in cls.body if isinstance(n, ast.ClassDef) and n.name == "Meta")
    champs = {t.targets[0].id: ast.literal_eval(t.value) for t in meta.body if isinstance(t, ast.Assign)
              and t.targets[0].id in ("fields", "read_only_fields")}
    kind_ecrivable = "kind" in champs["fields"] and "kind" not in champs["read_only_fields"]
    validate = any(isinstance(n, ast.FunctionDef) and n.name in ("validate_kind", "validate") for n in cls.body)
    vue = ast.get_source_segment(src := (DJ / "core/views.py").read_text(encoding="utf-8"), next(
        n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "_executer"))
    termine = "KIND_RESTORE:" in vue and "executer_sauvegarde(run)" in vue and "KIND_RESTORE_DRILL" not in vue
    echecs = [run() for _ in range(3)]
    v0, _ = kpi(echecs)
    faux = run(statut="termine", company=7, termine_le=MAINTENANT)   # créé par l'admin de la société 7
    v1, f1 = kpi(echecs + [faux])
    repro = kind_ecrivable and not validate and termine and v0 is None and v1 == 0
    return {"repro": repro, "observe": (
        f"kind écrivable={kind_ecrivable}, validate_kind={validate} ; _executer termine un restore_drill via executer_sauvegarde={termine} ; "
        f"KPI sans le faux run={v0}, avec le run de la société 7={v1} (franchi={f1}) — aucun filtre company dans le KPI")}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
