"""PUB106 — Chat NL « interroge ton compte pub » : les miroirs adsengine sont
LECTURE SEULE, company-scopes, et decrits pour l'agent SQL.

Prouve : les tables adsengine sont dans l'allowlist + porteuses de company_id +
decrites ; les 5 questions dorees produisent des SELECT valides et scopes ; toute
tentative d'ECRITURE est refusee ; une tentative de lire une AUTRE societe est
refusee (isolation multi-tenant) ; la table des credentials n'est jamais lisible.

unittest (stdlib). Le module importe langchain au runtime seulement ; on
n'inspecte ici que les constantes + la couche de securite SQL (pas de LLM, pas
de DB). Sans cle LLM, l'agent est indisponible proprement (comportement existant).
"""
import os
import sys
import unittest

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.services import sql_agent_service as svc
    _IMPORT_ERR = None
except Exception as exc:  # pragma: no cover - dependances manquantes
    svc = None
    _IMPORT_ERR = exc

_ADS_TABLES = [
    "adsengine_adcampaignmirror",
    "adsengine_insightsnapshot",
    "adsengine_metaleadmirror",
]

# 5 questions dorees → SQL de LECTURE mono-table (auto-scope par company_id).
_GOLDEN_QUERIES = [
    # « Combien ai-je depense cette semaine ? »
    "SELECT SUM(spend) FROM adsengine_insightsnapshot WHERE date >= '2026-07-13'",
    # « Combien de leads publicitaires ai-je eu ? »
    "SELECT COUNT(*) FROM adsengine_metaleadmirror",
    # « Quelles sont mes campagnes ? »
    "SELECT name, status FROM adsengine_adcampaignmirror",
    # « Combien de leads pour la campagne 123 ? »
    "SELECT COUNT(*) FROM adsengine_metaleadmirror WHERE campaign_id = '123'",
    # « Quelle depense en mai ? »
    "SELECT SUM(spend) FROM adsengine_insightsnapshot "
    "WHERE date >= '2026-05-01' AND date <= '2026-05-31'",
]


@unittest.skipIf(svc is None, f"sql_agent_service non importable: {_IMPORT_ERR}")
class AdsengineNlRegistryTests(unittest.TestCase):
    def test_tables_in_allowlist(self):
        for t in _ADS_TABLES:
            self.assertIn(t, svc._ALLOWED_TABLES, t)

    def test_tables_company_scoped(self):
        for t in _ADS_TABLES:
            self.assertIn(t, svc._TABLES_WITH_COMPANY_ID, t)

    def test_tables_described(self):
        for t in _ADS_TABLES:
            self.assertIn(t, svc._TABLE_DESCRIPTIONS, t)
            self.assertTrue(svc._TABLE_DESCRIPTIONS[t].strip(), t)

    def test_credentials_table_never_readable(self):
        # La table des credentials Meta (token write-only) n'est JAMAIS exposee.
        self.assertNotIn("adsengine_metaconnection", svc._ALLOWED_TABLES)
        self.assertNotIn("adsengine_metaconnection", svc._TENANT_SCOPED_TABLES)


@unittest.skipIf(svc is None, f"sql_agent_service non importable: {_IMPORT_ERR}")
class AdsengineNlSecurityTests(unittest.TestCase):
    def test_golden_queries_validate_and_scope(self):
        for sql in _GOLDEN_QUERIES:
            secured = svc._validate_and_secure(sql, 7)
            self.assertIn("company_id = 7", secured, sql)

    def test_write_attempts_refused(self):
        writes = [
            "UPDATE adsengine_insightsnapshot SET spend = 0",
            "DELETE FROM adsengine_metaleadmirror",
            "INSERT INTO adsengine_adcampaignmirror (name) VALUES ('x')",
            "DROP TABLE adsengine_insightsnapshot",
        ]
        for sql in writes:
            with self.assertRaises(svc.SQLSecurityError, msg=sql):
                svc._validate_and_secure(sql, 7)

    def test_cross_company_read_refused(self):
        # Un appelant de la societe 7 ne peut pas lire les lignes de la societe 9.
        sql = "SELECT SUM(spend) FROM adsengine_insightsnapshot WHERE company_id = 9"
        with self.assertRaises(svc.SQLSecurityError):
            svc._validate_and_secure(sql, 7)

    def test_company_filter_injected(self):
        out = svc._inject_company_filter(
            "SELECT COUNT(*) FROM adsengine_metaleadmirror", 42)
        self.assertIn("company_id = 42", out)


if __name__ == "__main__":
    unittest.main()
