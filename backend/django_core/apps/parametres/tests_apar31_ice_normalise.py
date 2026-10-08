"""APAR31 — l'ICE saisi est NORMALISÉ (espaces, tirets, points, préfixe
« ICE », chiffres arabo-indiens) avant validation, puis stocké en 15 chiffres
(C-APAR-041). Avant : « 001 234 567 000 089 » → 400 et les autres champs du
formulaire perdus.
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.parametres.models_company import CompanyProfile
from apps.parametres.tax_id_validators import normaliser_ice, validate_ice_ma
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from authentication.models import Company

User = get_user_model()
URL_PATCH = '/api/django/parametres/update/'


class NormaliserIceTests(SimpleTestCase):
    def test_formes_humaines(self):
        for saisie in ('001 234 567 000 089', '001-234-567-000-089',
                       '001.234.567.000.089', 'ICE 001234567000089',
                       'ice: 001 234 567 000 089',
                       '٠٠١٢٣٤٥٦'
                       '٧٠٠٠٠٨٩'):
            self.assertEqual(normaliser_ice(saisie), '001234567000089',
                             saisie)
            self.assertTrue(validate_ice_ma(saisie)['valide'], saisie)

    def test_quatorze_chiffres_refuse(self):
        self.assertFalse(validate_ice_ma('001 234 567 000 08')['valide'])
        self.assertFalse(validate_ice_ma('12345678901234A')['valide'])

    def test_vide_reste_vide(self):
        self.assertEqual(normaliser_ice(None), '')
        self.assertTrue(validate_ice_ma('  ')['valide'])


class IceNormaliseTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR31', slug='apar31')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
        self.user = User.objects.create_user(
            username='apar31', password='x', role=role, company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(self.user))

    def test_ice_espace_enregistre_normalise(self):
        r = self.api.patch(URL_PATCH, {
            'ice': '001 234 567 000 089', 'banque': 'CIH'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['ice'], '001234567000089')
        profil = CompanyProfile.objects.get(company=self.company)
        self.assertEqual(profil.ice, '001234567000089')
        self.assertEqual(profil.banque, 'CIH')

    def test_ice_tirets_enregistre_normalise(self):
        r = self.api.patch(
            URL_PATCH, {'ice': '001-234-567-000-089'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['ice'], '001234567000089')

    def test_ice_quatorze_chiffres_400_sous_le_champ(self):
        r = self.api.patch(URL_PATCH, {
            'ice': '001 234 567 000 08', 'banque': 'X'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('ice', r.data)
        profil = CompanyProfile.objects.get(company=self.company)
        self.assertNotEqual(profil.banque, 'X')
