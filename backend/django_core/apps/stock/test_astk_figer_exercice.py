"""ASTK203 (C-ASTK-051, MVT-19) — l'inventaire annuel d'un exercice NON CLOS
(31/12 ≥ aujourd'hui) ne se fige pas.

Sonde MVT-19 rejouée : le 06/10/2026, POST inventaires-annuels/figer/
{exercice: 2026} répondait 201 (date_reference 2026-12-31, snapshot
« immuable » d'un exercice encore ouvert) et {exercice: 2027} aussi. Après
correction : 400 nommé sous `exercice`, aucun InventaireAnnuel créé ;
l'exercice clos 2025 reste figeable (201).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from freezegun import freeze_time
from rest_framework.test import APIClient

from authentication.models import Company
from apps.stock.models import InventaireAnnuel

User = get_user_model()
URL = '/api/django/stock/inventaires-annuels/figer/'


@freeze_time('2026-10-06 10:00:00')
class FigerTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='astk203', slug='astk203')
        self.admin = User.objects.create_user(
            username='astk203-admin', password='x', company=self.company,
            role_legacy='admin')
        self.api = APIClient()
        self.api.force_authenticate(self.admin)

    def _figer(self, exercice):
        return self.api.post(URL, {'exercice': exercice}, format='json')

    def test_exercice_en_cours_400(self):
        resp = self._figer(2026)
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(resp.json()['exercice'], [
            "L'exercice 2026 n'est pas clos (31/12/2026) : figez-le à partir "
            'du 01/01/2027.'])
        self.assertFalse(InventaireAnnuel.objects.filter(
            company=self.company, exercice=2026).exists())

    def test_exercice_futur_400(self):
        resp = self._figer(2027)
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('2027', resp.json()['exercice'][0])
        self.assertFalse(InventaireAnnuel.objects.filter(
            company=self.company, exercice__in=[2026, 2027]).exists())

    def test_exercice_clos_201(self):
        resp = self._figer(2025)
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()['exercice'], 2025)
        self.assertTrue(InventaireAnnuel.objects.filter(
            company=self.company, exercice=2025).exists())

    @freeze_time('2026-12-31 12:00:00')
    def test_dernier_jour_de_l_exercice_encore_refuse(self):
        self.assertEqual(self._figer(2026).status_code, 400)

    @freeze_time('2027-01-01 09:00:00')
    def test_lendemain_de_la_cloture_201(self):
        self.assertEqual(self._figer(2026).status_code, 201)
