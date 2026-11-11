"""Agent SQL FastAPI (sql_agent_service.py::_validate_and_secure) : seul filtre = la société. Aucun droit de module (règle d'APFS4)
et aucune portée de rôle (records_scope_*) n'entrent dans la sécurisation d'une requête. Méthode « ast » (sqlglot absent, la
fonction réelle n'est pas exécutée) : on lit la signature et les appels de _validate_and_secure et de _inject_company_filter dans
le fichier réel, et on cherche tout code de droit consulté par le service ou le routeur ; les rôles viennent du registre vivant."""
SONDE = {"constat": "C-ALEC-014", "sha": "ae5a7ae4c",
         "attendu": "_validate_and_secure(sql, company_id, allow_price) ne reçoit ni module ni portée ; le service ne lit que "
                    "prix_achat_voir ; des rôles sans code du module d'une table, et des rôles à portée, lisent la table société entière"}
import ast, pathlib, re, runpy
RACINE = pathlib.Path(__file__).resolve().parents[4]
SERVICE = RACINE / "backend/fastapi_ia/app/services/sql_agent_service.py"
ENDPOINT = RACINE / "backend/fastapi_ia/app/api/endpoints/sql_agent.py"
TABLES_TEMOINS = {"crm_client": "crm", "ventes_facture": "ventes", "stock_produit": "stock", "sav_ticket": "sav",
                  "installations_installation": "installations"}


def fonction(arbre, nom):
    return next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == nom)


def sonde(ctx=None):
    texte = SERVICE.read_text(encoding="utf-8")
    arbre = ast.parse(texte)
    v, inj = fonction(arbre, "_validate_and_secure"), fonction(arbre, "_inject_company_filter")
    params_v = [a.arg for a in v.args.args]
    appels_v = sorted({n.func.id for n in ast.walk(v) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)})
    params_inj = [a.arg for a in inj.args.args]
    # codes de droit lus par le service et le routeur (littéraux « xxx_voir » / « records_scope_* »)
    lus = sorted(set(re.findall(r"[\"']([a-z_]+_voir|records_scope_[a-z_]+|[a-z]+_gerer)[\"']",
                                texte + ENDPOINT.read_text(encoding="utf-8"))))
    g = runpy.run_path(str(RACINE / "backend/django_core/apps/roles/permissions_registre.py"))
    pm = g["PERMISSION_MODULE"]
    portail = {r[0] if isinstance(r, tuple) else r for r in g["CANONICAL_PORTAIL_ROLES"]}
    internes = [(n, set(p)) for n, p in g["CANONICAL_SYSTEM_ROLES"] if n not in portail]
    sans_module = {t: [n for n, p in internes if not any(pm.get(c) == m for c in p)] for t, m in TABLES_TEMOINS.items()}
    a_portee = {n: sorted(c for c in p if c.startswith("records_scope_")) for n, p in internes
                if any(c.startswith("records_scope_") for c in p)}
    aveugle = (params_v == ["sql", "company_id", "allow_price"] and params_inj == ["sql", "company_id"]
               and set(lus) <= {"prix_achat_voir"})
    repro = bool(aveugle and any(sans_module.values()) and a_portee)
    return {"repro": repro, "observe": {
        "methode": "ast (sqlglot absent : _validate_and_secure non exécutée ; signature, appels et littéraux relus sur le fichier réel)",
        "fonction": "backend/fastapi_ia/app/services/sql_agent_service.py::_validate_and_secure",
        "parametres_validate_and_secure": params_v, "appels_directs": appels_v, "parametres_inject_company_filter": params_inj,
        "codes_de_droit_lus_par_service_et_routeur": lus,
        "garde_du_routeur": "exiger_compte_interne" in ENDPOINT.read_text(encoding="utf-8"),
        "roles_internes_livres_sans_aucun_code_du_module_de_la_table_mais_qui_la_lisent": sans_module,
        "roles_livres_a_portee_dont_la_portee_est_ignoree": a_portee}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
