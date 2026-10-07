"""Tests AANA30 — provisionnement du rôle Postgres restreint de l'agent SQL.

Stdlib pure (unittest), sans Postgres : on lit le fichier d'initialisation
(``backend/db/rls_roles.sql``), ``.env.example`` et ``docker-compose.yml``, et on
compare les GRANT à la liste blanche RÉELLE de l'agent
(``_ALLOWED_TABLES`` de ``backend/fastapi_ia/app/services/sql_agent_service.py``,
lue par AST — une seule source, jamais recopiée). Run :
    python -m unittest scripts.tests.test_agent_sql_role -v
"""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SQL = ROOT / "backend" / "db" / "rls_roles.sql"
ENV_EXAMPLE = ROOT / ".env.example"
COMPOSE = ROOT / "docker-compose.yml"
SERVICE = ROOT / "backend" / "fastapi_ia" / "app" / "services" / "sql_agent_service.py"
ROLE = "sql_agent_ro"


def _liste_service(nom: str) -> list:
    tree = ast.parse(SERVICE.read_text(encoding="utf-8"))
    for noeud in tree.body:
        cible = None
        if isinstance(noeud, ast.Assign) and isinstance(noeud.targets[0], ast.Name):
            cible = noeud.targets[0].id
        if cible == nom:
            return [e.value for e in noeud.value.elts]
    raise AssertionError(f"{nom} introuvable dans sql_agent_service.py")


def _sql_sans_commentaires(texte: str) -> str:
    return "\n".join(re.sub(r"--.*$", "", ligne) for ligne in texte.splitlines())


def _tables_grantees(sql: str) -> list:
    """Tables de ``GRANT SELECT ON <t1, t2…> TO sql_agent_ro`` (hors ALL TABLES)."""
    m = re.search(r"GRANT\s+SELECT\s+ON\s+(.*?)\s+TO\s+" + ROLE + r"\b", sql,
                  re.S | re.I)
    assert m, "aucun GRANT SELECT ... TO sql_agent_ro"
    return [t.strip() for t in m.group(1).split(",") if t.strip()]


class TestRoleAgentSql(unittest.TestCase):
    def setUp(self):
        self.sql = _sql_sans_commentaires(SQL.read_text(encoding="utf-8"))

    def test_init_cree_role_restreint(self):
        self.assertRegex(self.sql, r"CREATE\s+ROLE\s+" + ROLE
                         + r"\s+LOGIN\s+NOSUPERUSER\s+NOBYPASSRLS")
        self.assertRegex(self.sql, r"ALTER\s+ROLE\s+" + ROLE
                         + r"\s+LOGIN\s+NOSUPERUSER\s+NOBYPASSRLS")
        # Aucun « ALL TABLES », aucun droit par defaut sur les futures tables,
        # aucun droit d'ecriture/DDL pour ce role.
        for ligne in self.sql.split(";"):
            if ROLE not in ligne:
                continue
            self.assertNotRegex(ligne, r"(?i)ALL\s+TABLES")
            self.assertNotRegex(ligne, r"(?i)DEFAULT\s+PRIVILEGES")
            if re.search(r"(?i)\bGRANT\b", ligne):
                self.assertNotRegex(
                    ligne, r"(?i)\b(INSERT|UPDATE|DELETE|TRUNCATE|REFERENCES|"
                           r"TRIGGER|CREATE|ALL\s+PRIVILEGES)\b")

    def test_grants_egaux_a_la_liste_blanche_de_l_agent(self):
        # Une seule source : la liste de l'agent, moins la table a secrets.
        attendu = [t for t in _liste_service("_ALLOWED_TABLES")
                   if t not in _liste_service("_SECRET_TABLES")]
        self.assertEqual(sorted(_tables_grantees(self.sql)), sorted(attendu))

    def test_table_a_secrets_refusee(self):
        # SELECT count(*) FROM authentication_customuser doit etre refuse :
        # la table n'est ni dans un GRANT du role, ni via ALL TABLES.
        self.assertNotIn("authentication_customuser", _tables_grantees(self.sql))
        self.assertIn("authentication_customuser", _liste_service("_SECRET_TABLES"))

    def test_env_example_documente_les_trois_variables(self):
        texte = ENV_EXAMPLE.read_text(encoding="utf-8")
        for nom in ("SQL_AGENT_DB_USER", "SQL_AGENT_DB_PASSWORD",
                    "AGENT_HMAC_SECRET"):
            self.assertRegex(texte, r"(?m)^#?\s*" + nom + r"=", nom)
        # Jamais de secret reel dans le depot : valeurs vides ou « change_me ».
        for nom in ("SQL_AGENT_DB_PASSWORD", "AGENT_HMAC_SECRET"):
            valeur = re.search(r"(?m)^#?\s*" + nom + r"=(.*)$", texte).group(1)
            self.assertTrue(not valeur.strip() or "change_me" in valeur, nom)

    def test_compose_n_accorde_plus_select_sur_toutes_les_tables(self):
        # Test-du-test : retablir « SELECT ON ALL TABLES » dans le compose
        # (l'ancien gabarit de provisionnement) fait echouer ce test.
        compose = COMPOSE.read_text(encoding="utf-8")
        self.assertNotRegex(
            compose, r"(?i)GRANT\s+SELECT\s+ON\s+ALL\s+TABLES[^\n]*" + ROLE)
        self.assertIn("rls_roles.sql", compose)


if __name__ == "__main__":
    unittest.main()
