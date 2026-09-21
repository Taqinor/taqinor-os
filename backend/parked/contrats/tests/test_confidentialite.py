"""Tests CONTRAT6 — Niveaux de confidentialité + droits d'accès par type.

Couvre :
- La valeur par défaut du champ ``confidentialite`` (INTERNE).
- La création via API avec un niveau de confidentialité choisi.
- La visibilité des contrats CONFIDENTIEL réservée aux Administrateurs :
    * un Responsable NE VOIT PAS les contrats CONFIDENTIEL.
    * un Administrateur LES VOIT.
- L'isolation multi-tenant reste intacte (company B ne voit pas company A,
  quelle que soit la confidentialité).
- Le filtre ``?confidentialite=<niveau>`` fonctionne côté API.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats.models import Contrat
from apps.roles.models import RESPONSABLE_PERMISSIONS, Role

User = get_user_model()

BASE = '/api/django/contrats/contrats/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_role_fk_user(company, username, permissions):
    """Utilisateur provisionné via le Role FK (role_legacy laissé à 'normal',
    comme en production après ``init_roles``). Le palier faisant autorité dérive
    alors du Role, pas de ``role_legacy``."""
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class ConfidentialiteDefaultTests(TestCase):
    """Le niveau de confidentialité par défaut est INTERNE."""

    def setUp(self):
        self.co = make_company('conf-default', 'D')
        self.admin = make_user(self.co, 'conf-admin-default', role='admin')

    def test_default_confidentialite_is_interne(self):
        api = auth(self.admin)
        resp = api.post(BASE, {'objet': 'Contrat sans confidentialité'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Contrat.objects.get(id=resp.data['id'])
        self.assertEqual(obj.confidentialite, Contrat.NiveauConfidentialite.INTERNE)
        self.assertEqual(resp.data['confidentialite'], 'interne')
        self.assertEqual(resp.data['confidentialite_display'], 'Interne')

    def test_can_create_with_public(self):
        api = auth(self.admin)
        resp = api.post(
            BASE,
            {'objet': 'Contrat public', 'confidentialite': 'public'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['confidentialite'], 'public')

    def test_can_create_with_confidentiel(self):
        api = auth(self.admin)
        resp = api.post(
            BASE,
            {'objet': 'Contrat confidentiel', 'confidentialite': 'confidentiel'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['confidentialite'], 'confidentiel')


class ConfidentialiteVisibiliteTests(TestCase):
    """Visibilité des contrats CONFIDENTIEL selon le rôle.

    - Responsable : ne voit PAS les contrats CONFIDENTIEL.
    - Administrateur : les voit tous.
    """

    def setUp(self):
        self.co = make_company('conf-visib', 'V')
        self.admin = make_user(self.co, 'conf-admin-visib', role='admin')
        self.resp = make_user(self.co, 'conf-resp-visib', role='responsable')
        # Trois contrats : un de chaque niveau
        self.c_public = Contrat.objects.create(
            company=self.co, objet='Public',
            confidentialite=Contrat.NiveauConfidentialite.PUBLIC)
        self.c_interne = Contrat.objects.create(
            company=self.co, objet='Interne',
            confidentialite=Contrat.NiveauConfidentialite.INTERNE)
        self.c_confidentiel = Contrat.objects.create(
            company=self.co, objet='Confidentiel',
            confidentialite=Contrat.NiveauConfidentialite.CONFIDENTIEL)

    def test_responsable_ne_voit_pas_confidentiel(self):
        """Un Responsable reçoit public+interne mais PAS le contrat confidentiel."""
        api = auth(self.resp)
        resp = api.get(BASE)
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.c_public.id, ids)
        self.assertIn(self.c_interne.id, ids)
        self.assertNotIn(self.c_confidentiel.id, ids)

    def test_responsable_ne_peut_pas_acceder_detail_confidentiel(self):
        """Un Responsable reçoit 404 en accédant au détail d'un contrat CONFIDENTIEL."""
        api = auth(self.resp)
        resp = api.get(f'{BASE}{self.c_confidentiel.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_admin_voit_tous_les_niveaux(self):
        """Un Administrateur voit les trois niveaux de confidentialité."""
        api = auth(self.admin)
        resp = api.get(BASE)
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.c_public.id, ids)
        self.assertIn(self.c_interne.id, ids)
        self.assertIn(self.c_confidentiel.id, ids)

    def test_admin_accede_detail_confidentiel(self):
        """Un Administrateur peut accéder au détail d'un contrat CONFIDENTIEL."""
        api = auth(self.admin)
        resp = api.get(f'{BASE}{self.c_confidentiel.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['confidentialite'], 'confidentiel')


class ConfidentialiteRoleFKTests(TestCase):
    """Régression CONTRAT6 : le palier doit dériver du Role FK, pas de
    ``role_legacy``.

    En production (après ``init_roles``) un Administrateur porte un Role FK avec
    ``roles_gerer`` tout en gardant ``role_legacy='normal'``. La visibilité des
    contrats CONFIDENTIEL doit suivre le palier FAISANT AUTORITÉ (``menu_tier``)
    et non le champ legacy.
    """

    def setUp(self):
        self.co = make_company('conf-rolefk', 'R')
        # Admin via Role FK (roles_gerer) — role_legacy reste 'normal'.
        # YRBAC3 — contrat_voir est désormais requis pour accéder aux
        # endpoints contrats (avant, IsResponsableOrAdmin passait pour tout
        # rôle avec une permission d'écriture, dont roles_gerer) ; un admin
        # provisionné en production porte aussi les permissions contrats
        # (cf. ADMIN_PERMISSIONS, dérivé de ALL_PERMISSIONS) donc ce fixture
        # doit désormais le poser explicitement pour rester représentatif.
        self.admin_fk = make_role_fk_user(
            self.co, 'conf-admin-fk',
            permissions=['roles_gerer', 'contrat_voir', 'contrat_gerer'])
        # Responsable via Role FK (palier responsable : permissions d'écriture
        # + users_voir, mais PAS roles_gerer → non-admin).
        self.resp_fk = make_role_fk_user(
            self.co, 'conf-resp-fk',
            permissions=list(RESPONSABLE_PERMISSIONS))
        self.c_confidentiel = Contrat.objects.create(
            company=self.co, objet='Confidentiel RoleFK',
            confidentialite=Contrat.NiveauConfidentialite.CONFIDENTIEL)

    def test_admin_role_fk_voit_confidentiel(self):
        """Un admin provisionné via Role FK VOIT les contrats CONFIDENTIEL."""
        api = auth(self.admin_fk)
        resp = api.get(BASE)
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.c_confidentiel.id, ids)
        detail = api.get(f'{BASE}{self.c_confidentiel.id}/')
        self.assertEqual(detail.status_code, 200)

    def test_responsable_role_fk_ne_voit_pas_confidentiel(self):
        """Un responsable via Role FK NE VOIT PAS les contrats CONFIDENTIEL."""
        api = auth(self.resp_fk)
        resp = api.get(BASE)
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in rows(resp)]
        self.assertNotIn(self.c_confidentiel.id, ids)
        detail = api.get(f'{BASE}{self.c_confidentiel.id}/')
        self.assertEqual(detail.status_code, 404)


