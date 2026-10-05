"""VEIL23 — ``manage.py veille_mesurer --decouverte <id> [--modele-ambigu m]``.

Matrice de confusion ; précision, rappel, F1 par classe et pour l'étiquette
dropshipper, avec intervalles de Wilson à 95 % ; taux de passage vers le
second modèle et vers l'humain ; rappel de DÉCOUVERTE séparé (concurrents
nommés) ; verdict « atteint / non atteint » contre les seuils
``VEILLE_SEUIL_*`` (90/90/80, fixés le 03/10/2026). Refus si moins de 200
étiquettes de test, si une étiquette n'est pas humaine, ou si une étiquette de
test a servi à l'étalonnage.
"""
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.adsengine import veille_mesures
from apps.adsengine.models import VeilleDecouverte


class Command(BaseCommand):
    help = "Mesure précision et rappel du tri sur l'échantillon étiqueté."

    def add_arguments(self, parser):
        parser.add_argument('--decouverte', type=int, required=True)
        parser.add_argument(
            '--modele-ambigu', default='',
            help='Modèle du second passage (défaut : VEILLE_IA_MODELE_AMBIGU).')

    def handle(self, *args, **options):
        dec = VeilleDecouverte.objects.filter(pk=options['decouverte']).first()
        if dec is None:
            raise CommandError(
                f"Découverte introuvable : {options['decouverte']}.")
        modele = (options['modele_ambigu']
                  or getattr(settings, 'VEILLE_IA_MODELE_AMBIGU', '') or None)
        try:
            rapport = veille_mesures.mesurer_decouverte(
                dec, modele_ambigu=modele)
        except veille_mesures.MesureRefusee as exc:
            raise CommandError(exc.message_fr)
        self.stdout.write(json.dumps(rapport, ensure_ascii=False, indent=2,
                                     default=str))
