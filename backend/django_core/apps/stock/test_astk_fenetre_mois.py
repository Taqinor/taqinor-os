"""ASTK183 — ``?fenetre_mois=`` parsé une seule fois : illisible → 400 nommé.

Run :
    python manage.py test apps.stock.test_astk_fenetre_mois -v 2
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.stock.models import Fournisseur
from authentication.models import Company, CustomUser


class FenetreMoisTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='astk183-co', defaults={'nom': 'ASTK183 Co'})
        self.user = CustomUser.objects.create_user(
            username='astk183-admin', password='x',
            role_legacy='admin', company=self.company)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Four ASTK183')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.base = (f'/api/django/stock/fournisseurs/'
                     f'{self.fournisseur.id}/')

    def _assert_400_nomme(self, r):
        # Forme DRF native à la racine + enveloppe YAPIC3 `error` (son
        # `request_id` change à chaque requête : comparé hors du corps).
        corps = r.json()
        enveloppe = corps.pop('error')
        attendu = {'fenetre_mois': ['Entier de 1 à 36 attendu.']}
        self.assertEqual(corps, attendu)
        self.assertEqual(enveloppe['code'], 'validation_error')
        self.assertEqual(enveloppe['fields'], attendu)

    def test_otif_valeur_illisible_400(self):
        r = self.api.get(self.base + 'otif/?fenetre_mois=abc')
        self.assertEqual(r.status_code, 400)
        self._assert_400_nomme(r)

    def test_delai_mesure_valeur_illisible_400(self):
        r = self.api.get(self.base + 'delai-mesure/?fenetre_mois=abc')
        self.assertEqual(r.status_code, 400)
        self._assert_400_nomme(r)

    def test_hors_bornes_400(self):
        r = self.api.get(self.base + 'otif/?fenetre_mois=99')
        self.assertEqual(r.status_code, 400)

    def test_defaut_12(self):
        r = self.api.get(self.base + 'otif/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['fenetre_mois'], 12)
        r = self.api.get(self.base + 'delai-mesure/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['fenetre_mois'], 12)

    def test_fenetre_6_inchangee(self):
        r = self.api.get(self.base + 'otif/?fenetre_mois=6')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['fenetre_mois'], 6)
