"""NTPLT60 — Export intégral d'un tenant (portabilité société entière).

    python manage.py export_tenant --company <id> --out tenant.zip

Écrit un zip = un JSON par modèle company-scopé (serializers Django) +
manifeste des fichiers MinIO du tenant + checksums SHA-256. Complète
``core/dsr.py`` (DSR individuel CNDP) par la portabilité de TOUTE la société —
la réponse standard aux DSI qui demandent « et si on part ? ».
"""
from django.core.management.base import BaseCommand, CommandError

from core import dsr


class Command(BaseCommand):
    help = "Exporte l'intégralité des données d'une société dans un zip."

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', required=True, type=int,
            help='ID de la société à exporter.')
        parser.add_argument(
            '--out', required=True,
            help='Chemin du fichier zip de sortie (ex. tenant.zip).')

    def handle(self, *args, **options):
        from authentication.models import Company

        company_id = options['company']
        if not Company.objects.filter(pk=company_id).exists():
            raise CommandError(f'Société {company_id} introuvable.')

        out_path = options['out']
        summary = dsr.export_tenant(company_id, out_path)
        self.stdout.write(self.style.SUCCESS(
            f"Export société {company_id} : {summary['models']} modèle(s), "
            f"{summary['rows']} ligne(s), {summary['files']} fichier(s) MinIO "
            f"-> {summary['out']}"))
