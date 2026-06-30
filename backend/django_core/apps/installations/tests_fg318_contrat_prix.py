"""
FG318 — Contrats & accords de prix fournisseur (datés / versionnés).

Couvre :
  * création de contrat via l'API : référence (`CPF-`) + société +
    ``created_by`` posés CÔTÉ SERVEUR (jamais count()+1) ;
  * l'injection de ``company``/``reference``/``statut`` est ignorée ;
  * un fournisseur d'une autre société est rejeté ;
  * lignes (SKU + prix convenu) ; une ligne produit d'une autre société rejetée ;
  * le lookup `prix-convenu` : ne retourne que les contrats EN VIGUEUR (actif +
    période couvrante), prend la plus haute version ;
  * le cycle de vie activer/expirer ;
  * le scope société et la barrière de rôle.

Run :
    python manage.py test apps.installations.tests_fg318_contrat_prix -v2
"""
import itertools
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    ContratPrixFournisseur, ContratPrixLigne,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg318-co-{n}', defaults={'nom': nom or f'FG318 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg318-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_fournisseur(company, nom='Prix Garanti'):
    from apps.stock.models import Fournisseur
    return Fournisseur.objects.create(company=company, nom=nom)


def make_produit(company, nom='Panneau 550W'):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=1500, prix_achat=0)


class TestContratCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.f = make_fournisseur(self.company)

    def test_create_server_side_ref(self):
        r = self.api.post(f'{BASE}/contrats-prix-fournisseur/', {
            'intitule': 'Tarif 2026', 'fournisseur': self.f.id, 'version': 1,
        })
        self.assertEqual(r.status_code, 201, r.data)
        c = ContratPrixFournisseur.objects.get(id=r.data['id'])
        self.assertEqual(c.company_id, self.company.id)
        self.assertEqual(c.created_by_id, self.user.id)
        self.assertTrue(c.reference.startswith('CPF-'), c.reference)
        self.assertEqual(c.statut, ContratPrixFournisseur.Statut.BROUILLON)

    def test_injected_fields_ignored(self):
        autre = make_company()
        r = self.api.post(f'{BASE}/contrats-prix-fournisseur/', {
            'company': autre.id, 'reference': 'CPF-HACK', 'statut': 'actif',
            'intitule': 'X', 'fournisseur': self.f.id,
        })
        self.assertEqual(r.status_code, 201, r.data)
        c = ContratPrixFournisseur.objects.get(id=r.data['id'])
        self.assertEqual(c.company_id, self.company.id)
        self.assertNotEqual(c.reference, 'CPF-HACK')
        self.assertEqual(c.statut, ContratPrixFournisseur.Statut.BROUILLON)

    def test_foreign_fournisseur_rejected(self):
        autre = make_company()
        f_o = make_fournisseur(autre)
        r = self.api.post(f'{BASE}/contrats-prix-fournisseur/', {
            'intitule': 'X', 'fournisseur': f_o.id,
        })
        self.assertEqual(r.status_code, 400, r.data)


