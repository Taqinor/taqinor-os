"""Notifie les ressources en retard de saisie de temps (XPRJ7).

Pour chaque société (ou une seule ``--company``), détecte les ressources
ACTIVES liées à un compte utilisateur qui ont des jours OUVRÉS sans saisie de
``Timesheet`` sur la fenêtre ``[--debut, --fin]`` (défaut : les 7 derniers
jours) et diffuse une notification interne PAR RESSOURCE en retard via le
service ``notifications`` existant. IDEMPOTENT : relancer la commande plusieurs
fois le même jour ne notifie jamais deux fois la même ressource pour la même
fenêtre (voir ``services.rappeler_temps_manquants``).

Pensé pour être exécuté à la demande ou par un planificateur (cron / Celery
beat).

Run (dans le conteneur django_core ou avec les variables DB) :
  python manage.py rappels_timesheets                              # 7 derniers jours, toutes sociétés
  python manage.py rappels_timesheets --company taqinor-demo        # une société
  python manage.py rappels_timesheets --debut 2026-07-01 --fin 2026-07-31
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError

from apps.gestion_projet.services import rappeler_temps_manquants


class Command(BaseCommand):
    help = (
        "Notifie les ressources en retard de saisie de temps sur une fenêtre "
        "(défaut : 7 derniers jours), par société ou pour une seule "
        "--company (idempotent : une ressource n'est jamais notifiée deux "
        "fois pour la même fenêtre le même jour)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help="Slug d'une seule société à traiter (défaut : toutes).",
        )
        parser.add_argument(
            '--debut', default=None,
            help='Date de début YYYY-MM-DD (défaut : aujourd\'hui - 7 jours).',
        )
        parser.add_argument(
            '--fin', default=None,
            help="Date de fin YYYY-MM-DD (défaut : aujourd'hui).",
        )

    def handle(self, *args, **options):
        from authentication.models import Company

        slug = options.get('company')
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

        today = date.today()
        debut_raw = options.get('debut')
        fin_raw = options.get('fin')
        try:
            debut = date.fromisoformat(debut_raw) if debut_raw \
                else today - timedelta(days=7)
            fin = date.fromisoformat(fin_raw) if fin_raw else today
        except ValueError as exc:
            raise CommandError(
                f'Date invalide (format attendu YYYY-MM-DD) : {exc}')

        total_en_retard = 0
        total_notifies = 0
        total_deja = 0
        for company in companies:
            resultat = rappeler_temps_manquants(company, debut, fin)
            total_en_retard += resultat['nb_en_retard']
            total_notifies += resultat['nb_notifies']
            total_deja += resultat['nb_deja_notifies']

        self.stdout.write(self.style.SUCCESS(
            f'Rappels temps manquants [{debut} → {fin}] sur '
            f'{len(companies)} société(s) : {total_en_retard} ressource(s) '
            f'en retard, {total_notifies} notification(s) envoyée(s), '
            f'{total_deja} déjà notifiée(s) aujourd\'hui.'))
