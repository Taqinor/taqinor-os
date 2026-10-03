"""AGR102 — une courbe de pompe est refusée si elle n'est pas physiquement
lisible (débits strictement croissants, HMT non croissante, valeurs >= 0).

Même règle côté API (``ProduitSerializer.validate_courbe_pompe``) et côté
admin Django (``ProduitAdminForm.clean``). Aucun seuil inventé.
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role, CANONICAL_SYSTEM_ROLES
from apps.stock.admin import ProduitAdminForm
from apps.stock.management.commands.seed_catalogue import (
    OSP, OSP_DEBITS_M3H,
)
from apps.stock.models import Produit
from apps.stock.serializers import controle_courbe_pompe_lisible
from authentication.models import Company

User = get_user_model()
URL_PRODUITS = '/api/django/stock/produits/'


def api_for(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


class TestControleLisible(SimpleTestCase):
    def test_courbe_lisible_passe(self):
        self.assertIsNone(controle_courbe_pompe_lisible(
            {'debits_m3h': [0, 6, 12], 'hmt_m': [91, 88, 85]}))

    def test_hmt_constante_acceptee(self):
        self.assertIsNone(controle_courbe_pompe_lisible(
            {'debits_m3h': [0, 6, 12], 'hmt_m': [80, 80, 70]}))

    def test_debits_non_tries_cite_le_point_3(self):
        msg = controle_courbe_pompe_lisible(
            {'debits_m3h': [0, 12, 10], 'hmt_m': [80, 70, 60]})
        self.assertIn('Point 3', msg)

    def test_debit_repete_refuse(self):
        msg = controle_courbe_pompe_lisible(
            {'debits_m3h': [0, 12, 12], 'hmt_m': [80, 70, 60]})
        self.assertIn('Point 3', msg)

    def test_hmt_croissante_refusee(self):
        msg = controle_courbe_pompe_lisible(
            {'debits_m3h': [0, 6, 12], 'hmt_m': [80, 85, 60]})
        self.assertIn('Point 2', msg)

    def test_valeur_negative_refusee(self):
        self.assertIn('Point 1', controle_courbe_pompe_lisible(
            {'debits_m3h': [-1, 6], 'hmt_m': [80, 70]}))
        self.assertIn('Point 2', controle_courbe_pompe_lisible(
            {'debits_m3h': [0, 6], 'hmt_m': [80, -5]}))

    def test_les_11_courbes_osp_du_seed_passent(self):
        self.assertEqual(len(OSP), 11)
        for nom, sku, _cv, _kw, hmts in OSP:
            self.assertIsNone(
                controle_courbe_pompe_lisible(
                    {'debits_m3h': OSP_DEBITS_M3H, 'hmt_m': hmts}), sku)


class TestApiRefus(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug='agr102-co', defaults={'nom': 'AGR102 Co'})[0]
        roles = {}
        for nom, perms in CANONICAL_SYSTEM_ROLES:
            roles[nom] = Role.objects.create(
                company=cls.company, nom=nom, permissions=list(perms),
                est_systeme=True)
        cls.user = User.objects.create_user(
            username='agr102_dir', password='x', company=cls.company,
            role=roles['Directeur'])

    def _post(self, courbe):
        return api_for(self.user).post(URL_PRODUITS, {
            'nom': 'Pompe courbe AGR102', 'prix_vente': '1',
            'courbe_pompe': courbe}, format='json')

    def test_debits_non_tries_400_cite_le_point_3(self):
        r = self._post({'debits_m3h': [0, 12, 10], 'hmt_m': [80, 70, 60]})
        self.assertEqual(r.status_code, 400)
        self.assertIn('Point 3', str(r.data['courbe_pompe']))

    def test_hmt_croissante_400(self):
        r = self._post({'debits_m3h': [0, 6, 12], 'hmt_m': [80, 85, 60]})
        self.assertEqual(r.status_code, 400)
        self.assertIn('courbe_pompe', r.data)

    def test_valeur_negative_400(self):
        r = self._post({'debits_m3h': [0, 6, 12], 'hmt_m': [80, 70, -1]})
        self.assertEqual(r.status_code, 400)

    def test_courbe_lisible_201(self):
        r = self._post({'debits_m3h': [0, 6, 12], 'hmt_m': [91, 88, 85]})
        self.assertEqual(r.status_code, 201, r.data)

    def test_garde_anti_effacement_inchange(self):
        p = Produit.objects.create(
            company=self.company, nom='Pompe avec courbe', prix_vente=1,
            courbe_pompe={'debits_m3h': [0, 6], 'hmt_m': [80, 70]})
        r = api_for(self.user).patch(
            f'{URL_PRODUITS}{p.pk}/', {'courbe_pompe': None}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('courbe_pompe', r.data)


class TestAdminMiroir(TestCase):
    def test_formulaire_admin_refuse_courbe_illisible(self):
        co = Company.objects.get_or_create(
            slug='agr102-admin-co', defaults={'nom': 'AGR102 Admin'})[0]
        p = Produit.objects.create(company=co, nom='Pompe admin', prix_vente=1)
        form = ProduitAdminForm(
            data={'nom': 'Pompe admin', 'prix_vente': '1',
                  'courbe_pompe': '{"debits_m3h": [0, 12, 10], '
                                  '"hmt_m": [80, 70, 60]}'},
            instance=p)
        form.is_valid()
        self.assertIn('courbe_pompe', form.errors)
        self.assertIn('Point 3', ' '.join(form.errors['courbe_pompe']))
