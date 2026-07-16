"""SCA20 — ``manage.py seed_company <slug>`` : rejoue les seeds « nouvelle
société » sur une société EXISTANTE (idempotent).

Réapplique les rôles système + le ``CompanyProfile`` (comme le signup), puis
exécute TOUS les hooks enregistrés (types d'activité, niveaux de relance,
catalogue…). Tout est idempotent/additif : rejouable sans doublon ni écrasement
de données existantes. Utile pour rattraper une société créée avant SCA20 (sans
catalogue) ou pour re-seeder après l'ajout d'un nouveau hook.
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = ("Rejoue les seeds « nouvelle société » (rôles + profil + hooks : "
            "types d'activité, relances, catalogue) sur une société existante.")

    def add_arguments(self, parser):
        parser.add_argument(
            'slug',
            help="Slug de la société à (re)seeder.")

    def handle(self, *args, **options):
        from authentication.models import Company
        from authentication.views import _create_system_roles
        from core.signup_hooks import run_signup_hooks

        slug = options['slug']
        try:
            company = Company.objects.get(slug=slug)
        except Company.DoesNotExist:
            raise CommandError(f"Aucune société avec le slug « {slug} ».")

        # Rôles système + profil (idempotents), comme au signup.
        _create_system_roles(company)
        try:
            from apps.parametres.models import CompanyProfile
            CompanyProfile.objects.get_or_create(
                company=company, defaults={'nom': company.nom})
        except Exception as exc:  # noqa: BLE001 — profil optionnel
            self.stderr.write(f"Profil non seedé: {exc}")

        resultats = run_signup_hooks(company)
        self.stdout.write(self.style.SUCCESS(
            f"Société « {company.nom} » re-seedée. Hooks: {resultats}"))
