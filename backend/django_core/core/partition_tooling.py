"""NTPLT37 — outillage de migration d'une table existante vers le partitionnement.

Convertir une grosse table à croissance monotone (ex. ``audit_auditlog``, des
journaux à 100 M de lignes) en table PARTITIONNÉE par mois rend la purge
instantanée (``DROP PARTITION`` au lieu d'un ``DELETE`` massif) et garde les
requêtes récentes rapides (partition pruning). Postgres ne sait PAS convertir
une table simple en table partitionnée en place : on passe par une table SHADOW
partitionnée, une copie par lots hors pointe, puis un SWAP atomique — l'ancienne
table est CONSERVÉE en ``<table>_old`` pour un revert immédiat.

Ce module GÉNÈRE le plan SQL (testable sans base). L'exécution (dry-run par
défaut) vit dans la commande ``partition_table``. JAMAIS lancée automatiquement —
c'est une opération d'exploitation ponctuelle, documentée dans
docs/online-migrations.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List


def _month_starts(start: date, end: date) -> List[date]:
    """Premiers jours de chaque mois de start..end inclus (bornes mensuelles)."""
    months = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append(date(y, m, 1))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def _next_month(d: date) -> date:
    return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)


@dataclass
class PartitionPlan:
    table: str
    key: str
    date_min: date
    date_max: date
    batch_size: int = 50000
    shadow: str = field(init=False)
    old: str = field(init=False)

    def __post_init__(self):
        self.shadow = f'{self.table}_part_new'
        self.old = f'{self.table}_old'

    def partitions(self) -> List[dict]:
        """Une partition mensuelle par mois couvrant [date_min, date_max]."""
        out = []
        for start in _month_starts(self.date_min, self.date_max):
            end = _next_month(start)
            out.append({
                'name': f'{self.table}_p{start:%Y%m}',
                'from': start.isoformat(),
                'to': end.isoformat(),
            })
        return out

    def create_statements(self) -> List[str]:
        """DDL de création de la table shadow + ses partitions mensuelles."""
        stmts = [
            f'CREATE TABLE {self.shadow} '
            f'(LIKE {self.table} INCLUDING DEFAULTS INCLUDING CONSTRAINTS) '
            f'PARTITION BY RANGE ({self.key});'
        ]
        for p in self.partitions():
            stmts.append(
                f"CREATE TABLE {p['name']} PARTITION OF {self.shadow} "
                f"FOR VALUES FROM ('{p['from']}') TO ('{p['to']}');")
        return stmts

    def swap_statements(self) -> List[str]:
        """SWAP atomique : original → _old, shadow → nom original (une TX)."""
        return [
            'BEGIN;',
            f'ALTER TABLE {self.table} RENAME TO {self.old};',
            f'ALTER TABLE {self.shadow} RENAME TO {self.table};',
            'COMMIT;',
        ]

    def revert_statements(self) -> List[str]:
        """Revert : rétablit l'ancienne table depuis ``_old``."""
        return [
            'BEGIN;',
            f'ALTER TABLE {self.table} RENAME TO {self.shadow};',
            f'ALTER TABLE {self.old} RENAME TO {self.table};',
            'COMMIT;',
        ]

    def full_plan(self) -> List[str]:
        return self.create_statements() + [
            f'-- copie par lots de {self.batch_size} lignes '
            f'(INSERT ... SELECT hors pointe) depuis {self.table}',
        ] + self.swap_statements() + [
            f'-- {self.old} CONSERVÉE pour revert ; DROP TABLE {self.old} '
            f'seulement après validation.',
        ]
