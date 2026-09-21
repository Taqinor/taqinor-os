"""XRH2 — Types d'absence légaux Maroc pré-configurés (seed).

``TypeAbsence`` (FG164) est configurable mais rien n'est semé par défaut :
cette commande crée les types d'absence STATUTAIRES du Code du travail
marocain avec leur bonne règle de décompte, pour UNE société (par slug) ou
TOUTES les sociétés.

Idempotent et strictement ADDITIF (pattern ``seed_catalogue``) :
  - un type est matché par ``code`` (unique par société) ;
  - un type déjà présent n'est JAMAIS modifié (ni ses règles, ni son
    ``jours_legaux``) — seuls les types manquants sont créés.

Run:
  python manage.py seed_types_absence
  python manage.py seed_types_absence --company-slug taqinor-demo
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.rh.models import TypeAbsence


# (code, libellé, decompte_jours_ouvres, deduit_solde, remunere, jours_legaux)
# — références : Code du travail marocain (dahir n° 1-03-194), art. 152-159
# (congés spéciaux), CNSS (maternité).
TYPES_LEGAUX = [
    ('MAT', 'Congé de maternité', False, False, True, Decimal('98')),   # 14 sem.
    ('PAT', 'Congé de paternité', False, False, True, Decimal('3')),
    ('MAR', 'Congé pour mariage (salarié)', False, False, True, Decimal('4')),
    ('NAI', 'Congé pour naissance', False, False, True, Decimal('3')),
    ('DEC', "Congé pour décès (famille proche)", False, False, True, Decimal('3')),
    ('CIRC', 'Congé pour circoncision', False, False, True, Decimal('2')),
    ('AT', 'Accident du travail', False, False, True, None),
    # YHIRE7 — mise à pied disciplinaire (Sanction.TypeSanction.MISE_A_PIED) :
    # jours calendaires (pas ouvrés — c'est une sanction, pas un congé), NON
    # rémunérée, NE déduit PAS le solde de congés (compteur distinct).
    ('MAP', 'Mise à pied disciplinaire', False, False, False, None),
]


class Command(BaseCommand):
    help = ("Sème les types d'absence légaux marocains statutaires "
            "(idempotent, additif — jamais de modification d'un type "
            'existant).')

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-slug', type=str, default=None,
            help='Limiter à une société (slug). Par défaut : toutes.')

    def handle(self, *args, **options):
        from authentication.models import Company

        companies = Company.objects.all()
        slug = options['company_slug']
        if slug:
            companies = companies.filter(slug=slug)

        total_created = 0
        total_skipped = 0
        for company in companies:
            existing_codes = set(
                TypeAbsence.objects.filter(company=company)
                .values_list('code', flat=True))
            for code, libelle, jours_ouvres, deduit, remunere, plafond in \
                    TYPES_LEGAUX:
                if code in existing_codes:
                    total_skipped += 1
                    continue
                TypeAbsence.objects.create(
                    company=company, code=code, libelle=libelle,
                    decompte_jours_ouvres=jours_ouvres,
                    deduit_solde=deduit, remunere=remunere,
                    jours_legaux=plafond,
                )
                total_created += 1
            self.stdout.write(f'{company} : types légaux vérifiés.')

        self.stdout.write(self.style.SUCCESS(
            f'{total_created} type(s) créé(s), '
            f'{total_skipped} déjà présent(s) (inchangés).'))
