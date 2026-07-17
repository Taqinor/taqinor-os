"""Reset (wipe + re-seed) a single demo tenant — NTDMO6.

Deletes ONE demo company by ``--slug`` (via the existing FK cascade — NEVER raw
SQL) then re-invokes ``seed_demo_company`` with the same slug, producing an
identical record count (the seed is deterministic, ``Faker.seed``/fixed RNG).

Safety guards (to never wipe a real company by accident):
  * ``--slug`` is REQUIRED (no default) — the caller must name the tenant.
  * the slug MUST contain ``demo`` — otherwise the command refuses.

Run:
  python manage.py reset_demo_company --slug taqinor-demo-full
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = ('Wipe and re-seed a single demo company (by --slug). Refuses any '
            "slug that does not contain 'demo'.")

    def add_arguments(self, parser):
        # Pas de défaut : le slug DOIT être fourni explicitement (garde-fou).
        parser.add_argument(
            '--slug', required=True,
            help='Slug de la société démo à réinitialiser (doit contenir '
                 "'demo').")
        parser.add_argument(
            '--force', action='store_true',
            help='Transmis à seed_demo_company (re-seed hors DEBUG).')

    def handle(self, *args, **options):
        slug = options['slug']
        if 'demo' not in slug.lower():
            raise CommandError(
                f"Refus : le slug « {slug} » ne contient pas 'demo'. "
                "reset_demo_company ne réinitialise QUE des sociétés de "
                "démonstration (garde-fou anti-effacement d'une société réelle).")

        from authentication.models import Company, CustomUser

        company = Company.objects.filter(slug=slug).first()
        if company is not None:
            with transaction.atomic():
                # CustomUser.company est SET_NULL → supprimer explicitement les
                # comptes de la société démo (sinon ils seraient orphelinés).
                CustomUser.objects.filter(company=company).delete()
                # Cascade FK sur les données métier scopées société — jamais de
                # SQL brut.
                company.delete()
            self.stdout.write(self.style.WARNING(
                f'Société démo "{slug}" vidée.'))
        else:
            self.stdout.write(self.style.WARNING(
                f'Aucune société "{slug}" existante — création directe.'))

        call_command('seed_demo_company', slug=slug,
                     force=options.get('force', False), verbosity=0)
        self.stdout.write(self.style.SUCCESS(
            f'Société démo "{slug}" réinitialisée (vidée puis re-peuplée).'))
