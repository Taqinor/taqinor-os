"""Rappelle les échéances déclaratives de paie à venir (NTPAY25).

Balaie les ``EcheanceDeclarative`` à J-7 / J-3 / J-0 non encore déposées et
notifie les gestionnaires de paie — UNE SEULE FOIS par jour-seuil.

Planifiée par Celery beat (``paie.rappeler_echeances_declaratives``,
quotidien) ; cette commande sert au rattrapage manuel et au diagnostic. Elle
est IDEMPOTENTE : la rejouer le même jour ne renotifie rien.

Exécution (dans le conteneur django_core ou avec les variables DB) :
  python manage.py rappeler_echeances_declaratives
  python manage.py rappeler_echeances_declaratives --company taqinor-demo
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Rappelle les échéances déclaratives de paie à J-7/J-3/J-0 "
        "(idempotent). Planifiée par Celery beat "
        "(paie.rappeler_echeances_declaratives)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help="Slug d'une seule société (défaut : toutes les actives).",
        )

    def handle(self, *args, **options):
        from authentication.models import Company
        from authentication.selectors import active_companies

        from apps.paie.tasks import rappeler_echeances_declaratives_company

        slug = options.get('company')
        if slug:
            try:
                companies = [Company.objects.get(slug=slug)]
            except Company.DoesNotExist:
                raise CommandError(f"Société de slug '{slug}' introuvable.")
        else:
            companies = list(active_companies())

        total = 0
        for company in companies:
            notifies = rappeler_echeances_declaratives_company(company)
            total += len(notifies)
            for echeance, seuil in notifies:
                self.stdout.write(
                    f'{company.slug} — {echeance.get_type_echeance_display()} '
                    f'J-{seuil} (limite {echeance.date_limite})')

        self.stdout.write(self.style.SUCCESS(
            f'{total} rappel(s) envoyé(s) sur {len(companies)} société(s).'))
