"""N110 — Régression : un administrateur change le rôle d'un employé.

Reproduction directe du flux signalé « Administration → Utilisateurs → éditer un
employé → Rôle ». La revue de code n'a trouvé AUCUN bug backend : ``UserViewSet``
+ ``UserSerializer`` acceptent un ``role`` inscriptible, ``update`` réaligne
``role_legacy``/``menu_tier`` sur le palier du nouveau rôle, et les seules gardes
sont la rétrogradation du propriétaire protégé / du dernier admin (préservées).
Le chemin est déjà couvert par ``TestRoleAssignmentN103`` (tests_users.py).

Ces tests verrouillent en plus les deux hypothèses de la fiche N110 :
  1. la réponse API renvoie bien le NOUVEAU rôle + le palier réaligné (ce que le
     menu / la liste relisent après sauvegarde) ;
  2. le « value mismatch » du sélecteur : la PK envoyée comme entier OU comme
     chaîne (selon le navigateur) est acceptée de façon identique.

Conclusion (documentée) : le backend est correct et testé. Sur la PROD, la cause
la plus probable d'un écran qui ne sauvegarde pas est environnementale — un JWT
périmé portant un ancien ``menu_tier``, ou une ligne Role dérivée
(``est_systeme=False`` / sans ``roles_gerer``) sur le COMPTE QUI ÉDITE, qui le
résout au palier limité → 403 sur /users/ et /roles/ → l'écran ne charge plus.
Remède côté serveur : exécuter ``init_roles`` (auto-réparation, voir
``TestSystemRoleSeedingSelfHealsN103``) puis se reconnecter pour rafraîchir le
JWT. Aucun changement de code applicatif n'est requis.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import (
    Role, ADMIN_PERMISSIONS, COMMERCIAL_PERMISSIONS, VIEWER_PERMISSIONS,
)

User = get_user_model()


class TestRoleChangeN110(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='N110 Co', slug='n110-co')
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=list(ADMIN_PERMISSIONS), est_systeme=True)
        self.commercial_role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS), est_systeme=True)
        self.viewer_role = Role.objects.create(
            company=self.company, nom='Viewer',
            permissions=list(VIEWER_PERMISSIONS), est_systeme=True)
        self.admin = User.objects.create_user(
            username='n110_admin', password='x', role=self.admin_role,
            role_legacy='admin', company=self.company)
        self.employee = User.objects.create_user(
            username='n110_emp', password='x', role=self.commercial_role,
            role_legacy='normal', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def test_change_role_response_reflects_new_role_and_tier(self):
        """La sauvegarde renvoie le nouveau rôle + le palier réaligné — ce que
        l'UI relit immédiatement après l'édition."""
        resp = self.api.patch(
            f'/api/django/users/{self.employee.id}/',
            {'role': self.viewer_role.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['role'], self.viewer_role.id)
        self.assertEqual(resp.data['role_nom'], 'Viewer')
        # menu_tier dérivé du NOUVEAU rôle (Viewer = palier 'normal').
        self.assertEqual(resp.data['menu_tier'], 'normal')
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.role_id, self.viewer_role.id)

    def test_change_role_accepts_string_pk_like_dropdown(self):
        """« value mismatch » : une PK envoyée comme CHAÎNE (ce que certains
        <select> postent) est acceptée comme un entier — donc ce n'est pas la
        cause d'un échec côté API."""
        resp = self.api.patch(
            f'/api/django/users/{self.employee.id}/',
            {'role': str(self.viewer_role.id)}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.role_id, self.viewer_role.id)

    def test_change_role_persists_on_reload(self):
        """Le rôle changé est bien persistant : un GET ultérieur le confirme."""
        self.api.patch(
            f'/api/django/users/{self.employee.id}/',
            {'role': self.viewer_role.id}, format='json')
        got = self.api.get(f'/api/django/users/{self.employee.id}/')
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.data['role'], self.viewer_role.id)

    def test_change_role_does_not_weaken_last_admin_guard(self):
        """Garde inchangée : rétrograder le DERNIER admin reste refusé."""
        # L'admin de ce test est le seul compte palier-admin → dernier admin.
        resp = self.api.patch(
            f'/api/django/users/{self.admin.id}/',
            {'role': self.commercial_role.id}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role_id, self.admin_role.id)
