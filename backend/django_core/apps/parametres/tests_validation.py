"""Validations de l'enregistrement du profil entreprise.

L769 — garde-fou TVA : un taux ne peut pas être laissé VIDE et re-snappé
silencieusement au défaut (20/10) ; un 0 DÉLIBÉRÉ est préservé.
L788 — commission : la valeur est obligatoire dès qu'un mode actif est choisi.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()


class ProfileValidationBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='val-co', defaults={'nom': 'Val Co'})[0]
        self.admin = User.objects.create_user(
            username='val_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')


class TestTvaGuard(ProfileValidationBase):
    def test_empty_tva_rejected_not_resnapped(self):
        # Champ vide → erreur de validation (au lieu d'un re-snap silencieux).
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'tva_standard': '', 'tva_panneaux': 10}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('tva_standard', resp.data)

    def test_deliberate_zero_preserved(self):
        # 0 délibéré (exonéré) est valide et préservé tel quel.
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'tva_standard': 0, 'tva_panneaux': 0}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(str(resp.data['tva_standard']), '0.00')
        self.assertEqual(str(resp.data['tva_panneaux']), '0.00')

    def test_out_of_range_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'tva_standard': 150}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('tva_standard', resp.data)

    def test_normal_value_saved(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'tva_standard': 20, 'tva_panneaux': 10}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(str(resp.data['tva_standard']), '20.00')


class TestCommissionRequiresValue(ProfileValidationBase):
    def test_active_mode_requires_value(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'commission_mode': 'pct_devis', 'commission_valeur': None},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('commission_valeur', resp.data)

    def test_active_mode_with_value_ok(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'commission_mode': 'par_kwc', 'commission_valeur': '500'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['commission_mode'], 'par_kwc')

    def test_off_mode_allows_empty_value(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'commission_mode': 'off', 'commission_valeur': None},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_patch_mode_only_uses_stored_value(self):
        # Mode actif posé avec une valeur, puis re-PATCH du seul mode : la
        # valeur déjà enregistrée satisfait la contrainte (PATCH partiel).
        self.api.patch(
            '/api/django/parametres/update/',
            {'commission_mode': 'pct_devis', 'commission_valeur': '5'},
            format='json')
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'commission_mode': 'par_kwc'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
