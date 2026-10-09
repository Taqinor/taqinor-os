"""APDF21 (D-APDF-1 = a) — identité légale du profil société.

Un responsable PATCH ``capital_social`` / ``forme_juridique`` sur le profil de SA
société ; ``company_identity`` les expose (chaîne vide quand non renseignés) ;
la société n'est jamais lue du corps. Le contrat committé
(``contract_samples/company_identite_legale.json``) liste exactement ces clés.

Test-du-test : retirer les clés de ``company_identity`` ⇒
``test_company_identity_expose`` échoue.
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.parametres.models_company import CompanyProfile
from apps.parametres.selectors import company_identity
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from authentication.models import Company

User = get_user_model()
URL_GET = '/api/django/parametres/'
URL_PATCH = '/api/django/parametres/update/'
ECHANTILLON = (Path(__file__).parent / 'contract_samples'
               / 'company_identite_legale.json')


class IdentiteLegaleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APDF21', slug='apdf21')
        self.autre = Company.objects.create(nom='APDF21 autre', slug='apdf21b')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
        self.user = User.objects.create_user(
            username='apdf21', password='x', role=role, company=self.company)
        CompanyProfile.get(company=self.company)
        CompanyProfile.get(company=self.autre)

    def _api(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(self.user))
        return api

    def test_vide_par_defaut(self):
        identite = company_identity(self.company)
        self.assertEqual(identite['capital_social'], '')
        self.assertEqual(identite['forme_juridique'], '')
        r = self._api().get(URL_GET)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['capital_social'], '')
        self.assertEqual(r.data['forme_juridique'], '')

    def test_patch_et_relecture(self):
        api = self._api()
        r = api.patch(URL_PATCH, {
            'capital_social': '100 000,00 MAD',
            'forme_juridique': 'SARLAU',
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        relu = api.get(URL_GET)
        self.assertEqual(relu.data['capital_social'], '100 000,00 MAD')
        self.assertEqual(relu.data['forme_juridique'], 'SARLAU')

    def test_company_identity_expose(self):
        self._api().patch(URL_PATCH, {
            'capital_social': '100 000,00 MAD',
            'forme_juridique': 'SARLAU',
        }, format='json')
        identite = company_identity(self.company)
        self.assertEqual(identite['capital_social'], '100 000,00 MAD')
        self.assertEqual(identite['forme_juridique'], 'SARLAU')

    def test_company_jamais_lue_du_corps(self):
        r = self._api().patch(URL_PATCH, {
            'company': self.autre.pk,
            'capital_social': '1 000,00 MAD',
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(
            CompanyProfile.objects.get(company=self.company).capital_social,
            '1 000,00 MAD')
        self.assertEqual(
            CompanyProfile.objects.get(company=self.autre).capital_social, '')

    def test_contrat_liste_les_cles(self):
        contrat = json.loads(ECHANTILLON.read_text(encoding='utf-8'))
        self.assertEqual(
            sorted(contrat['exemple']), ['capital_social', 'forme_juridique'])
        # Le contrat et la vraie réponse portent les mêmes clés.
        reponse = self._api().get(URL_GET).data
        for cle in contrat['exemple']:
            self.assertIn(cle, reponse)
