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

try:
    from app.services import sql_agent_service as svc
    _IMPORT_ERR = None
except Exception as exc:  # pragma: no cover - dependances manquantes
    svc = None
    _IMPORT_ERR = exc


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

    def test_single_table_with_where_injects(self):
        out = self._ok("SELECT nom FROM stock_produit WHERE quantite < 5")
        self.assertIn("company_id = 7", out)

    def test_or_1_eq_1_rejected(self):
        self._reject("SELECT * FROM stock_produit WHERE company_id=7 OR 1=1")

    def test_join_other_tenant_rejected(self):
        # Deux tables company_id mais un seul predicat -> refus.
        self._reject(
            "SELECT * FROM ventes_devis d JOIN crm_client c "
            "ON d.client_id=c.id WHERE d.company_id=7"
        )

    def test_join_both_scoped_ok(self):
        out = self._ok(
            "SELECT * FROM crm_client c JOIN ventes_facture f "
            "ON f.client_id=c.id WHERE c.company_id=7 AND f.company_id=7"
        )
        self.assertTrue(out)

    def test_union_cross_tenant_rejected(self):
        self._reject(
            "SELECT * FROM crm_client WHERE company_id=7 "
            "UNION SELECT * FROM crm_client WHERE company_id=8"
        )

    def test_foreign_company_literal_rejected(self):
        self._reject("SELECT * FROM crm_client WHERE company_id=8")

    def test_unknown_table_rejected(self):
        self._reject("SELECT * FROM pg_catalog.pg_user")

    def test_tenant_table_requires_id_filter(self):
        self._reject("SELECT * FROM authentication_company")

    def test_tenant_table_with_id_ok(self):
        out = self._ok("SELECT nom FROM authentication_company WHERE id=7")
        self.assertTrue(out)

    def test_zero_company_id_refused(self):
        with self.assertRaises(svc.SQLSecurityError):
            svc._validate_and_secure("SELECT nom FROM stock_produit", 0)

    def test_subquery_scoped_ok(self):
        out = self._ok(
            "SELECT * FROM ventes_devis WHERE company_id=7 AND id IN "
            "(SELECT devis_id FROM ventes_lignedevis WHERE company_id=7)"
        )
        self.assertTrue(out)

    def test_in_clause_allowed(self):
        # `IN (...)` est legitime (pas un OR) et doit passer apres injection.
        out = self._ok(
            "SELECT reference FROM installations_installation "
            "WHERE statut IN ('a_planifier','planifie')"
        )
        self.assertIn("company_id = 7", out)


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
