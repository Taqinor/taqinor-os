"""Tests — rôles (Feature D), superviseur/équipe (E), visibilité (F).

Vérifie que le narrowing est OPT-IN (seuls les rôles à marqueur de portée sont
restreints), que personne ne perd l'accès à ses propres enregistrements, et que
les prix d'achat sont réservés par permission.
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser
from apps.roles.models import (
    Role, DIRECTEUR_PERMISSIONS, COMMERCIAL_PERMISSIONS,
    COMMERCIAL_RESP_PERMISSIONS,
)
from apps.crm.models import Lead
from apps.stock.models import Produit


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def names(resp):
    data = resp.data
    rows = data['results'] if isinstance(data, dict) and 'results' in data else data
    return {r['nom'] for r in rows}


class TestVisibilityScoping(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Scope Co', slug='scope-co')
        self.dir_role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=DIRECTEUR_PERMISSIONS, est_systeme=True)
        self.cr_role = Role.objects.create(
            company=self.company, nom='Commercial responsable',
            permissions=COMMERCIAL_RESP_PERMISSIONS, est_systeme=True)
        self.com_role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=COMMERCIAL_PERMISSIONS, est_systeme=True)

        def u(name, role=None, supervisor=None, legacy='normal'):
            return CustomUser.objects.create_user(
                username=name, password='x', company=self.company,
                role=role, role_legacy=legacy, supervisor=supervisor)

        self.directeur = u('dir', role=self.dir_role, legacy='admin')
        self.boss = u('boss', role=self.cr_role)            # responsable
        self.alice = u('alice', role=self.com_role, supervisor=self.boss)
        self.bob = u('bob', role=self.com_role, supervisor=self.boss)
        self.carol = u('carol', role=self.com_role)         # équipe à part
        self.legacy = u('legacy_resp', legacy='responsable')  # sans rôle fin

        Lead.objects.create(company=self.company, nom='LA', owner=self.alice)
        Lead.objects.create(company=self.company, nom='LB', owner=self.bob)
        Lead.objects.create(company=self.company, nom='LC', owner=self.carol)
        Lead.objects.create(company=self.company, nom='LU')  # sans propriétaire

    def test_directeur_sees_all(self):
        resp = auth(self.directeur).get('/api/django/crm/leads/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(names(resp), {'LA', 'LB', 'LC', 'LU'})

    def test_legacy_account_sees_all(self):
        # Compte sans rôle fin → comportement historique préservé (voit tout).
        resp = auth(self.legacy).get('/api/django/crm/leads/')
        self.assertEqual(names(resp), {'LA', 'LB', 'LC', 'LU'})

    def test_commercial_sees_only_team(self):
        # alice : ses pairs = même superviseur (boss) → alice + bob.
        resp = auth(self.alice).get('/api/django/crm/leads/')
        self.assertEqual(names(resp), {'LA', 'LB'})

    def test_commercial_responsable_sees_subtree(self):
        # boss : son sous-arbre = alice + bob (qui lui remontent).
        resp = auth(self.boss).get('/api/django/crm/leads/')
        self.assertEqual(names(resp), {'LA', 'LB'})

    def test_user_always_sees_own_even_alone(self):
        # carol : sans superviseur ni pair → uniquement son propre lead.
        resp = auth(self.carol).get('/api/django/crm/leads/')
        self.assertEqual(names(resp), {'LC'})

    def test_detail_of_foreign_record_is_404(self):
        la = Lead.objects.get(nom='LA')
        resp = auth(self.carol).get(f'/api/django/crm/leads/{la.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_scoped_user_keeps_created_lead(self):
        # Un commercial crée un lead sans propriétaire → il en garde la propriété
        # et le revoit dans sa liste.
        api = auth(self.carol)
        r = api.post('/api/django/crm/leads/', {'nom': 'Nouveau de Carol'})
        self.assertEqual(r.status_code, 201, r.data)
        resp = api.get('/api/django/crm/leads/')
        self.assertIn('Nouveau de Carol', names(resp))


class TestBuyPriceGating(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Prix Co', slug='prix-co')
        self.dir_role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=DIRECTEUR_PERMISSIONS, est_systeme=True)
        self.com_role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=COMMERCIAL_PERMISSIONS, est_systeme=True)
        self.directeur = CustomUser.objects.create_user(
            username='pdir', password='x', company=self.company,
            role=self.dir_role, role_legacy='admin')
        self.com = CustomUser.objects.create_user(
            username='pcom', password='x', company=self.company,
            role=self.com_role)
        Produit.objects.create(
            company=self.company, nom='Panneau', sku='PV-1',
            prix_achat='100', prix_vente='200')

    def test_directeur_sees_buy_price(self):
        resp = auth(self.directeur).get('/api/django/stock/produits/')
        row = (resp.data['results'] if 'results' in resp.data else resp.data)[0]
        self.assertIn('prix_achat', row)

    def test_commercial_never_sees_buy_price(self):
        resp = auth(self.com).get('/api/django/stock/produits/')
        row = (resp.data['results'] if 'results' in resp.data else resp.data)[0]
        self.assertNotIn('prix_achat', row)
        self.assertIn('prix_vente', row)  # le prix de vente reste visible


class TestSupervisorAssignment(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Sup Co', slug='sup-co')
        self.other = Company.objects.create(nom='Autre', slug='autre-co')
        self.dir_role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=DIRECTEUR_PERMISSIONS, est_systeme=True)
        self.directeur = CustomUser.objects.create_user(
            username='sdir', password='x', company=self.company,
            role=self.dir_role, role_legacy='admin')
        self.emp = CustomUser.objects.create_user(
            username='emp', password='x', company=self.company)
        self.boss = CustomUser.objects.create_user(
            username='theboss', password='x', company=self.company)
        self.foreigner = CustomUser.objects.create_user(
            username='foreign', password='x', company=self.other)

    def test_directeur_assigns_supervisor(self):
        resp = auth(self.directeur).patch(
            f'/api/django/users/{self.emp.id}/',
            {'supervisor': self.boss.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.supervisor_id, self.boss.id)

    def test_cross_company_supervisor_rejected(self):
        resp = auth(self.directeur).patch(
            f'/api/django/users/{self.emp.id}/',
            {'supervisor': self.foreigner.id}, format='json')
        self.assertEqual(resp.status_code, 400)
