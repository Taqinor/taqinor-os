# flake8: noqa  (sonde HÔTE de la contre-visite AMSG du 17/11 — Django importé sans base, sans envoi, sans Celery)
"""C-AMSG-VER4-400 — la borne d'AMSG98 (copiée par AMSG72) PERD la reprise quand la fenêtre des messages ouvre plus de
`visibility_timeout` (5 400 s) après le balayage de 07:45 LE MÊME JOUR : `signature_relances_expiration` et
`rappel_rdv_j1` ne programment rien et n'envoient rien ; le balayage du lendemain ne rattrape pas les poses J-1.
Déclencheurs réels : Ramadan saisi avec `ramadan_appel_debut` à 10:00 (défaut de la migration 0082, que 0099 n'a jamais
réécrit) ou `message_heure_debut` réglé après 09:15 dans Paramètres. Exécute le VRAI `apps/crm/horaires.py`, la VRAIE
`fenetre_notifications` et les VRAIS corps de `ged.tasks.signature_relances_expiration`, `installations.tasks.rappel_rdv_j1`
et `_jours_cibles` (extraits par ast), sur bouchons (aucune base). Témoins : ouverture 08:30 et Ramadan à 09:00 ⇒ une reprise
`apply_async` de chaque tâche, ce qui prouve que la chaîne réelle est traversée."""
SONDE = {"constat": "C-AMSG-VER4-400", "sha": "0d834aa12",
         "attendu": "jeudi de Ramadan 07:45, ouverture 10:00 (ou message_heure_debut 09:30) : 0 relance, 0 reprise ged, "
                    "0 reprise rappel J-1, ORM des poses jamais atteint ; témoins 08:30 et 09:00 : une reprise de chaque"}
import ast, datetime, pathlib, re, sys, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ, NS = RACINE / "backend/django_core", types.SimpleNamespace


def mod(nom, **attrs):  # module-bouchon enregistré (parents créés, attribut posé sur le parent)
    m = sys.modules.get(nom) or types.ModuleType(nom); m.__path__ = []; m.__dict__.update(attrs); sys.modules[nom] = m
    if "." in nom: setattr(mod(nom.rsplit(".", 1)[0]), nom.rsplit(".", 1)[1], m)
    return m


def charge(nom, rel):  # VRAI module du dépôt exécuté en entier sous ``nom``
    m = mod(nom, __file__=str(DJ / rel), __package__=nom.rsplit(".", 1)[0])
    exec(compile((DJ / rel).read_text(encoding="utf-8"), str(DJ / rel), "exec"), m.__dict__); return m


def fonction(rel, nom, g):  # VRAIE fonction de module exécutée dans ``g`` (décorateurs retirés)
    arbre = ast.parse((DJ / rel).read_text(encoding="utf-8"))
    f = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == nom); f.decorator_list = []
    exec(compile(ast.Module(body=[f], type_ignores=[]), rel, "exec"), g); return g[nom]


def _profil(**kw):
    p = dict(message_heure_debut=datetime.time(8, 30), appel_heure_debut=datetime.time(9, 0),
             appel_heure_fin=datetime.time(20, 0), vendredi_pause_debut=datetime.time(11, 30),
             vendredi_pause_fin=datetime.time(15, 0), ramadan_debut=None, ramadan_fin=None,
             ramadan_appel_debut=datetime.time(9, 0), ramadan_appel_fin=datetime.time(15, 0),
             fuseau_horaire="Africa/Casablanca")
    p.update(kw); return NS(**p)


