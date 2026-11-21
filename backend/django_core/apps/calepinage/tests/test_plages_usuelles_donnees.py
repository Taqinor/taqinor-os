"""ACAL701 — le fichier de bandes « usuelles » par étape : chaque bande est
SOURCÉE (url https, date de lecture ISO non future), bien bornée, définie
comme part de l'énergie qui entre dans l'étape, et nomme une étape réelle.

Nouveau fichier car : aucun module de test ne couvre un fichier de données de
bandes. Aucune base, aucun réseau.
"""
from __future__ import annotations

import datetime
import json
import pathlib
import unittest

from apps.calepinage.services.chaine_pertes import ORDRE_ETAPES

FICHIER = (pathlib.Path(__file__).resolve().parents[1] / 'data'
           / 'plages_usuelles.json')
GRANDEUR = 'perte_pct_etape'


def _donnees():
    return json.loads(FICHIER.read_text(encoding='utf-8'))


def _erreurs_de_bande(bande, aujourd_hui):
    """Les défauts d'une bande (liste vide = bande recevable)."""
    erreurs = []
    if not str(bande.get('url') or '').startswith('https://'):
        erreurs.append('url')
    try:
        lue = datetime.date.fromisoformat(str(bande.get('date_lecture')))
        if lue > aujourd_hui:
            erreurs.append('date_lecture future')
    except ValueError:
        erreurs.append('date_lecture')
    bas, haut = bande.get('min'), bande.get('max')
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
               for v in (bas, haut)) or bas > haut:
        erreurs.append('min/max')
    if bande.get('grandeur') != GRANDEUR:
        erreurs.append('grandeur')
    if bande.get('unite') != '%' or bande.get('source') != 'texte':
        erreurs.append('unite/source')
    return erreurs


class PlagesUsuellesDonneesTest(unittest.TestCase):

    def setUp(self):
        self.donnees = _donnees()
        self.aujourd_hui = datetime.date.today()

    def test_chaque_bande_est_sourcee_et_bornee(self):
        for bande in self.donnees['bandes']:
            with self.subTest(etape=bande.get('etape')):
                self.assertEqual(_erreurs_de_bande(bande, self.aujourd_hui),
                                 [])
                self.assertIn(bande['etape'], ORDRE_ETAPES)
        total = self.donnees.get('total')
        if total is not None:
            self.assertEqual(_erreurs_de_bande(total, self.aujourd_hui), [])

    def test_au_plus_une_bande_par_etape(self):
        etapes = [bande['etape'] for bande in self.donnees['bandes']]
        self.assertEqual(len(etapes), len(set(etapes)))
        self.assertLessEqual(len(etapes), len(ORDRE_ETAPES))

    def test_sans_bande_nomme_des_etapes_reelles_avec_motif(self):
        avec = {bande['etape'] for bande in self.donnees['bandes']}
        for ligne in self.donnees['sans_bande']:
            with self.subTest(etape=ligne.get('etape')):
                self.assertIn(ligne['etape'], ORDRE_ETAPES)
                self.assertNotIn(ligne['etape'], avec)
                self.assertTrue(ligne['motif'].strip())

    def test_le_garde_refuse_une_bande_sans_url(self):
        # Mutant « retirer l'url d'une bande » : le garde la refuse.
        bande = {'etape': 'thermique', 'min': 1.0, 'max': 2.0, 'unite': '%',
                 'grandeur': GRANDEUR, 'source': 'texte',
                 'url': 'https://exemple.invalid/page',
                 'date_lecture': '2026-11-21'}
        self.assertEqual(_erreurs_de_bande(bande, datetime.date(2026, 11, 21)),
                         [])
        sans_url = dict(bande, url='')
        self.assertIn('url', _erreurs_de_bande(
            sans_url, datetime.date(2026, 11, 21)))


if __name__ == '__main__':
    unittest.main()
