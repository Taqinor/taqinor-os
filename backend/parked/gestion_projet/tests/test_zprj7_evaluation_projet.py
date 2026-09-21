"""Tests de l'enquête de satisfaction client par projet - CSAT (ZPRJ7).

Couvre : dépôt public UNIQUE via token (2e POST refusé) ; isolation tenant ;
aucune donnée interne (coût/budget/marge) dans la réponse publique ; la note
remonte au portefeuille (moyenne) ; migration additive ; action
``lien-evaluation`` idempotente (get_or_create, jamais de doublon).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import EvaluationProjet, Projet

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class LienEvaluationApiTests(TestCase):
    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co_a = make_company('gp-z7-a', 'A')
        self.co_b = make_company('gp-z7-b', 'B')
        self.user_a = make_user(self.co_a, 'z7-api-a')
        self.user_b = make_user(self.co_b, 'z7-api-b')
        self.projet = Projet.objects.create(company=self.co_a, code='P-Z7', nom='P')

    def test_creation_lien(self):
        api = auth(self.user_a)
        resp = api.post(f'{self.BASE}{self.projet.id}/lien-evaluation/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('token', resp.data)
        self.assertFalse(resp.data['deja_soumis'])
        self.assertEqual(
            EvaluationProjet.objects.filter(projet=self.projet).count(), 1)

    def test_idempotent_meme_token(self):
        api = auth(self.user_a)
        resp1 = api.post(f'{self.BASE}{self.projet.id}/lien-evaluation/')
        resp2 = api.post(f'{self.BASE}{self.projet.id}/lien-evaluation/')
        self.assertEqual(resp1.data['token'], resp2.data['token'])
        self.assertEqual(
            EvaluationProjet.objects.filter(projet=self.projet).count(), 1)

    def test_isolation_societe_404(self):
        api = auth(self.user_b)
        resp = api.post(f'{self.BASE}{self.projet.id}/lien-evaluation/')
        self.assertEqual(resp.status_code, 404)


class EvaluationPubliqueApiTests(TestCase):
    BASE = '/api/django/gestion-projet/portail/evaluation/'

    def setUp(self):
        self.co = make_company('gp-z7-pub', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-Z7PUB', nom='P Public',
            budget_total=100000)
        self.evaluation = EvaluationProjet.objects.create(
            company=self.co, projet=self.projet)

    def _url(self, token):
        return f'{self.BASE}{token}/'

    def test_get_formulaire(self):
        api = APIClient()
        resp = api.get(self._url(self.evaluation.token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['projet']['code'], 'P-Z7PUB')
        self.assertFalse(resp.data['deja_soumis'])

    def test_post_soumet_note(self):
        api = APIClient()
        resp = api.post(
            self._url(self.evaluation.token),
            {'note': 5, 'commentaire': 'Excellent travail'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.evaluation.refresh_from_db()
        self.assertEqual(self.evaluation.note, 5)
        self.assertEqual(self.evaluation.commentaire, 'Excellent travail')
        self.assertIsNotNone(self.evaluation.soumis_le)

    def test_deuxieme_post_refuse(self):
        api = APIClient()
        api.post(self._url(self.evaluation.token), {'note': 4}, format='json')
        resp2 = api.post(
            self._url(self.evaluation.token), {'note': 1}, format='json')
        self.assertEqual(resp2.status_code, 400)
        self.evaluation.refresh_from_db()
        self.assertEqual(self.evaluation.note, 4)  # inchangée

    def test_note_hors_bornes_refusee(self):
        api = APIClient()
        resp = api.post(
            self._url(self.evaluation.token), {'note': 7}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_note_manquante_refusee(self):
        api = APIClient()
        resp = api.post(self._url(self.evaluation.token), {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_token_inconnu_404(self):
        api = APIClient()
        resp = api.get(self._url('inexistant'))
        self.assertEqual(resp.status_code, 404)

    def test_aucune_donnee_interne_exposee(self):
        api = APIClient()
        resp = api.get(self._url(self.evaluation.token))
        self.assertNotIn('budget_total', resp.data['projet'])
        self.assertNotIn('marge', str(resp.data).lower())
        self.assertNotIn('cout', str(resp.data).lower())


class PortefeuilleNoteSatisfactionTests(TestCase):
    BASE = '/api/django/gestion-projet/'

    def setUp(self):
        self.co = make_company('gp-z7-port', 'S')
        self.user = make_user(self.co, 'z7-port-u')
        self.projet1 = Projet.objects.create(
            company=self.co, code='P-Z7-1', nom='P1')
        self.projet2 = Projet.objects.create(
            company=self.co, code='P-Z7-2', nom='P2')

    def test_note_remonte_au_portefeuille(self):
        EvaluationProjet.objects.create(
            company=self.co, projet=self.projet1, note=4,
            soumis_le='2026-06-01T10:00:00Z')
        data = selectors.tableau_portefeuille(self.co)
        ligne1 = next(
            ln for ln in data['projets'] if ln['projet_id'] == self.projet1.id)
        ligne2 = next(
            ln for ln in data['projets'] if ln['projet_id'] == self.projet2.id)
        self.assertEqual(ligne1['note_satisfaction'], 4)
        self.assertIsNone(ligne2['note_satisfaction'])
        self.assertEqual(data['note_satisfaction_moyenne'], 4.0)

    def test_sans_evaluation_moyenne_none(self):
        data = selectors.tableau_portefeuille(self.co)
        self.assertIsNone(data['note_satisfaction_moyenne'])

    def test_isolation_societe(self):
        co_b = make_company('gp-z7-port-b', 'B')
        projet_b = Projet.objects.create(company=co_b, code='P-B', nom='B')
        EvaluationProjet.objects.create(
            company=co_b, projet=projet_b, note=1,
            soumis_le='2026-06-01T10:00:00Z')
        data = selectors.tableau_portefeuille(self.co)
        ids = [ln['projet_id'] for ln in data['projets']]
        self.assertNotIn(projet_b.id, ids)
