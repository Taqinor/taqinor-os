"""NTPLT61 — Import d'un tenant exporté dans une société VIDE (staging).

    python manage.py import_tenant tenant.zip --into <company_id> [--with-files]
        [--dry-run]

Symétrique de ``export_tenant`` (NTPLT60) : recrée les lignes du zip dans la
société cible avec REMAP complet des identifiants. Refuse une company
inexistante ou NON VIDE (jamais d'écrasement). Combiné à l'anonymisation
YHARD10, reproduit fidèlement un bug client sur staging sans données réelles.
JAMAIS exposé par API — opération d'exploitation uniquement.
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = ("Importe un tenant exporté (zip NTPLT60) dans une société vide, "
            "IDs remappés.")

    def add_arguments(self, parser):
        parser.add_argument(
            'zip_path', help='Chemin du zip d\'export du tenant.')
        parser.add_argument(
            '--into', required=True, type=int,
            help='ID de la société CIBLE (doit être vide).')
        parser.add_argument(
            '--with-files', action='store_true',
            help='(réservé) importer aussi les fichiers MinIO du manifeste.')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Analyse et ordre d\'import sans rien écrire.')

    def handle(self, *args, **options):
        from authentication.models import Company
        from core import tenant_import

        company_id = options['into']
        if not Company.objects.filter(pk=company_id).exists():
            raise CommandError(f'Société cible {company_id} introuvable.')

        dry_run = options['dry_run']
        if not dry_run and not tenant_import.target_is_empty(company_id):
            raise CommandError(
                f'Société cible {company_id} NON VIDE — import refusé '
                f'(on n\'écrase jamais une société existante).')

        try:
            summary = tenant_import.apply_import(
                company_id, options['zip_path'],
                with_files=options['with_files'], dry_run=dry_run)
        except tenant_import.TenantImportError as exc:
            raise CommandError(str(exc))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"[dry-run] {summary['rows']} ligne(s) sur "
                f"{summary['models']} modèle(s) seraient importées dans la "
                f"société {company_id}."))
            return
        self.stdout.write(self.style.SUCCESS(
            f"Import société {company_id} : {summary['rows']} ligne(s), "
            f"{summary['models']} modèle(s), "
            f"{summary['deferred_fk_patched']} FK différée(s) recâblée(s)."))
