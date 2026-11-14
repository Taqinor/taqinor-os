"""Contre-visite de clôture ALEC (14/11) — jumeau oublié d'ALEC16/ALEC41 : les miroirs publicitaires de l'assistant SQL.
`backend/fastapi_ia/app/services/sql_agent_service.py::_verifier_module_et_portee` exige le droit du module pour les seuls
préfixes de `_MODULE_DES_TABLES` (ventes_, crm_, installations_, sav_, stock_) et ne refuse à un code `records_scope_*` que les
tables de `_TABLES_A_PROPRIETAIRE` ; or `_ALLOWED_TABLES` sert aussi `adsengine_metaleadmirror`, dont la colonne `phone_key`
est le numéro de téléphone du lead Meta en clair (chiffres seuls, `crm/leads_doublons.py::normalize_phone`) à côté de
`crm_lead_id`, et la garde des données personnelles ne connaît que `crm_client` (`_PII_TABLE`).
sqlglot n'est pas installé sur l'hôte : on EXÉCUTE le vrai corps de `_verifier_module_et_portee` (extrait par ast) avec un
bouchon minimal du parseur (noms de tables lus après FROM / JOIN), contre les codes RÉELS des rôles livrés (registre exécuté
hors Django) ; la garde PII est relue sur ses constantes réelles ; `normalize_phone` est exécutée telle quelle (ast)."""
SONDE = {"constat": "C-ALEC-VER2-201", "sha": "a12f40f821",
         "attendu": "Commercial (records_scope_soi) : SELECT phone_key, crm_lead_id FROM adsengine_metaleadmirror passe module + "
                    "portée (témoin crm_client refusé « Portée restreinte ») ; Commercial terrain et Admin RH (ni client_pii_voir "
                    "ni adsengine_view) passent aussi ; phone_key hors de toute liste de colonnes gardées ; la clé est le numéro"}
import ast, pathlib, re, runpy, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend").is_dir():
    RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
SERVICE = RACINE / "backend/fastapi_ia/app/services/sql_agent_service.py"
REGISTRE = RACINE / "backend/django_core/apps/roles/permissions_registre.py"
MODELES_ADS = RACINE / "backend/django_core/apps/adsengine/models.py"
DOUBLONS = RACINE / "backend/django_core/apps/crm/leads_doublons.py"
RLS = RACINE / "backend/db/rls_roles.sql"
NOMS = {"_MODULE_DES_TABLES", "_TABLES_A_PROPRIETAIRE", "_ALLOWED_TABLES", "_TABLES_WITH_COMPANY_ID", "_PII_TABLE",
        "_PII_COLUMNS", "_FORBIDDEN_COLUMNS", "_SECRET_COLUMNS", "_PRICE_ONLY_TABLES", "_PRICE_TABLES"}


def constantes(arbre):
    out = {}
    for n in arbre.body:
        cible = n.targets[0] if isinstance(n, ast.Assign) else n.target if isinstance(n, ast.AnnAssign) else None
        if isinstance(cible, ast.Name) and cible.id in NOMS:
            v = n.value
            if isinstance(v, ast.Call) and v.args:  # frozenset({...}) / frozenset([...])
                v = v.args[0]
            out[cible.id] = ast.literal_eval(v)
    return out


class SQLSecurityError(Exception):
    pass


class _Table:
    def __init__(s, nom):
        s.name = nom


class _Arbre:
    def __init__(s, sql):
        s.tables = [_Table(m) for m in re.findall(r"(?:from|join)\s+([A-Za-z_][A-Za-z_0-9]*)", sql, re.I)]

    def find_all(s, typ):
        return iter(s.tables) if typ is _Table else iter(())


def fonction(chemin, nom, ns):
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    f = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == nom)
    exec(compile(ast.Module([f], []), str(chemin), "exec"), ns)
    return ns[nom]


def joue(fn, sql, codes):
    try:
        fn(sql, codes)
        return "passe"
    except SQLSecurityError as e:
        return f"refus : {e}"


