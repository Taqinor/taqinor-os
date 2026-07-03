"""Notifie le responsable des projets ACTIFS en retard/à risque (XPRJ22).

Balaie ``retards_projet`` (PROJ14) sur les projets actifs de la société et
notifie leur ``responsable``. IDEMPOTENT : relancer la commande plusieurs fois
le même jour ne spamme jamais deux fois le même (projet, élément) — voir
``services.alertes_retards_projets``. Pensé pour être exécuté à la demande ou
par un planificateur (cron / Celery beat).

Run (dans le conteneur django_core ou avec les variables DB) :
  python manage.py alertes_retards_projets                          # toutes sociétés
  python manage.py alertes_retards_projets --company taqinor-demo
  python manage.py alertes_retards_projets --seuil-jours 5
"""
from django.core.management.base import BaseCommand, CommandError

from apps.gestion_projet.services import alertes_retards_projets


class Command(BaseCommand):
    help = (
        "Notifie le responsable de chaque projet actif en retard/à risque "
        "de planning, par société ou pour une seule --company (idempotent : "
        "jamais deux alertes pour le même (projet, élément) le même jour)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help="Slug d'une seule société à traiter (défaut : toutes).",
        )
        parser.add_argument(
            '--seuil-jours', type=int, default=None,
            help='Horizon « à risque » en jours (défaut du sélecteur).',
        )

    def handle(self, *args, **options):
        from authentication.models import Company

        slug = options.get('company')
        seuil_jours = options.get('seuil_jours')
        if slug:
            try:
                companies = [Company.objects.get(slug=slug)]
            except Company.DoesNotExist:
                raise CommandError(f"Company with slug '{slug}' not found.")
        else:
            companies = list(Company.objects.all())

        if not companies:
            self.stdout.write(self.style.WARNING(
                'No company to process — nothing done.'))
            return

        total_scannes = 0
        total_envoyees = 0
        total_deja = 0
        for company in companies:
            resultat = alertes_retards_projets(
                company, seuil_jours=seuil_jours)
            total_scannes += resultat['nb_projets_scannes']
            total_envoyees += resultat['nb_alertes_envoyees']
            total_deja += resultat['nb_deja_notifiees']

        self.stdout.write(self.style.SUCCESS(
            f'Alertes retards sur {len(companies)} société(s) : '
            f'{total_scannes} projet(s) scanné(s), '
            f'{total_envoyees} alerte(s) envoyée(s), '
            f'{total_deja} déjà notifiée(s) aujourd\'hui.'))
