"""VEIL21 — ``manage.py veille_exporter_fiches --decouverte <id> [--sortie f]``.

Écrit un JSONL d'UNE fiche par annonceur ``incertain`` de la découverte (tri
IA hors ligne du pilote, D-VEIL-8). Champs de la LISTE BLANCHE seulement
(``veille_decouverte.CHAMPS_FICHE``) : aucun jeton, aucune URL de snapshot.
Une décision humaine n'est jamais renvoyée au tri.
"""
import json

from django.core.management.base import BaseCommand, CommandError

from apps.adsengine import veille_decouverte as vd
from apps.adsengine.models import VeilleDecouverte


class Command(BaseCommand):
    help = "Exporte les fiches des annonceurs incertains d'une découverte."

    def add_arguments(self, parser):
        parser.add_argument('--decouverte', type=int, required=True)
        parser.add_argument('--sortie', default='',
                            help='Fichier JSONL (défaut : sortie standard).')

    def handle(self, *args, **options):
        dec = VeilleDecouverte.objects.filter(pk=options['decouverte']).first()
        if dec is None:
            raise CommandError(
                f"Découverte introuvable : {options['decouverte']}.")
        annonceurs = (vd.annonceurs_de(dec).filter(classe='incertain')
                      .select_related('verdict_courant').order_by('id'))
        lignes = [json.dumps(vd.fiche_tri(a), ensure_ascii=False)
                  for a in annonceurs
                  if not (a.verdict_courant
                          and a.verdict_courant.decide_par == 'humain')]
        texte = '\n'.join(lignes) + ('\n' if lignes else '')
        if options['sortie']:
            with open(options['sortie'], 'w', encoding='utf-8') as fichier:
                fichier.write(texte)
            self.stderr.write(f'{len(lignes)} fiche(s) écrite(s).')
        else:
            self.stdout.write(texte, ending='')
