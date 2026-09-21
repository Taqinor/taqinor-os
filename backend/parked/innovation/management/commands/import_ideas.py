"""NTIDE24 — ``manage.py import_ideas file.json [--company SLUG]``.

Réimporte un export produit par ``export_ideas`` (dev/test uniquement).
IDEMPOTENT : rejouer la même commande sur le même fichier ne duplique
jamais une idée déjà présente pour (titre, company, auteur).

Sans ``--company`` : chaque enregistrement résout sa propre société via son
slug (``record['company']``, échoue proprement si introuvable). Avec
``--company`` : TOUS les enregistrements sont importés dans cette société,
quel que soit le slug d'origine (rejouer un export dans un environnement de
démo/test différent).

Exemples :
  python manage.py import_ideas idees.json
  python manage.py import_ideas idees.json --company taqinor-demo
"""
import json

from django.core.management.base import BaseCommand, CommandError

from apps.innovation.data_io import import_ideas


class Command(BaseCommand):
    help = (
        'Réimporte des idées depuis un export JSON (export_ideas, NTIDE24) '
        '— dev/test. Idempotent (titre+company+auteur).'
    )

    def add_arguments(self, parser):
        parser.add_argument('file', help='Fichier JSON produit par export_ideas.')
        parser.add_argument(
            '--company', default=None,
            help="Slug société cible (surcharge le 'company' de chaque enregistrement).")

    def handle(self, *args, **opts):
        from authentication.models import Company

        company = None
        slug = opts.get('company')
        if slug:
            try:
                company = Company.objects.get(slug=slug)
            except Company.DoesNotExist:
                raise CommandError(f'Société introuvable : {slug}')

        path = opts['file']
        try:
            with open(path, encoding='utf-8') as fh:
                records = json.load(fh)
        except OSError as exc:
            raise CommandError(f'Impossible de lire {path} : {exc}')
        except json.JSONDecodeError as exc:
            raise CommandError(f'JSON invalide dans {path} : {exc}')

        if not isinstance(records, list):
            raise CommandError('Le fichier doit contenir une liste JSON.')

        result = import_ideas(records, company=company)
        self.stdout.write(self.style.SUCCESS(
            f'{result.created} idée(s) créée(s), '
            f'{result.skipped} déjà présente(s) (ignorée(s)).'))
        for err in result.errors:
            self.stderr.write(self.style.WARNING(err))
