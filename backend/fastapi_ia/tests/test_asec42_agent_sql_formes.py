"""ASEC42 — trois formes que la liste d'acceptation d'AANA2 ne citait pas.

Constat C-ASEC-011 : `UNION`/`UNION ALL` sur la même table, sous-requête
scalaire (agrégat dans la liste SELECT) et littéral de chaîne imitant le filtre
sur une requête MONO-table. Attendu : soit `SQLSecurityError`, soit une
requête réécrite dont CHAQUE lecture de table est la sous-requête filtrée
d'AANA2 ; et, exécutée sur une vraie base Postgres à deux sociétés, aucune
ligne de l'autre société (l'oracle est le comptage réel, pas une regex).

Les formes sont jouées sur `crm_client` puis sur `authentication_customuser`.
L'exécution réelle utilise des tables TEMPORAIRES homonymes (pg_temp est
prioritaire dans le search_path) dans une transaction annulée : aucune table
réelle n'est touchée, ni la base ni le garde ne sont simulés. Sans Postgres de
test configuré (DB_HOST), seule la vérification d'arbre s'exécute.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests._import_optionnel import verifier_import_optionnel  # noqa: E402

try:  # pragma: no cover - dépend des dépendances installées
    from app.services import sql_agent_service as svc
    _IMPORT_ERR = None
except Exception as exc:  # pragma: no cover
    svc = None
    _IMPORT_ERR = exc
    verifier_import_optionnel(exc)

CID = 7
AUTRE = 8

#: (nom, gabarit) — `{t}` = table lue, colonne `email` présente dans les deux.
FORMES = {
    "union": (
        "SELECT email FROM {t} UNION SELECT email FROM {t}",
        "SELECT email FROM {t} UNION ALL SELECT email FROM {t}",
    ),
    "scalaire": (
        "SELECT (SELECT count(*) FROM {t}) AS total",
        "SELECT email, (SELECT max(email) FROM {t}) AS dernier "
        "FROM {t} WHERE company_id = 7",
    ),
    "litteral": (
        "SELECT email FROM {t} WHERE 'company_id = 7' <> ''",
        "SELECT email FROM {t} WHERE email <> 'company_id = 7'",
    ),
}
TABLES = ("crm_client", "authentication_customuser")


def _securiser(sql):
    """Renvoie le SQL réécrit, ou None si le garde refuse (acceptable)."""
    try:
        return svc._validate_and_secure(sql, CID)
    except svc.SQLSecurityError:
        return None


def _assert_chaque_table_filtree(test, secured_sql):
    """Sur l'ARBRE réécrit : chaque table lue est
    `(SELECT * FROM <t> WHERE company_id = 7)` — jamais une table nue."""
    import sqlglot
    from sqlglot import exp

    tree = sqlglot.parse_one(secured_sql, read="postgres")
    ctes = {(c.alias or "").lower() for c in tree.find_all(exp.CTE)}
    tables = [t for t in tree.find_all(exp.Table)
              if t.name.lower() not in ctes]
    test.assertTrue(tables, secured_sql)
    for table in tables:
        select = (table.parent.parent
                  if isinstance(table.parent, exp.From) else None)
        test.assertIsInstance(select, exp.Select, secured_sql)
        test.assertIsInstance(select.parent, exp.Subquery, secured_sql)
        test.assertEqual(len(select.args.get("joins") or []), 0, secured_sql)
        cond = select.args.get("where").this
        test.assertIsInstance(cond, exp.EQ, secured_sql)
        test.assertEqual(cond.this.name, "company_id", secured_sql)
        test.assertEqual(cond.expression, exp.Literal.number(CID),
                         secured_sql)


def _moteur_test():
    """Moteur Postgres de TEST (variables DB_* explicites) ou None."""
    if not os.environ.get("DB_HOST"):
        return None
    try:
        from urllib.parse import quote_plus

        from sqlalchemy import create_engine, text
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
class _Base(unittest.TestCase):
    forme = None

    def _verifier(self):
        requetes = [g.format(t=t) for t in TABLES for g in FORMES[self.forme]]
        securisees = []
        for sql in requetes:
            with self.subTest(sql=sql):
                secured = _securiser(sql)
                if secured is not None:
                    _assert_chaque_table_filtree(self, secured)
                    securisees.append((sql, secured))
        self._executer(securisees)

    def _executer(self, securisees):
        engine = _moteur_test()
        if engine is None:
            return  # vérification d'arbre seule (pas de Postgres de test)
        from sqlalchemy import text
        with engine.connect() as conn:
            tx = conn.begin()
            try:
                for table in TABLES:
                    conn.execute(text(
                        f"CREATE TEMP TABLE {table} (id int, email text, "
                        "company_id int)"))
                    conn.execute(text(
                        f"INSERT INTO {table} VALUES "
                        "(1,'a@soc7',7),(2,'b@soc7',7),"
                        "(3,'c@soc8',8),(4,'d@soc8',8),(5,'e@soc8',8)"))
                for sql, secured in securisees:
                    with self.subTest(sql=sql):
                        rows = conn.execute(text(secured)).fetchall()
                        valeurs = " ".join(
                            str(v) for r in rows for v in r)
                        self.assertNotIn("soc8", valeurs, secured)
                        if "count(" in sql:
                            # Comptage réel : 2 lignes de la société 7.
                            self.assertEqual(rows[0][0], 2, secured)
            finally:
                tx.rollback()


class UnionTests(_Base):
    forme = "union"

    def test_union_meme_table_isole(self):
        self._verifier()


class ScalaireTests(_Base):
    forme = "scalaire"

    def test_sous_requete_scalaire_isolee(self):
        self._verifier()


class LitteralTests(_Base):
    forme = "litteral"

    def test_litteral_mono_table_isole(self):
        self._verifier()
