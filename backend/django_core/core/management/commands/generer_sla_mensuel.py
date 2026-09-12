"""NTOBS3 — génère le snapshot SLA mensuel de toutes les sociétés actives.

Calcule et persiste (upsert) un ``core.SlaSnapshot`` par société pour une
période donnée (défaut : le mois PRÉCÉDENT — càd le mois qui vient de se
terminer). Câblée sur Celery Beat le 1er du mois (voir
``erp_agentique/celery.py``), aussi exécutable à la main pour un rattrapage.

Exemples :
  python manage.py generer_sla_mensuel
  python manage.py generer_sla_mensuel --periode=2026-08
"""
import datetime

from django.core.management.base import BaseCommand, CommandError

from core.sla import generer_sla_mensuel


class Command(BaseCommand):
    help = 'Génère le snapshot SLA mensuel de toutes les sociétés actives.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--periode', default=None,
            help='Mois à générer, format YYYY-MM (défaut : le mois précédent).')

    def handle(self, *args, **options):
        periode = None
        if options['periode']:
            try:
                annee_str, mois_str = options['periode'].split('-')
                periode = datetime.date(int(annee_str), int(mois_str), 1)
            except (ValueError, TypeError) as exc:
                raise CommandError(
                    'Format de période invalide (attendu YYYY-MM).') from exc

        snapshots = generer_sla_mensuel(periode)
        self.stdout.write(self.style.SUCCESS(
            f'{len(snapshots)} rapport(s) SLA généré(s).'))
