"""Seed the standard fleet reference lists (FLOTTE6) per company.

Creates the standard ``ReferentielFlotte`` entries for every company (or a single
``--company`` slug): énergie, catégorie de permis, type de véhicule, type
d'engin and (ZCTR10) type de service/entretien. The ``énergie`` and
``type_engin`` values deliberately MIRROR the frozen
``TextChoices`` carried by ``Vehicule``/``EnginRoulant`` so the editable list is a
faithful parallel of the hardcoded choices (which stay untouched).

Idempotent and strictly additive — modelled on ``seed_itp_solaire``:
  * each entry is matched by the stable key ``(company, domaine, code)`` via
    ``get_or_create`` — re-running creates nothing new;
  * an entry already present (even with an edited ``libelle``/``ordre``/``actif``)
    is left untouched: the seeder only fills missing rows, it never updates one.

Run (inside the django_core container or with DB env vars set):
  python manage.py seed_referentiels_flotte                       # all companies
  python manage.py seed_referentiels_flotte --company taqinor-demo  # one company
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.flotte.models import ReferentielFlotte


# ── Standard reference values : domaine -> [(code, libelle), …] ──────────────
# ordre is assigned by position (10, 20, 30…). énergie/type_engin codes mirror
# the frozen TextChoices on Vehicule/EnginRoulant so the editable list matches.
DEFAULTS = {
    ReferentielFlotte.Domaine.ENERGIE: [
        ('diesel', 'Diesel'),
        ('essence', 'Essence'),
        ('electrique', 'Électrique'),
        ('hybride', 'Hybride'),
    ],
    ReferentielFlotte.Domaine.CATEGORIE_PERMIS: [
        ('A', 'A — Motocyclettes'),
        ('B', 'B — Véhicules légers'),
        ('C', 'C — Poids lourds'),
        ('D', 'D — Transport en commun'),
        ('EC', 'EC — Poids lourds + remorque'),
    ],
    ReferentielFlotte.Domaine.TYPE_VEHICULE: [
        ('utilitaire', 'Utilitaire'),
        ('camion', 'Camion'),
        ('voiture', 'Voiture de service'),
        ('fourgon', 'Fourgon'),
    ],
    ReferentielFlotte.Domaine.TYPE_ENGIN: [
        ('nacelle', 'Nacelle'),
        ('groupe_electrogene', 'Groupe électrogène'),
        ('chariot', 'Chariot'),
    ],
    # ZCTR10 — types de service/entretien standard (référentiel éditable,
    # référencé par ``OrdreReparation.type_service``).
    ReferentielFlotte.Domaine.TYPE_SERVICE: [
        ('vidange', 'Vidange'),
        ('freins', 'Freins'),
        ('pneus', 'Pneus'),
        ('revision', 'Révision'),
        ('carrosserie', 'Carrosserie'),
        ('climatisation', 'Climatisation'),
        ('batterie', 'Batterie'),
        ('controle_technique', 'Contrôle technique'),
    ],
}


def seed_referentiels_flotte_for_company(company):
    """Seed the standard reference lists for one company (idempotent, additive).

    Returns the number of NEW rows created. Existing rows (matched by
    ``(company, domaine, code)``) are never touched, so an edited ``libelle`` /
    ``ordre`` / ``actif`` survives a re-run. Usable as a ``defaults`` helper from
    other code as well as from the management command."""
    created = 0
    for domaine, values in DEFAULTS.items():
        for index, (code, libelle) in enumerate(values, start=1):
            _, is_new = ReferentielFlotte.objects.get_or_create(
                company=company,
                domaine=domaine,
                code=code,
                defaults={
                    'libelle': libelle,
                    'ordre': index * 10,
                    'actif': True,
                },
            )
            if is_new:
                created += 1
    return created


class Command(BaseCommand):
    help = (
        "Seed the standard fleet reference lists (énergie, catégorie de permis, "
        "type de véhicule, type d'engin) per company or a single --company "
        "(idempotent, additive only)."
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
            total_created += seed_referentiels_flotte_for_company(company)

        self.stdout.write(self.style.SUCCESS(
            f"Référentiels de flotte seeded for {len(companies)} société(s): "
            f"{total_created} entrée(s) created (existing rows left untouched)."))
