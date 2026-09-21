"""NTHOT1 — App hospitality + plan des chambres/unités.

Done = une chambre est créée avec son type et son statut par défaut `libre`,
isolation tenant testée.
"""
from django.test import TestCase

from apps.hospitality.models import Chambre, TypeChambre

from .helpers import auth, make_company, make_user, rows


class PlanChambresApiTests(TestCase):
    BASE_TYPES = '/api/django/hospitality/types-chambre/'
    BASE_CHAMBRES = '/api/django/hospitality/chambres/'

    def setUp(self):
        self.co_a = make_company('hot-a', 'Hôtel A')
        self.co_b = make_company('hot-b', 'Hôtel B')
        self.user_a = make_user(self.co_a, 'hot-a-user')
        self.user_b = make_user(self.co_b, 'hot-b-user')
        self.type_a = TypeChambre.objects.create(
            company=self.co_a, libelle='Standard', capacite_max=2)

    def test_chambre_created_with_type_and_default_statut_libre(self):
        api = auth(self.user_a)
        resp = api.post(
            self.BASE_CHAMBRES,
            {'type_chambre': self.type_a.id, 'numero': '101'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        chambre = Chambre.objects.get(id=resp.data['id'])
        self.assertEqual(chambre.type_chambre_id, self.type_a.id)
        self.assertEqual(chambre.statut, Chambre.Statut.LIBRE)
        self.assertEqual(chambre.company, self.co_a)

    def test_tenant_isolation_chambres(self):
        Chambre.objects.create(
            company=self.co_a, type_chambre=self.type_a, numero='101')
        api_b = auth(self.user_b)
        resp = api_b.get(self.BASE_CHAMBRES)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_tenant_isolation_types_chambre(self):
        api_b = auth(self.user_b)
        resp = api_b.get(self.BASE_TYPES)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_filter_by_statut(self):
        c1 = Chambre.objects.create(
            company=self.co_a, type_chambre=self.type_a, numero='101')
        Chambre.objects.create(
            company=self.co_a, type_chambre=self.type_a, numero='102',
            statut=Chambre.Statut.HORS_SERVICE)
        api = auth(self.user_a)
        resp = api.get(self.BASE_CHAMBRES, {'statut': 'libre'})
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['id'], c1.id)

    def test_write_forbidden_for_normal_role(self):
        normal = make_user(self.co_a, 'hot-a-normal', role='normal')
        resp = auth(normal).post(
            self.BASE_CHAMBRES,
            {'type_chambre': self.type_a.id, 'numero': '201'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)