class ConfidentialiteMultiTenantTests(TestCase):
    """L'isolation multi-tenant reste intacte quelle que soit la confidentialité."""

    def setUp(self):
        self.co_a = make_company('conf-mt-a', 'A')
        self.co_b = make_company('conf-mt-b', 'B')
        self.admin_a = make_user(self.co_a, 'conf-mt-admin-a', role='admin')
        self.admin_b = make_user(self.co_b, 'conf-mt-admin-b', role='admin')
        # Contrat PUBLIC de la société A — l'admin B ne doit pas le voir.
        self.c_a_public = Contrat.objects.create(
            company=self.co_a, objet='Public A',
            confidentialite=Contrat.NiveauConfidentialite.PUBLIC)

    def test_admin_b_ne_voit_pas_contrat_a_meme_public(self):
        """Même un contrat PUBLIC d'une autre société reste invisible."""
        api = auth(self.admin_b)
        resp = api.get(BASE)
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in rows(resp)]
        self.assertNotIn(self.c_a_public.id, ids)


class ConfidentialiteFiltreTests(TestCase):
    """Le filtre ``?confidentialite=`` restreint la liste retournée."""

    def setUp(self):
        self.co = make_company('conf-filtre', 'F')
        self.admin = make_user(self.co, 'conf-filtre-admin', role='admin')
        self.c_pub = Contrat.objects.create(
            company=self.co, objet='Public F',
            confidentialite=Contrat.NiveauConfidentialite.PUBLIC)
        self.c_int = Contrat.objects.create(
            company=self.co, objet='Interne F',
            confidentialite=Contrat.NiveauConfidentialite.INTERNE)
        self.c_conf = Contrat.objects.create(
            company=self.co, objet='Confidentiel F',
            confidentialite=Contrat.NiveauConfidentialite.CONFIDENTIEL)

    def test_filtre_confidentiel(self):
        api = auth(self.admin)
        resp = api.get(f'{BASE}?confidentialite=confidentiel')
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.c_conf.id, ids)
        self.assertNotIn(self.c_pub.id, ids)
        self.assertNotIn(self.c_int.id, ids)

    def test_filtre_public(self):
        api = auth(self.admin)
        resp = api.get(f'{BASE}?confidentialite=public')
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.c_pub.id, ids)
        self.assertNotIn(self.c_int.id, ids)
        self.assertNotIn(self.c_conf.id, ids)
