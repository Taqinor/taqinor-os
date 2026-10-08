"""ERR1 / ERR2 / ERR20 / ERR84 — Securite de l'agent NL->SQL au niveau du CODE.

Le prompt LLM ne suffit pas : ces tests verifient les gardes DETERMINISTES qui
s'executent AVANT toute requete, independamment du modele :
  - ERR1 : seule une (1) instruction SELECT en lecture seule passe ; toute DML/
    DDL / instruction multiple / CTE-avec-DML est refusee.
  - ERR2 : isolation tenant fail-closed — table hors allowlist, OR 1=1, JOIN/
    UNION vers une autre societe, table tenant non filtree => refus.
  - ERR20 : prix_achat / marge bloques au niveau requete (deja couvert par
    test_margin_guard ; on revalide l'integration du garde).
  - ERR84 : le SQL brut n'est jamais renvoye au client.

unittest (stdlib). A lancer depuis backend/fastapi_ia :
    python -m unittest discover -s tests

Les imports lourds (langchain) sont differes dans les methodes du service, mais
le module importe langchain.callbacks au chargement. Si une dependance manque,
le test se saute proprement (comme les autres suites du dossier).
"""
import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._import_optionnel import verifier_import_optionnel  # noqa: E402

try:
    from app.services import sql_agent_service as svc
    _IMPORT_ERR = None
except Exception as exc:  # pragma: no cover - dependances manquantes
    svc = None
    _IMPORT_ERR = exc
    verifier_import_optionnel(exc)


@unittest.skipIf(svc is None, f"sql_agent_service non importable: {_IMPORT_ERR}")
class SingleSelectEnforcementTests(unittest.TestCase):
    """ERR1 — seule une instruction SELECT en lecture seule est acceptee."""

    def _accept(self, sql):
        svc._enforce_single_select(sql)  # ne doit pas lever

    def _reject(self, sql):
        with self.assertRaises(svc.SQLSecurityError):
            svc._enforce_single_select(sql)

    def test_plain_select_ok(self):
        self._accept("SELECT nom FROM stock_produit WHERE company_id = 7")

    def test_lowercase_select_ok(self):
        self._accept("select count(*) from crm_client where company_id=7")

    def test_cte_select_ok(self):
        self._accept(
            "WITH c AS (SELECT id FROM crm_client WHERE company_id=7) "
            "SELECT * FROM c"
        )

    def test_insert_rejected(self):
        self._reject("INSERT INTO crm_client (nom) VALUES ('x')")

    def test_update_rejected(self):
        self._reject("UPDATE stock_produit SET quantite = 0")

    def test_delete_rejected(self):
        self._reject("DELETE FROM crm_client")

    def test_drop_rejected(self):
        self._reject("DROP TABLE crm_client")

    def test_alter_rejected(self):
        self._reject("ALTER TABLE crm_client ADD COLUMN x int")

    def test_create_rejected(self):
        self._reject("CREATE TABLE t (a int)")

    def test_grant_rejected(self):
        self._reject("GRANT ALL ON crm_client TO public")

    def test_truncate_rejected(self):
        self._reject("TRUNCATE crm_client")

    def test_copy_rejected(self):
        self._reject("COPY crm_client TO '/tmp/x.csv'")

    def test_select_into_rejected(self):
        # SELECT ... INTO cree une table -> interdit.
        self._reject("SELECT nom INTO newtbl FROM stock_produit")

    def test_multiple_statements_rejected(self):
        self._reject("SELECT 1; DROP TABLE crm_client")

    def test_trailing_second_select_rejected(self):
        self._reject("SELECT nom FROM stock_produit; SELECT 1")

    def test_cte_with_dml_rejected(self):
        self._reject(
            "WITH x AS (DELETE FROM crm_client RETURNING id) SELECT * FROM x"
        )

    def test_comment_masked_drop_is_neutralized(self):
        # Le DROP est dans un commentaire -> retire -> il reste un SELECT valide.
        svc._enforce_single_select(
            "SELECT nom FROM stock_produit -- ; DROP TABLE x\n"
        )


