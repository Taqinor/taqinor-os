"""NTIDE24 — ``manage.py export_ideas [--company SLUG] [--out-file PATH]``.

Exporte les idées (titre/description/auteur/…) au format JSON (dev/test
uniquement). Sans ``--company`` : exporte TOUTES les sociétés (chaque
enregistrement porte son propre slug de société). Sans ``--out-file`` :
écrit sur stdout (redirigeable).

Exemples :
  python manage.py export_ideas --company taqinor-demo --out-file /tmp/idees.json
  python manage.py export_ideas > idees.json
"""
import json

from django.core.management.base import BaseCommand, CommandError

from apps.innovation.data_io import export_ideas


class Command(BaseCommand):
    help = (
        'Exporte les idées (NTIDE1) en JSON — dev/test. --company filtre '
        'par slug société (vide = toutes) ; --out-file écrit dans un '
        'fichier (défaut : stdout).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help='Slug de la société à exporter (vide = toutes).')
        parser.add_argument(
            '--out-file', default=None,
            help='Fichier de sortie (défaut : stdout).')

    def handle(self, *args, **opts):
        from authentication.models import Company

        company = None
        slug = opts.get('company')
        if slug:
            try:
                company = Company.objects.get(slug=slug)
            except Company.DoesNotExist:
                raise CommandError(f'Société introuvable : {slug}')

        data = export_ideas(company=company)
        payload = json.dumps(data, ensure_ascii=False, indent=2)

        out_file = opts.get('out_file')
        if out_file:
            with open(out_file, 'w', encoding='utf-8') as fh:
                fh.write(payload)
            self.stdout.write(self.style.SUCCESS(
                f'{len(data)} idée(s) exportée(s) → {out_file}'))
        else:
            self.stdout.write(payload)