class TestLignesEtLookup(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.f = make_fournisseur(self.company)
        self.produit = make_produit(self.company)

    def _contrat(self, version=1, statut='actif', debut=None, fin=None):
        return ContratPrixFournisseur.objects.create(
            company=self.company, reference=f'CPF-T-{next(_seq)}',
            intitule='X', fournisseur=self.f, version=version,
            statut=statut, date_debut=debut, date_fin=fin)

    def test_ligne_create_ok(self):
        c = self._contrat()
        r = self.api.post(f'{BASE}/contrats-prix-lignes/', {
            'contrat': c.id, 'produit': self.produit.id,
            'prix_convenu': '1100',
        })
        self.assertEqual(r.status_code, 201, r.data)

    def test_foreign_produit_rejected(self):
        c = self._contrat()
        autre = make_company()
        p_o = make_produit(autre)
        r = self.api.post(f'{BASE}/contrats-prix-lignes/', {
            'contrat': c.id, 'produit': p_o.id, 'prix_convenu': '1',
        })
        self.assertEqual(r.status_code, 400, r.data)

    def test_lookup_returns_active_contract_price(self):
        c = self._contrat(version=1, statut='actif')
        ContratPrixLigne.objects.create(
            contrat=c, produit=self.produit, prix_convenu=1100)
        r = self.api.get(f'{BASE}/contrats-prix-fournisseur/prix-convenu/', {
            'produit': self.produit.id, 'fournisseur': self.f.id,
        })
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(float(r.data['prix_convenu']), 1100.0)
        self.assertEqual(r.data['version'], 1)

    def test_lookup_prefers_highest_version(self):
        c1 = self._contrat(version=1, statut='actif')
        ContratPrixLigne.objects.create(
            contrat=c1, produit=self.produit, prix_convenu=1100)
        c2 = self._contrat(version=2, statut='actif')
        ContratPrixLigne.objects.create(
            contrat=c2, produit=self.produit, prix_convenu=1050)
        r = self.api.get(f'{BASE}/contrats-prix-fournisseur/prix-convenu/', {
            'produit': self.produit.id,
        })
        self.assertEqual(r.data['version'], 2)
        self.assertEqual(float(r.data['prix_convenu']), 1050.0)

    def test_lookup_ignores_non_active(self):
        c = self._contrat(version=1, statut='brouillon')
        ContratPrixLigne.objects.create(
            contrat=c, produit=self.produit, prix_convenu=999)
        r = self.api.get(f'{BASE}/contrats-prix-fournisseur/prix-convenu/', {
            'produit': self.produit.id,
        })
        self.assertIsNone(r.data['prix_convenu'])

    def test_lookup_respects_date_window(self):
        past = date.today() - timedelta(days=60)
        old_end = date.today() - timedelta(days=30)
        c = self._contrat(version=1, statut='actif', debut=past, fin=old_end)
        ContratPrixLigne.objects.create(
            contrat=c, produit=self.produit, prix_convenu=1200)
        # Aujourd'hui : hors fenêtre → aucun prix.
        r = self.api.get(f'{BASE}/contrats-prix-fournisseur/prix-convenu/', {
            'produit': self.produit.id,
        })
        self.assertIsNone(r.data['prix_convenu'])
        # À une date couverte → prix retourné.
        r2 = self.api.get(f'{BASE}/contrats-prix-fournisseur/prix-convenu/', {
            'produit': self.produit.id,
            'date': (past + timedelta(days=5)).isoformat(),
        })
        self.assertEqual(float(r2.data['prix_convenu']), 1200.0)

    def test_lookup_missing_produit(self):
        r = self.api.get(f'{BASE}/contrats-prix-fournisseur/prix-convenu/')
        self.assertEqual(r.status_code, 400, r.data)


class TestLifecycleScopeRole(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.f = make_fournisseur(self.company)
        self.c = ContratPrixFournisseur.objects.create(
            company=self.company, reference='CPF-T-X', intitule='X',
            fournisseur=self.f, created_by=self.user)

    def test_activer_expirer(self):
        r = self.api.post(
            f'{BASE}/contrats-prix-fournisseur/{self.c.id}/activer/')
        self.assertEqual(r.data['statut'], 'actif')
        r = self.api.post(
            f'{BASE}/contrats-prix-fournisseur/{self.c.id}/expirer/')
        self.assertEqual(r.data['statut'], 'expire')

    def test_write_requires_role(self):
        normal = make_user(self.company, role='normal')
        api = auth(normal)
        r = api.post(f'{BASE}/contrats-prix-fournisseur/', {
            'intitule': 'X', 'fournisseur': self.f.id,
        })
        self.assertEqual(r.status_code, 403, r.data)

    def test_scope_isolation(self):
        other = make_company()
        f_o = make_fournisseur(other)
        ContratPrixFournisseur.objects.create(
            company=other, reference='CPF-O-1', intitule='Autre',
            fournisseur=f_o)
        r = self.api.get(f'{BASE}/contrats-prix-fournisseur/')
        results = r.data['results'] if 'results' in r.data else r.data
        self.assertEqual(len(results), 1)
