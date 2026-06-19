"""N97 — Export en ligne de commande des données d'UNE société (admin / serveur).

Génère, dans un répertoire de sortie EXPLICITE (jamais le dépôt), un fichier
par objet OU un ZIP de sauvegarde. Strictement filtré par société. Le prix
d'achat (``Produit.prix_achat``) n'est jamais exporté (cf. export_registry).

``--out-dir`` est OBLIGATOIRE et ne doit jamais pointer vers le dépôt : aucune
donnée réelle n'est committée.

Exemples :
  python manage.py export_company_data --company-slug taqinor-demo \\
      --out-dir /tmp/export --format csv
  python manage.py export_company_data --company-slug taqinor-demo \\
      --out-dir /tmp/export --zip --objects clients,leads,devis
"""
import datetime
import os

from django.core.management.base import BaseCommand, CommandError

from apps.dataimport.exporters import (
    DEFAULT_FORMAT, FORMATS, backup_filename, build_backup_zip,
    export_bytes, filename_for,
)
from apps.dataimport.export_registry import DEFAULT_OBJECTS, REGISTRY


class Command(BaseCommand):
    help = (
        "Exporte les données d'une société (CSV/XLSX/JSON ou ZIP). "
        "Toujours filtré par société ; jamais de prix d'achat."
    )

    def add_arguments(self, parser):
        parser.add_argument('--company-slug', required=True,
                            help='Slug de la société à exporter.')
        parser.add_argument('--out-dir', required=True,
                            help='Répertoire de sortie (jamais le dépôt).')
        parser.add_argument('--format', default=DEFAULT_FORMAT,
                            choices=list(FORMATS),
                            help='Format des fichiers (csv/xlsx/json).')
        parser.add_argument('--objects', default='',
                            help='Clés séparées par des virgules ; vide = tout.')
        parser.add_argument('--zip', action='store_true',
                            help='Produire un seul ZIP de sauvegarde.')

    def handle(self, *args, **opts):
        from authentication.models import Company

        try:
            company = Company.objects.get(slug=opts['company_slug'])
        except Company.DoesNotExist:
            raise CommandError(
                f"Société introuvable : {opts['company_slug']}")

        fmt = opts['format']
        raw_objects = (opts['objects'] or '').strip()
        if raw_objects:
            keys = [k for k in (s.strip() for s in raw_objects.split(','))
                    if k in REGISTRY]
            if not keys:
                raise CommandError('Aucun objet valide demandé.')
        else:
            keys = list(DEFAULT_OBJECTS)

        out_dir = opts['out_dir']
        os.makedirs(out_dir, exist_ok=True)
        stamp = datetime.date.today().isoformat()
        specs = [REGISTRY[k] for k in keys]

        if opts['zip']:
            data = build_backup_zip(specs, company, fmt, stamp)
            path = os.path.join(out_dir, backup_filename(company, stamp))
            with open(path, 'wb') as fh:
                fh.write(data)
            self.stdout.write(self.style.SUCCESS(
                f'Sauvegarde écrite : {path} ({len(specs)} objets)'))
            return

        for spec in specs:
            data = export_bytes(spec, company, fmt)
            path = os.path.join(out_dir, filename_for(spec, fmt, stamp))
            with open(path, 'wb') as fh:
                fh.write(data)
            self.stdout.write(f'{spec.label}: {path}')
        self.stdout.write(self.style.SUCCESS(
            f'{len(specs)} objet(s) exporté(s) dans {out_dir}'))
