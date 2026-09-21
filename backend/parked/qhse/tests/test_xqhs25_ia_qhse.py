"""XQHS25 — Assistance IA QHSE (classification + brouillon d'analyse), key-gated.

Couvre :
  * avec clé (mockée) les suggestions reviennent structurées et éditables ;
  * sans clé tout dégrade proprement (200, ``disponible=False``, jamais
    d'exception ni de no-op cassant) ;
  * aucune donnée d'une autre société ne part dans le prompt (seul le texte
    fourni par CET utilisateur est envoyé) ;
  * l'échec réseau/API dégrade proprement (pas de 500).
"""
import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.services import (
    ia_disponible, suggerer_analyse_capa, suggerer_classification_incident,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class IaDisponibleTests(TestCase):
    @patch.dict('os.environ', {}, clear=True)
    def test_sans_cle_indisponible(self):
        self.assertFalse(ia_disponible())

    @patch.dict('os.environ', {'GROQ_API_KEY': 'fake-key'})
    def test_avec_cle_disponible(self):
        self.assertTrue(ia_disponible())


class SuggererClassificationTests(TestCase):
    @patch.dict('os.environ', {}, clear=True)
    def test_sans_cle_degrade_proprement(self):
        result = suggerer_classification_incident('Câble dénudé au sol')
        self.assertEqual(result, {'disponible': False})

    @patch.dict('os.environ', {'GROQ_API_KEY': 'fake-key'})
    @patch('apps.qhse.services.requests.post')
    def test_avec_cle_suggestion_structuree(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': json.dumps({
                'type': 'danger', 'gravite': 'majeure',
                'code_defaut_suggere': 'ELEC-DENUDE',
                'justification': 'Risque électrocution',
            })}}]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = suggerer_classification_incident('Câble dénudé au sol')
        self.assertTrue(result['disponible'])
        self.assertEqual(result['suggestion']['gravite'], 'majeure')

    @patch.dict('os.environ', {'GROQ_API_KEY': 'fake-key'})
    def test_description_vide_pas_dappel_reseau(self):
        result = suggerer_classification_incident('')
        self.assertTrue(result['disponible'])
        self.assertIsNone(result['suggestion'])

    @patch.dict('os.environ', {'GROQ_API_KEY': 'fake-key'})
    @patch('apps.qhse.services.requests.post')
    def test_echec_reseau_degrade_proprement(self, mock_post):
        mock_post.side_effect = Exception('timeout')
        result = suggerer_classification_incident('Description quelconque')
        self.assertTrue(result['disponible'])
        self.assertIsNone(result['suggestion'])
        self.assertIn('erreur', result)

    @patch.dict('os.environ', {'GROQ_API_KEY': 'fake-key'})
    @patch('apps.qhse.services.requests.post')
    def test_seul_le_texte_fourni_part_dans_le_prompt(self, mock_post):
        """Aucune donnée d'une autre société n'est jamais injectée — seul le
        texte explicitement passé en argument constitue le prompt."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': '{"type": "incident"}'}}]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        description = 'Fuite huile transfo site A'
        suggerer_classification_incident(description)
        _, kwargs = mock_post.call_args
        prompt_envoye = kwargs['json']['messages'][1]['content']
        self.assertEqual(prompt_envoye, description)


class SuggererAnalyseCapaTests(TestCase):
    @patch.dict('os.environ', {}, clear=True)
    def test_sans_cle_degrade_proprement(self):
        result = suggerer_analyse_capa('Récit investigation')
        self.assertEqual(result, {'disponible': False})

    @patch.dict('os.environ', {'GROQ_API_KEY': 'fake-key'})
    @patch('apps.qhse.services.requests.post')
    def test_avec_cle_plan_capa_structure(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': json.dumps({
                'cinq_pourquoi': ['pourquoi1', 'pourquoi2', '', '', ''],
                'cause_racine': 'Défaut de formation',
                'plan_capa': [
                    {'description': 'Former les équipes',
                     'type_action': 'preventive'},
                ],
            })}}]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = suggerer_analyse_capa('Récit détaillé de l\'incident')
        self.assertTrue(result['disponible'])
        self.assertEqual(len(result['suggestion']['plan_capa']), 1)

    @patch.dict('os.environ', {'GROQ_API_KEY': 'fake-key'})
    def test_recit_vide(self):
        result = suggerer_analyse_capa('')
        self.assertTrue(result['disponible'])
        self.assertIsNone(result['suggestion'])


class IaEndpointsApiTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs25-api', 'Xqhs25 Api')
        self.user = make_user(self.company, 'xqhs25-user')

    @patch.dict('os.environ', {}, clear=True)
    def test_classification_endpoint_sans_cle_200(self):
        resp = auth(self.user).post(
            '/api/django/qhse/ia/suggestion-classification/',
            {'description': 'Test'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['disponible'])

    @patch.dict('os.environ', {}, clear=True)
    def test_analyse_endpoint_sans_cle_200(self):
        resp = auth(self.user).post(
            '/api/django/qhse/ia/suggestion-analyse/',
            {'recit': 'Test'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['disponible'])

    @patch.dict('os.environ', {'GROQ_API_KEY': 'fake-key'})
    @patch('apps.qhse.services.requests.post')
    def test_classification_endpoint_avec_cle(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': '{"type": "incident"}'}}]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        resp = auth(self.user).post(
            '/api/django/qhse/ia/suggestion-classification/',
            {'description': 'Câble dénudé'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['disponible'])
        self.assertEqual(resp.data['suggestion']['type'], 'incident')
