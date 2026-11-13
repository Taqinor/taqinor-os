"""Contre-visite ALEC (13/11) — ALEC16 : l'assistant SQL borne au propriétaire seulement six tables.
`backend/fastapi_ia/app/services/sql_agent_service.py::_verifier_module_et_portee` refuse à un code `records_scope_*` les
tables de la liste figée `_TABLES_A_PROPRIETAIRE` ; or `_ALLOWED_TABLES` sert aussi les lignes de devis / de facture (scopées
par la seule SOCIÉTÉ du parent, `_TABLES_PAR_PARENT`), les interventions, les équipements et les contrats de maintenance.
sqlglot n'est pas installé sur l'hôte : on EXÉCUTE le vrai corps de `_verifier_module_et_portee` (extrait par ast) avec un
bouchon minimal de `_parse_single_query` / `exp.Table` (noms de tables lus après FROM / JOIN), contre les codes RÉELS du rôle
livré « Commercial » (registre des rôles exécuté hors Django). La garde prix / PII est relue sur ses constantes réelles."""
SONDE = {"constat": "C-ALEC-VER1-101", "sha": "d64fa1e4e4",
         "attendu": "Commercial (records_scope_soi) : SELECT ... FROM ventes_lignefacture passe module + portée (aucun refus), "
                    "alors que SELECT ... FROM ventes_facture est refusé « Portée restreinte »"}
import ast, pathlib, re, runpy, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
SERVICE = RACINE / "backend/fastapi_ia/app/services/sql_agent_service.py"
REGISTRE = RACINE / "backend/django_core/apps/roles/permissions_registre.py"


def constantes(arbre, noms):
    out = {}
    for n in arbre.body:
        cible = n.targets[0] if isinstance(n, ast.Assign) else n.target if isinstance(n, ast.AnnAssign) else None
        if isinstance(cible, ast.Name) and cible.id in noms:
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


def verifier_reel(c):
    """Le VRAI corps de _verifier_module_et_portee, compilé avec ses constantes réelles et un parseur bouchonné."""
    arbre = ast.parse(SERVICE.read_text(encoding="utf-8"))
    f = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "_verifier_module_et_portee")
    ns = {"_MODULE_DES_TABLES": c["_MODULE_DES_TABLES"], "_TABLES_A_PROPRIETAIRE": frozenset(c["_TABLES_A_PROPRIETAIRE"]),
          "_parse_single_query": _Arbre, "exp": types.SimpleNamespace(Table=_Table), "SQLSecurityError": SQLSecurityError}
    exec(compile(ast.Module([f], []), str(SERVICE), "exec"), ns)
    return ns["_verifier_module_et_portee"]


def joue(fn, sql, codes):
    try:
        fn(sql, codes)
        return "passe"
    except SQLSecurityError as e:
        return f"refus : {e}"


def sonde(ctx=None):
    arbre = ast.parse(SERVICE.read_text(encoding="utf-8"))
    c = constantes(arbre, {"_MODULE_DES_TABLES", "_TABLES_A_PROPRIETAIRE", "_ALLOWED_TABLES", "_TABLES_PAR_PARENT",
                           "_FORBIDDEN_COLUMNS", "_SECRET_COLUMNS", "_PII_COLUMNS"})
    fn = verifier_reel(c)
    reg = runpy.run_path(str(REGISTRE))
    commercial = dict(reg["CANONICAL_SYSTEM_ROLES"])["Commercial"]
    codes = list(commercial)
    requetes = {
        "ventes_lignefacture": "SELECT designation, quantite, prix_unitaire FROM ventes_lignefacture",
        "ventes_lignedevis": "SELECT designation, quantite, prix_unitaire FROM ventes_lignedevis",
        "installations_intervention": "SELECT id, statut FROM installations_intervention",
        "sav_equipement": "SELECT id, numero_serie FROM sav_equipement",
        "sav_contratmaintenance": "SELECT id, statut FROM sav_contratmaintenance",
    }
    verdicts = {t: joue(fn, q, codes) for t, q in requetes.items()}
    temoin = joue(fn, "SELECT reference, total_ttc FROM ventes_facture", codes)
    interdites = {x.lower() for x in c["_FORBIDDEN_COLUMNS"]} | {x.lower() for x in c["_SECRET_COLUMNS"]}
    colonnes_lignes = {"designation", "quantite", "prix_unitaire"}
    manquantes = sorted(t for t in requetes if t in c["_ALLOWED_TABLES"] and t not in c["_TABLES_A_PROPRIETAIRE"])
    repro = (verdicts["ventes_lignefacture"] == "passe" and temoin.startswith("refus")
             and "records_scope_soi" in codes and "ventes_lignefacture" in c["_TABLES_PAR_PARENT"]
             and not (colonnes_lignes & interdites) and len(manquantes) == 5)
    return {"repro": repro, "observe": {
        "methode": "exécution du vrai _verifier_module_et_portee (ast, parseur bouchonné) ; codes du rôle livré Commercial",
        "commercial_porte_records_scope_soi": "records_scope_soi" in codes,
        "commercial_codes_ventes": sorted(x for x in codes if x.startswith(("ventes_", "encaisser"))),
        "tables_a_proprietaire": sorted(c["_TABLES_A_PROPRIETAIRE"]),
        "tables_servies_non_bornees_au_proprietaire": manquantes,
        "scope_des_lignes_par_parent_societe_seule": c["_TABLES_PAR_PARENT"],
        "verdicts_commercial": verdicts, "temoin_ventes_facture": temoin,
        "colonnes_des_lignes_dans_la_garde_prix": sorted(colonnes_lignes & interdites)}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
