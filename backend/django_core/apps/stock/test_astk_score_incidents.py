"""ASTK187 — facteur incidents qualité critiques du score de risque.

Run :
    python manage.py test apps.stock.test_astk_score_incidents -v 2
"""
import datetime

from django.test import TestCase

from apps.stock import selectors as stock_selectors
from apps.stock.models import Fournisseur, IncidentQualiteFournisseur
from authentication.models import Company


class ScoreIncidentsTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='astk187-co', defaults={'nom': 'ASTK187 Co'})
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Four ASTK187')

    def _score(self):
        return stock_selectors.score_risque_fournisseur(
            self.company, self.fournisseur.pk)

    def _incident(self, gravite='critique', resolu=False):
        return IncidentQualiteFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            gravite=gravite, resolu=resolu,
            date_incident=datetime.date(2026, 10, 1))

    def test_incidents_critiques_penalisent(self):
        for _ in range(3):
            self._incident()
        res = self._score()
        facteur = next(f for f in res['facteurs']
                       if f['code'] == 'incidents_qualite')
        self.assertGreater(facteur['penalite'], 0)
        self.assertEqual(facteur['detail']['incidents_critiques_ouverts'], 3)
        self.assertNotEqual(res['niveau'], 'faible')

    def test_resolus_et_mineurs_ignores(self):
        self._incident(resolu=True)
        self._incident(gravite='mineure')
        res = self._score()
        self.assertEqual(res['score'], 100)

    def test_aucun_facteur_litiges(self):
        res = self._score()
        codes = [f['code'] for f in res['facteurs']]
        self.assertNotIn('litiges', codes)
        for f in res['facteurs']:
            self.assertNotIn('litige', f['libelle'].lower())
