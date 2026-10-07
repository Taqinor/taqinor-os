-- NTPLT3 — Rôles Postgres pour la défense en profondeur RLS (multi-tenant).
--
-- À exécuter UNE FOIS, manuellement, par le fondateur, SUR la base applicative
-- (jamais automatiquement — c'est une bascule d'infrastructure délibérée qui
-- accompagne l'activation de POSTGRES_RLS_ENABLED=1 + `manage.py rls --apply`).
-- Choisir un mot de passe robuste (ne jamais committer de secret ici).
--
-- Modèle :
--   * Le rôle OWNER existant (${DB_USER}, ex. erp_user) reste le rôle
--     MIGRATIONS/ADMIN : il POSSÈDE les tables, donc — même avec FORCE ROW
--     LEVEL SECURITY posé par `manage.py rls` — il faut lui accorder BYPASSRLS
--     pour que `migrate`, `seed_catalogue` et `core.dump_database` (pg_dump)
--     voient TOUTES les lignes de TOUS les tenants. C'est voulu : ces chemins
--     sont hors requête HTTP, jamais exposés à un tenant.
--   * Le rôle APPLICATIF (app_rls, NON-BYPASSRLS) est celui que le serveur
--     Django (gunicorn) et les workers Celery utilisent au RUNTIME quand
--     POSTGRES_RLS_ENABLED=1 : SANS BYPASSRLS, il est PHYSIQUEMENT soumis aux
--     policies RLS. Le GUC `app.current_company` (posé par requête, NTPLT1)
--     décide alors quelles lignes il voit — une fuite cross-tenant devient
--     impossible même via une requête SQL brute.
--
-- Surfaces globales légitimes (superuser sans société, tâches cross-company du
-- beat) : elles tournent hors requête (pas de GUC) → elles doivent utiliser le
-- rôle OWNER/BYPASSRLS, JAMAIS le rôle applicatif. NTPLT4 pose le GUC dans les
-- tâches Celery à effet tenant ; une tâche VOLONTAIREMENT cross-company ne pose
-- pas de GUC et s'exécute sous l'owner.

-- 1) Le rôle owner conserve/obtient BYPASSRLS (migrations, seed, dumps).
--    (Remplacer erp_user par ${DB_USER} si différent.)
ALTER ROLE erp_user BYPASSRLS;

-- 2) Rôle applicatif NON-BYPASSRLS pour le runtime Django/Celery.
--    LOGIN + mot de passe à CHOISIR (aligné avec DB_APP_USER/DB_APP_PASSWORD).
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rls') THEN
    CREATE ROLE app_rls LOGIN PASSWORD 'CHANGE_ME_ROBUSTE' NOBYPASSRLS;
  ELSE
    ALTER ROLE app_rls NOBYPASSRLS;
  END IF;
END
$$;

-- 3) Droits du rôle applicatif : DML complet (l'app lit/écrit), aucun DDL
--    (les migrations restent le fait de l'owner). Les policies RLS, pas les
--    GRANT, portent l'isolation par tenant.
GRANT CONNECT ON DATABASE erp_db TO app_rls;
GRANT USAGE ON SCHEMA public TO app_rls;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_rls;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_rls;
-- Les tables/séquences créées par de FUTURES migrations (owner) héritent des
-- mêmes droits automatiquement.
ALTER DEFAULT PRIVILEGES FOR ROLE erp_user IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_rls;
ALTER DEFAULT PRIVILEGES FOR ROLE erp_user IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO app_rls;

-- 4) AANA30 (C-AANA-002) — Rôle LECTURE SEULE de l'AGENT SQL (NL->SQL, FastAPI).
--    L'agent ne doit JAMAIS tourner sous le propriétaire de la base (en local
--    `erp_user` : rolsuper=t, rolbypassrls=t) : tout contournement du garde SQL
--    deviendrait une lecture/écriture sans limite. Rôle dédié :
--    LOGIN NOSUPERUSER NOBYPASSRLS, SELECT sur les SEULES tables de la liste
--    blanche de l'agent (`_ALLOWED_TABLES` de
--    backend/fastapi_ia/app/services/sql_agent_service.py — une seule source, le
--    test scripts/tests/test_agent_sql_role.py compare les deux), et AUCUN droit
--    d'écriture, de DDL, ni sur les futures tables (pas d'ALTER DEFAULT
--    PRIVILEGES : une table ajoutée à la liste blanche se re-grante ici, à la
--    main). `authentication_customuser` (table à secrets : hash de mot de
--    passe, jetons) est VOLONTAIREMENT exclue du GRANT : `SELECT count(*) FROM
--    authentication_customuser` est refusé par Postgres. Mot de passe : à CHOISIR
--    (`ALTER ROLE sql_agent_ro PASSWORD '<robuste>'`), puis le poser dans .env
--    (SQL_AGENT_DB_USER / SQL_AGENT_DB_PASSWORD) ; jamais committé.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sql_agent_ro') THEN
    CREATE ROLE sql_agent_ro LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD 'CHANGE_ME_ROBUSTE';
  ELSE
    ALTER ROLE sql_agent_ro LOGIN NOSUPERUSER NOBYPASSRLS;
  END IF;
END
$$;

GRANT CONNECT ON DATABASE erp_db TO sql_agent_ro;
GRANT USAGE ON SCHEMA public TO sql_agent_ro;
GRANT SELECT ON
    stock_produit,
    stock_categorie,
    stock_fournisseur,
    stock_mouvementstock,
    crm_client,
    ventes_devis,
    ventes_lignedevis,
    ventes_boncommande,
    ventes_facture,
    ventes_lignefacture,
    authentication_company,
    parametres_companyprofile,
    roles_role,
    ia_ocr_document,
    installations_installation,
    installations_intervention,
    sav_equipement,
    sav_ticket,
    sav_contratmaintenance,
    adsengine_adcampaignmirror,
    adsengine_insightsnapshot,
    adsengine_metaleadmirror
  TO sql_agent_ro;

-- Revert (défaire ce script) :
--   REVOKE ALL ON ALL TABLES IN SCHEMA public FROM sql_agent_ro;
--   REVOKE USAGE ON SCHEMA public FROM sql_agent_ro;
--   REVOKE CONNECT ON DATABASE erp_db FROM sql_agent_ro;
--   DROP ROLE sql_agent_ro;
--   REVOKE ALL ON ALL TABLES IN SCHEMA public FROM app_rls;
--   REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM app_rls;
--   REVOKE USAGE ON SCHEMA public FROM app_rls;
--   REVOKE CONNECT ON DATABASE erp_db FROM app_rls;
--   DROP ROLE app_rls;
--   -- (l'owner garde BYPASSRLS — inoffensif tant qu'aucune policy n'est posée)
