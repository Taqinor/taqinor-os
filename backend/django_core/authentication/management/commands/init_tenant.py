"""
One-time migration command: assign all existing data to a default company.

Run ONCE after applying the multi-tenant schema migration:
  docker compose exec django_core python manage.py init_tenant
  docker compose exec django_core python manage.py init_tenant \
      --nom "Mon Entreprise" --admin-username admin
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Assign all existing data to a default Company (run once).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--nom',
            default='Mon Entreprise',
            help='Name of the default company (default: Mon Entreprise)',
        )
        parser.add_argument(
            '--admin-username',
            default=None,
            help='Username to promote to admin role for the company',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from authentication.models import Company, CustomUser
        from apps.parametres.models import CompanyProfile
        from apps.stock.models import Categorie, Fournisseur, Produit
        from apps.crm.models import Client
        from apps.ventes.models import Devis, BonCommande, Facture

        nom = options['nom']
        admin_username = options['admin_username']

        # ── 1. Get or create the default Company ──────────────────────
        company, created = Company.objects.get_or_create(
            slug='default',
            defaults={'nom': nom},
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Created company: {company.nom}')
            )
        else:
            self.stdout.write(
                f'Using existing company: {company.nom} (pk={company.pk})'
            )

        # ── 2. Link CompanyProfile pk=1 if it exists ───────────────────
        try:
            profile = CompanyProfile.objects.get(pk=1)
            if profile.company_id is None:
                profile.company = company
                profile.save(update_fields=['company'])
                self.stdout.write('Linked existing CompanyProfile to company.')
        except CompanyProfile.DoesNotExist:
            CompanyProfile.objects.get_or_create(
                company=company,
                defaults={'nom': nom},
            )
            self.stdout.write('Created CompanyProfile for company.')

        # ── 3. Assign all users without a company ──────────────────────
        updated = CustomUser.objects.filter(
            company__isnull=True
        ).update(company=company)
        self.stdout.write(f'Assigned {updated} user(s) to company.')

        if admin_username:
            try:
                user = CustomUser.objects.get(username=admin_username)
                user.role = CustomUser.ROLE_ADMIN
                user.company = company
                user.save(update_fields=['role', 'company'])
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Promoted {admin_username} to admin.'
                    )
                )
            except CustomUser.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f'User "{admin_username}" not found.'
                    )
                )

        # ── 4. Assign all business data to the default company ─────────
        counts = {}

        counts['categories'] = Categorie.objects.filter(
            company__isnull=True
        ).update(company=company)

        counts['fournisseurs'] = Fournisseur.objects.filter(
            company__isnull=True
        ).update(company=company)

        counts['produits'] = Produit.objects.filter(
            company__isnull=True
        ).update(company=company)

        counts['clients'] = Client.objects.filter(
            company__isnull=True
        ).update(company=company)

        counts['devis'] = Devis.objects.filter(
            company__isnull=True
        ).update(company=company)

        counts['bons_commande'] = BonCommande.objects.filter(
            company__isnull=True
        ).update(company=company)

        counts['factures'] = Facture.objects.filter(
            company__isnull=True
        ).update(company=company)

        for model_name, count in counts.items():
            if count:
                self.stdout.write(
                    f'Migrated {count} {model_name}.'
                )

        self.stdout.write(
            self.style.SUCCESS(
                '\nMigration complete. '
                f'All data assigned to company "{company.nom}" '
                f'(pk={company.pk}).'
            )
        )
