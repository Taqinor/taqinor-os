"""NTPLT36 — Outillage de partitionnement mensuel (étend YOPSB11).

Helpers de FONDATION (aucun import d'app métier) pour gérer des tables
Postgres partitionnées par ``RANGE(date)`` avec des partitions MENSUELLES :

* ``partition_by_range_sql(table, date_col)`` — SQL de création d'une table
  PARENT partitionnée (à jouer via ``RunSQL`` dans une migration : Django ne
  modélise pas nativement ``PARTITION BY``).
* ``create_monthly_partition(table, year, month)`` — crée (idempotent) la
  partition d'un mois : ``<table>_YYYY_MM PARTITION OF <table>``.
* ``ensure_partitions(table, months_ahead=2, now=None)`` — crée le mois courant
  et les ``months_ahead`` suivants (crée M+1 et M+2 À L'AVANCE) ; idempotent.
* ``register_partitioned_table(table, date_col)`` — registre en mémoire des
  tables partitionnées, peuplé par chaque app dans son ``ready()`` ; consommé
  par la tâche beat ``core.ensure_partitions`` (``core.ensure_partitions``
  module) pour maintenir les partitions à l'avance.

Une table neuve destinée à naître partitionnée (p. ex. ``OutboxEvent``,
NTPLT9) crée son PARENT via ``partition_by_range_sql`` dans sa migration, puis
s'enregistre ici pour que le beat crée ses partitions futures — on prouve le
pattern sur une table NEUVE avant toute migration d'un existant (NTPLT37).
"""
from __future__ import annotations

import calendar
import logging

from django.db import connection

logger = logging.getLogger(__name__)

# Registre {table -> date_col} des tables partitionnées à maintenir. Peuplé par
# les apps dans leur ``ready()`` ; ``core`` n'y met rien de force.
_REGISTRY: dict = {}


def register_partitioned_table(table: str, date_col: str) -> None:
    """Déclare ``table`` (partitionnée par ``date_col``) à maintenir par le
    beat. Ré-enregistrer remplace (idempotent au rechargement d'app)."""
    _REGISTRY[table] = date_col


def registered_tables() -> dict:
    """Copie du registre {table -> date_col} (triée par table à l'usage)."""
    return dict(_REGISTRY)


def clear_registry() -> None:
    """Vide le registre (test uniquement)."""
    _REGISTRY.clear()


def partition_name(table: str, year: int, month: int) -> str:
    """Nom canonique d'une partition mensuelle : ``<table>_YYYY_MM``."""
    return f'{table}_{year:04d}_{month:02d}'


def _month_bounds(year: int, month: int):
    """Bornes ``[premier_jour_ce_mois, premier_jour_mois_suivant)`` (ISO)."""
    start = f'{year:04d}-{month:02d}-01'
    if month == 12:
        end = f'{year + 1:04d}-01-01'
    else:
        end = f'{year:04d}-{month + 1:02d}-01'
    return start, end


def partition_by_range_sql(table: str, date_col: str) -> str:
    """Retourne un commentaire-guide : Django crée la table via ``CreateModel``.

    Le vrai ``CREATE TABLE ... PARTITION BY RANGE`` se pose en ``RunSQL`` dans
    la migration (le PARENT ne peut pas être une table Django ordinaire). Cette
    fonction documente la clause à insérer, pour garder le SQL au même endroit.
    """
    return (f'-- PARENT partitionné : CREATE TABLE "{table}" (...) '
            f'PARTITION BY RANGE ("{date_col}");')


def create_monthly_partition(table: str, year: int, month: int,
                             cursor=None) -> str:
    """Crée (idempotent) la partition mensuelle de ``table`` pour ``year/month``.

    ``CREATE TABLE IF NOT EXISTS <table>_YYYY_MM PARTITION OF <table>
    FOR VALUES FROM (start) TO (end)`` — n'échoue pas si la partition existe
    déjà. Requiert que ``table`` soit un PARENT partitionné. Renvoie le nom de
    la partition.
    """
    name = partition_name(table, year, month)
    start, end = _month_bounds(year, month)
    sql = (
        f'CREATE TABLE IF NOT EXISTS "{name}" PARTITION OF "{table}" '
        f"FOR VALUES FROM ('{start}') TO ('{end}');"
    )
    if cursor is not None:
        cursor.execute(sql)
    else:
        with connection.cursor() as cur:
            cur.execute(sql)
    return name


def ensure_partitions(table: str, months_ahead: int = 2, now=None) -> list:
    """Crée le mois courant + les ``months_ahead`` mois suivants (idempotent).

    Garantit qu'une insertion tombant dans les prochaines semaines a toujours
    une partition prête. Renvoie la liste des partitions garanties (créées ou
    déjà présentes).
    """
    from django.utils import timezone
    now = now or timezone.now()
    year, month = now.year, now.month
    created = []
    for _ in range(months_ahead + 1):
        created.append(create_monthly_partition(table, year, month))
        # Avance d'un mois.
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return created


def list_partitions(table: str) -> list:
    """Noms des partitions existantes de ``table`` (via pg_inherits), triés."""
    sql = (
        'SELECT c.relname FROM pg_inherits i '
        'JOIN pg_class c ON c.oid = i.inhrelid '
        'JOIN pg_class p ON p.oid = i.inhparent '
        'WHERE p.relname = %s ORDER BY c.relname;'
    )
    with connection.cursor() as cur:
        cur.execute(sql, [table])
        rows = cur.fetchall()
    return [r[0] for r in rows]


def month_days(year: int, month: int) -> int:
    """Nombre de jours du mois (utilitaire, sans dépendance externe)."""
    return calendar.monthrange(year, month)[1]
