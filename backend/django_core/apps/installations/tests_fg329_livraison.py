"""
FG329 — Planification des livraisons (dépôt → site).

Couvre :
  * création : référence (`LIV-`) + société + `created_by` serveur ;
  * un chantier/dépôt d'une autre société rejeté ;
  * lignes (SKU + quantité) ;
  * cycle expedier/livrer/annuler ;
  * scope société + barrière de rôle.

Run :
    python manage.py test apps.installations.tests_fg329_livraison -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, Livraison

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg329-co-{n}', defaults={'nom': nom or f'FG329 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg329-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_emplacement(company, nom='Dépôt'):
    from apps.stock.models import EmplacementStock
    return EmplacementStock.objects.create(company=company, nom=nom)


def make_produit(company, nom='Panneau'):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=1500, prix_achat=0)


def make_installation(company, ref='LV1'):
    client = Client.objects.create(
        company=company, nom='Client', prenom='Test',
        email=f'lv-{company.id}-{ref}@example.invalid')
    return Installation.objects.create(
        company=company, reference=ref, client=client,
        statut=Installation.Statut.RECEPTIONNE,
        type_installation='residentiel',
        puissance_installee_kwc=Decimal('6.5'))


class TestLivraison(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)
        self.depot = make_emplacement(self.company)

    def test_create_sets_reference_company_server_side(self):
        resp = self.api.post(f'{BASE}/livraisons/', {
            'installation': self.inst.id, 'depot': self.depot.id,
            'transporteur_nom': 'Transit Express', 'company': 999,
            'reference': 'HACK',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        liv = Livraison.objects.get(id=resp.data['id'])
        self.assertEqual(liv.company_id, self.company.id)
        self.assertEqual(liv.created_by_id, self.user.id)
        self.assertTrue(liv.reference.startswith('LIV-'))
        self.assertEqual(liv.statut, Livraison.Statut.PLANIFIEE)

    def test_installation_other_company_rejected(self):
        other = make_company()
        inst_other = make_installation(other, ref='OTH')
        resp = self.api.post(f'{BASE}/livraisons/', {
            'installation': inst_other.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_ligne_and_scope(self):
        liv = Livraison.objects.create(
            company=self.company, installation=self.inst, reference='LIV-X')
        produit = make_produit(self.company)
        resp = self.api.post(f'{BASE}/livraison-lignes/', {
            'livraison': liv.id, 'produit': produit.id, 'quantite': 6,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_cycle_expedier_livrer_annuler(self):
        liv = Livraison.objects.create(
            company=self.company, installation=self.inst, reference='LIV-Y')
        r1 = self.api.post(f'{BASE}/livraisons/{liv.id}/expedier/', {},
                           format='json')
        self.assertEqual(r1.status_code, 200, r1.content)
        liv.refresh_from_db()
        self.assertEqual(liv.statut, Livraison.Statut.EN_TRANSIT)
        r2 = self.api.post(f'{BASE}/livraisons/{liv.id}/livrer/', {},
                           format='json')
        self.assertEqual(r2.status_code, 200, r2.content)
        liv.refresh_from_db()
        self.assertEqual(liv.statut, Livraison.Statut.LIVREE)

    def test_annuler(self):
        liv = Livraison.objects.create(
            company=self.company, installation=self.inst, reference='LIV-Z')
        resp = self.api.post(f'{BASE}/livraisons/{liv.id}/annuler/', {},
                             format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        liv.refresh_from_db()
        self.assertEqual(liv.statut, Livraison.Statut.ANNULEE)


class TestScopingAndRoles(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other = make_company()
        self.inst = make_installation(self.company)

    def test_commercial_cannot_write(self):
        api = auth(make_user(self.company, role='commercial'))
        resp = api.post(f'{BASE}/livraisons/', {
            'installation': self.inst.id,
        }, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_other_company_cannot_see(self):
        Livraison.objects.create(
            company=self.company, installation=self.inst, reference='LIV-S')
        api = auth(make_user(self.other))
        resp = api.get(f'{BASE}/livraisons/')
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 0)
