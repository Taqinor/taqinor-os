"""Contre-visite ALEC du 17/11 — jumeau d'ALEC37 et d'ALEC31 dans l'assistant SQL.
ALEC37 retire `lien_client_token` / `lien_rapport_token` de la lecture des interventions (écran) : seules les actions
`lien-client` / `lien-rapport` (`IsResponsableOrAdmin`) les rendent. ALEC31 ajoute `adresse_siege` aux coordonnées
masquées du client. Or `backend/fastapi_ia/app/services/sql_agent_service.py` sert `installations_intervention` et
`crm_client` : ni les deux jetons ni `adresse_siege` ne figurent dans une liste de colonnes gardées.
sqlglot n'est pas installé sur l'hôte : on EXÉCUTE le vrai corps de `_verifier_module_et_portee` (ast, parseur bouchonné :
noms de tables lus après FROM / JOIN) avec les codes RÉELS des rôles livrés (registre exécuté hors Django) ; les listes
gardées sont relues sur leurs constantes. « Responsable au sens d'IsResponsableOrAdmin » = au moins un code d'écriture
(ni `_voir`/`_view`, ni `records_scope_*`, ni `portail_*`), règle de `CustomUser._role_grants_write`."""
SONDE = {"constat": "C-ALEC-VER3-301", "sha": "0d834aa12f",
         "attendu": "Utilisateur (installation_voir, aucune portée, aucun code d'écriture) : SELECT des deux jetons sur "
                    "installations_intervention passe module + portée alors que l'action lien-rapport lui est refusée ; "
                    "jetons et adresse_siege hors de toute liste gardée"}
import ast, pathlib, re, runpy, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend").is_dir():
    RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
SERVICE = RACINE / "backend/fastapi_ia/app/services/sql_agent_service.py"
REGISTRE = RACINE / "backend/django_core/apps/roles/permissions_registre.py"
SER_INTERV = RACINE / "backend/django_core/apps/installations/serializers.py"
SER_CLIENT = RACINE / "backend/django_core/apps/crm/serializers_clients.py"
NOMS = {"_MODULE_DES_TABLES", "_TABLES_A_PROPRIETAIRE", "_SECRET_COLUMNS", "_FORBIDDEN_COLUMNS", "_PII_COLUMNS",
        "_TABLES_LIGNE_SECRETE", "_ALLOWED_TABLES"}


class _Refus(Exception):
    pass


class _Table:
    def __init__(s, nom):
        s.name = nom


class _Arbre:
    def __init__(s, sql):
        s.tables = [_Table(m) for m in re.findall(r"(?:from|join)\s+([A-Za-z_]\w*)", sql, re.I)]

    def find_all(s, typ):
        return iter(s.tables)


def sonde(ctx=None):
    arbre = ast.parse(SERVICE.read_text(encoding="utf-8"))
    c = {}
    for n in arbre.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id in NOMS:
            v = n.value.args[0] if isinstance(n.value, ast.Call) else n.value
            c[n.targets[0].id] = ast.literal_eval(v)
    f = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "_verifier_module_et_portee")
    ns = {"_MODULE_DES_TABLES": c["_MODULE_DES_TABLES"], "_TABLES_A_PROPRIETAIRE": frozenset(c["_TABLES_A_PROPRIETAIRE"]),
          "_parse_single_query": _Arbre, "exp": types.SimpleNamespace(Table=_Table),
          "SQLSecurityError": _Refus, "RefusDeDroit": _Refus}
    exec(compile(ast.Module([f], []), str(SERVICE), "exec"), ns)
    roles = dict(runpy.run_path(str(REGISTRE))["CANONICAL_SYSTEM_ROLES"])
    sql = "SELECT reference, lien_client_token, lien_rapport_token FROM installations_intervention"
    par_role = {}
    for nom in ("Utilisateur", "Responsable", "Directeur", "Commercial", "Technicien"):
        codes = list(roles[nom])
        try:
            ns["_verifier_module_et_portee"](sql, codes)
            r = "passe"
        except _Refus as e:
            r = f"refus : {e}"
        ecriture = [p for p in codes if not (p.endswith(("_voir", "_view")) or p.startswith(("records_scope", "portail_")))]
        par_role[nom] = {"assistant": r, "action_lien_rapport_permise": bool(ecriture)}
    gardees = {x.lower() for k in ("_SECRET_COLUMNS", "_FORBIDDEN_COLUMNS", "_PII_COLUMNS") for x in c[k]}
    ecran_sans_jetons = "exclude = ['lien_client_token', 'lien_rapport_token']" in SER_INTERV.read_text(encoding="utf-8")
    ecran_siege_masque = "'adresse_siege')" in SER_CLIENT.read_text(encoding="utf-8")
    u = par_role["Utilisateur"]
    repro = (u["assistant"] == "passe" and not u["action_lien_rapport_permise"]
             and not ({"lien_client_token", "lien_rapport_token"} & gardees)
             and "installations_intervention" not in c["_TABLES_LIGNE_SECRETE"]
             and "installations_intervention" in c["_ALLOWED_TABLES"]
             and ecran_sans_jetons and "adresse_siege" not in gardees and ecran_siege_masque)
    return {"repro": repro, "observe": {
        "methode": "exécution du vrai _verifier_module_et_portee (ast, parseur bouchonné) ; codes des rôles livrés ; "
                   "listes gardées relues sur leurs constantes",
        "par_role": par_role,
        "jetons_dans_une_liste_gardee": sorted({"lien_client_token", "lien_rapport_token"} & gardees),
        "ligne_entiere_intervention_refusee": "installations_intervention" in c["_TABLES_LIGNE_SECRETE"],
        "adresse_siege_gardee": "adresse_siege" in gardees, "pii_colonnes": list(c["_PII_COLUMNS"]),
        "ecran_intervention_sans_jetons_ALEC37": ecran_sans_jetons,
        "ecran_client_masque_adresse_siege_ALEC31": ecran_siege_masque}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
