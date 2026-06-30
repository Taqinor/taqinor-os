"""
FG328 — Pré-assemblage / kitting magasin.

Couvre :
  * création d'un kit + composants : société/`created_by` serveur ;
  * un produit composant d'une autre société rejeté ;
  * ordre d'assemblage : référence (`ASM-`) serveur ; quantité <= 0 rejetée ;
  * un kit d'une autre société rejeté à la création de l'ordre ;
  * cycle démarrer/terminer ;
  * scope société + barrière de rôle.

Run :
    python manage.py test apps.installations.tests_fg328_kitting -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import Kit, OrdreAssemblage

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg328-co-{n}', defaults={'nom': nom or f'FG328 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg328-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_produit(company, nom='Disjoncteur'):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=200, prix_achat=0)


class TestKit(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def test_create_kit_and_composant(self):
        resp = self.api.post(f'{BASE}/kits/', {
            'nom': 'Coffret AC/DC', 'company': 999,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        kit = Kit.objects.get(id=resp.data['id'])
        self.assertEqual(kit.company_id, self.company.id)
        self.assertEqual(kit.created_by_id, self.user.id)
        produit = make_produit(self.company)
        r2 = self.api.post(f'{BASE}/kit-composants/', {
            'kit': kit.id, 'produit': produit.id, 'quantite': 2,
        }, format='json')
        self.assertEqual(r2.status_code, 201, r2.content)

    def test_blank_nom_rejected(self):
        resp = self.api.post(f'{BASE}/kits/', {'nom': '  '}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_composant_other_company_produit_rejected(self):
        kit = Kit.objects.create(company=self.company, nom='K')
        other = make_company()
        p_other = make_produit(other)
        resp = self.api.post(f'{BASE}/kit-composants/', {
            'kit': kit.id, 'produit': p_other.id, 'quantite': 1,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)


class TestOrdreAssemblage(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.kit = Kit.objects.create(company=self.company, nom='Coffret')

    def test_create_sets_reference_server_side(self):
        resp = self.api.post(f'{BASE}/ordres-assemblage/', {
            'kit': self.kit.id, 'quantite': 3, 'reference': 'HACK',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        ordre = OrdreAssemblage.objects.get(id=resp.data['id'])
        self.assertTrue(ordre.reference.startswith('ASM-'))
        self.assertEqual(ordre.statut, OrdreAssemblage.Statut.PLANIFIE)

    def test_zero_quantite_rejected(self):
        resp = self.api.post(f'{BASE}/ordres-assemblage/', {
            'kit': self.kit.id, 'quantite': 0,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_kit_other_company_rejected(self):
        other = make_company()
        kit_other = Kit.objects.create(company=other, nom='K2')
        resp = self.api.post(f'{BASE}/ordres-assemblage/', {
            'kit': kit_other.id, 'quantite': 1,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_cycle_demarrer_terminer(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-X', kit=self.kit, quantite=2)
        r1 = self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/demarrer/', {}, format='json')
        self.assertEqual(r1.status_code, 200, r1.content)
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreAssemblage.Statut.EN_COURS)
        r2 = self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/terminer/', {}, format='json')
        self.assertEqual(r2.status_code, 200, r2.content)
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreAssemblage.Statut.TERMINE)
        self.assertIsNotNone(ordre.date_terminaison)


class TestScopingAndRoles(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other = make_company()

    def test_commercial_cannot_write(self):
        api = auth(make_user(self.company, role='commercial'))
        resp = api.post(f'{BASE}/kits/', {'nom': 'X'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_other_company_cannot_see(self):
        Kit.objects.create(company=self.company, nom='Secret')
        api = auth(make_user(self.other))
        resp = api.get(f'{BASE}/kits/')
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 0)
