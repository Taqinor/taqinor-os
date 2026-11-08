"""NTI18N10 — CompanyProfile.fuseau_horaire (affichage, jamais le stockage).

Couvre : défaut 'Africa/Casablanca' (comportement historique inchangé),
validation IANA (accepte Africa/Dakar, rejette une valeur inconnue), lecture
via GET /parametres/, écriture via PATCH /parametres/update/ (rôle
responsable/admin uniquement), isolation multi-tenant.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.parametres.models import CompanyProfile
from apps.parametres.serializers import CompanyProfileSerializer

User = get_user_model()


def _company(slug='nti18n10-co', nom='NTI18N10 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class FuseauHoraireFieldTests(TestCase):
    def test_default_is_africa_casablanca(self):
        company = _company()
        profile = CompanyProfile.get(company)
        self.assertEqual(profile.fuseau_horaire, 'Africa/Casablanca')


class FuseauHoraireSerializerValidationTests(TestCase):
    def setUp(self):
        self.company = _company('nti18n10-co2', 'NTI18N10 Co2')
        self.profile = CompanyProfile.get(self.company)

    def test_accepts_valid_iana_zone(self):
        ser = CompanyProfileSerializer(
            self.profile, data={'fuseau_horaire': 'Africa/Dakar'}, partial=True)
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_rejects_unknown_zone(self):
        ser = CompanyProfileSerializer(
            self.profile, data={'fuseau_horaire': 'Pas/UnFuseau'}, partial=True)
        self.assertFalse(ser.is_valid())
        self.assertIn('fuseau_horaire', ser.errors)


class FuseauHoraireApiTests(TestCase):
    def setUp(self):
        self.company = _company('nti18n10-co3', 'NTI18N10 Co3')
        self.admin = User.objects.create_user(
            username='nti18n10_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def test_get_profile_exposes_fuseau_horaire(self):
        resp = self.api.get('/api/django/parametres/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['fuseau_horaire'], 'Africa/Casablanca')

    def test_patch_persists_new_timezone(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'fuseau_horaire': 'Africa/Dakar'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['fuseau_horaire'], 'Africa/Dakar')
        profile = CompanyProfile.get(self.company)
        profile.refresh_from_db()
        self.assertEqual(profile.fuseau_horaire, 'Africa/Dakar')

    def test_patch_rejects_unknown_zone(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'fuseau_horaire': 'Not/AZone'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_only_affects_own_company(self):
        other_company = _company('nti18n10-co4', 'NTI18N10 Co4')
        other_profile = CompanyProfile.get(other_company)
        self.api.patch(
            '/api/django/parametres/update/',
            {'fuseau_horaire': 'Africa/Dakar'}, format='json')
        other_profile.refresh_from_db()
        self.assertEqual(other_profile.fuseau_horaire, 'Africa/Casablanca')


# NTI18N9 — devise d'affichage société (CompanyProfile.devise_tenant).
class DeviseTenantTests(TestCase):
    def test_default_mad_and_independent_of_devise_defaut(self):
        p = CompanyProfile.get(_company('nti18n9-a'))
        self.assertEqual(p.devise_tenant, 'MAD')
        self.assertEqual(p.devise_defaut, 'MAD')

    def test_xof_company_does_not_touch_other_company_or_document_currency(self):
        xof = CompanyProfile.get(_company('nti18n9-xof'))
        xof.devise_tenant = 'XOF'
        xof.save(update_fields=['devise_tenant'])
        autre = CompanyProfile.get(_company('nti18n9-mad'))
        xof.refresh_from_db()
        self.assertEqual(xof.devise_tenant, 'XOF')
        self.assertEqual(xof.devise_defaut, 'MAD')  # devise document (FG52) intacte
        self.assertEqual(autre.devise_tenant, 'MAD')

    def test_exposed_by_serializer(self):
        p = CompanyProfile.get(_company('nti18n9-ser'))
        p.devise_tenant = 'XOF'
        p.save(update_fields=['devise_tenant'])
        self.assertEqual(CompanyProfileSerializer(p).data['devise_tenant'], 'XOF')

    def test_invalid_code_rejected(self):
        p = CompanyProfile.get(_company('nti18n9-bad'))
        p.devise_tenant = 'xof'
        with self.assertRaises(ValidationError):
            p.full_clean()
