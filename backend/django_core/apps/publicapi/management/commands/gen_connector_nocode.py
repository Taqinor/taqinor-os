"""NTAPI32 — émet le manifeste du connecteur no-code (Zapier / Make).

    python manage.py gen_connector_nocode --dossier docs/connectors/zapier-make

Le manifeste est DÉRIVÉ du vocabulaire d'évènements, de la table de scopes du
flux (NTAPI17) et de la référence FR des endpoints d'écriture (FG105) : ajouter
un évènement ou un endpoint d'écriture enrichit le connecteur sans qu'aucune
liste ne soit tenue à la main.

Aucune publication sur l'annuaire Zapier/Make (étape fondateur, hors périmètre) :
cette commande écrit un artefact de dépôt, rien de plus.
"""
from django.core.management.base import BaseCommand

from apps.publicapi.connector_nocode import NOM_FICHIER, ecrire

DOSSIER_PAR_DEFAUT = 'docs/connectors/zapier-make'


class Command(BaseCommand):
    help = ("NTAPI32 — génère le manifeste du connecteur no-code "
            "(triggers sur le flux d'évènements + actions d'écriture).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--dossier', default=DOSSIER_PAR_DEFAUT,
            help=f'Dossier de sortie (défaut : {DOSSIER_PAR_DEFAUT}).')

    def handle(self, *args, **options):
        fichier = ecrire(options['dossier'])
        self.stdout.write(self.style.SUCCESS(
            f'Manifeste du connecteur écrit : {fichier} ({NOM_FICHIER})'))
