"""NTPLT2 — Génère/applique/révoque les politiques RLS Postgres par introspection.

Pour chaque modèle portant une FK ``company`` (découverte partagée avec le scan
d'isolation YRBAC12), active Row Level Security + une policy
``company_id = current_setting('app.current_company', true)::int``.

    python manage.py rls --dry-run   # imprime le SQL, ne touche RIEN (défaut)
    python manage.py rls --apply     # applique réellement (ENABLE+FORCE+policy)
    python manage.py rls --revert    # retire policy + désactive RLS

JAMAIS lancée automatiquement : c'est une bascule d'infrastructure délibérée
(elle suppose le GUC posé — NTPLT1 — et le rôle applicatif non-BYPASSRLS —
NTPLT3). Idempotente et réversible. Refuse sur un backend non-PostgreSQL.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from core import rls


class Command(BaseCommand):
    help = ('Active/désactive Row Level Security (RLS Postgres) sur les tables '
            'company-scopées. Dry-run par défaut ; jamais lancée automatiquement.')

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '--dry-run', action='store_true', default=False,
            help='Imprime le SQL sans rien exécuter (défaut si aucun mode).')
        group.add_argument(
            '--apply', action='store_true', default=False,
            help='Applique réellement RLS + les policies.')
        group.add_argument(
            '--revert', action='store_true', default=False,
            help='Retire les policies et désactive RLS.')

    def handle(self, *args, **options):
        action = 'apply' if options['apply'] else (
            'revert' if options['revert'] else 'dry-run')

        tables, statements = rls.build_statements(
            'revert' if action == 'revert' else 'apply')

        if not tables:
            self.stdout.write(self.style.WARNING(
                'rls: aucune table company-scopée découverte.'))
            return

        self.stdout.write(self.style.NOTICE(
            f"rls: {len(tables)} table(s) company-scopée(s) découverte(s)."))

        if action == 'dry-run':
            for stmt in statements:
                self.stdout.write(stmt)
            self.stdout.write(self.style.SUCCESS(
                f"rls --dry-run: {len(statements)} instruction(s) générée(s) "
                f"pour {len(tables)} table(s) (aucune exécution)."))
            return

        # apply / revert : exige PostgreSQL (RLS n'existe que là).
        if connection.vendor != 'postgresql':
            raise CommandError(
                'rls --apply/--revert exige PostgreSQL '
                f'(backend actuel : {connection.vendor}).')

        with transaction.atomic():
            with connection.cursor() as cursor:
                for stmt in statements:
                    cursor.execute(stmt)

        verb = 'appliqué' if action == 'apply' else 'révoqué'
        self.stdout.write(self.style.SUCCESS(
            f"rls --{action}: RLS {verb} sur {len(tables)} table(s) "
            f"({len(statements)} instruction(s))."))
