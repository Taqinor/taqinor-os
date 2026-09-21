"""Tests de la fermeture de feedback via annonce produit (NTIDE39).

Couvre : ``services.fermer_feedback_via_annonce`` (lien à une annonce
EXISTANTE ou création d'une NOUVELLE annonce à la volée, statut →
``adresse``, message optionnel), et l'action
``POST .../feedback-produit/{id}/lier-annonce/`` (palier admin)."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation import services
from apps.innovation.models import AnnonceProduit, FeedbackProduit

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


class FermerFeedbackViaAnnonceServiceTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide39-a', 'A')
        self.user = make_user(self.co_a, 'ntide39-user')
        self.fb = FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.user, titre='Export CSV manquant')

    def test_links_existing_annonce(self):
        annonce = AnnonceProduit.objects.create(
            company=self.co_a, titre='Export CSV disponible')
        services.fermer_feedback_via_annonce(
            self.fb, annonce_id=annonce.id, message="C'est livré !")
        self.fb.refresh_from_db()
        self.assertEqual(self.fb.annonce, annonce)
        self.assertEqual(self.fb.statut, FeedbackProduit.Statut.ADRESSE)
        self.assertEqual(self.fb.message_fermeture, "C'est livré !")

    def test_creates_new_annonce_inline(self):
        services.fermer_feedback_via_annonce(
            self.fb, annonce_data={
                'titre': 'Export CSV', 'description': 'Ajouté ce mois-ci.',
            })
        self.fb.refresh_from_db()
        self.assertIsNotNone(self.fb.annonce)
        self.assertEqual(self.fb.annonce.titre, 'Export CSV')
        self.assertEqual(self.fb.statut, FeedbackProduit.Statut.ADRESSE)

    def test_requires_annonce_id_or_data(self):
        with self.assertRaises(ValidationError):
            services.fermer_feedback_via_annonce(self.fb)

    def test_new_annonce_requires_titre(self):
        with self.assertRaises(ValidationError):
            services.fermer_feedback_via_annonce(
                self.fb, annonce_data={'description': 'Sans titre'})

    def test_unknown_annonce_id_raises(self):
        with self.assertRaises(ValidationError):
            services.fermer_feedback_via_annonce(self.fb, annonce_id=999999)

    def test_feedback_never_deleted(self):
        annonce = AnnonceProduit.objects.create(
            company=self.co_a, titre='Livré')
        services.fermer_feedback_via_annonce(self.fb, annonce_id=annonce.id)
        self.assertTrue(FeedbackProduit.objects.filter(pk=self.fb.pk).exists())


class LierAnnonceEndpointTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide39-api-a', 'A')
        self.admin = make_user(self.co_a, 'ntide39-api-admin', role_legacy='admin')
        self.normal = make_user(self.co_a, 'ntide39-api-normal')
        self.fb = FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.normal, titre='Retour')

    def _url(self):
        return f'/api/django/innovation/feedback-produit/{self.fb.id}/lier-annonce/'

    def test_admin_can_close_with_new_annonce(self):
        resp = auth(self.admin).post(self._url(), {
            'annonce': {'titre': 'Export CSV', 'lien': ''},
            'message': "Vous l'aviez demandé, c'est livré !",
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'adresse')

    def test_missing_annonce_returns_400(self):
        resp = auth(self.admin).post(self._url(), {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_normal_role_refused(self):
        resp = auth(self.normal).post(self._url(), {
            'annonce': {'titre': 'X'},
        }, format='json')
        self.assertEqual(resp.status_code, 403)
