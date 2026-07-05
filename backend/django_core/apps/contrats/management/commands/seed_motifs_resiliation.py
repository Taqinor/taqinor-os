"""Seed the 6 standard close reasons (motifs de résiliation) — ZCTR3.

Creates ``MotifResiliation`` rows for every company (or a single ``--company``
slug). Purely additive : an EXISTING motif (matched by ``(company, code)``)
is left UNTOUCHED — a founder-edited motif survives a re-run.

Run (inside the django_core container or with DB env vars set):
  python manage.py seed_motifs_resiliation                        # all companies
  python manage.py seed_motifs_resiliation --company taqinor-demo  # one company
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.contrats.models import MotifResiliation

# ── 6 motifs standard : code -> (libellé, ordre, catégorie) ─────────────────
DEFAULTS = [
    ('prix', 'Prix trop élevé', 1, MotifResiliation.Categorie.PRIX),
    ('concurrent', 'Parti chez un concurrent', 2,
     MotifResiliation.Categorie.CONCURRENT),
    ('insatisfaction_service', 'Insatisfaction du service', 3,
     MotifResiliation.Categorie.INSATISFACTION),
    ('insatisfaction_produit', 'Insatisfaction du produit', 4,
     MotifResiliation.Categorie.INSATISFACTION),
    ('fin_projet', 'Fin de projet / chantier terminé', 5,
     MotifResiliation.Categorie.FIN_PROJET),
    ('autre', 'Autre', 6, MotifResiliation.Categorie.AUTRE),
]


def seed_motifs_resiliation_for_company(company):
    """Seed the 6 standard motifs for one company (idempotent, additive).

    Returns the number of NEW motifs created. Existing motifs (matched by
    ``(company, code)``) are never touched. Usable as a helper from other
    code as well as from the management command.
    """
    created = 0
    for code, libelle, ordre, categorie in DEFAULTS:
        _, is_new = MotifResiliation.objects.get_or_create(
            company=company,
            code=code,
            defaults={
                'libelle': libelle,
                'ordre': ordre,
                'categorie': categorie,
                'actif': True,
            },
        )
        if is_new:
            created += 1
    return created


class Command(BaseCommand):
    help = (
        'Seed the 6 standard close reasons (motifs de résiliation) per '
        'company or a single --company (idempotent, additive only).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help='Slug of a single company to seed (default: all companies).',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from authentication.models import Company

        slug = options.get('company')
        if slug:
            try:
                companies = [Company.objects.get(slug=slug)]
            except Company.DoesNotExist:
                raise CommandError(f"Company with slug '{slug}' not found.")
        else:
            companies = list(Company.objects.all())

        if not companies:
            self.stdout.write(self.style.WARNING(
                'No company to seed — nothing done.'))
            return

        total_created = 0
        for company in companies:
            total_created += seed_motifs_resiliation_for_company(company)

        self.stdout.write(self.style.SUCCESS(
            f'Motifs de résiliation seeded for {len(companies)} société(s): '
            f'{total_created} motif(s) created (existing motifs left '
            'untouched).'))
