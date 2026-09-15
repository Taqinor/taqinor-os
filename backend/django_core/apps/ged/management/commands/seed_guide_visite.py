"""Rattrapage du dépôt GED du guide « visite dans le suivi commercial ».

La migration ged/0048 seede best-effort au déploiement ; si le stockage objet
était indisponible à ce moment-là, cette commande rejoue le dépôt (idempotent
par source — jamais un doublon).
"""
from django.core.management.base import BaseCommand

from apps.ged.services import seed_guide_visite


class Command(BaseCommand):
    help = ('Dépose le guide PDF « La visite technique dans le suivi '
            'commercial » dans la GED de chaque société non-démo '
            '(idempotent).')

    def handle(self, *args, **options):
        crees, existants, echecs = seed_guide_visite()
        self.stdout.write(self.style.SUCCESS(
            f'Guide visite : {crees} déposé(s), {existants} déjà '
            f'présent(s), {echecs} échec(s).'))
        if echecs:
            self.stdout.write(self.style.WARNING(
                'Des dépôts ont échoué — détail dans les logs ; relancer '
                'la commande une fois le stockage disponible.'))
