"""XSAV28 — Triage IA du ticket + brouillon de réponse (clé-gated, propose→confirme).

Couvre :
  * sans GROQ_API_KEY, `suggerer_triage_ticket` renvoie `{'disponible':
    False}` (comportement actuel byte-identique, jamais d'exception) ;
  * avec clé (mockée), la suggestion structurée revient (type de panne,
    priorité, résumé, brouillon de réponse) ET les articles KB pertinents
    sont injectés en contexte du prompt ;
  * la suggestion n'est JAMAIS auto-appliquée au ticket (GET pur) ;
  * un échec réseau/API dégrade proprement (pas de 500).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav28 -v 2
"""
import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import KbArticle, Ticket
from apps.sav.services import ia_disponible, suggerer_triage_ticket

User = get_user_model()


def make_company(slug='sav-xsav28', nom='Sav Co XSAV28'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


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


class SuggererTriageTicketTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='xsav28_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav28-client@example.invalid')

    @patch.dict('os.environ', {}, clear=True)
    def test_sans_cle_degrade_proprement(self):
        result = suggerer_triage_ticket(
            company=self.company, description='Onduleur affiche code E07')
        self.assertEqual(result, {'disponible': False})

    @patch.dict('os.environ', {'GROQ_API_KEY': 'fake-key'})
    @patch('apps.sav.services.requests.post')
    def test_avec_cle_suggestion_structuree(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': json.dumps({
                'type_panne_suggere': 'Onduleur en défaut',
                'priorite_suggeree': 'haute',
                'resume': "Code d'erreur onduleur E07",
                'brouillon_reponse': 'Bonjour, nous programmons une visite.',
            })}}]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = suggerer_triage_ticket(
            company=self.company, description='Onduleur affiche code E07')
        self.assertTrue(result['disponible'])
        self.assertEqual(
            result['suggestion']['priorite_suggeree'], 'haute')
        self.assertIn('brouillon_reponse', result['suggestion'])

    @patch.dict('os.environ', {'GROQ_API_KEY': 'fake-key'})
    def test_description_vide_pas_dappel_reseau(self):
        result = suggerer_triage_ticket(company=self.company, description='')
        self.assertTrue(result['disponible'])
        self.assertIsNone(result['suggestion'])

    @patch.dict('os.environ', {'GROQ_API_KEY': 'fake-key'})
    @patch('apps.sav.services.requests.post')
    def test_echec_reseau_degrade_proprement(self, mock_post):
        mock_post.side_effect = Exception('timeout')
        result = suggerer_triage_ticket(
            company=self.company, description='Panne quelconque')
        self.assertTrue(result['disponible'])
        self.assertIsNone(result['suggestion'])
        self.assertIn('erreur', result)

    @patch.dict('os.environ', {'GROQ_API_KEY': 'fake-key'})
    @patch('apps.sav.services.requests.post')
    def test_articles_kb_pertinents_injectes_dans_le_prompt(self, mock_post):
        KbArticle.objects.create(
            company=self.company, titre='Code E07 onduleur',
            corps='Le code E07 indique un défaut de tension côté string.')
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': '{"resume": "ok"}'}}]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = suggerer_triage_ticket(
            company=self.company,
            description='Onduleur affiche code E07 depuis ce matin')
        self.assertEqual(len(result['kb_articles']), 1)
        _, kwargs = mock_post.call_args
        prompt_envoye = kwargs['json']['messages'][1]['content']
        self.assertIn('Code E07 onduleur', prompt_envoye)


class TriageIaEndpointTest(TestCase):
    def setUp(self):
        self.company = make_company('sav-xsav28-api', 'Sav Co XSAV28 Api')
        self.admin = User.objects.create_user(
            username='xsav28_api_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Api',
            email='xsav28-api-client@example.invalid')
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XSAV28-1',
            client=self.client_obj, type=Ticket.Type.CORRECTIF,
            description='Onduleur affiche code E07', created_by=self.admin)

    @patch.dict('os.environ', {}, clear=True)
    def test_endpoint_sans_cle_200_disponible_false(self):
        resp = auth(self.admin).get(
            f'/api/django/sav/tickets/{self.ticket.id}/triage-ia/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['disponible'])

        # Rien n'est jamais écrit sur le ticket (GET pur).
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.description, 'Onduleur affiche code E07')

    @patch.dict('os.environ', {'GROQ_API_KEY': 'fake-key'})
    @patch('apps.sav.services.requests.post')
    def test_endpoint_avec_cle_ne_modifie_jamais_le_ticket(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': json.dumps({
                'type_panne_suggere': 'Onduleur en défaut',
                'priorite_suggeree': 'haute',
                'resume': 'résumé',
                'brouillon_reponse': 'brouillon',
            })}}]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        resp = auth(self.admin).get(
            f'/api/django/sav/tickets/{self.ticket.id}/triage-ia/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['disponible'])
        self.assertEqual(
            resp.data['suggestion']['priorite_suggeree'], 'haute')

        self.ticket.refresh_from_db()
        # La priorité réelle du ticket reste inchangée (jamais auto-appliquée).
        self.assertEqual(self.ticket.priorite, Ticket.Priorite.NORMALE)
