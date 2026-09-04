"""AUD402 — force du mot de passe à la CRÉATION d'un compte.

Défaut audité : ``AUTH_PASSWORD_VALIDATORS`` n'était câblé QUE dans
``ChangePasswordView``. Le signup public ``register-company/`` (AllowAny) ne
vérifiait que ``if not password:`` avant ``create_user(...)`` → un POST anonyme
avec ``password=1`` créait une société entière et son compte Directeur (accès
total) protégé par un mot de passe d'UN caractère. Idem pour la création
admin→collaborateur via ``RegisterSerializer``.

Ces tests sont ROUGES avant le correctif (201) et VERTS après (400), et
vérifient qu'un mot de passe correct reste accepté sur les deux chemins.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from authentication import password_policy as pp
from apps.parametres.models import CompanyProfile
from apps.roles.models import Role, ALL_PERMISSIONS

User = get_user_model()

STRONG = 'Sup3rSecret!23'


class Aud402RegisterCompanyTest(TestCase):
    """Signup public : le mot de passe d'un caractère doit être refusé."""

    def setUp(self):
        self.api = APIClient()

    def _post(self, password, username='boss402', nom='AUD402 SARL'):
        return self.api.post('/api/django/auth/register-company/', {
            'company_nom': nom,
            'username': username,
            'password': password,
            'email': 'boss@aud402.ma',
        }, format='json')

    def test_mot_de_passe_dun_caractere_refuse(self):
        r = self._post('1')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('password', r.data)
        # Aucune société ni compte orphelin laissé derrière le refus.
        self.assertFalse(Company.objects.filter(nom='AUD402 SARL').exists())
        self.assertFalse(User.objects.filter(username='boss402').exists())

    def test_mot_de_passe_trop_court_refuse(self):
        r = self._post('abc123')
        self.assertEqual(r.status_code, 400, r.data)

    def test_mot_de_passe_entierement_numerique_refuse(self):
        r = self._post('19481948194')
        self.assertEqual(r.status_code, 400, r.data)

    def test_mot_de_passe_valide_cree_toujours_la_societe(self):
        r = self._post(STRONG)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(Company.objects.filter(nom='AUD402 SARL').exists())
        user = User.objects.get(username='boss402')
        self.assertTrue(user.check_password(STRONG))

    def test_champ_password_manquant_reste_un_400(self):
        """Le contrat historique (champ requis) n'est pas altéré."""
        r = self._post('')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('password', r.data)


class Aud402RegisterViewTest(TestCase):
    """Création admin→collaborateur : mêmes gardes."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='AUD402 Co', slug='aud402-co')
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.owner = User.objects.create_user(
            username='owner402', password=STRONG, role=self.admin_role,
            role_legacy='admin', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.owner)}')

    def _post(self, password, username='collab402'):
        return self.api.post('/api/django/register/', {
            'username': username, 'password': password,
            'email': 'c@aud402.ma'}, format='json')

    def test_mot_de_passe_faible_refuse(self):
        r = self._post('azerty')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(User.objects.filter(username='collab402').exists())

    def test_mot_de_passe_valide_accepte(self):
        r = self._post(STRONG)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(User.objects.filter(username='collab402').exists())

    def test_politique_societe_fg22_appliquee_a_la_creation(self):
        """Une société qui a durci FG22 voit sa politique honorée ICI aussi."""
        CompanyProfile.objects.update_or_create(
            company=self.company,
            defaults={'nom': 'AUD402 Co', 'password_min_length': 20},
        )
        r = self._post(STRONG, username='collab402b')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(User.objects.filter(username='collab402b').exists())


class Aud402HelperTest(TestCase):
    """L'entrée unique combine validateurs Django + politique société."""

    def test_helper_refuse_un_caractere_sans_societe(self):
        self.assertTrue(pp.validate_new_password('1', None))

    def test_helper_accepte_un_mot_de_passe_solide(self):
        self.assertEqual(pp.validate_new_password(STRONG, None), [])

    def test_helper_cumule_la_politique_societe(self):
        company = Company.objects.create(nom='H402', slug='h402')
        CompanyProfile.objects.create(
            company=company, nom='H402', password_min_length=32)
        self.assertTrue(pp.validate_new_password(STRONG, company))

    def test_helper_refuse_le_vide(self):
        self.assertTrue(pp.validate_new_password('', None))
