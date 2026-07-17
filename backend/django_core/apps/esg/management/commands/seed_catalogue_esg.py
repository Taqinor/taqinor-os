"""Commande NTESG3 — seed idempotent du catalogue GRI-lite pour une société.

Usage :
    python manage.py seed_catalogue_esg --company <id_ou_slug>
    python manage.py seed_catalogue_esg --all   # toutes les sociétés

Idempotent : ``get_or_create`` par ``(company, code)`` — ne touche jamais un
enregistrement déjà seedé (mêmes garanties que ``seed_catalogue`` de
``apps.ventes``)."""
from django.core.management.base import BaseCommand, CommandError

from apps.esg.catalogue_data import GRI_LITE_CATALOGUE
from apps.esg.models import CatalogueIndicateurESG


def seed_catalogue_esg_for_company(company):
    """Seed idempotent du catalogue GRI-lite pour UNE société.

    Renvoie le nombre de lignes CRÉÉES (0 si déjà seedé)."""
    created_count = 0
    for code, libelle, pilier, unite, reference in GRI_LITE_CATALOGUE:
        _, created = CatalogueIndicateurESG.objects.get_or_create(
            company=company, code=code,
            defaults={
                'libelle': libelle,
                'pilier': pilier,
                'unite_attendue': unite,
                'reference_gri': reference,
            },
        )
        if created:
            created_count += 1
    return created_count


class Command(BaseCommand):
    help = 'Seed idempotent du catalogue GRI-lite ESG (NTESG3).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company', default=None,
            help='id ou slug de la société à seeder.')
        parser.add_argument(
            '--all', dest='all_companies', action='store_true',
            help='Seed toutes les sociétés existantes.')

    def handle(self, *args, **options):
        from authentication.models import Company

        company_ref = options.get('company')
        all_companies = options.get('all_companies')

        if not company_ref and not all_companies:
            raise CommandError(
                'Précisez --company <id_ou_slug> ou --all.')

        if all_companies:
            companies = list(Company.objects.all())
        else:
            qs = Company.objects.all()
            company = qs.filter(pk=company_ref).first() \
                if str(company_ref).isdigit() else None
            if company is None:
                company = qs.filter(slug=company_ref).first()
            if company is None:
                raise CommandError(f'Société introuvable : {company_ref}')
            companies = [company]

        total_created = 0
        for company in companies:
            created = seed_catalogue_esg_for_company(company)
            total_created += created
            self.stdout.write(
                f'{company} : {created} indicateur(s) créé(s) '
                f'(catalogue = {len(GRI_LITE_CATALOGUE)} indicateurs).')

        self.stdout.write(self.style.SUCCESS(
            f'Terminé — {total_created} indicateur(s) créé(s) au total sur '
            f'{len(companies)} société(s).'))
