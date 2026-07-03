"""XPLT15 — conditions dynamiques (visible/requis/lecture seule) sans code."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.customfields.models import CustomFieldDef
from apps.customfields.serializers import validate_custom_data
from authentication.models import Company

User = get_user_model()


class CF15Base(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='cf15-co', defaults={'nom': 'CF15 Co'})[0]
        self.admin = User.objects.create_user(
            username='cf15_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')


class TestConditionsDefinitionValidation(CF15Base):
    def test_valid_requis_si_accepted(self):
        resp = self.api.post('/api/django/custom-fields/definitions/', {
            'module': 'lead', 'code': 'motif_perte', 'libelle': 'Motif perte',
            'type': 'text',
            'conditions': {'requis_si': {
                'field': 'statut', 'operator': 'eq', 'value': 'perdu'}},
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_unknown_condition_key_rejected(self):
        resp = self.api.post('/api/django/custom-fields/definitions/', {
            'module': 'lead', 'code': 'x', 'libelle': 'X', 'type': 'text',
            'conditions': {'bidule_si': {
                'field': 'a', 'operator': 'eq', 'value': 1}},
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('conditions', resp.data)

    def test_malformed_condition_tree_rejected(self):
        resp = self.api.post('/api/django/custom-fields/definitions/', {
            'module': 'lead', 'code': 'y', 'libelle': 'Y', 'type': 'text',
            'conditions': {'visible_si': {
                'field': 'a', 'operator': 'not_an_operator', 'value': 1}},
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_conditions_not_a_dict_rejected(self):
        resp = self.api.post('/api/django/custom-fields/definitions/', {
            'module': 'lead', 'code': 'z', 'libelle': 'Z', 'type': 'text',
            'conditions': ['not', 'a', 'dict'],
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_none_conditions_accepted_unchanged(self):
        resp = self.api.post('/api/django/custom-fields/definitions/', {
            'module': 'lead', 'code': 'plain', 'libelle': 'Plain',
            'type': 'text',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.data.get('conditions'))


class TestRequisSiServerEnforcement(CF15Base):
    """Done= — un champ requis-si masqué non rempli -> 400 quand la condition
    est vraie, accepté quand fausse."""

    def _make_def(self):
        return CustomFieldDef.objects.create(
            company=self.company, module='lead', code='motif_perte',
            libelle='Motif de perte', type='text',
            conditions={'requis_si': {
                'field': 'statut', 'operator': 'eq', 'value': 'perdu'}})

    def test_required_when_condition_true(self):
        self._make_def()
        with self.assertRaises(ValidationError):
            validate_custom_data(
                'lead', self.company, {'statut': 'perdu'})

    def test_not_required_when_condition_false(self):
        self._make_def()
        clean = validate_custom_data(
            'lead', self.company, {'statut': 'en_cours'})
        self.assertEqual(clean, {})

    def test_accepted_when_condition_true_and_filled(self):
        self._make_def()
        clean = validate_custom_data(
            'lead', self.company,
            {'statut': 'perdu', 'motif_perte': 'Prix trop élevé'})
        self.assertEqual(clean['motif_perte'], 'Prix trop élevé')

    def test_missing_context_field_never_raises_condition_error(self):
        # Champ 'statut' absent du contexte -> feuille False (core.rules est
        # tolérant), donc pas requis : jamais d'exception inattendue.
        self._make_def()
        clean = validate_custom_data('lead', self.company, {})
        self.assertEqual(clean, {})

    def test_static_obligatoire_still_enforced_independent_of_conditions(self):
        CustomFieldDef.objects.create(
            company=self.company, module='lead', code='budget',
            libelle='Budget', type='number', obligatoire=True)
        with self.assertRaises(ValidationError):
            validate_custom_data('lead', self.company, {})
