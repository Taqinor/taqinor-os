"""Régression — le jeton JWT d'authentification reste BORNÉ en taille.

Incident 2026-07-16 : un login RÉUSSI d'un compte admin renvoyait un 502
« upstream sent too big header » côté nginx. Cause racine : ``get_token``
embarquait la LISTE COMPLÈTE des permissions du rôle dans le jeton (claim
``permissions``). Pour un rôle admin (64 permissions) chaque jeton pesait
≈1,9 ko ; avec les deux cookies (access + refresh) l'en-tête ``Set-Cookie``
dépassait le buffer par défaut de nginx (4 ko). Et ce claim grossissait à
CHAQUE module ajouté (adsengine/qhse/projet…), donc la panne serait revenue.

Ce claim était MORT : le frontend lit les permissions via ``/auth/me/`` (source
DB, jamais en décodant le jeton) et le backend autorise sur ``request.user``
(DB). Ces tests garantissent que :
  1. le jeton NE contient PLUS le claim ``permissions`` ;
  2. sa taille NE dépend PLUS du nombre de permissions du rôle (bornée) ;
  3. ``/auth/me/`` continue de servir la liste complète (les droits effectifs
     et l'affichage frontend sont inchangés) ;
  4. le claim « société active » (lu par ``CookieJWTAuthentication``) reste là.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from authentication.serializers import CustomTokenObtainPairSerializer
from authentication.active_company import ACTIVE_COMPANY_CLAIM
from apps.roles.models import Role, ALL_PERMISSIONS

User = get_user_model()


class JwtTokenSizeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Size Co', slug='size-co')
        # Rôle admin = LA plus grande liste de permissions du système.
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.tiny_role = Role.objects.create(
            company=self.company, nom='Lecture', permissions=['crm_voir'],
            est_systeme=False)
        self.admin = User.objects.create_user(
            username='big', password='x', role=self.admin_role,
            role_legacy='admin', company=self.company)
        self.reader = User.objects.create_user(
            username='small', password='x', role=self.tiny_role,
            company=self.company)

    def test_token_ne_contient_plus_le_claim_permissions(self):
        token = CustomTokenObtainPairSerializer.get_token(self.admin)
        self.assertNotIn('permissions', token.payload)
        # Le claim société active (le SEUL lu côté serveur) reste présent.
        self.assertEqual(token.payload[ACTIVE_COMPANY_CLAIM],
                         self.admin.company_id)

    def test_taille_du_jeton_ne_depend_pas_du_nombre_de_permissions(self):
        # 64 permissions (admin) vs 1 (lecture) : les deux jetons doivent rester
        # petits ET quasi identiques en taille — la taille ne scale plus avec
        # les permissions (sinon un futur module recasserait le login).
        big = len(str(CustomTokenObtainPairSerializer.get_token(
            self.admin).access_token))
        small = len(str(CustomTokenObtainPairSerializer.get_token(
            self.reader).access_token))
        self.assertLess(big, 900,
                        'le jeton admin doit rester borné (<900 o)')
        self.assertLess(abs(big - small), 100,
                        'la taille ne doit pas suivre le nombre de permissions')

    def test_auth_me_sert_toujours_toutes_les_permissions(self):
        # Les droits effectifs sont inchangés : le frontend récupère la liste
        # complète via /auth/me/ (source DB), pas via le jeton.
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        resp = api.get('/api/django/auth/me/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(sorted(resp.data['permissions']),
                         sorted(ALL_PERMISSIONS))
