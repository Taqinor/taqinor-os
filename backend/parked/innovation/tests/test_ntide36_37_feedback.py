"""Tests du modèle ``FeedbackProduit`` (NTIDE36) et du bouton discret
« Envoyer un retour » (NTIDE37).

Couvre : création du modèle (company-scopée, thème/statut par défaut),
l'endpoint ``POST /api/django/innovation/feedback-produit/`` (tout
utilisateur connecté, auteur/société posés côté serveur), ``retrieve``
bascule ``envoye`` → ``lu``, et l'absence d'``update``/``destroy`` directs
(le feedback n'est jamais accessible via un menu normal, ne se supprime
jamais)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation.models import FeedbackProduit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class FeedbackProduitModelTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide36-a', 'A')
        self.user = make_user(self.co_a, 'ntide36-user')

    def test_defaults(self):
        fb = FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.user, titre='Lenteur du tableau')
        self.assertEqual(fb.theme, FeedbackProduit.Theme.AUTRE)
        self.assertEqual(fb.statut, FeedbackProduit.Statut.ENVOYE)
        self.assertIsNone(fb.annonce)

    def test_company_scoped_isolation(self):
        co_b = make_company('innov-ntide36-b', 'B')
        FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.user, titre='A')
        self.assertEqual(
            FeedbackProduit.objects.filter(company=co_b).count(), 0)


class FeedbackCreateEndpointTests(TestCase):
    BASE = '/api/django/innovation/feedback-produit/'

    def setUp(self):
        self.co_a = make_company('innov-ntide37-a', 'A')
        self.normal = make_user(self.co_a, 'ntide37-normal')
        self.admin = make_user(self.co_a, 'ntide37-admin', role_legacy='admin')

    def test_any_logged_in_user_can_send_feedback(self):
        resp = auth(self.normal).post(self.BASE, {
            'titre': 'Le bouton export est trop petit',
            'description': 'Difficile à cliquer sur mobile.',
            'theme': 'ux',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        fb = FeedbackProduit.objects.get(pk=resp.data['id'])
        self.assertEqual(fb.auteur, self.normal)
        self.assertEqual(fb.company, self.co_a)

    def test_company_and_auteur_never_taken_from_body(self):
        other_co = make_company('innov-ntide37-other', 'Other')
        other_user = make_user(other_co, 'ntide37-other-user')
        resp = auth(self.normal).post(self.BASE, {
            'titre': 'Test', 'company': other_co.id, 'auteur': other_user.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        fb = FeedbackProduit.objects.get(pk=resp.data['id'])
        self.assertEqual(fb.company, self.co_a)
        self.assertEqual(fb.auteur, self.normal)

    def test_list_reserved_to_admin(self):
        resp = auth(self.normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_list(self):
        FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.normal, titre='Un retour')
        resp = auth(self.admin).get(self.BASE)
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_retrieve_marks_lu(self):
        fb = FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.normal, titre='Un retour')
        self.assertEqual(fb.statut, FeedbackProduit.Statut.ENVOYE)
        resp = auth(self.admin).get(f'{self.BASE}{fb.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        fb.refresh_from_db()
        self.assertEqual(fb.statut, FeedbackProduit.Statut.LU)

    def test_retrieve_does_not_downgrade_adresse(self):
        fb = FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.normal, titre='Un retour',
            statut=FeedbackProduit.Statut.ADRESSE)
        auth(self.admin).get(f'{self.BASE}{fb.id}/')
        fb.refresh_from_db()
        self.assertEqual(fb.statut, FeedbackProduit.Statut.ADRESSE)

    def test_no_update_or_destroy_allowed(self):
        fb = FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.normal, titre='Un retour')
        resp = auth(self.admin).patch(
            f'{self.BASE}{fb.id}/', {'titre': 'Modifié'}, format='json')
        self.assertEqual(resp.status_code, 405)
        resp = auth(self.admin).delete(f'{self.BASE}{fb.id}/')
        self.assertEqual(resp.status_code, 405)
