"""Seed standard environmental aspects (AspectEnvironnemental) for a solar
installer's activities (XQHS20, ISO 14001 6.1.2).

Idempotent and strictly additive, modelled on ``seed_codes_defaut_solaire``:
  * each aspect is matched by the stable key ``(company, activite, aspect)``
    via ``get_or_create`` — re-running creates nothing new;
  * an aspect already present (even with edited cotation) is left untouched.

Run (inside the django_core container or with DB env vars set):
  python manage.py seed_aspects_environnementaux_solaire            # all
  python manage.py seed_aspects_environnementaux_solaire --company taqinor-demo
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


# (activite, aspect, impact, frequence, gravite) — installateur solaire type.
ASPECTS_SOLAIRE = [
    ('Transport de matériel', 'Émissions de GES (véhicules/engins)',
     "Contribution au changement climatique", 3, 2),
    ('Pose de panneaux/structures', 'Déchets d\'emballage et chutes',
     'Pollution des sols si non collectés', 4, 2),
    ('Stockage de batteries', 'Risque de fuite électrolyte',
     'Pollution du sol/eau en cas de déversement', 2, 4),
    ('Stockage de batteries', "Risque d'incendie (emballement thermique)",
     "Émissions toxiques, pollution de l'air", 1, 5),
    ('Déchets de chantier', "Production de déchets d'emballage/chutes de câble",
     'Pollution si mise en décharge sauvage', 5, 2),
    ('Recyclage de modules PV', 'Déchets électroniques (DEEE)',
     'Pollution si non traités par filière agréée', 2, 3),
    ('Entretien véhicules/engins', 'Fuites d\'huile/carburant',
     'Pollution du sol', 2, 3),
    ('Nettoyage de panneaux', "Consommation d'eau",
     "Pression sur la ressource en eau", 3, 1),
]


class Command(BaseCommand):
    help = (
        "Seed standard environmental aspects (AspectEnvironnemental) for a "
        "solar installer's activities (XQHS20). Idempotent and additive — "
        "safe to re-run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company', default=None,
            help='Company slug to seed. Omit to seed all companies.')

    @transaction.atomic
    def handle(self, *args, **options):
        from authentication.models import Company
        from apps.qhse.models import AspectEnvironnemental

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

        aspects_created = 0
        for company in companies:
            for activite, aspect, impact, frequence, gravite in ASPECTS_SOLAIRE:
                _, is_new = AspectEnvironnemental.objects.get_or_create(
                    company=company,
                    activite=activite,
                    aspect=aspect,
                    defaults={
                        'impact': impact,
                        'frequence': frequence,
                        'gravite': gravite,
                    },
                )
                if is_new:
                    aspects_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Aspects environnementaux seedés pour {len(companies)} "
            f"société(s) : {aspects_created} aspect(s) créé(s) "
            f"(existants laissés intacts)."))
