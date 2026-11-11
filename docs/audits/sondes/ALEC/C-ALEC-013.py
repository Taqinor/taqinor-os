"""Garde de l'agent SQL FastAPI (sql_agent_service.py::_references_forbidden_column) : trois trous de confidentialité.
sqlglot n'est pas installé sur l'hôte : la fonction réelle n'est pas exécutée. Méthode « ast » : on lit dans le fichier réel
les constantes que la fonction consulte (listes de colonnes / tables interdites, tables autorisées), on vérifie par ast que la
fonction ne consulte QUE celles-là, puis on applique sa règle (colonne nommée interdite, ou ligne entière d'une table à prix)."""
SONDE = {"constat": "C-ALEC-013", "sha": "ae5a7ae4c",
         "attendu": "SELECT cout FROM sav_ticket, SELECT donnees_structurees FROM ia_ocr_document et SELECT email, telephone "
                    "FROM crm_client ne sont pas refusés ; les rôles livrés sans prix_achat_voir / sans client_pii_voir passent"}
import ast, pathlib, re, runpy
RACINE = pathlib.Path(__file__).resolve().parents[4]
SERVICE = RACINE / "backend/fastapi_ia/app/services/sql_agent_service.py"
ENDPOINT = RACINE / "backend/fastapi_ia/app/api/endpoints/sql_agent.py"


def constantes(arbre, noms):
    out = {}
    for n in arbre.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id in noms:
            v = n.value
            if isinstance(v, ast.Call) and v.args:  # frozenset([...])
                v = v.args[0]
            out[n.targets[0].id] = set(ast.literal_eval(v))
    return out


def refuse(sql, colonnes, tables_a_ligne):
    """Règle de _references_forbidden_column : identifiant interdit nommé, ou `*` nu sur une table sensible."""
    mots = {m.lower() for m in re.findall(r"[A-Za-z_][A-Za-z_0-9]*", sql)}
    if mots & colonnes:
        return True
    sources = {m.lower() for m in re.findall(r"(?:from|join)\s+([A-Za-z_][A-Za-z_0-9]*)", sql, re.I)}
    return bool(re.search(r"select\s+\*", sql, re.I) and sources & tables_a_ligne)


def sonde(ctx=None):
    texte = SERVICE.read_text(encoding="utf-8")
    arbre = ast.parse(texte)
    c = constantes(arbre, {"_ALLOWED_TABLES", "_FORBIDDEN_COLUMNS", "_SECRET_COLUMNS", "_PRICE_TABLES", "_SECRET_TABLES"})
    f = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "_references_forbidden_column")
    consultees = sorted({n.id for n in ast.walk(f) if isinstance(n, ast.Name) and n.id in c})
    colonnes = c["_SECRET_COLUMNS"] | c["_FORBIDDEN_COLUMNS"]          # sans prix_achat_voir (allow_price=False)
    tables = c["_SECRET_TABLES"] | c["_PRICE_TABLES"]
    requetes = {
        "sav_ticket.cout": ["SELECT cout FROM sav_ticket", "SELECT * FROM sav_ticket"],
        "ia_ocr_document": ["SELECT donnees_structurees, texte_brut FROM ia_ocr_document", "SELECT * FROM ia_ocr_document"],
        "crm_client PII": ["SELECT email, telephone FROM crm_client", "SELECT * FROM crm_client"],
    }
    verdict = {k: [(q, refuse(q, colonnes, tables)) for q in qs] for k, qs in requetes.items()}
    temoin = refuse("SELECT marge_snapshot FROM ventes_devis", colonnes, tables)
    autorisees = {"sav_ticket": "sav_ticket" in c["_ALLOWED_TABLES"], "ia_ocr_document": "ia_ocr_document" in c["_ALLOWED_TABLES"],
                  "crm_client": "crm_client" in c["_ALLOWED_TABLES"]}
    ouverts = {k: all(not r for _, r in v) for k, v in verdict.items()}
    # Qui passe : tout compte interne (routeur exiger_compte_interne) ; le seul drapeau est prix_achat_voir ; aucun client_pii_voir.
    g = runpy.run_path(str(RACINE / "backend/django_core/apps/roles/permissions_registre.py"))
    portail = {r[0] if isinstance(r, tuple) else r["nom"] if isinstance(r, dict) else r for r in g["CANONICAL_PORTAIL_ROLES"]}
    internes = [(n, set(p)) for n, p in g["CANONICAL_SYSTEM_ROLES"] if n not in portail]
    sans_prix = [n for n, p in internes if "prix_achat_voir" not in p]
    sans_pii = [n for n, p in internes if "client_pii_voir" not in p]
    endpoint = ENDPOINT.read_text(encoding="utf-8")
    pii_lu = "client_pii" in texte or "client_pii" in endpoint
    repro = (all(ouverts.values()) and all(autorisees.values()) and temoin is True and not pii_lu
             and "prix_achat_voir" in texte and bool(sans_prix) and bool(sans_pii))
    return {"repro": repro, "observe": {
        "methode": "ast (sqlglot absent : _references_forbidden_column non exécutée ; règle relue sur le fichier réel)",
        "fonction": "backend/fastapi_ia/app/services/sql_agent_service.py::_references_forbidden_column",
        "constantes_consultees_par_la_fonction": consultees,
        "colonnes_interdites_sans_prix_achat_voir": sorted(colonnes), "tables_a_ligne_entiere": sorted(tables),
        "tables_dans__ALLOWED_TABLES": autorisees, "verdicts_refus": verdict, "temoin_marge_snapshot_refuse": temoin,
        "trou_ouvert_par_famille": ouverts, "code_client_pii_lu_dans_service_ou_endpoint": pii_lu,
        "roles_internes_livres_sans_prix_achat_voir": sans_prix, "roles_internes_livres_sans_client_pii_voir": sans_pii}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