@unittest.skipIf(svc is None, f"sql_agent_service non importable: {_IMPORT_ERR}")
class TenantIsolationTests(unittest.TestCase):
    """ERR2 — isolation tenant fail-closed via _validate_and_secure(sql, 7)."""

    CID = 7

    def _ok(self, sql):
        return svc._validate_and_secure(sql, self.CID)

    def _reject(self, sql):
        with self.assertRaises(svc.SQLSecurityError):
            svc._validate_and_secure(sql, self.CID)

    def test_single_table_injects_company_id(self):
        out = self._ok("SELECT nom FROM stock_produit")
        self.assertIn("company_id = 7", out)
        _assert_every_table_scoped(self, out, self.CID)

    def test_single_table_with_where_injects(self):
        out = self._ok("SELECT nom FROM stock_produit WHERE quantite < 5")
        self.assertIn("company_id = 7", out)
        _assert_every_table_scoped(self, out, self.CID)

    def test_or_1_eq_1_neutralise_par_reecriture(self):
        # AANA2 — le OR ne peut plus rien ouvrir : la table lue EST deja la
        # sous-requete filtree sur la societe 7.
        out = self._ok(
            "SELECT nom FROM stock_produit WHERE company_id=7 OR 1=1")
        _assert_every_table_scoped(self, out, self.CID)

    def test_join_une_seule_table_filtree_reecrite(self):
        # Deux tables mais un seul predicat ecrit par le LLM : la seconde est
        # quand meme reecrite (plus de « preuve » par comptage de predicats).
        out = self._ok(
            "SELECT d.reference FROM ventes_devis d JOIN crm_client c "
            "ON d.client_id=c.id WHERE d.company_id=7"
        )
        _assert_every_table_scoped(self, out, self.CID)

    def test_join_both_scoped_ok(self):
        out = self._ok(
            "SELECT c.nom FROM crm_client c JOIN ventes_facture f "
            "ON f.client_id=c.id WHERE c.company_id=7 AND f.company_id=7"
        )
        _assert_every_table_scoped(self, out, self.CID)

    def test_union_cross_tenant_rejected(self):
        self._reject(
            "SELECT * FROM crm_client WHERE company_id=7 "
            "UNION SELECT * FROM crm_client WHERE company_id=8"
        )

    def test_foreign_company_literal_rejected(self):
        self._reject("SELECT * FROM crm_client WHERE company_id=8")

    def test_unknown_table_rejected(self):
        self._reject("SELECT * FROM pg_catalog.pg_user")

    def test_tenant_table_sans_filtre_reecrite_par_id(self):
        # La table societe est reecrite en `(SELECT * ... WHERE id = 7)`.
        out = self._ok("SELECT nom FROM authentication_company")
        _assert_every_table_scoped(self, out, self.CID)

    def test_tenant_table_with_id_ok(self):
        out = self._ok("SELECT nom FROM authentication_company WHERE id=7")
        _assert_every_table_scoped(self, out, self.CID)

    def test_zero_company_id_refused(self):
        with self.assertRaises(svc.SQLSecurityError):
            svc._validate_and_secure("SELECT nom FROM stock_produit", 0)

    def test_subquery_scoped_ok(self):
        out = self._ok(
            "SELECT reference FROM ventes_devis WHERE company_id=7 AND id IN "
            "(SELECT devis_id FROM ventes_lignedevis WHERE company_id=7)"
        )
        _assert_every_table_scoped(self, out, self.CID)

    def test_in_clause_allowed(self):
        # `IN (...)` est legitime (pas un OR) et doit passer apres injection.
        out = self._ok(
            "SELECT reference FROM installations_installation "
            "WHERE statut IN ('a_planifier','planifie')"
        )
        self.assertIn("company_id = 7", out)
        _assert_every_table_scoped(self, out, self.CID)

    # ── AANA2 — C-AANA-001 : la « preuve » par regex est contournee ─────────
    def test_predicat_societe_neutralise_rejete_ou_reecrit(self):
        """Les 5 requetes de la sonde du 05/10 etaient ACCEPTEES TELLES QUELLES
        (le texte contenait `company_id = 7`). Chacune doit maintenant etre
        rejetee ou reecrite pour que TOUTE table lue soit
        `(SELECT * FROM <t> WHERE company_id = 7)`."""
        for sql in SONDE_PREDICAT_NEUTRALISE:
            with self.subTest(sql=sql):
                try:
                    out = svc._validate_and_secure(sql, self.CID)
                except svc.SQLSecurityError:
                    continue
                _assert_every_table_scoped(self, out, self.CID)

    def test_cte_reference_reecrite_dans_son_corps(self):
        out = self._ok(
            "WITH c AS (SELECT id, nom FROM crm_client) "
            "SELECT c.nom FROM c JOIN ventes_devis d ON d.client_id = c.id"
        )
        _assert_every_table_scoped(self, out, self.CID)

    def test_cte_ne_masque_pas_une_vraie_table(self):
        # Une CTE n'est visible qu'APRES sa definition : `pg_user` dans le corps
        # de `a` est la vraie table catalogue -> refus.
        self._reject(
            "WITH a AS (SELECT * FROM pg_user), pg_user AS "
            "(SELECT id FROM crm_client) SELECT * FROM a"
        )

    def test_cte_homonyme_d_une_table_refusee(self):
        self._reject(
            "WITH crm_client AS (SELECT id FROM ventes_devis) "
            "SELECT id FROM crm_client"
        )

    def test_schema_etranger_refuse(self):
        self._reject("SELECT nom FROM autre_schema.crm_client")

    def test_fonction_en_position_de_table_refusee(self):
        self._reject("SELECT * FROM generate_series(1, 3)")

    def test_with_recursive_refuse(self):
        self._reject(
            "WITH RECURSIVE r AS (SELECT id FROM crm_client) "
            "SELECT id FROM r"
        )

    def test_commentaires_retires_du_sql_execute(self):
        out = self._ok("SELECT nom /* company_id = 7 */ FROM crm_client")
        self.assertNotIn("/*", out)
        _assert_every_table_scoped(self, out, self.CID)


