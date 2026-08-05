"""N100(b) — création administrée d'un tenant depuis la console fondateur.

Un tenant créé ici doit être INDISCERNABLE d'un tenant auto-inscrit via
``/auth/register-company/`` : mêmes rôles système, même CompanyProfile, mêmes
hooks de signup.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Company, CustomUser


class TenantConsoleCreateTests(TestCase):
    def setUp(self):
        self.fondateur = CustomUser.objects.create_superuser(
            username='fondateur_creation', password='pw70452',
            email='fondateur.creation@exemple.ma')
        self.tenant_existant = Company.objects.create(
            nom='Deja La', slug='deja-la')
        self.admin_tenant = CustomUser.objects.create_user(
            username='admin_deja_la', password='pw70452',
            company=self.tenant_existant, role_legacy='admin',
            email='admin@deja-la.ma')

    def _api(self, user=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    URL = '/api/django/auth/console/tenants/creer/'

    # ── Garde d'accès ───────────────────────────────────────────────────────
    def test_non_superuser_refuse(self):
        resp = self._api(self.admin_tenant).post(
            self.URL, {'nom': 'Pirate', 'email': 'x@y.ma'}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Company.objects.filter(nom='Pirate').exists())

    def test_anonyme_refuse(self):
        resp = self._api().post(
            self.URL, {'nom': 'Pirate', 'email': 'x@y.ma'}, format='json')
        self.assertIn(resp.status_code, (401, 403))

    # ── Validation ──────────────────────────────────────────────────────────
    def test_nom_et_email_requis(self):
        resp = self._api(self.fondateur).post(self.URL, {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('nom', resp.data)
        self.assertIn('email', resp.data)

    def test_email_invalide_refuse(self):
        resp = self._api(self.fondateur).post(
            self.URL, {'nom': 'Nouveau', 'email': 'pas-un-email'},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('email', resp.data)

    # ── Provisionnement complet ─────────────────────────────────────────────
    def test_creation_provisionne_societe_profil_roles_et_admin(self):
        resp = self._api(self.fondateur).post(
            self.URL,
            {'nom': 'Installateur Nord', 'email': 'chef@installateur-nord.ma'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

        company = Company.objects.get(slug='installateur-nord')
        self.assertEqual(company.nom, 'Installateur Nord')

        # CompanyProfile créé.
        from apps.parametres.models import CompanyProfile
        self.assertTrue(
            CompanyProfile.objects.filter(company=company).exists())

        # Rôles système seedés (même fonction que `init_roles`).
        from apps.roles.models import Role
        self.assertTrue(
            Role.objects.filter(company=company, nom='Directeur').exists())

        # Premier administrateur, invitation-style.
        admin = CustomUser.objects.get(company=company)
        self.assertEqual(admin.email, 'chef@installateur-nord.ma')
        self.assertEqual(admin.role_legacy, CustomUser.ROLE_ADMIN)
        self.assertTrue(admin.must_change_password)
        self.assertIn(company, admin.societes_autorisees.all())

        # Le mot de passe provisoire est renvoyé UNE fois et fonctionne.
        provisoire = resp.data['mot_de_passe_provisoire']
        self.assertTrue(provisoire)
        self.assertTrue(admin.check_password(provisoire))
        # Jamais stocké en clair.
        self.assertNotEqual(admin.password, provisoire)

    def test_hooks_de_signup_executes(self):
        """SCA20 — les seeds « nouvelle société » tournent aussi ici."""
        self._api(self.fondateur).post(
            self.URL, {'nom': 'Avec Hooks', 'email': 'chef@avec-hooks.ma'},
            format='json')
        company = Company.objects.get(slug='avec-hooks')
        from apps.records.models import ActivityType
        self.assertTrue(
            ActivityType.objects.filter(company=company).exists(),
            "les hooks de signup (types d'activité) doivent avoir tourné")

    # ── Idempotence ─────────────────────────────────────────────────────────
    def test_rejeu_exact_est_idempotent(self):
        payload = {'nom': 'Rejouable', 'email': 'chef@rejouable.ma'}
        premier = self._api(self.fondateur).post(
            self.URL, payload, format='json')
        self.assertEqual(premier.status_code, 201)

        second = self._api(self.fondateur).post(
            self.URL, payload, format='json')
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data.get('deja_existant'))
        # Aucune société ni aucun compte en double.
        self.assertEqual(Company.objects.filter(slug='rejouable').count(), 1)
        self.assertEqual(
            CustomUser.objects.filter(email__iexact='chef@rejouable.ma').count(), 1)

    def test_slug_deja_pris_par_une_autre_societe_409(self):
        resp = self._api(self.fondateur).post(
            self.URL, {'nom': 'Deja La', 'email': 'autre@exemple.ma'},
            format='json')
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(Company.objects.filter(slug='deja-la').count(), 1)

    def test_email_deja_utilise_409(self):
        resp = self._api(self.fondateur).post(
            self.URL, {'nom': 'Autre Societe', 'email': 'admin@deja-la.ma'},
            format='json')
        self.assertEqual(resp.status_code, 409)
        self.assertFalse(Company.objects.filter(slug='autre-societe').exists())

    def test_tenant_cree_est_isole_du_tenant_existant(self):
        self._api(self.fondateur).post(
            self.URL, {'nom': 'Isole', 'email': 'chef@isole.ma'},
            format='json')
        company = Company.objects.get(slug='isole')
        admin = CustomUser.objects.get(company=company)
        # L'admin du nouveau tenant n'est membre QUE de sa société.
        self.assertEqual(
            list(admin.societes_autorisees.values_list('pk', flat=True)),
            [company.pk])
        self.assertNotIn(
            self.tenant_existant, admin.societes_autorisees.all())
