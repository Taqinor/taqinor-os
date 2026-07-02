"""
FG309 — Retenue de garantie sur sous-traitant (pratique BTP marocaine).

Couvre :
  * création via l'API avec société + ``created_by`` posés CÔTÉ SERVEUR ;
  * un ``ordre`` d'une autre société est rejeté ;
  * le calcul `montant_retenu` (base × %) et `montant_a_liberer` (0 si levée) ;
  * la base = réalisé sinon engagé ;
  * la validation du pourcentage (0–100) ;
  * l'action `lever` (idempotente) : pose levee + date, montant_a_liberer → 0 ;
  * le scope société et la barrière de rôle (écriture responsable/admin).

Run :
    python manage.py test apps.installations.tests_fg309_retenue_garantie -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    RetenueGarantieSousTraitant, OrdreSousTraitance,
)
from apps.stock.services import create_sous_traitant

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg309-co-{n}', defaults={'nom': nom or f'FG309 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg309-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_sous_traitant(company):
    # DC34 — un sous-traitant est un stock.Fournisseur(type='service').
    return create_sous_traitant(
        company=company, nom='Genie SARL', metier='genie_civil')


def make_ordre(company, montant='100000', realise=None):
    st = make_sous_traitant(company)
    n = next(_seq)
    return OrdreSousTraitance.objects.create(
        company=company, reference=f'OST-T-{n}', sous_traitant=st,
        prestation='Génie civil', montant=Decimal(montant),
        montant_realise=Decimal(realise) if realise is not None else None)


class TestRetenueCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.ordre = make_ordre(self.company, montant='100000')

    def test_create_and_montant(self):
        r = self.api.post(f'{BASE}/retenues-garantie-sous-traitant/', {
            'ordre': self.ordre.id, 'pourcentage': '10',
        })
        self.assertEqual(r.status_code, 201, r.data)
        rg = RetenueGarantieSousTraitant.objects.get(id=r.data['id'])
        self.assertEqual(rg.company_id, self.company.id)
        self.assertEqual(rg.created_by_id, self.user.id)
        # 10 % de 100000 = 10000.
        self.assertEqual(float(r.data['montant_retenu']), 10000.0)
        self.assertEqual(float(r.data['montant_a_liberer']), 10000.0)
        self.assertFalse(r.data['levee'])

    def test_base_uses_realise_when_present(self):
        ordre = make_ordre(self.company, montant='100000', realise='80000')
        rg = RetenueGarantieSousTraitant.objects.create(
            company=self.company, ordre=ordre, pourcentage=Decimal('10'))
        # base = réalisé (80000) → 8000.
        self.assertEqual(rg.montant_retenu, Decimal('8000.00'))

    def test_pourcentage_out_of_range(self):
        r = self.api.post(f'{BASE}/retenues-garantie-sous-traitant/', {
            'ordre': self.ordre.id, 'pourcentage': '150',
        })
        self.assertEqual(r.status_code, 400, r.data)

    def test_foreign_ordre_rejected(self):
        autre = make_company()
        ordre_o = make_ordre(autre)
        r = self.api.post(f'{BASE}/retenues-garantie-sous-traitant/', {
            'ordre': ordre_o.id, 'pourcentage': '5',
        })
        self.assertEqual(r.status_code, 400, r.data)


class TestLever(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.ordre = make_ordre(self.company, montant='50000')
        self.rg = RetenueGarantieSousTraitant.objects.create(
            company=self.company, ordre=self.ordre, pourcentage=Decimal('10'))

    def test_lever_sets_levee_and_zero_a_liberer(self):
        r = self.api.post(
            f'{BASE}/retenues-garantie-sous-traitant/{self.rg.id}/lever/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['levee'])
        self.assertIsNotNone(r.data['date_levee'])
        self.assertEqual(float(r.data['montant_a_liberer']), 0.0)
        # montant_retenu reste calculé (5000).
        self.assertEqual(float(r.data['montant_retenu']), 5000.0)

    def test_lever_idempotent(self):
        self.api.post(
            f'{BASE}/retenues-garantie-sous-traitant/{self.rg.id}/lever/')
        r2 = self.api.post(
            f'{BASE}/retenues-garantie-sous-traitant/{self.rg.id}/lever/')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertTrue(r2.data['levee'])


class TestScopeAndRole(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.ordre = make_ordre(self.company)

    def test_write_requires_role(self):
        normal = make_user(self.company, role='normal')
        api = auth(normal)
        r = api.post(f'{BASE}/retenues-garantie-sous-traitant/', {
            'ordre': self.ordre.id, 'pourcentage': '10',
        })
        self.assertEqual(r.status_code, 403, r.data)

    def test_scope_isolation(self):
        other = make_company()
        ordre_o = make_ordre(other)
        RetenueGarantieSousTraitant.objects.create(
            company=other, ordre=ordre_o, pourcentage=Decimal('10'))
        RetenueGarantieSousTraitant.objects.create(
            company=self.company, ordre=self.ordre, pourcentage=Decimal('10'))
        r = self.api.get(f'{BASE}/retenues-garantie-sous-traitant/')
        results = r.data['results'] if 'results' in r.data else r.data
        self.assertEqual(len(results), 1)
