"""NTI18N3 — Langue d'interface persistée par utilisateur (pas seulement
`localStorage`), pour qu'il la retrouve en se connectant d'un autre poste.

Couvre :
- ``CustomUser.langue_interface`` par défaut = 'fr' (comportement N93 inchangé
  pour tout compte existant) ;
- l'endpoint self-service (`PATCH /auth/me/langue/`) persiste UNIQUEMENT le
  compte courant, rejette une valeur hors whitelist fr/en/ar ;
- la valeur est exposée en lecture par `/auth/me/`, mais jamais écrivable par
  le PATCH générique du profil (`UserViewSet`/`/auth/me/`).
"""
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company, CustomUser


def _make_company(name='NTI18N3 Co', slug='nti18n3-co'):
    return Company.objects.create(nom=name, slug=slug)


def _make_user(company, username):
    return CustomUser.objects.create_user(
        username=username, password='pw', company=company)


class LangueInterfaceFieldTests(TestCase):
    def test_default_is_fr(self):
        company = _make_company()
        user = _make_user(company, 'plain')
        self.assertEqual(user.langue_interface, 'fr')


class LangueInterfaceApiTests(TestCase):
    def setUp(self):
        self.company = _make_company('ApiCo3', 'api-co-nti18n3')
        self.alice = _make_user(self.company, 'alice3')
        self.bob = _make_user(self.company, 'bob3')
        self.client = APIClient()
        self.client.force_authenticate(self.alice)

    def test_persists_chosen_langue(self):
        res = self.client.patch(
            '/api/django/auth/me/langue/',
            {'langue_interface': 'ar'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['langue_interface'], 'ar')
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.langue_interface, 'ar')

    def test_rejects_value_outside_whitelist(self):
        res = self.client.patch(
            '/api/django/auth/me/langue/',
            {'langue_interface': 'darija'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.langue_interface, 'fr')

    def test_only_affects_current_user(self):
        self.client.patch(
            '/api/django/auth/me/langue/',
            {'langue_interface': 'en'}, format='json')
        self.bob.refresh_from_db()
        self.assertEqual(self.bob.langue_interface, 'fr')

    def test_returned_in_me_endpoint(self):
        self.alice.langue_interface = 'en'
        self.alice.save(update_fields=['langue_interface'])
        res = self.client.get('/api/django/auth/me/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['langue_interface'], 'en')

    def test_me_patch_cannot_write_langue_interface(self):
        # NTI18N3 — écriture réservée à LangueInterfaceView (whitelist
        # stricte) ; le PATCH générique de profil reste read-only ici.
        res = self.client.patch(
            '/api/django/auth/me/', {'langue_interface': 'ar'}, format='json')
        self.assertIn(res.status_code, (200, 405))  # RetrieveAPIView : pas de PATCH
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.langue_interface, 'fr')

    def test_scenario_acceptance_same_langue_from_another_workstation(self):
        # Critère d'acceptation littéral : changer de langue sur un poste,
        # puis se reconnecter (simulé ici par un second APIClient/session
        # authentifié pour le MÊME utilisateur, sans état localStorage
        # partagé) doit retrouver la MÊME langue via /auth/me/.
        self.client.patch(
            '/api/django/auth/me/langue/',
            {'langue_interface': 'ar'}, format='json')
        autre_poste = APIClient()
        autre_poste.force_authenticate(self.alice)
        res = autre_poste.get('/api/django/auth/me/')
        self.assertEqual(res.data['langue_interface'], 'ar')
