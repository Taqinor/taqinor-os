"""Tests des constantes ROI éditables (T6).

Garantit que les DÉFAUTS sont strictement identiques aux valeurs codées en dur
côté frontend (solar.js) : tant que le founder n'édite rien, le ROI ne change
pas.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.parametres.models import CompanyProfile, ROI_CONSTANTS_DEFAULTS

User = get_user_model()


# Valeurs codées en dur dans frontend/src/features/ventes/solar.js — toute
# divergence de défaut casserait ce test (c'est le but : un garde-fou).
SOLAR_JS_GHI = [
    83.99, 96.79, 133.43, 155.30, 175.28, 179.62,
    179.56, 161.17, 137.03, 111.59, 81.91, 74.61,
]
SOLAR_JS_EFFICIENCY = 0.8
SOLAR_JS_KWH_PRICE = 1.75
SOLAR_JS_BATTERY = 60
SOLAR_JS_DAY_USAGE = {
    'Résidentielle': 60,
    'Commerciale': 80,
    'Industrielle': 80,
    'Agricole': 100,
}


class TestRoiConstants(TestCase):
    def setUp(self):
        from apps.roles.models import Role, ALL_PERMISSIONS
        self.company, _ = Company.objects.get_or_create(
            slug='roi-co', defaults={'nom': 'ROI Co'})
        admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.admin = User.objects.create_user(
            username='roi_admin', password='x', role=admin_role,
            role_legacy='admin', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def test_defaults_equal_hardcoded_solar_js_values(self):
        self.assertEqual(ROI_CONSTANTS_DEFAULTS['ghi'], SOLAR_JS_GHI)
        self.assertEqual(
            ROI_CONSTANTS_DEFAULTS['efficiency'], SOLAR_JS_EFFICIENCY)
        self.assertEqual(
            ROI_CONSTANTS_DEFAULTS['kwh_price'], SOLAR_JS_KWH_PRICE)
        self.assertEqual(
            ROI_CONSTANTS_DEFAULTS['battery_value_per_kwh_month'],
            SOLAR_JS_BATTERY)
        self.assertEqual(
            ROI_CONSTANTS_DEFAULTS['day_usage_defaults'], SOLAR_JS_DAY_USAGE)

    def test_profile_roi_constants_default_null_falls_back(self):
        # Nouveau profil : roi_constants NULL → effective == défauts.
        profile = CompanyProfile.get(company=self.company)
        self.assertIsNone(profile.roi_constants)
        self.assertEqual(
            profile.roi_constants_effective, ROI_CONSTANTS_DEFAULTS)

    def test_partial_edit_merges_with_defaults(self):
        profile = CompanyProfile.get(company=self.company)
        profile.roi_constants = {'kwh_price': 2.0}
        profile.save(update_fields=['roi_constants'])
        eff = profile.roi_constants_effective
        self.assertEqual(eff['kwh_price'], 2.0)
        # Le reste garde les défauts historiques.
        self.assertEqual(eff['efficiency'], SOLAR_JS_EFFICIENCY)
        self.assertEqual(eff['ghi'], SOLAR_JS_GHI)

    def test_api_exposes_effective_and_defaults(self):
        r = self.api.get('/api/django/parametres/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn('roi_constants_effective', r.data)
        self.assertIn('roi_constants_defaults', r.data)
        self.assertEqual(
            r.data['roi_constants_defaults']['kwh_price'], SOLAR_JS_KWH_PRICE)

    def test_admin_can_save_roi_constants(self):
        r = self.api.patch('/api/django/parametres/update/', {
            'roi_constants': {'efficiency': 0.85},
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        profile = CompanyProfile.get(company=self.company)
        self.assertEqual(profile.roi_constants, {'efficiency': 0.85})
        # Effective fusionne avec les défauts.
        self.assertEqual(profile.roi_constants_effective['kwh_price'],
                         SOLAR_JS_KWH_PRICE)
