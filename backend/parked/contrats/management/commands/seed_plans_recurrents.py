"""Seed the 3 standard recurring billing plans (ZCTR1) per company.

Creates ``PlanRecurrent`` rows for the standard cadences (mensuel, trimestriel,
annuel) for every company (or a single ``--company`` slug). Purely additive :
an EXISTING plan (matched by ``(company, nom)``) is left UNTOUCHED — a
founder-edited plan survives a re-run.

Run (inside the django_core container or with DB env vars set):
  python manage.py seed_plans_recurrents                        # all companies
  python manage.py seed_plans_recurrents --company taqinor-demo  # one company
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.contrats.models import PlanRecurrent

# ── 3 plans standard : nom -> (unite, intervalle) ────────────────────────────
DEFAULTS = [
    ('Mensuel', PlanRecurrent.Unite.MENSUEL, 1),
    ('Trimestriel', PlanRecurrent.Unite.TRIMESTRIEL, 1),
    ('Annuel', PlanRecurrent.Unite.ANNUEL, 1),
]


def seed_plans_recurrents_for_company(company):
    """Seed the 3 standard plans for one company (idempotent, additive).

    Returns the number of NEW plans created. Existing plans (matched by
    ``(company, nom)``) are never touched. Usable as a helper from other code
    as well as from the management command.
    """
    created = 0
    for nom, unite, intervalle in DEFAULTS:
        _, is_new = PlanRecurrent.objects.get_or_create(
            company=company,
            nom=nom,
            defaults={
                'unite': unite,
                'intervalle': intervalle,
                'actif': True,
            },
        )
        if is_new:
            created += 1
    return created


class Command(BaseCommand):
    help = (
        "Seed the 3 standard recurring billing plans (Mensuel/Trimestriel/"
        "Annuel) per company or a single --company (idempotent, additive only)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help="Slug of a single company to seed (default: all companies).",
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
                "No company to seed — nothing done."))
            return

        total_created = 0
        for company in companies:
            total_created += seed_plans_recurrents_for_company(company)

        self.stdout.write(self.style.SUCCESS(
            f"Plans récurrents seeded for {len(companies)} société(s): "
            f"{total_created} plan(s) created (existing plans left untouched)."))