@unittest.skipIf(svc is None, f"sql_agent_service non importable: {_IMPORT_ERR}")
class FunctionWhitelistTests(unittest.TestCase):
    """AANA3 — C-AANA-002 : toute fonction hors liste blanche (agregats,
    dates, chaines, arrondis) est refusee AVANT execution. La sonde du 05/10
    montrait `query_to_xml` lisant 155 clients de 2 societes et `pg_read_file`
    lisant un fichier du serveur."""

    CID = 7

    def test_fonctions_hors_liste_rejetees(self):
        hostiles = (
            "SELECT query_to_xml('select nom,email,company_id from crm_client'"
            ",true,true,'') FROM stock_categorie WHERE company_id = 7 LIMIT 1",
            "SELECT pg_read_file('/etc/passwd') FROM stock_categorie "
            "WHERE company_id = 7",
            "SELECT lo_export(1, '/tmp/x') FROM stock_categorie "
            "WHERE company_id = 7",
            "SELECT lo_import('/etc/passwd') FROM stock_categorie "
            "WHERE company_id = 7",
            "SELECT set_config('app.current_company','8',false) "
            "FROM stock_categorie WHERE company_id = 7",
            "SELECT pg_sleep(100000) FROM stock_categorie WHERE company_id = 7",
            "SELECT nom FROM crm_client WHERE company_id = 7 "
            "AND pg_sleep(100000) IS NOT NULL",
            "SELECT dblink('host=x', 'select 1') FROM stock_categorie "
            "WHERE company_id = 7",
            "SELECT current_setting('app.current_company') FROM crm_client",
            # Appel qualifie par un schema : meme un nom « autorise » est
            # refuse (il viserait une fonction homonyme d'un autre schema).
            "SELECT pg_catalog.pg_read_file('x') FROM crm_client",
            "SELECT public.sum(id) FROM crm_client",
            # Fonction-table en sous-requete.
            "SELECT nom FROM crm_client WHERE id IN "
            "(SELECT * FROM generate_series(1, 10))",
        )
        for sql in hostiles:
            with self.subTest(sql=sql):
                with self.assertRaises(svc.SQLSecurityError):
                    svc._validate_and_secure(sql, self.CID)

    def test_fonctions_metier_acceptees(self):
        acceptees = (
            "SELECT count(*), date_trunc('month', date_creation) "
            "FROM ventes_devis GROUP BY 2",
            "SELECT round(avg(montant_ttc), 2), sum(montant_ttc), "
            "max(date_echeance) FROM ventes_facture",
            "SELECT upper(nom), coalesce(email, ''), length(nom) "
            "FROM crm_client ORDER BY 1 LIMIT 100",
            "SELECT extract(year FROM date_creation), count(DISTINCT client_id)"
            " FROM ventes_devis GROUP BY 1",
            "SELECT to_char(date_creation, 'YYYY-MM'), "
            "row_number() OVER (ORDER BY date_creation) FROM ventes_devis",
            "SELECT numero_serie FROM sav_equipement WHERE date_fin_garantie "
            "BETWEEN CURRENT_DATE AND (CURRENT_DATE + INTERVAL '3 months')",
            "SELECT nom FROM crm_client c WHERE EXISTS (SELECT 1 FROM "
            "ventes_devis d WHERE d.client_id = c.id)",
            "SELECT CASE WHEN quantite <= seuil_alerte THEN 'rupture' "
            "ELSE 'ok' END, CAST(quantite AS INT) FROM stock_produit",
        )
        for sql in acceptees:
            with self.subTest(sql=sql):
                out = svc._validate_and_secure(sql, self.CID)
                _assert_every_table_scoped(self, out, self.CID)

    def test_instructions_non_select_toujours_refusees(self):
        for sql in (
            "SELECT nom FROM crm_client FOR UPDATE",
            "SET app.current_company = '8'",
            "SELECT set_config('x', '1', false)",
            "WITH x AS (UPDATE crm_client SET nom = 'x' RETURNING id) "
            "SELECT id FROM x",
        ):
            with self.subTest(sql=sql):
                with self.assertRaises(svc.SQLSecurityError):
                    svc._validate_and_secure(sql, self.CID)


