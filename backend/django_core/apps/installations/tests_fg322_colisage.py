"""
FG322 — Colisage / préparation (pack).

Couvre :
  * création d'un colis : référence (`COL-`) + société + `created_by` serveur ;
  * un chantier d'une autre société rejeté ;
  * lignes (SKU + quantité) ; un produit d'une autre société rejeté ;
  * cycle controler (pose `controle_par`/date) / expedier ;
  * scope société + barrière de rôle.

Run :
    python manage.py test apps.installations.tests_fg322_colisage -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, Colis

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg322-co-{n}', defaults={'nom': nom or f'FG322 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg322-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_produit(company, nom='Panneau 550W'):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=1500, prix_achat=0)


def make_installation(company, ref='CL1'):
    client = Client.objects.create(
        company=company, nom='Client', prenom='Test',
        email=f'cl-{company.id}-{ref}@example.invalid')
    return Installation.objects.create(
        company=company, reference=ref, client=client,
        statut=Installation.Statut.RECEPTIONNE,
        type_installation='residentiel',
        puissance_installee_kwc=Decimal('6.5'))


class TestColis(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)
        self.produit = make_produit(self.company)

    def test_create_sets_reference_company_server_side(self):
        resp = self.api.post(f'{BASE}/colis/', {
            'installation': self.inst.id, 'poids_kg': '12.5',
            'company': 999, 'reference': 'HACK',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        c = Colis.objects.get(id=resp.data['id'])
        self.assertEqual(c.company_id, self.company.id)
        self.assertEqual(c.created_by_id, self.user.id)
        self.assertTrue(c.reference.startswith('COL-'))
        self.assertEqual(c.statut, Colis.Statut.PREPARATION)

    def test_installation_other_company_rejected(self):
        other = make_company()
        inst_other = make_installation(other, ref='OTH')
        resp = self.api.post(f'{BASE}/colis/', {
            'installation': inst_other.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_ligne_and_produit_scope(self):
        colis = Colis.objects.create(
            company=self.company, installation=self.inst, reference='COL-X')
        resp = self.api.post(f'{BASE}/colis-lignes/', {
            'colis': colis.id, 'produit': self.produit.id, 'quantite': 4,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        # produit d'une autre société rejeté
        other = make_company()
        p_other = make_produit(other)
        resp2 = self.api.post(f'{BASE}/colis-lignes/', {
            'colis': colis.id, 'produit': p_other.id, 'quantite': 1,
        }, format='json')
        self.assertEqual(resp2.status_code, 400, resp2.content)

    def test_cycle_controler_expedier(self):
        colis = Colis.objects.create(
            company=self.company, installation=self.inst, reference='COL-Y')
        r1 = self.api.post(f'{BASE}/colis/{colis.id}/controler/', {},
                           format='json')
        self.assertEqual(r1.status_code, 200, r1.content)
        colis.refresh_from_db()
        self.assertEqual(colis.statut, Colis.Statut.CONTROLE)
        self.assertEqual(colis.controle_par_id, self.user.id)
        self.assertIsNotNone(colis.date_controle)
        r2 = self.api.post(f'{BASE}/colis/{colis.id}/expedier/', {},
                           format='json')
        self.assertEqual(r2.status_code, 200, r2.content)
        colis.refresh_from_db()
        self.assertEqual(colis.statut, Colis.Statut.EXPEDIE)


class TestScopingAndRoles(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other = make_company()
        self.inst = make_installation(self.company)

    def test_commercial_cannot_write(self):
        api = auth(make_user(self.company, role='commercial'))
        resp = api.post(f'{BASE}/colis/', {
            'installation': self.inst.id,
        }, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_other_company_cannot_see(self):
        Colis.objects.create(
            company=self.company, installation=self.inst, reference='COL-Z')
        api = auth(make_user(self.other))
        resp = api.get(f'{BASE}/colis/')
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 0)
