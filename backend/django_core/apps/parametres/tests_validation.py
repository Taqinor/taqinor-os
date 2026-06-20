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


class TestCompanyReadOnly(ProfileValidationBase):
    """ERR25 — `company` est read-only : un PATCH ne peut pas repointer le
    profil de l'appelant vers une autre société."""

    def test_company_field_ignored_on_patch(self):
        other = Company.objects.get_or_create(
            slug='val-other', defaults={'nom': 'Other Co'})[0]
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.get(self.company)
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'company': other.id, 'nom': 'Renommé'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        profile.refresh_from_db()
        # Le FK société est inchangé (non détourné), seul `nom` a été pris.
        self.assertEqual(profile.company_id, self.company.id)
        self.assertEqual(profile.nom, 'Renommé')


class TestThresholdRanges(ProfileValidationBase):
    """ERR55 — bornes [0, 100] sur les pourcentages éditables et non-négativité
    des seuils kWc ; un NULL reste accepté (champ optionnel)."""

    def test_negative_remise_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'remise_max_pct': -5}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('remise_max_pct', resp.data)

    def test_over_100_remise_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'remise_max_pct': 120}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('remise_max_pct', resp.data)

    def test_discount_threshold_out_of_range_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'discount_approval_threshold': 150}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('discount_approval_threshold', resp.data)

    def test_negative_overage_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'overage_seuil_pct': -1}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('overage_seuil_pct', resp.data)

    def test_negative_regime_threshold_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'seuil_regime_declaration_kwc': -3}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('seuil_regime_declaration_kwc', resp.data)

    def test_valid_threshold_saved(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'remise_max_pct': 15, 'discount_approval_threshold': 10},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(str(resp.data['remise_max_pct']), '15.00')

    def test_null_remise_allowed(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'remise_max_pct': None}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)


class TestJsonShapeValidation(ProfileValidationBase):
    """ERR55 — forme des champs JSON doc_prefixes / doc_numbering /
    payment_terms ; NULL reste accepté (repli sur le défaut historique)."""

    def test_doc_prefixes_must_be_object(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'doc_prefixes': ['DEV', 'FAC']}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('doc_prefixes', resp.data)

    def test_doc_prefixes_unknown_key_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'doc_prefixes': {'inconnu': 'X'}}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('doc_prefixes', resp.data)

    def test_doc_prefixes_valid_saved(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'doc_prefixes': {'devis': 'DV', 'facture': 'FC'}}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['doc_prefixes']['devis'], 'DV')

    def test_doc_numbering_bad_padding_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'doc_numbering': {'devis': {'padding': 99, 'reset': 'monthly'}}},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('doc_numbering', resp.data)

    def test_doc_numbering_bad_reset_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'doc_numbering': {'devis': {'padding': 4, 'reset': 'hourly'}}},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('doc_numbering', resp.data)

    def test_doc_numbering_valid_saved(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'doc_numbering': {'facture': {'padding': 5, 'reset': 'yearly'}}},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_payment_terms_must_be_object(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'payment_terms': [30, 60, 10]}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('payment_terms', resp.data)

    def test_payment_terms_over_100_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'payment_terms': {'reseau': {'acompte': 60, 'materiel': 60,
                                          'solde': 10}}}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('payment_terms', resp.data)

    def test_payment_terms_non_numeric_rejected(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'payment_terms': {'reseau': {'acompte': 'beaucoup'}}},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('payment_terms', resp.data)

    def test_payment_terms_valid_saved(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'payment_terms': {'reseau': {'acompte': 30, 'materiel': 60,
                                          'solde': 10}}}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
