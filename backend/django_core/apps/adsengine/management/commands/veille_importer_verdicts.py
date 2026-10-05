"""VEIL21 — ``manage.py veille_importer_verdicts <fichier> --company <id>``.

Relit un JSONL ``{page_id, classe, confiance, dropshipper, indices, modele,
jetons_entree, jetons_sortie}`` (produit par ``tools/veille_tri/trier.py``) et
enregistre chaque ligne en ``VeilleVerdict(decide_par=ia)``. Une ligne sans
``modele`` ou de classe hors contrat est REFUSÉE (erreur FR ligne par ligne) ;
une décision humaine n'est jamais écrasée.
"""
import json

from django.core.management.base import BaseCommand, CommandError

from authentication.models import Company

from apps.adsengine import veille_decouverte as vd


class Command(BaseCommand):
    help = "Importe les verdicts du tri IA hors ligne (pilote de veille)."

    def add_arguments(self, parser):
        parser.add_argument('fichier')
        parser.add_argument('--company', type=int, required=True)

    def handle(self, *args, **options):
        company = Company.objects.filter(pk=options['company']).first()
        if company is None:
            raise CommandError(f"Société introuvable : {options['company']}.")
        compte = {'importe': 0, 'ignore': 0, 'erreur': 0}
        with open(options['fichier'], encoding='utf-8') as fichier:
            for numero, brut in enumerate(fichier, start=1):
                if not brut.strip():
                    continue
                try:
                    ligne = json.loads(brut)
                except ValueError:
                    statut, message = 'erreur', 'JSON illisible'
                else:
                    statut, message = vd.importer_verdict_ia(company, ligne)
                compte[statut] += 1
                if statut != 'importe':
                    self.stderr.write(f'ligne {numero} : {message}')
        self.stdout.write(
            f"{compte['importe']} importé(s), {compte['ignore']} ignoré(s), "
            f"{compte['erreur']} en erreur.")
