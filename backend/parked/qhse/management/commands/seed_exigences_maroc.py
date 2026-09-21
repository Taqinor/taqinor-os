"""Seed the Moroccan regulatory requirements pack (ConformiteEnvironnementale,
généralisé XQHS8) — EIE loi 49-17, déchets 28-00, eau 36-15, code du travail
(CSH ≥50, médecine du travail, règlement intérieur ≥10), vérifications
électriques périodiques.

Every entry is marked "applicabilité à confirmer" (``notes``) since the pack
is generic — the founder must confirm which items actually apply to this
company's activity/size before treating them as binding obligations.

Idempotent and strictly additive, modelled on ``seed_codes_defaut_solaire``:
each entry is matched by the stable key ``(company, intitule)`` via
``get_or_create`` — re-running creates nothing new; an entry already present
is left untouched.

Run (inside the django_core container or with DB env vars set):
  python manage.py seed_exigences_maroc            # all companies
  python manage.py seed_exigences_maroc --company taqinor-demo
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


APPLICABILITE_A_CONFIRMER = 'Applicabilité à confirmer.'

# (intitule, type_conformite, thematique, autorite) — la loi/texte source est
# tracée dans l'intitulé pour la traçabilité réglementaire.
EXIGENCES_MAROC = [
    (
        "EIE — Étude d'impact environnemental (loi 49-17)",
        'etude_impact', 'environnement',
        "Comité national/régional des études d'impact",
    ),
    (
        'Enregistrement déchets (loi 28-00)',
        'enregistrement_dechets', 'environnement',
        'Autorité locale / Ministère chargé de l\'environnement',
    ),
    (
        'Rejets / prélèvements eau (loi 36-15 sur l\'eau)',
        'rejets', 'environnement',
        "Agence du bassin hydraulique",
    ),
    (
        'Commission locale de sécurité (code du travail)',
        'commission_locale', 'securite',
        'Autorité locale / protection civile',
    ),
    (
        'Vérifications électriques périodiques',
        'verification_electrique', 'securite',
        'Organisme agréé de contrôle',
    ),
    (
        'CSH — comité de sécurité et d\'hygiène (≥50 salariés)',
        'csh', 'travail',
        'Inspection du travail',
    ),
    (
        'Médecine du travail',
        'autre', 'travail',
        'Service médical du travail',
    ),
    (
        'Règlement intérieur (≥10 salariés)',
        'reglement_interieur', 'travail',
        'Inspection du travail',
    ),
]


class Command(BaseCommand):
    help = (
        'Seed the Moroccan regulatory requirements pack (XQHS8) into the '
        'generalized ConformiteEnvironnementale registry. Idempotent and '
        'additive — safe to re-run. Every entry is flagged "applicabilité à '
        'confirmer".'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company', default=None,
            help='Company slug to seed. Omit to seed all companies.')

    @transaction.atomic
    def handle(self, *args, **options):
        from authentication.models import Company
        from apps.qhse.models import ConformiteEnvironnementale

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
            for intitule, type_conformite, thematique, autorite in \
                    EXIGENCES_MAROC:
                _, is_new = ConformiteEnvironnementale.objects.get_or_create(
                    company=company,
                    intitule=intitule,
                    defaults={
                        'type_conformite': type_conformite,
                        'thematique': thematique,
                        'autorite': autorite,
                        'notes': APPLICABILITE_A_CONFIRMER,
                    },
                )
                if is_new:
                    created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Pack marocain seedé pour {len(companies)} société(s) : '
            f'{created} exigence(s) créée(s) (existantes laissées intactes).'
        ))
