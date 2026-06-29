"""Seed the standard Moroccan vignette / TSAV grid (FLOTTE20) per company.

Creates the standard ``BaremeVignette`` lines for every company (or a single
``--company`` slug): the TSAV (Taxe Spéciale Annuelle sur les Véhicules) amount
per energy type and fiscal-power (CV) bracket. The grid is seeded as a GENERIC
barème (``annee = 0``, i.e. valid for any year unless a dated line overrides it).

The bracket amounts mirror the standard Moroccan TSAV grid (essence vs diesel,
electric exempt). They are EDITABLE afterwards via the API — the seeder only
fills missing rows, it never updates an existing one (a founder-edited amount
survives a re-run).

Idempotent and strictly additive — modelled on ``seed_referentiels_flotte``:
  * each line is matched by the stable key
    ``(company, energie, cv_min, cv_max, annee)`` via ``get_or_create`` —
    re-running creates nothing new;
  * a line already present (even with an edited ``montant`` / ``actif``) is left
    untouched.

Run (inside the django_core container or with DB env vars set):
  python manage.py seed_baremes_vignette                       # all companies
  python manage.py seed_baremes_vignette --company taqinor-demo  # one company
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.flotte.models import BaremeVignette


# ── Standard TSAV grid : energie -> [(cv_min, cv_max, montant), …] ───────────
# Generic barème (annee=0). Brackets are inclusive on both ends; the open top
# bracket uses BaremeVignette.CV_MAX_OUVERT (9999). Electric is exempt (0).
CV_MAX = BaremeVignette.CV_MAX_OUVERT

DEFAULTS = {
    BaremeVignette.Energie.ESSENCE: [
        (0, 7, Decimal('350')),
        (8, 10, Decimal('650')),
        (11, 14, Decimal('3000')),
        (15, CV_MAX, Decimal('8000')),
    ],
    BaremeVignette.Energie.DIESEL: [
        (0, 7, Decimal('700')),
        (8, 10, Decimal('1500')),
        (11, 14, Decimal('6000')),
        (15, CV_MAX, Decimal('20000')),
    ],
    # L'hybride suit, par défaut, la grille essence (éditable ensuite).
    BaremeVignette.Energie.HYBRIDE: [
        (0, 7, Decimal('350')),
        (8, 10, Decimal('650')),
        (11, 14, Decimal('3000')),
        (15, CV_MAX, Decimal('8000')),
    ],
    # L'électrique est exonéré : une seule tranche couvrante à 0 MAD.
    BaremeVignette.Energie.ELECTRIQUE: [
        (0, CV_MAX, Decimal('0')),
    ],
}


def seed_baremes_vignette_for_company(company, annee=0):
    """Seed the standard TSAV grid for one company (idempotent, additive).

    Returns the number of NEW rows created. Existing rows (matched by
    ``(company, energie, cv_min, cv_max, annee)``) are never touched, so an
    edited ``montant`` survives a re-run. Usable as a helper from other code as
    well as from the management command.
    """
    created = 0
    for energie, brackets in DEFAULTS.items():
        for cv_min, cv_max, montant in brackets:
            _, is_new = BaremeVignette.objects.get_or_create(
                company=company,
                energie=energie,
                cv_min=cv_min,
                cv_max=cv_max,
                annee=annee,
                defaults={
                    'montant': montant,
                    'actif': True,
                },
            )
            if is_new:
                created += 1
    return created


class Command(BaseCommand):
    help = (
        "Seed the standard Moroccan vignette / TSAV grid (montant par énergie "
        "et tranche de CV) per company or a single --company (idempotent, "
        "additive only)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help="Slug of a single company to seed (default: all companies).",
        )
        parser.add_argument(
            '--annee', type=int, default=0,
            help="Année du barème (0 = générique, défaut).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from authentication.models import Company

        slug = options.get('company')
        annee = options.get('annee') or 0
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
            total_created += seed_baremes_vignette_for_company(
                company, annee=annee)

        self.stdout.write(self.style.SUCCESS(
            f"Barème vignette / TSAV seeded for {len(companies)} société(s): "
            f"{total_created} ligne(s) created (existing rows left untouched)."))
