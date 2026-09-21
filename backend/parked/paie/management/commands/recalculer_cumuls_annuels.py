"""Recalcule les cumuls annuels de paie EN DÉRIVE (NTPAY26).

Recompare chaque ``CumulAnnuel`` à la somme réelle des bulletins VALIDÉS de
l'année et ne corrige QUE les cumuls divergents, en déposant une ligne
d'ajustement tracée sur leur chatter. Un cumul cohérent n'est jamais touché.

Planifiée par Celery beat (``paie.recalculer_cumuls_annuels``, mensuel à J+1
de la clôture) ; cette commande sert au rattrapage manuel et au diagnostic.

Exécution (dans le conteneur django_core ou avec les variables DB) :
  python manage.py recalculer_cumuls_annuels
  python manage.py recalculer_cumuls_annuels --company taqinor-demo --annee 2026
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Corrige les cumuls annuels de paie divergents (trace d'ajustement "
        "sur le chatter). Planifiée par Celery beat "
        "(paie.recalculer_cumuls_annuels)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help="Slug d'une seule société (défaut : toutes les actives).",
        )
        parser.add_argument(
            '--annee', type=int, default=None,
            help="Année à contrôler (défaut : l'année en cours).",
        )

    def handle(self, *args, **options):
        from authentication.models import Company
        from authentication.selectors import active_companies

        from apps.paie.tasks import recalculer_cumuls_annuels_company

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
            corriges = recalculer_cumuls_annuels_company(
                company, annee=options.get('annee'))
            total += len(corriges)
            for cumul, ecarts in corriges:
                self.stdout.write(
                    f'{company.slug} — cumul #{cumul.id} '
                    f'(profil #{cumul.profil_id}, {cumul.annee}) : '
                    f'{len(ecarts)} écart(s) corrigé(s)')

        self.stdout.write(self.style.SUCCESS(
            f'{total} cumul(s) corrigé(s) sur {len(companies)} société(s).'))
