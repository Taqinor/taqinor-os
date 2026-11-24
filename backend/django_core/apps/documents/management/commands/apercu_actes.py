"""Tire les PDF d'exemple des actes du dossier contractuel, sans base.

Lit ``apps/documents/contract_samples/acte_contractuel.json`` (l'exemple
principal et chaque ``exemple_*`` qui porte un ``contenu``) et rend chaque
contenu par ``contrats.rendu.pdf_de`` — exactement le rendu servi par l'API.
Aucune lecture de base : utile pour regarder la mise en page après une
modification du rendu ou des textes.

Exemple :
  python manage.py apercu_actes --sortie /tmp/actes
  python manage.py apercu_actes --sortie /tmp/actes --html
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

ECHANTILLON = (Path(__file__).resolve().parents[2]
               / 'contract_samples' / 'acte_contractuel.json')


def exemples():
    """``[(nom, contenu)]`` des exemples du contrat d'API qui portent un
    contenu (l'exemple principal d'abord)."""
    donnees = json.loads(ECHANTILLON.read_text(encoding='utf-8'))
    sortie = []
    for cle, valeur in donnees.items():
        if not (cle == 'exemple' or cle.startswith('exemple_')):
            continue
        if isinstance(valeur, dict) and isinstance(valeur.get('contenu'), dict):
            nom = 'contrat_installation' if cle == 'exemple' else cle[len('exemple_'):]
            sortie.append((nom, valeur['contenu']))
    return sortie


class Command(BaseCommand):
    help = ("Rend les PDF d'exemple des quatre actes du dossier contractuel "
            "depuis le contrat d'API (sans base de données).")

    def add_arguments(self, parser):
        parser.add_argument('--sortie', required=True,
                            help='Dossier où écrire les PDF.')
        parser.add_argument('--html', action='store_true',
                            help='Écrit aussi le HTML de chaque acte.')

    def handle(self, *args, **options):
        from apps.documents.contrats.rendu import html_de, pdf_de
        dossier = Path(options['sortie'])
        try:
            dossier.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CommandError(f'Dossier de sortie inutilisable : {exc}')
        liste = exemples()
        if not liste:
            raise CommandError("Aucun exemple avec contenu dans le contrat d'API.")
        for nom, contenu in liste:
            chemin = dossier / f'{nom}.pdf'
            chemin.write_bytes(pdf_de(contenu))
            if options['html']:
                (dossier / f'{nom}.html').write_text(html_de(contenu),
                                                     encoding='utf-8')
            self.stdout.write(f'{chemin}')
        self.stdout.write(self.style.SUCCESS(f'{len(liste)} acte(s) rendu(s).'))
