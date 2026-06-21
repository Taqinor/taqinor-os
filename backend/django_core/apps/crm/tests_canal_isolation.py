"""Fonctionnel + multi-tenant — listes de référence CRM (canaux) pilotées depuis
l'écran Paramètres → Leads → Canaux (via crmApi).

Couvre un trou réel : rien ne vérifiait (a) qu'un canal créé par un admin persiste
et réapparaît dans la liste (la fonctionnalité « marche » vraiment, du point de vue
utilisateur), (b) qu'une société ne voit JAMAIS les canaux d'une autre (isolation
multi-tenant), (c) que `company` est forcé côté serveur et jamais lu du corps de la
requête, (d) que l'écriture est réservée aux admins.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser
from apps.crm.models import Canal

User = get_user_model()
CANAUX = '/api/django/crm/canaux/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _libelles(resp):
    rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
    return {r['libelle'] for r in rows}


class TestCanalReferenceList(TestCase):
    def setUp(self):
        self.company_a, _ = Company.objects.get_or_create(
            slug='canal-a', defaults={'nom': 'Société A'})
        self.company_b, _ = Company.objects.get_or_create(
            slug='canal-b', defaults={'nom': 'Société B'})
        self.admin_a = User.objects.create_user(
            username='canal_admin_a', password='x',
            role_legacy=CustomUser.ROLE_ADMIN, company=self.company_a)
        self.admin_b = User.objects.create_user(
            username='canal_admin_b', password='x',
            role_legacy=CustomUser.ROLE_ADMIN, company=self.company_b)
        self.member_a = User.objects.create_user(
            username='canal_member_a', password='x',
            role_legacy='responsable', company=self.company_a)

    def test_admin_creates_then_sees_canal(self):
        """Parcours utilisateur : ajouter un canal → il persiste et réapparaît."""
        api = _api(self.admin_a)
        r = api.post(CANAUX, {'cle': 'salon', 'libelle': 'Salon pro'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(
            Canal.objects.filter(cle='salon', company=self.company_a).exists())
        self.assertIn('Salon pro', _libelles(api.get(CANAUX)))

    def test_company_isolation(self):
        """La société B ne voit JAMAIS le canal personnalisé de la société A."""
        _api(self.admin_a).post(
            CANAUX, {'cle': 'salon', 'libelle': 'Salon pro'}, format='json')
        self.assertNotIn('Salon pro', _libelles(_api(self.admin_b).get(CANAUX)))

    def test_company_not_taken_from_request_body(self):
        """`company` est forcé serveur : injecter B en tant qu'admin A est ignoré."""
        api = _api(self.admin_a)
        r = api.post(
            CANAUX,
            {'cle': 'web2', 'libelle': 'Web 2', 'company': self.company_b.id},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Canal.objects.get(cle='web2').company, self.company_a)

    def test_non_admin_cannot_create(self):
        """Lecture tout rôle, mais écriture admin uniquement."""
        r = _api(self.member_a).post(
            CANAUX, {'cle': 'x', 'libelle': 'X'}, format='json')
        self.assertIn(r.status_code, (401, 403))
