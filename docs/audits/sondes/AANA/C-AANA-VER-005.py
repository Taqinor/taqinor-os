# flake8: noqa  (sonde de contre-visite vérifie AANA ; fonction pure du validateur de l'agent SQL, sans LLM ni réseau)
# Usage : depuis backend/fastapi_ia (image fastapi_ia) : python <cette sonde>  -> imprime le verdict, sortie 0 = REPRO.
"""AANA2 : `backend/fastapi_ia/app/services/sql_agent_service.py::_rewrite_node` compare les noms de CTE en minuscules ;
Postgres respecte la casse d'un identifiant entre guillemets. `WITH "CRM_LEAD" AS (...) SELECT * FROM crm_lead` est
acceptée et ressort sans filtre société : la CTE "CRM_LEAD" ne masque pas la vraie table crm_lead pour Postgres."""
SONDE = {"constat": "C-AANA-VER-005", "sha": "32375fe65",
         "attendu": "une CTE homonyme entre guillemets : la vraie table est lue sans filtre company_id dans le SQL exécuté"}


def sonde(ctx=None):
    import sqlglot
    from sqlglot import exp
    from app.services import sql_agent_service as s

    def nom_pg(i):
        return i.this if i.quoted else i.this.lower()
    res = {}
    for q in ('WITH "CRM_LEAD" AS (SELECT 1 AS id) SELECT * FROM crm_lead',
              'WITH "DJANGO_SESSION" AS (SELECT 1 AS a) SELECT * FROM django_session',
              'SELECT nom FROM crm_client WHERE EXISTS (WITH "CRM_LEAD" AS (SELECT 1) SELECT 1 FROM crm_lead)'):
        try:
            out = s._validate_and_secure(q, 7)
        except s.SQLSecurityError as e:
            res[q] = {'rejete': str(e)[:80]}
            continue
        t = sqlglot.parse_one(out, read='postgres')
        ctes = {nom_pg(c.args['alias'].this) for c in t.find_all(exp.CTE)}
        fuites = sorted({nom_pg(x.this) for x in t.find_all(exp.Table)
                         if not x.text('db') and nom_pg(x.this) not in ctes
                         and nom_pg(x.this) not in s._TENANT_SCOPED_TABLES})
        res[q] = {'sql_execute': out, 'tables_lues_sans_filtre': fuites}
    return {'repro': any(v.get('tables_lues_sans_filtre') for v in res.values()), 'cas': res}


if __name__ == '__main__':
    import json
    import sys
    r = sonde()
    print(json.dumps(r, ensure_ascii=False, indent=1))
    print('verdict :', 'REPRO' if r['repro'] else 'NON REPRODUIT')
    sys.exit(0 if r['repro'] else 1)