@unittest.skipIf(svc is None, f"sql_agent_service non importable: {_IMPORT_ERR}")
class WholeRowProjectionTests(unittest.TestCase):
    """AANA4 — C-AANA-003 : une projection LIGNE ENTIERE (`row_to_json(u)`,
    `to_json[b]`, `alias.*`, `*`, `alias::text`) d'une table a secret ou a prix
    d'achat restituait le hash du mot de passe, la graine TOTP ou prix_achat
    sans jamais NOMMER la colonne (sonde du 05/10 : `row_to_json(u)` contenait
    la cle `password`)."""

    CID = 7

    def test_projection_ligne_entiere_table_sensible_rejetee(self):
        for sql in (
            "SELECT row_to_json(u) FROM authentication_customuser u "
            "WHERE u.company_id = 7",
            "SELECT to_json(u) FROM authentication_customuser u",
            "SELECT to_jsonb(u) FROM authentication_customuser u",
            "SELECT u::text FROM authentication_customuser u",
            "SELECT CAST(u AS TEXT) FROM authentication_customuser u",
            "SELECT array_agg(u) FROM authentication_customuser u",
            "SELECT (u).* FROM authentication_customuser u",
            "SELECT authentication_customuser FROM authentication_customuser",
            "SELECT p.* FROM stock_produit p WHERE p.company_id = 7",
            "SELECT * FROM stock_produit",
            "SELECT row_to_json(p) FROM stock_produit p",
            "SELECT p::text FROM stock_produit p",
            "SELECT * FROM ventes_devis",
            "SELECT marge_snapshot FROM ventes_devis",
            "SELECT x.nom FROM (SELECT * FROM stock_produit) x",
            "WITH x AS (SELECT * FROM authentication_customuser) "
            "SELECT x.username FROM x",
        ):
            with self.subTest(sql=sql):
                with self.assertRaises(svc.SQLSecurityError):
                    svc._validate_and_secure(sql, self.CID)
        self.assertTrue(svc._references_forbidden_column(
            "SELECT p.* FROM stock_produit p"))

    def test_secret_toujours_refuse_meme_avec_prix_autorise(self):
        with self.assertRaises(svc.SQLSecurityError):
            svc._validate_and_secure(
                "SELECT row_to_json(u) FROM authentication_customuser u",
                self.CID, allow_price=True)

    def test_prix_autorise_ouvre_la_ligne_produit(self):
        # Porteur de `prix_achat_voir` : la ligne produit n'a plus de secret.
        out = svc._validate_and_secure(
            "SELECT p.* FROM stock_produit p", self.CID, allow_price=True)
        _assert_every_table_scoped(self, out, self.CID)

    def test_projections_non_sensibles_acceptees(self):
        for sql in (
            "SELECT * FROM crm_client",
            "SELECT c.* FROM crm_client c",
            "SELECT array_agg(c) FROM crm_client c",
            "SELECT COUNT(*) FROM authentication_customuser",
            "SELECT username, email FROM authentication_customuser",
            "SELECT nom, prix_vente FROM stock_produit",
            "SELECT array_agg(x) FROM (SELECT nom, prix_vente "
            "FROM stock_produit) x",
            "SELECT c.* FROM crm_client c JOIN ventes_devis d "
            "ON d.client_id = c.id",
        ):
            with self.subTest(sql=sql):
                out = svc._validate_and_secure(sql, self.CID)
                _assert_every_table_scoped(self, out, self.CID)


