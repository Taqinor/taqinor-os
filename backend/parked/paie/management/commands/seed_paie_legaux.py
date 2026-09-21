"""Seed les valeurs légales de paie 2026 par société (PAIE3).

Provisionne, pour chaque société (ou une seule via ``--company <slug>``), le
``ParametrePaie`` et le ``BaremeIR`` (+ ``TrancheIR``) officiels au
1ᵉʳ janvier 2026, avec ``valide_par_fondateur=False`` (valeurs éditables en
attente de confirmation du fondateur).

Idempotent et strictement additif (cf. ``apps.paie.services.ensure_defaults``) :
ancré sur ``(company, date_effet=2026-01-01)``, re-jouer ne crée aucun doublon
et ne touche jamais une ligne existante.

Exécution (dans le conteneur django_core ou avec les variables DB) :
  python manage.py seed_paie_legaux                        # toutes les sociétés
  python manage.py seed_paie_legaux --company taqinor-demo  # une seule société
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.paie.services import ensure_defaults


class Command(BaseCommand):
    help = (
        "Seed les valeurs légales de paie 2026 (paramètres sociaux + barème IR) "
        "par société ou une seule --company (idempotent, additif, "
        "valide_par_fondateur=False)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help="Slug d'une seule société à seed (défaut : toutes).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from authentication.models import Company

        slug = options.get('company')
        if slug:
            try:
                companies = [Company.objects.get(slug=slug)]
            except Company.DoesNotExist:
                raise CommandError(f"Société de slug '{slug}' introuvable.")
        else:
            companies = list(Company.objects.all())

        if not companies:
            self.stdout.write(self.style.WARNING(
                "Aucune société à seed — rien fait."))
            return

        totaux = {'parametre': 0, 'bareme': 0, 'tranches': 0}
        for company in companies:
            res = ensure_defaults(company)
            for key in totaux:
                totaux[key] += res[key]

        self.stdout.write(self.style.SUCCESS(
            f"Valeurs légales 2026 seedées pour {len(companies)} société(s) : "
            f"{totaux['parametre']} paramètre(s), {totaux['bareme']} barème(s) IR, "
            f"{totaux['tranches']} tranche(s) créé(s) "
            f"(lignes existantes inchangées, valide_par_fondateur=False)."))
