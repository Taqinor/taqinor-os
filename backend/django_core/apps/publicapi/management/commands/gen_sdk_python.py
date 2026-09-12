"""NTAPI28 — émet le SDK Python de l'API publique dans un dossier.

    python manage.py gen_sdk_python --dossier docs/sdk/python

Le code est DÉRIVÉ de l'OpenAPI (NTAPI20), lui-même dérivé de la référence FR
(FG105) : régénérer après tout ajout d'endpoint suffit, il n'y a jamais de
liste d'endpoints à tenir à la main dans le SDK.

Pas de publication PyPI (le plan la garde explicitement hors périmètre) :
cette commande écrit un artefact de dépôt, rien de plus.
"""
from django.core.management.base import BaseCommand

from apps.publicapi.sdk_python import NOM_MODULE, ecrire

DOSSIER_PAR_DEFAUT = 'docs/sdk/python'


class Command(BaseCommand):
    help = ("NTAPI28 — génère le client Python de l'API publique depuis "
            "l'OpenAPI (aucune publication PyPI).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--dossier', default=DOSSIER_PAR_DEFAUT,
            help=f'Dossier de sortie (défaut : {DOSSIER_PAR_DEFAUT}).')
        parser.add_argument(
            '--max-reprises', type=int, default=3,
            help='Reprises maximales sur 429 dans le client généré (défaut 3).')

    def handle(self, *args, **options):
        fichier = ecrire(options['dossier'],
                         max_reprises=options['max_reprises'])
        self.stdout.write(self.style.SUCCESS(
            f'SDK Python écrit : {fichier} ({NOM_MODULE})'))
