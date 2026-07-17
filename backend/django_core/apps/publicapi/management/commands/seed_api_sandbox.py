"""NTAPI27 — seed IDEMPOTENT/ADDITIF des données de démo du bac à sable API.

Pour chaque société réelle (ou une seule via ``--company``), get-or-create sa
société-jumelle isolée (``publicapi.SandboxTenant``) et y seed un jeu de
leads de démonstration via le point d'entrée cross-app déjà sanctionné
(``crm.services.create_lead_from_public_api``) — jamais d'import direct de
``apps.crm.models``. Ré-exécuter ne duplique jamais un lead de démo déjà
présent (dédup sur l'email) :

    python manage.py seed_api_sandbox [--company <id>]
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "NTAPI27 — seed idempotent des données de démo du bac à sable API."

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', type=int, default=None,
            help='Ne seeder que cette société (id) — sinon toutes les sociétés réelles.')

    def handle(self, *args, **options):
        from authentication.models import Company
        from apps.publicapi.services import get_or_create_sandbox

        qs = Company.objects.all()
        company_id = options.get('company')
        if company_id:
            qs = qs.filter(pk=company_id)
        # Ne jamais seeder une société qui EST déjà une société-jumelle
        # sandbox (évite toute récursion sandbox-de-sandbox).
        qs = qs.exclude(sandbox_of__isnull=False)

        total = 0
        for company in qs:
            get_or_create_sandbox(company)
            total += 1
            self.stdout.write(f'  · {company.nom} : bac à sable prêt.')
        self.stdout.write(self.style.SUCCESS(
            f'Bac à sable API : {total} société(s) traitée(s).'))
