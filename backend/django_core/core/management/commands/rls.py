"""NTPLT2 — Génère/applique/révoque les politiques RLS Postgres par introspection.

Pour chaque modèle portant une FK ``company`` (découverte partagée avec le scan
d'isolation YRBAC12), active Row Level Security + une policy
``company_id = current_setting('app.current_company', true)::int``.

    python manage.py rls --dry-run   # imprime le SQL, ne touche RIEN (défaut)
    python manage.py rls --apply     # applique réellement (ENABLE+FORCE+policy)
    python manage.py rls --revert    # retire policy + désactive RLS

AUD422 — ``--only`` permet un déploiement ÉTAGÉ (le tout-ou-rien d'origine
était la raison pour laquelle RLS n'a jamais été activé sur AUCUNE table) :

    python manage.py rls --dry-run --only argent
    python manage.py rls --apply --only compta.EcritureComptable,facturation.Facture

Les 5 tables argent sont d'ailleurs posées par MIGRATION (compta, ventes,
facturation) : la commande reste l'outil d'inspection et d'élargissement.

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
        # AUD422 — déploiement ÉTAGÉ. Sans cette option la commande était
        # tout-ou-rien sur les ~900 tables company-scopées : le seul geste
        # possible était un big-bang que personne n'ose lancer, et RLS n'a donc
        # JAMAIS été activé sur une seule table depuis NTPLT2.
        parser.add_argument(
            '--only', default='',
            help="Restreint à une liste de modèles « app_label.Model » séparés "
                 "par des virgules (ex. compta.EcritureComptable,"
                 "facturation.Facture). Un libellé inconnu FAIT ÉCHOUER la "
                 "commande — jamais un silence. Raccourci : « argent » vise "
                 "les 5 tables argent (core.rls.TABLES_ARGENT).")

    def _labels(self, brut):
        """Résout ``--only`` : '' → None (tout), 'argent' → TABLES_ARGENT."""
        valeur = (brut or '').strip()
        if not valeur:
            return None
        if valeur.lower() == 'argent':
            return list(rls.TABLES_ARGENT)
        return [part.strip() for part in valeur.split(',') if part.strip()]

    def handle(self, *args, **options):
        action = 'apply' if options['apply'] else (
            'revert' if options['revert'] else 'dry-run')

        try:
            only = self._labels(options.get('only'))
            tables, statements = rls.build_statements(
                'revert' if action == 'revert' else 'apply', only=only)
        except ValueError as exc:
            raise CommandError(str(exc))

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
