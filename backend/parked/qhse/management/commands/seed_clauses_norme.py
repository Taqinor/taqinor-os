"""Seed the main clauses of ISO 9001 / 14001 / 45001 (ClauseNorme, XQHS11).

Uses the shared HLS (High Level Structure — clauses 4 to 10 are numbered
identically across recent ISO management-system standards) so that the same
clause number under a different ``referentiel`` reads as "the same slot,
different standard" — a single piece of evidence can serve several norms.

Idempotent and strictly additive, modelled on ``seed_codes_defaut_solaire``:
each clause is matched by the stable key ``(company, referentiel, numero)``
via ``get_or_create`` — re-running creates nothing new.

Run (inside the django_core container or with DB env vars set):
  python manage.py seed_clauses_norme            # all companies
  python manage.py seed_clauses_norme --company taqinor-demo
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


# HLS clauses (4-10) common to ISO 9001/14001/45001 + a few norm-specific
# sub-clauses relevant to a solar installer's QHSE practice.
HLS_CLAUSES = [
    ('4', 'Contexte de l\'organisation'),
    ('5', 'Leadership'),
    ('6', 'Planification'),
    ('7', 'Support'),
    ('8', 'Réalisation des activités opérationnelles'),
    ('9', 'Évaluation des performances'),
    ('10', 'Amélioration'),
]

REFERENTIEL_SPECIFIQUES = {
    '9001': [
        ('8.5.1', 'Maîtrise de la production et de la fourniture de service'),
        ('8.6', 'Libération des produits et services'),
        ('9.1.2', 'Satisfaction du client'),
        ('10.2', 'Non-conformité et action corrective'),
    ],
    '14001': [
        ('6.1.2', 'Aspects environnementaux'),
        ('8.1', 'Maîtrise opérationnelle'),
        ('9.1', 'Surveillance, mesure, analyse et évaluation'),
    ],
    '45001': [
        ('6.1.2', 'Identification des dangers et évaluation des risques'),
        ('8.1.2', 'Élimination des dangers et réduction des risques SST'),
        ('9.1', 'Surveillance, mesure, analyse et évaluation des performances'),
    ],
}


class Command(BaseCommand):
    help = (
        'Seed the main ISO 9001/14001/45001 clauses (ClauseNorme, XQHS11), '
        'shared HLS structure. Idempotent and additive — safe to re-run.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company', default=None,
            help='Company slug to seed. Omit to seed all companies.')

    @transaction.atomic
    def handle(self, *args, **options):
        from authentication.models import Company
        from apps.qhse.models import ClauseNorme

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

        created = 0
        for company in companies:
            for referentiel, specifiques in REFERENTIEL_SPECIFIQUES.items():
                clauses = HLS_CLAUSES + specifiques
                for numero, intitule in clauses:
                    _, is_new = ClauseNorme.objects.get_or_create(
                        company=company, referentiel=referentiel, numero=numero,
                        defaults={'intitule': intitule},
                    )
                    if is_new:
                        created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Clauses de norme seedées pour {len(companies)} société(s) : '
            f'{created} clause(s) créée(s) (existantes laissées intactes).'
        ))
