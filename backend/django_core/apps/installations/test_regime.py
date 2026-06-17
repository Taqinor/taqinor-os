"""Tests N43 — suggestion configurable du régime loi 82-21."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.installations.models import Installation
from apps.installations.regime import suggest_regime_8221, suggest_for_company
from apps.installations.services import create_installation_from_devis
from apps.installations.tests import make_company, auth, make_accepted_devis

User = get_user_model()


class TestSuggestRegimePure(TestCase):
    """Cœur pur de la suggestion (sans Django/DB)."""

    def test_small_is_declaration(self):
        self.assertEqual(suggest_regime_8221(6.5), 'declaration_bt')
        self.assertEqual(suggest_regime_8221(10.99), 'declaration_bt')

    def test_medium_is_accord(self):
        self.assertEqual(suggest_regime_8221(11), 'accord_raccordement')
        self.assertEqual(suggest_regime_8221(500), 'accord_raccordement')
        self.assertEqual(suggest_regime_8221(1000), 'accord_raccordement')

    def test_large_is_anre(self):
        self.assertEqual(suggest_regime_8221(1000.01), 'autorisation_anre')
        self.assertEqual(suggest_regime_8221(2500), 'autorisation_anre')

    def test_unknown_is_non_concerne(self):
        self.assertEqual(suggest_regime_8221(None), 'non_concerne')
        self.assertEqual(suggest_regime_8221(0), 'non_concerne')
        self.assertEqual(suggest_regime_8221('pas un nombre'), 'non_concerne')

    def test_custom_thresholds(self):
        # Seuil déclaration relevé à 20 kWc → 15 kWc retombe en déclaration.
        self.assertEqual(
            suggest_regime_8221(15, seuil_declaration=20, seuil_anre=1000),
            'declaration_bt')


class TestRegimeOnChantierCreation(TestCase):
    def setUp(self):
        self.company = make_company(slug='reg-co', nom='Reg Co')
        self.user = User.objects.create_user(
            username='reg_user', password='x', role_legacy='responsable',
            company=self.company)

    def test_creation_sets_suggested_regime(self):
        # make_accepted_devis → etude_params puissance 7.2 kWc → déclaration.
        devis = make_accepted_devis(self.company)
        inst, created = create_installation_from_devis(
            devis, self.user, self.company)
        self.assertTrue(created)
        self.assertEqual(inst.regime_8221, 'declaration_bt')

    def test_company_thresholds_applied(self):
        from apps.parametres.models import CompanyProfile
        prof = CompanyProfile.get(company=self.company)
        prof.seuil_regime_declaration_kwc = Decimal('5')  # 7.2 > 5 → accord
        prof.save()
        self.assertEqual(
            suggest_for_company(Decimal('7.2'), self.company),
            'accord_raccordement')


class TestRegimeSuggestionEndpoint(TestCase):
    def setUp(self):
        self.company = make_company(slug='reg-ep-co', nom='Reg EP Co')
        self.user = User.objects.create_user(
            username='reg_ep_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)

    def test_endpoint_returns_suggestion(self):
        url = '/api/django/installations/chantiers/regime-suggestion/'
        r = self.api.get(url, {'kwc': '6'})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['code'], 'declaration_bt')
        self.assertIn('label', r.data)
        r2 = self.api.get(url, {'kwc': '300'})
        self.assertEqual(r2.data['code'], 'accord_raccordement')
        r3 = self.api.get(url, {'kwc': '5000'})
        self.assertEqual(r3.data['code'], 'autorisation_anre')

    def test_serializer_exposes_regime_suggere(self):
        devis = make_accepted_devis(self.company, with_lead=False)
        devis.etude_params = {'puissance_kwc': 250}
        devis.save()
        inst, _ = create_installation_from_devis(devis, self.user, self.company)
        r = self.api.get(
            f'/api/django/installations/chantiers/{inst.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            Installation.objects.get(pk=inst.id).regime_8221,
            'accord_raccordement')
        self.assertEqual(r.data['regime_suggere']['code'], 'accord_raccordement')
