"""ZRH5 — Clôture automatique des pointages oubliés (« Automatic check-out »
Odoo).

Un pointage ARRIVÉE sans DÉPART reste ouvert indéfiniment si l'employé oublie
de pointer son départ, faussant les heures. Cette commande clôture les
pointages ouverts au-delà du seuil société (réglage RH
``pointage_auto_depart_apres_h``, désactivé par défaut) : ``heure_depart =
heure_arrivee + seuil``, ``depart_auto=True``, et crée un ``IncidentPresence``
« départ automatique » pour traçabilité. Dry-run par défaut.
"""
from django.core.management.base import BaseCommand

from apps.rh import services


class Command(BaseCommand):
    help = (
        'ZRH5 — clôture les pointages ouverts au-delà du seuil société '
        '(pointage_auto_depart_apres_h). Dry-run par défaut.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Committe réellement (sinon dry-run, rien n’est écrit).')
        parser.add_argument(
            '--company', type=int, default=None,
            help='Limiter à une société (ID). Défaut : toutes.')

    def handle(self, *args, **options):
        apply_ = options['apply']
        company_id = options['company']

        from authentication.models import Company
        companies = Company.objects.all()
        if company_id is not None:
            companies = companies.filter(pk=company_id)

        total = 0
        for company in companies:
            traites = services.clore_pointages_ouverts(
                company, apply=apply_)
            if traites:
                self.stdout.write(
                    f'{company} : {len(traites)} pointage(s) ouvert(s) '
                    'traité(s).')
            total += len(traites)

        mode = 'APPLIQUÉ' if apply_ else 'DRY-RUN'
        self.stdout.write(self.style.SUCCESS(
            f'[{mode}] {total} pointage(s) clôturé(s) au total.'))
