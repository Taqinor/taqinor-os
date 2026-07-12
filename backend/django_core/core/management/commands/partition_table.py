"""NTPLT37 — migre une table existante vers un partitionnement mensuel.

DRY-RUN PAR DÉFAUT : sans ``--apply``, la commande se contente d'AFFICHER le plan
SQL (création de la table shadow partitionnée, copie par lots, swap atomique) et
n'exécute RIEN. JAMAIS lancée automatiquement (aucune tâche beat ne l'appelle) —
opération d'exploitation ponctuelle, hors pointe, documentée dans
docs/online-migrations.md.

    python manage.py partition_table audit_auditlog --dry-run   # plan seulement
    python manage.py partition_table audit_auditlog --apply --key created_at

Garde-fous à l'``--apply`` : PostgreSQL uniquement ; refuse si ``<table>_old``
existe déjà (drill précédent non nettoyé) ; le swap est atomique (une seule
transaction) ; l'ancienne table est CONSERVÉE en ``<table>_old`` (revert immédiat
via ``--revert``).
"""
from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from core.partition_tooling import PartitionPlan


class Command(BaseCommand):
    help = ('Migre une table vers un partitionnement mensuel via table shadow + '
            'swap atomique. Dry-run par défaut. Jamais automatique.')

    def add_arguments(self, parser):
        parser.add_argument('table', help='Nom de la table à partitionner.')
        parser.add_argument(
            '--key', default='created_at',
            help='Colonne date/timestamp servant de clé de partition.')
        parser.add_argument(
            '--batch-size', type=int, default=50000,
            help='Taille des lots de copie (défaut 50000).')
        group = parser.add_mutually_exclusive_group()
        group.add_argument('--dry-run', action='store_true', default=True,
                           help='Affiche le plan sans rien exécuter (défaut).')
        group.add_argument('--apply', action='store_true', default=False,
                           help='Exécute réellement la migration (hors pointe).')
        group.add_argument('--revert', action='store_true', default=False,
                           help='Rétablit la table depuis <table>_old.')

    def _table_exists(self, name):
        with connection.cursor() as cur:
            cur.execute('SELECT to_regclass(%s)', [name])
            return cur.fetchone()[0] is not None

    def _date_range(self, table, key):
        with connection.cursor() as cur:
            cur.execute(
                f'SELECT MIN({key})::date, MAX({key})::date FROM {table}')
            lo, hi = cur.fetchone()
        return lo or date.today().replace(day=1), hi or date.today()

    def handle(self, *args, **options):
        table = options['table']
        key = options['key']
        apply_ = options['apply']
        revert = options['revert']

        if connection.vendor != 'postgresql':
            raise CommandError('partition_table : PostgreSQL uniquement.')

        if apply_ or revert:
            if not self._table_exists(table):
                raise CommandError(f'Table introuvable : {table}.')

        if revert:
            plan = PartitionPlan(table, key, date.today(), date.today())
            if not self._table_exists(plan.old):
                raise CommandError(f'{plan.old} introuvable : rien à revert.')
            with transaction.atomic():  # swap atomique
                self._execute(plan.revert_statements())
            self.stdout.write(self.style.SUCCESS(
                f'Revert de {table} effectué depuis {plan.old}.'))
            return

        if apply_:
            date_min, date_max = self._date_range(table, key)
        else:
            # Dry-run : bornes symboliques (le plan est illustratif).
            date_min, date_max = date.today().replace(day=1), date.today()

        plan = PartitionPlan(table, key, date_min, date_max,
                             batch_size=options['batch_size'])

        if not apply_:
            self.stdout.write(self.style.WARNING(
                f'DRY-RUN — plan de partitionnement de {table} (clé {key}) :'))
            for stmt in plan.full_plan():
                self.stdout.write('  ' + stmt)
            self.stdout.write(self.style.WARNING(
                'Rien exécuté. Relancer avec --apply hors pointe.'))
            return

        # --apply : garde-fou anti-résidu.
        if self._table_exists(plan.old):
            raise CommandError(
                f'{plan.old} existe déjà (drill précédent ?). Nettoyer avant.')

        self._execute(plan.create_statements())
        self._copy_batches(plan)
        with transaction.atomic():  # swap atomique original ↔ shadow
            self._execute(plan.swap_statements())
        self.stdout.write(self.style.SUCCESS(
            f'{table} partitionnée. Ancienne table conservée : {plan.old} '
            f'(revert : partition_table {table} --revert).'))

    def _copy_batches(self, plan: PartitionPlan):
        """Copie INSERT ... SELECT (le partitionnement route chaque ligne)."""
        with connection.cursor() as cur:
            cur.execute(
                f'INSERT INTO {plan.shadow} SELECT * FROM {plan.table}')

    def _execute(self, statements):
        with connection.cursor() as cur:
            for stmt in statements:
                s = stmt.strip()
                if not s or s.startswith('--') or s in ('BEGIN;', 'COMMIT;'):
                    continue
                cur.execute(s)
