"""ASTK97 — renommer une marque propage le libellé à ``Produit.marque``.

Run :
    python manage.py test apps.stock.test_astk_marque_renommage -v 2
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.stock.models import Marque, Produit
from authentication.models import Company, CustomUser

URL = '/api/django/stock/marques/'


class MarqueRenommageTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='astk97-co', defaults={'nom': 'ASTK97 Co'})
        self.autre, _ = Company.objects.get_or_create(
            slug='astk97-autre', defaults={'nom': 'ASTK97 Autre'})
        self.user = CustomUser.objects.create_user(
            username='astk97-admin', password='x',
            role_legacy='admin', company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def _produit(self, company, sku):
        return Produit.objects.create(
            company=company, nom=f'P {sku}', sku=sku, marque='Deye',
            prix_vente='100.00')

    def test_renommage_propage_et_pas_de_doublon(self):
        marque = Marque.objects.create(company=self.company, nom='Deye')
        p1 = self._produit(self.company, 'A97-1')
        p2 = self._produit(self.company, 'A97-2')
        etranger = self._produit(self.autre, 'A97-3')

        r = self.api.patch(f'{URL}{marque.id}/', {'nom': 'Deye 2'},
                           format='json')
        self.assertEqual(r.status_code, 200, r.content)

        liste = self.api.get(URL).json()
        noms = [m['nom'] for m in (liste['results']
                                   if isinstance(liste, dict) else liste)]
        self.assertEqual(noms, ['Deye 2'])
        # Persistance : relu depuis la base.
        p1.refresh_from_db()
        p2.refresh_from_db()
        etranger.refresh_from_db()
        self.assertEqual(p1.marque, 'Deye 2')
        self.assertEqual(p2.marque, 'Deye 2')
        self.assertEqual(etranger.marque, 'Deye')
