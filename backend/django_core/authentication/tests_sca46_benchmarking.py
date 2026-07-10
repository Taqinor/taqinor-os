"""SCA46 — Company.benchmarking_opt_in : le consentement comme donnée.

Vérifie que :
* le défaut est False (opt-in strict) ;
* le champ est exposé en lecture par le profil Paramètres ;
* un admin peut donner/révoquer le consentement via PATCH /parametres/update/ ;
* l'écriture est scopée à la société de l'appelant (jamais un id du corps) ;
* aucune agrégation n'existe (le champ est une pure donnée).
"""
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from testkit.base import TenantAPITestCase
from testkit.factories import CompanyFactory, UserFactory
from authentication.models import CustomUser


class BenchmarkingOptInDefaultTest(TenantAPITestCase):
    def test_defaut_false(self):
        c = CompanyFactory(nom='OptDefault', slug='optdefault')
        self.assertFalse(c.benchmarking_opt_in)

    def test_expose_dans_company_serializer(self):
        from authentication.serializers import CompanySerializer
        c = CompanyFactory(nom='OptSer', slug='optser')
        data = CompanySerializer(c).data
        self.assertIn('benchmarking_opt_in', data)
        self.assertFalse(data['benchmarking_opt_in'])


class BenchmarkingOptInApiTest(TenantAPITestCase):
    def _admin_client(self):
        admin = UserFactory(
            username='opt-admin', company=self.company,
            role_legacy=CustomUser.ROLE_ADMIN)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(admin)}')
        return api

    def test_profil_expose_le_consentement(self):
        api = self._admin_client()
        r = api.get('/api/django/parametres/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('benchmarking_opt_in', r.data)
        self.assertFalse(r.data['benchmarking_opt_in'])

    def test_admin_donne_puis_revoque_le_consentement(self):
        api = self._admin_client()
        r = api.patch('/api/django/parametres/update/',
                      {'benchmarking_opt_in': True}, format='json')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        self.company.refresh_from_db()
        self.assertTrue(self.company.benchmarking_opt_in)
        # Révocation.
        r = api.patch('/api/django/parametres/update/',
                      {'benchmarking_opt_in': False}, format='json')
        self.assertEqual(r.status_code, 200)
        self.company.refresh_from_db()
        self.assertFalse(self.company.benchmarking_opt_in)

    def test_ecriture_scopee_a_la_societe_de_l_appelant(self):
        # Le consentement posé par la société A ne touche JAMAIS la société B.
        api = self._admin_client()
        api.patch('/api/django/parametres/update/',
                  {'benchmarking_opt_in': True}, format='json')
        self.other_company.refresh_from_db()
        self.assertFalse(self.other_company.benchmarking_opt_in)

    def test_absent_du_corps_inchange(self):
        self.company.benchmarking_opt_in = True
        self.company.save(update_fields=['benchmarking_opt_in'])
        api = self._admin_client()
        r = api.patch('/api/django/parametres/update/',
                      {'nom': 'Nom modifié'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.company.refresh_from_db()
        self.assertTrue(self.company.benchmarking_opt_in)
