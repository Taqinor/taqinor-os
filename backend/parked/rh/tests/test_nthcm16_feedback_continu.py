"""Tests NTHCM16 — feedback continu (reconnaissance / coaching hors cycle).

Couvre :
* envoyer un feedback à un collègue le journalise, l'auteur étant posé côté
  serveur (jamais lu du corps) ;
* l'auto-adressage est refusé (400) ;
* le manager du destinataire voit UNIQUEMENT les feedbacks partagés ;
* le destinataire ne voit pas un feedback marqué non visible ;
* isolation société.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import DossierEmploye, FeedbackContinu

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def lignes(reponse):
    """Corps d'une liste DRF, paginée ou non."""
    donnees = reponse.data
    return donnees['results'] if isinstance(donnees, dict) else donnees


class FeedbackContinuTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm16-a', 'A')
        # Manager + deux subordonnés directs (NTHCM1).
        self.u_chef = make_user(self.co, 'nthcm16-chef')
        self.u_alice = make_user(self.co, 'nthcm16-alice')
        self.u_bob = make_user(self.co, 'nthcm16-bob')
        self.chef = DossierEmploye.objects.create(
            company=self.co, matricule='M-001', nom='Chef', prenom='Le',
            user=self.u_chef)
        self.alice = DossierEmploye.objects.create(
            company=self.co, matricule='M-002', nom='Alaoui', prenom='Alice',
            user=self.u_alice, manager=self.chef)
        self.bob = DossierEmploye.objects.create(
            company=self.co, matricule='M-003', nom='Bennani', prenom='Bob',
            user=self.u_bob, manager=self.chef)

    def test_envoyer_un_feedback_pose_lauteur_cote_serveur(self):
        api = auth(self.u_bob)
        reponse = api.post(
            '/api/django/rh/feedbacks-continus/',
            {'pour': self.alice.id, 'type': 'reconnaissance',
             # L'auteur transmis est IGNORÉ : le serveur pose le sien.
             'de': self.alice.id,
             'message': 'Merci pour le coup de main sur le chantier.'},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.content)
        feedback = FeedbackContinu.objects.get(pk=reponse.data['id'])
        self.assertEqual(feedback.de_id, self.bob.id)
        self.assertEqual(feedback.pour_id, self.alice.id)
        self.assertEqual(feedback.company_id, self.co.id)
        self.assertTrue(feedback.visible_par_pour)
        self.assertFalse(feedback.partage_avec_manager)

    def test_auto_envoi_refuse(self):
        api = auth(self.u_bob)
        reponse = api.post(
            '/api/django/rh/feedbacks-continus/',
            {'pour': self.bob.id, 'type': 'coaching', 'message': 'Bravo moi'},
            format='json')
        self.assertEqual(reponse.status_code, 400, reponse.content)
        self.assertEqual(FeedbackContinu.objects.count(), 0)

    def test_clean_refuse_lauto_adressage(self):
        feedback = FeedbackContinu(
            company=self.co, de=self.bob, pour=self.bob, message='x')
        with self.assertRaises(ValidationError):
            feedback.full_clean()

    def test_destinataire_ne_voit_que_ce_qui_lui_est_visible(self):
        FeedbackContinu.objects.create(
            company=self.co, de=self.bob, pour=self.alice,
            message='Visible', visible_par_pour=True)
        FeedbackContinu.objects.create(
            company=self.co, de=self.bob, pour=self.alice,
            message='Note privée', visible_par_pour=False)
        api = auth(self.u_alice)
        reponse = api.get('/api/django/rh/feedbacks-continus/')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        messages = [ligne['message'] for ligne in lignes(reponse)]
        self.assertEqual(messages, ['Visible'])

    def test_manager_voit_uniquement_les_feedbacks_partages(self):
        FeedbackContinu.objects.create(
            company=self.co, de=self.bob, pour=self.alice,
            message='Partagé', partage_avec_manager=True)
        FeedbackContinu.objects.create(
            company=self.co, de=self.bob, pour=self.alice,
            message='Non partagé', partage_avec_manager=False)
        api = auth(self.u_chef)
        reponse = api.get('/api/django/rh/feedbacks-continus/')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        messages = [ligne['message'] for ligne in lignes(reponse)]
        self.assertEqual(messages, ['Partagé'])

    def test_rh_voit_tout_le_perimetre_societe(self):
        FeedbackContinu.objects.create(
            company=self.co, de=self.bob, pour=self.alice,
            message='Non partagé', partage_avec_manager=False,
            visible_par_pour=False)
        u_rh = make_user(self.co, 'nthcm16-rh', role='responsable')
        reponse = auth(u_rh).get('/api/django/rh/feedbacks-continus/')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(len(lignes(reponse)), 1)

    def test_isolation_societe(self):
        autre = make_company('nthcm16-b', 'B')
        u_autre = make_user(autre, 'nthcm16-autre', role='responsable')
        FeedbackContinu.objects.create(
            company=self.co, de=self.bob, pour=self.alice, message='A moi')
        reponse = auth(u_autre).get('/api/django/rh/feedbacks-continus/')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(list(lignes(reponse)), [])