def sonde(ctx=None):
    from unittest import mock
    from zoneinfo import ZoneInfo
    from django.conf import settings
    base = (DJ / "erp_agentique/settings/base.py").read_text(encoding="utf-8")
    vt = int(re.search(r"CELERY_BROKER_TRANSPORT_OPTIONS = \{'visibility_timeout': (\d+)\}", base).group(1))
    if not settings.configured:
        settings.configure(USE_TZ=True, TIME_ZONE="Africa/Casablanca",
                           CELERY_BROKER_TRANSPORT_OPTIONS={"visibility_timeout": vt})
    sauve, pyc = dict(sys.modules), sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        from django.utils import timezone
        casa = ZoneInfo("Africa/Casablanca")
        jours_ouvres = lambda d, c: d.weekday() < 5
        def pjo(d, c):
            while d.weekday() >= 5: d += datetime.timedelta(days=1)
            return d
        mod("apps.notifications.calendar_utils", is_jour_ouvre=jours_ouvres, prochain_jour_ouvre=pjo,
            feries_entre=lambda *a, **k: [])
        mod("core.tz_display", DEFAULT_TIMEZONE="Africa/Casablanca")
        profil = {}
        horaires = charge("apps.crm.horaires", "apps/crm/horaires.py")
        horaires._profil = lambda company: profil["p"]
        mod("apps.crm", horaires=horaires)
        src_sel = (DJ / "apps/notifications/selectors.py").read_text(encoding="utf-8")
        gsel = {"datetime": datetime, "logger": NS(warning=lambda *a, **k: None),
                "CANAL_NOTIFICATIONS": re.search(r"CANAL_NOTIFICATIONS = '(\w+)'", src_sel).group(1),
                "FenetreNotifications": lambda o, p: NS(ouverte=o, prochaine_ouverture=p),
                "_fenetre_repli": lambda c, m: NS(ouverte=True, prochaine_ouverture=m)}
        fenetre = fonction("apps/notifications/selectors.py", "fenetre_notifications", gsel)
        mod("apps.notifications.selectors", fenetre_notifications=fenetre)
        company = NS(pk=1)

        class Societes(list):
            def filter(self, **kw): return self

        mod("authentication.selectors", active_companies=lambda: Societes([company]))

        def jouer(instant):
            appels, relances = [], []
            mod("apps.ged", services=NS(relancer_signataires_dus=lambda c: relances.append(c) or [1],
                                        expirer_demandes_echues=lambda c: 0))
            g = {"__name__": "apps.ged.tasks", "__package__": "apps.ged",
                 "logger": NS(warning=lambda *a, **k: None, info=lambda *a, **k: None),
                 "relancer_signataires_societe": NS(apply_async=lambda **kw: appels.append("ged"))}
            sig = fonction("apps/ged/tasks.py", "signature_relances_expiration", g)
            orm = []
            mod("apps.installations.models", Intervention=NS(objects=NS(actives=lambda: orm.append(1) or NS(
                filter=lambda **kw: NS(select_related=lambda *a: [])))))
            gi = {"__name__": "apps.installations.tasks", "__package__": "apps.installations",
                  "casablanca_today": lambda: instant.date(),
                  "_jours_cibles": fonction("apps/installations/tasks.py", "_jours_cibles", {})}
            rdv = fonction("apps/installations/tasks.py", "rappel_rdv_j1", gi)
            gi["rappel_rdv_j1"] = NS(apply_async=lambda **kw: appels.append("rdv"))
            with mock.patch.object(timezone, "now", return_value=instant.astimezone(datetime.timezone.utc)):
                r = sig(); rdv()
            return {"relances": r["relances"], "reprises": appels, "orm_poses_atteint": bool(orm)}

        jeudi = datetime.datetime(2027, 2, 18, 7, 45, tzinfo=casa)  # jeudi ouvré du Ramadan 2027 (dates saisies)
        ramadan = dict(ramadan_debut=datetime.date(2027, 2, 8), ramadan_fin=datetime.date(2027, 3, 9))
        cas = {"témoin 08:30": _profil(), "Ramadan 09:00 (défaut 0099)": _profil(**ramadan),
               "Ramadan 10:00 (défaut 0082)": _profil(**ramadan, ramadan_appel_debut=datetime.time(10, 0)),
               "message_heure_debut 09:30": _profil(message_heure_debut=datetime.time(9, 30))}
        res = {}
        for nom, p in cas.items():
            profil["p"] = p
            res[nom] = jouer(jeudi)
        perdus = [res[n] for n in ("Ramadan 10:00 (défaut 0082)", "message_heure_debut 09:30")]
        temoins = [res[n] for n in ("témoin 08:30", "Ramadan 09:00 (défaut 0099)")]
        repro = (all(r["reprises"] == [] and r["relances"] == 0 and not r["orm_poses_atteint"] for r in perdus)
                 and all(sorted(r["reprises"]) == ["ged", "rdv"] for r in temoins))
        return {"repro": repro, "visibility_timeout": vt, "cas": res}
    finally:
        sys.modules.clear(); sys.modules.update(sauve); sys.dont_write_bytecode = pyc


if __name__ == "__main__":
    import json
    r = sonde()
    print(json.dumps(r, ensure_ascii=False, indent=1, default=str))
    print("repro:", r["repro"])