# Sonde C-AANA-001 (dossier docs/audits/2026-10-05-analyse.md §5) : predicat
# societe present dans le TEXTE mais neutralise dans la LOGIQUE.
SONDE_PREDICAT_NEUTRALISE = (
    "SELECT nom,email FROM crm_client WHERE NOT (company_id = 7)",
    "SELECT nom,email FROM crm_client WHERE (company_id = 7) IS NOT NULL",
    "SELECT nom,email FROM crm_client WHERE company_id = 7 - 1",
    "SELECT company_id = 7 AS mine, nom, email FROM crm_client",
    "SELECT c.nom, c.email FROM crm_client c, ventes_devis d "
    "WHERE c.company_id = 7 AND 'company_id = 7' <> ''",
)


def _assert_every_table_scoped(test, secured_sql, company_id):
    """Verifie sur l'ARBRE du SQL reecrit que CHAQUE table lue est
    `(SELECT * FROM <t> WHERE company_id = <id>)` (ou `id = <id>` pour la
    table societe) — jamais une table nue."""
    import sqlglot
    from sqlglot import exp

    tree = sqlglot.parse_one(secured_sql, read="postgres")
    ctes = {(c.alias or "").lower() for c in tree.find_all(exp.CTE)}
    tables = [t for t in tree.find_all(exp.Table)
              if t.name.lower() not in ctes]
    test.assertTrue(tables, secured_sql)
    for table in tables:
        attendu = "id" if table.name == "authentication_company" else "company_id"
        select = table.parent.parent if isinstance(table.parent, exp.From) else None
        test.assertIsInstance(select, exp.Select, secured_sql)
        test.assertIsInstance(select.parent, exp.Subquery, secured_sql)
        test.assertEqual(len(select.args.get("joins") or []), 0, secured_sql)
        test.assertEqual(
            [type(e) for e in select.expressions], [exp.Star], secured_sql)
        where = select.args.get("where")
        test.assertIsNotNone(where, secured_sql)
        cond = where.this
        test.assertIsInstance(cond, exp.EQ, secured_sql)
        test.assertIsInstance(cond.this, exp.Column, secured_sql)
        test.assertEqual(cond.this.name, attendu, secured_sql)
        test.assertIsNone(cond.this.args.get("table"), secured_sql)
        test.assertEqual(cond.expression, exp.Literal.number(company_id),
                         secured_sql)


