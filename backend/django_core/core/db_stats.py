"""NTPLT19 — statistiques DB pour l'exploitant (SUPERUSER only, lecture seule).

Introspection Postgres READ-ONLY : top requêtes par temps total
(``pg_stat_statements``), tables par taille, index jamais utilisés. JAMAIS
exposé à un tenant — c'est une vue transverse d'exploitation. Chaque section
DÉGRADE PROPREMENT : si ``pg_stat_statements`` n'est pas préchargée
(``shared_preload_libraries``), la section renvoie un message au lieu de lever ;
sur un backend non-PostgreSQL (SQLite de test), tout est vide sans erreur.

Rappel : ces requêtes sont des SELECT d'introspection interne à NOTRE Postgres
d'application — sans rapport avec la règle #1 (qui interdit d'écrire dans la base
Odoo en SQL). Aucune écriture ici.
"""
from __future__ import annotations

from django.db import connection

_TOP_QUERIES_SQL = """
    SELECT queryid, calls,
           round(total_exec_time::numeric, 2) AS total_ms,
           round(mean_exec_time::numeric, 2) AS mean_ms,
           rows,
           left(query, 300) AS query
      FROM pg_stat_statements
     ORDER BY total_exec_time DESC
     LIMIT 20
"""

_TABLE_SIZE_SQL = """
    SELECT relname AS table,
           pg_total_relation_size(relid) AS total_bytes,
           pg_size_pretty(pg_total_relation_size(relid)) AS total_pretty,
           n_live_tup AS live_rows
      FROM pg_stat_user_tables
     ORDER BY pg_total_relation_size(relid) DESC
     LIMIT 20
"""

_UNUSED_INDEX_SQL = """
    SELECT relname AS table,
           indexrelname AS index,
           pg_size_pretty(pg_relation_size(indexrelid)) AS size,
           idx_scan AS scans
      FROM pg_stat_user_indexes
     WHERE idx_scan = 0
     ORDER BY pg_relation_size(indexrelid) DESC
     LIMIT 50
"""


def _rows(cursor):
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def collect_db_stats() -> dict:
    """Renvoie {top_queries, table_sizes, unused_indexes, pg_stat_statements}.

    Chaque section est isolée : une erreur (extension absente, droit manquant)
    remplit un champ ``error`` sur CETTE section sans casser les autres.
    """
    result = {
        'backend': connection.vendor,
        'pg_stat_statements': False,
        'top_queries': [],
        'table_sizes': [],
        'unused_indexes': [],
    }
    if connection.vendor != 'postgresql':
        result['detail'] = "Introspection disponible uniquement sur PostgreSQL."
        return result

    with connection.cursor() as cursor:
        # Top requêtes — nécessite pg_stat_statements préchargée.
        try:
            cursor.execute(_TOP_QUERIES_SQL)
            result['top_queries'] = _rows(cursor)
            result['pg_stat_statements'] = True
        except Exception as exc:  # noqa: BLE001 — extension absente → dégradé
            result['top_queries_error'] = (
                "pg_stat_statements indisponible (shared_preload_libraries ?) : "
                f"{exc}")

        for key, sql in (('table_sizes', _TABLE_SIZE_SQL),
                         ('unused_indexes', _UNUSED_INDEX_SQL)):
            try:
                cursor.execute(sql)
                result[key] = _rows(cursor)
            except Exception as exc:  # noqa: BLE001 — dégrade section par section
                result[f'{key}_error'] = str(exc)
    return result