def sonde(ctx=None):
    c = constantes(ast.parse(SERVICE.read_text(encoding="utf-8")))
    verifier = fonction(SERVICE, "_verifier_module_et_portee", {
        "_MODULE_DES_TABLES": c["_MODULE_DES_TABLES"], "_TABLES_A_PROPRIETAIRE": frozenset(c["_TABLES_A_PROPRIETAIRE"]),
        "_parse_single_query": _Arbre, "exp": types.SimpleNamespace(Table=_Table), "SQLSecurityError": SQLSecurityError})
    roles = dict(runpy.run_path(str(REGISTRE))["CANONICAL_SYSTEM_ROLES"])
    lead_ads = "SELECT phone_key, crm_lead_id FROM adsengine_metaleadmirror"
    depense = "SELECT spend FROM adsengine_insightsnapshot"
    temoin = "SELECT nom, telephone FROM crm_client"
    par_role = {}
    for nom in ("Commercial", "Commercial terrain", "Admin RH", "Admin Ventes", "Directeur"):
        codes = list(roles[nom])
        par_role[nom] = {
            "records_scope": sorted(x for x in codes if x.startswith("records_scope_")),
            "client_pii_voir": "client_pii_voir" in codes, "adsengine_view": "adsengine_view" in codes,
            "metaleadmirror": joue(verifier, lead_ads, codes), "insightsnapshot": joue(verifier, depense, codes),
            "temoin_crm_client": joue(verifier, temoin, codes)}
    # Garde PII : une seule table, quatre colonnes ; phone_key n'est dans aucune liste gardée.
    gardees = {x.lower() for k in ("_PII_COLUMNS", "_FORBIDDEN_COLUMNS", "_SECRET_COLUMNS") for x in c[k]}
    champ_modele = "phone_key = models.CharField" in MODELES_ADS.read_text(encoding="utf-8")
    normalise = fonction(DOUBLONS, "normalize_phone", {"_re": re})
    exemple = normalise("+212 6 61 02 80 28")
    rls = RLS.read_text(encoding="utf-8")
    com, ter, rh = par_role["Commercial"], par_role["Commercial terrain"], par_role["Admin RH"]
    repro = (com["metaleadmirror"] == "passe" and com["temoin_crm_client"].startswith("refus : Portee")
             and com["records_scope"] == ["records_scope_soi"]
             and ter["metaleadmirror"] == "passe" and not ter["client_pii_voir"] and not ter["adsengine_view"]
             and rh["metaleadmirror"] == "passe" and not rh["client_pii_voir"]
             and "adsengine_metaleadmirror" in c["_ALLOWED_TABLES"]
             and "adsengine_metaleadmirror" in c["_TABLES_WITH_COMPANY_ID"]
             and c["_PII_TABLE"] == "crm_client" and "phone_key" not in gardees and champ_modele
             and exemple == "661028028" and "'adsengine_metaleadmirror'" in rls)
    return {"repro": repro, "observe": {
        "methode": "exécution du vrai _verifier_module_et_portee (ast, parseur bouchonné) et de normalize_phone ; "
                   "codes des rôles livrés ; garde PII relue sur ses constantes",
        "prefixes_a_droit_de_module": [p for p, _ in c["_MODULE_DES_TABLES"]],
        "tables_a_proprietaire": sorted(c["_TABLES_A_PROPRIETAIRE"]),
        "par_role": par_role,
        "garde_pii_table_unique": c["_PII_TABLE"], "garde_pii_colonnes": list(c["_PII_COLUMNS"]),
        "phone_key_dans_une_liste_gardee": "phone_key" in gardees,
        "phone_key_champ_du_modele_MetaLeadMirror": champ_modele,
        "normalize_phone('+212 6 61 02 80 28')": exemple,
        "role_postgres_sql_agent_ro_lit_la_table": "'adsengine_metaleadmirror'" in rls}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