def _test_engine():
    """Moteur Postgres de TEST (variables DB_* explicites, comme le job
    release-verify) ou None : sans base configuree, le test se saute."""
    if not os.environ.get("DB_HOST"):
        return None
    try:
        from sqlalchemy import create_engine, text
        from urllib.parse import quote_plus
        url = "postgresql://{u}:{p}@{h}:{port}/{n}".format(
            u=os.environ.get("DB_USER", "erp_user"),
            p=quote_plus(os.environ.get("DB_PASSWORD", "")),
            h=os.environ["DB_HOST"],
            port=os.environ.get("DB_PORT", "5432"),
            n=os.environ.get("DB_NAME", "erp_db"),
        )
        engine = create_engine(url, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception:
        return None


@unittest.skipIf(svc is None, f"sql_agent_service non importable: {_IMPORT_ERR}")
class ReecritureSurPostgresTests(unittest.TestCase):
    """AANA2 — execution REELLE du SQL reecrit sur Postgres, 2 societes. Aucune
    table reelle n'est touchee : des tables TEMPORAIRES homonymes (pg_temp est
    prioritaire dans le search_path) sont creees dans une transaction annulee.
    Ni la base ni le garde ne sont simules."""

    def test_reecriture_isole_les_societes(self):
        engine = _test_engine()
        if engine is None:
            self.skipTest("Postgres de test non configure (DB_HOST absent).")
        from sqlalchemy import text
        with engine.connect() as conn:
            tx = conn.begin()
            try:
                conn.execute(text(
                    "CREATE TEMP TABLE crm_client (id int, nom text, "
                    "email text, company_id int)"))
                conn.execute(text(
                    "CREATE TEMP TABLE ventes_devis (id int, client_id int, "
                    "reference text, company_id int)"))
                conn.execute(text(
                    "INSERT INTO crm_client VALUES "
                    "(1,'A7','a@soc7',7),(2,'B7','b@soc7',7),"
                    "(3,'C8','c@soc8',8),(4,'D8','d@soc8',8),"
                    "(5,'E8','e@soc8',8)"))
                conn.execute(text(
                    "INSERT INTO ventes_devis VALUES "
                    "(1,1,'D7',7),(2,3,'D8',8)"))
                # Temoin positif : la societe 7 voit ses 2 clients.
                temoin = conn.execute(text(svc._validate_and_secure(
                    "SELECT nom, email FROM crm_client", 7))).fetchall()
                self.assertEqual(sorted(r[1] for r in temoin),
                                 ["a@soc7", "b@soc7"])
                for sql in SONDE_PREDICAT_NEUTRALISE:
                    with self.subTest(sql=sql):
                        try:
                            secured = svc._validate_and_secure(sql, 7)
                        except svc.SQLSecurityError:
                            continue
                        rows = conn.execute(text(secured)).fetchall()
                        valeurs = " ".join(str(v) for r in rows for v in r)
                        self.assertNotIn("soc8", valeurs, secured)
                        self.assertNotIn("C8", valeurs, secured)
            finally:
                tx.rollback()


@unittest.skipIf(svc is None, f"sql_agent_service non importable: {_IMPORT_ERR}")
class CombinedGuardTests(unittest.TestCase):
    """ERR1+ERR2 — un DML qui passerait l'isolation est quand meme refuse."""

    def test_dml_rejected_even_if_company_scoped(self):
        with self.assertRaises(svc.SQLSecurityError):
            svc._validate_and_secure(
                "UPDATE stock_produit SET quantite=0 WHERE company_id=7", 7)

    def test_prix_achat_still_flagged_at_query_layer(self):
        # ERR20 — le garde colonne confidentielle reste actif (test_margin_guard
        # couvre le tool ; ici on confirme la fonction de detection).
        self.assertTrue(
            svc._references_forbidden_column(
                "SELECT prix_achat FROM stock_produit WHERE company_id=7"))


@unittest.skipIf(svc is None, f"sql_agent_service non importable: {_IMPORT_ERR}")
class TenantGucTests(unittest.TestCase):
    """NTPLT4 — GUC app.current_company pose sur le moteur du SQL-agent.

    Defense en profondeur : meme une requete ecrite par le LLM ne peut pas lire
    un autre tenant. No-op sans POSTGRES_RLS_ENABLED (defaut).
    """

    class _FakeEngine:
        """Enregistre les listeners `connect` poses via sqlalchemy.event."""

    def _fake_db(self):
        db = type("FakeDB", (), {})()
        db._engine = self._FakeEngine()
        return db

    def test_rls_flag_off_by_default(self):
        with mock.patch.dict(os.environ, {"POSTGRES_RLS_ENABLED": "0"}):
            self.assertFalse(svc._rls_enabled())

    def test_rls_flag_on(self):
        with mock.patch.dict(os.environ, {"POSTGRES_RLS_ENABLED": "1"}):
            self.assertTrue(svc._rls_enabled())

    def test_apply_guc_noop_when_flag_off(self):
        # Flag OFF : aucun listener n'est enregistre (event.listens_for pas
        # appele du tout).
        db = self._fake_db()
        with mock.patch.dict(os.environ, {"POSTGRES_RLS_ENABLED": "0"}):
            with mock.patch("sqlalchemy.event.listens_for") as m_listen:
                svc._apply_tenant_guc(db, 7)
                m_listen.assert_not_called()

    def test_apply_guc_noop_when_company_missing(self):
        db = self._fake_db()
        with mock.patch.dict(os.environ, {"POSTGRES_RLS_ENABLED": "1"}):
            with mock.patch("sqlalchemy.event.listens_for") as m_listen:
                svc._apply_tenant_guc(db, 0)
                m_listen.assert_not_called()

    def test_apply_guc_registers_connect_listener_when_on(self):
        db = self._fake_db()
        with mock.patch.dict(os.environ, {"POSTGRES_RLS_ENABLED": "1"}):
            with mock.patch("sqlalchemy.event.listens_for") as m_listen:
                # listens_for renvoie un decorateur ; on l'imite.
                m_listen.return_value = lambda fn: fn
                svc._apply_tenant_guc(db, 7)
                m_listen.assert_called_once()
                # Le 2e argument positionnel est l'evenement "connect".
                args, _ = m_listen.call_args
                self.assertEqual(args[1], "connect")


if __name__ == "__main__":
    unittest.main()
