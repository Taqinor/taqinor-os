"""Lit par ast les heures de passage de la tâche reporting.email_saved_reports dans celery.py, puis exécute les VRAIES _rapport_est_du/_heure_ok/_due_schedules de scheduled_reports.py à chacun de ces passages pour des rapports quotidiens réglés à 7, 8 ou 9 h."""
SONDE = {"constat": "C-ACEL-001", "sha": "3acfee471",
         "attendu": "un rapport quotidien réglé à une heure où le planning ne passe pas (7, 8, 9 h) n'est dû à AUCUN passage : il ne part jamais"}
import ast, datetime, pathlib, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
TACHE = "reporting.email_saved_reports"


def heures_de(valeur):  # heures couvertes par le champ ``hour`` d'un crontab (entier, liste, "*", "*/n", "a,b")
    if valeur is None: return set(range(24))
    try: v = ast.literal_eval(valeur)
    except ValueError: return set()
    if isinstance(v, int): return {v}
    if isinstance(v, (list, tuple, set)): return {int(x) for x in v}
    if isinstance(v, str):
        if v.strip() == "*": return set(range(24))
        if v.startswith("*/"): return set(range(0, 24, int(v[2:])))
        return {int(x) for x in v.split(",") if x.strip().isdigit()}
    return set()


def passages_beat():  # {nom d'entrée: heures} de toutes les entrées du beat_schedule qui lancent la tâche (lues dans le vrai celery.py)
    sortie = {}
    for d in ast.walk(ast.parse((DJ / "erp_agentique/celery.py").read_text(encoding="utf-8"))):
        if not isinstance(d, ast.Dict): continue
        for cle, val in zip(d.keys, d.values):
            if not (isinstance(val, ast.Dict) and isinstance(cle, ast.Constant)): continue
            champs = {k.value: v for k, v in zip(val.keys, val.values) if isinstance(k, ast.Constant)}
            tache = champs.get("task")
            if isinstance(tache, ast.Constant) and tache.value == TACHE and isinstance(champs.get("schedule"), ast.Call):
                kw = {k.arg: k.value for k in champs["schedule"].keywords}
                sortie[cle.value] = sorted(heures_de(kw.get("hour")))
    return sortie


def sonde(ctx=None):
    src = (DJ / "apps/reporting/scheduled_reports.py").read_text(encoding="utf-8")
    arbre = ast.parse(src)
    ns = {}
    for n in arbre.body:
        if isinstance(n, ast.FunctionDef) and n.name in ("_due_schedules", "_heure_ok", "_deja_envoye_ce_mois", "_rapport_est_du"):
            n.decorator_list = []
            exec(compile(ast.Module([n], []), "scheduled_reports.py", "exec"), ns)  # corps réels
    entrees = passages_beat()
    heures = sorted({h for hs in entrees.values() for h in hs})
    tz = datetime.timezone(datetime.timedelta(hours=1))
    lundi = datetime.date(2026, 11, 9)  # un lundi : daily ET weekly sont des cadences dues
    dus = {}
    for reglee in (7, 8, 9):
        r = types.SimpleNamespace(schedule="daily", heure_envoi=reglee, jour_du_mois=1, last_sent_at=None)
        dus[reglee] = [h for h in heures
                       if "daily" in ns["_due_schedules"](datetime.datetime.combine(lundi, datetime.time(h), tz))
                       and ns["_rapport_est_du"](r, datetime.datetime.combine(lundi, datetime.time(h), tz))]
    jamais = [h for h, p in dus.items() if not p]
    # la boucle fait ``continue`` sur « pas dû » AVANT toute ligne d'historique (journaliser_envoi)
    boucle = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "email_saved_reports")
    lignes_continue = [x.lineno for x in ast.walk(boucle) if isinstance(x, ast.Continue)]
    lignes_journal = [x.lineno for x in ast.walk(boucle) if isinstance(x, ast.Call) and getattr(x.func, "id", "") == "journaliser_envoi"]
    return {"repro": bool(jamais), "observe": {
        "methode": "configuration (beat_schedule lu par ast) + VRAIES _due_schedules/_rapport_est_du/_heure_ok exécutées",
        "fonction": "apps/reporting/scheduled_reports.py::_heure_ok / ::_rapport_est_du ; planning erp_agentique/celery.py",
        "entrees_beat_de_la_tache": entrees, "heures_de_passage": heures,
        "scenario": "rapport quotidien, heure_envoi = 7 / 8 / 9, jour = un lundi, évalué à chaque heure de passage",
        "passages_ou_le_rapport_est_du": dus, "heures_reglees_jamais_dues": jamais,
        "premier_continue_de_la_boucle": min(lignes_continue or [0]), "premiere_ligne_historique": min(lignes_journal or [0])}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
