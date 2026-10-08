"""ASEC3 — le mot de passe d'un compte se réinitialise par une action dédiée.

``POST /users/<id>/reinitialiser-mot-de-passe/`` : politique de mot de passe,
révocation de toutes les sessions de la cible, rotation forcée, journal (jamais
la valeur). Le PATCH/PUT générique refuse ``password`` (400
``password_via_reinitialisation``) ; la création sans mot de passe rend 400 (et
non plus un 500).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.parametres.models import SettingsAuditLog
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    COMMERCIAL_PERMISSIONS,
    DIRECTEUR_PERMISSIONS,
)
from authentication.models import Company, UserSession
from authentication.session_policy import SESSION_CLAIM

User = get_user_model()

_URL = '/api/django/users/{}/reinitialiser-mot-de-passe/'


class ReinitialisationMotDePasseTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASEC3 Co', slug='asec3-co')
        self.r_dir = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
        self.r_com = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS), est_systeme=True)
        self.directeur = User.objects.create_user(
            username='asec3_dir', password='Dir-mdp-123!', role=self.r_dir,
            company=self.company)
        self.cible = User.objects.create_user(
            username='asec3_com', password='Ancien-mdp-123!', role=self.r_com,
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.directeur)

    def _session_active(self, user):
        refresh = RefreshToken.for_user(user)
        UserSession.objects.create(
            company=self.company, user=user, jti=refresh['jti'])
        access = refresh.access_token
        access[SESSION_CLAIM] = refresh['jti']
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        return api

    def test_action_dediee_applique_politique(self):
        resp = self.api.post(
            _URL.format(self.cible.id), {'password': 'a'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('password', resp.data)
        self.cible.refresh_from_db()
        self.assertTrue(self.cible.check_password('Ancien-mdp-123!'))

        resp = self.api.post(
            _URL.format(self.cible.id), {'password': 'Nouveau-mdp-456!'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.cible.refresh_from_db()
        self.assertTrue(self.cible.check_password('Nouveau-mdp-456!'))
        self.assertTrue(self.cible.must_change_password)

    def test_action_dediee_revoque_sessions_cible(self):
        api_cible = self._session_active(self.cible)
        self.assertEqual(api_cible.get('/api/django/auth/me/').status_code, 200)
        resp = self.api.post(
            _URL.format(self.cible.id), {'password': 'Nouveau-mdp-456!'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(
            UserSession.objects.filter(user=self.cible, revoked=False).exists())
        self.assertEqual(api_cible.get('/api/django/auth/me/').status_code, 401)

    def test_action_dediee_journalise(self):
        resp = self.api.post(
            _URL.format(self.cible.id), {'password': 'Nouveau-mdp-456!'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        lignes = SettingsAuditLog.objects.filter(
            company=self.company, section='utilisateurs',
            field=f'user:{self.cible.username}:mot_de_passe')
        self.assertEqual(lignes.count(), 1)
        ligne = lignes.get()
        self.assertEqual(ligne.user_id, self.directeur.id)
        self.assertNotIn('Nouveau-mdp-456!', ligne.new_value)
        self.assertNotIn('Nouveau-mdp-456!', ligne.old_value)
        # Une relecture ne duplique rien.
        self.api.get(f'/api/django/users/{self.cible.id}/')
        self.assertEqual(lignes.count(), 1)

    def test_password_refuse_dans_patch(self):
        for methode in ('patch', 'put'):
            with self.subTest(methode=methode):
                corps = {'password': 'Nouveau-mdp-456!'}
                if methode == 'put':
                    corps['username'] = self.cible.username
                resp = getattr(self.api, methode)(
                    f'/api/django/users/{self.cible.id}/', corps, format='json')
                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertEqual(
                    resp.data.get('code'), 'password_via_reinitialisation')
                self.cible.refresh_from_db()
                self.assertTrue(self.cible.check_password('Ancien-mdp-123!'))

    def test_creation_sans_mdp_400(self):
        resp = self.api.post(
            '/api/django/users/', {'username': 'sans_mdp'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('password', resp.data)
        self.assertFalse(User.objects.filter(username='sans_mdp').exists())

        resp = self.api.post(
            '/api/django/users/', {'username': 'mdp_faible', 'password': 'a'},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('password', resp.data)
        self.assertFalse(User.objects.filter(username='mdp_faible').exists())

    def test_rang_inferieur_ne_reinitialise_pas_un_directeur(self):
        api = APIClient()
        api.force_authenticate(self.cible)
        resp = api.post(
            _URL.format(self.directeur.id), {'password': 'Nouveau-mdp-456!'},
            format='json')
        self.assertEqual(resp.status_code, 403)
        self.directeur.refresh_from_db()
        self.assertTrue(self.directeur.check_password('Dir-mdp-123!'))
