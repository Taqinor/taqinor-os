"""
FG314 — Commandes-cadres / contrats annuels (blanket orders).

Couvre :
  * création de contrat-cadre via l'API : référence (`CC-`) + société +
    ``created_by`` posés CÔTÉ SERVEUR (jamais count()+1) ;
  * l'injection de ``company``/``reference``/``statut`` est ignorée ;
  * un fournisseur d'une autre société est rejeté ;
  * lignes (SKU négocié + volume engagé) ; volume_consomme/volume_restant ;
  * commande d'appel qui consomme le volume ; un appel au-delà du restant est
    rejeté ;
  * le cycle de vie activer/cloturer ;
  * le scope société et la barrière de rôle.

Run :
    python manage.py test apps.installations.tests_fg314_commande_cadre -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    CommandeCadre, CommandeCadreLigne, AppelCommande,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg314-co-{n}', defaults={'nom': nom or f'FG314 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg314-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_fournisseur(company, nom='Annuel SARL'):
    from apps.stock.models import Fournisseur
    return Fournisseur.objects.create(company=company, nom=nom)


class TestCadreCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.f = make_fournisseur(self.company)

    def test_create_server_side_ref(self):
        r = self.api.post(f'{BASE}/commandes-cadre/', {
            'intitule': 'Panneaux 2026', 'fournisseur': self.f.id,
        })
        self.assertEqual(r.status_code, 201, r.data)
        cc = CommandeCadre.objects.get(id=r.data['id'])
        self.assertEqual(cc.company_id, self.company.id)
        self.assertEqual(cc.created_by_id, self.user.id)
        self.assertTrue(cc.reference.startswith('CC-'), cc.reference)
        self.assertEqual(cc.statut, CommandeCadre.Statut.BROUILLON)

    def test_injected_fields_ignored(self):
        autre = make_company()
        r = self.api.post(f'{BASE}/commandes-cadre/', {
            'company': autre.id, 'reference': 'CC-HACK', 'statut': 'clos',
            'intitule': 'X', 'fournisseur': self.f.id,
        })
        self.assertEqual(r.status_code, 201, r.data)
        cc = CommandeCadre.objects.get(id=r.data['id'])
        self.assertEqual(cc.company_id, self.company.id)
        self.assertNotEqual(cc.reference, 'CC-HACK')
        self.assertEqual(cc.statut, CommandeCadre.Statut.BROUILLON)

    def test_foreign_fournisseur_rejected(self):
        autre = make_company()
        f_o = make_fournisseur(autre)
        r = self.api.post(f'{BASE}/commandes-cadre/', {
            'intitule': 'X', 'fournisseur': f_o.id,
        })
        self.assertEqual(r.status_code, 400, r.data)


class TestLignesEtAppels(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.f = make_fournisseur(self.company)
        self.cc = CommandeCadre.objects.create(
            company=self.company, reference='CC-T-1', intitule='X',
            fournisseur=self.f, created_by=self.user)
        self.ligne = CommandeCadreLigne.objects.create(
            commande_cadre=self.cc, designation='Panneau 550W',
            prix_negocie=1200, volume_engage=100)

    def test_appel_consumes_volume(self):
        r = self.api.post(f'{BASE}/appels-commande/', {
            'ligne': self.ligne.id, 'quantite': '30',
        })
        self.assertEqual(r.status_code, 201, r.data)
        # montant = 30 × 1200 = 36000.
        self.assertEqual(float(r.data['montant']), 36000.0)
        self.ligne.refresh_from_db()
        self.assertEqual(float(self.ligne.volume_consomme), 30.0)
        self.assertEqual(float(self.ligne.volume_restant), 70.0)

    def test_appel_over_remaining_rejected(self):
        AppelCommande.objects.create(
            company=self.company, ligne=self.ligne, quantite=90)
        r = self.api.post(f'{BASE}/appels-commande/', {
            'ligne': self.ligne.id, 'quantite': '20',
        })
        self.assertEqual(r.status_code, 400, r.data)

    def test_ligne_requires_product_or_designation(self):
        r = self.api.post(f'{BASE}/commandes-cadre-lignes/', {
            'commande_cadre': self.cc.id,
            'prix_negocie': '10', 'volume_engage': '5',
        })
        self.assertEqual(r.status_code, 400, r.data)

    def test_ligne_create_ok(self):
        r = self.api.post(f'{BASE}/commandes-cadre-lignes/', {
            'commande_cadre': self.cc.id, 'designation': 'Câble',
            'prix_negocie': '10', 'volume_engage': '500',
        })
        self.assertEqual(r.status_code, 201, r.data)


class TestLifecycleScopeRole(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.f = make_fournisseur(self.company)
        self.cc = CommandeCadre.objects.create(
            company=self.company, reference='CC-T-2', intitule='X',
            fournisseur=self.f, created_by=self.user)

    def test_activer_cloturer(self):
        r = self.api.post(f'{BASE}/commandes-cadre/{self.cc.id}/activer/')
        self.assertEqual(r.data['statut'], 'actif')
        r = self.api.post(f'{BASE}/commandes-cadre/{self.cc.id}/cloturer/')
        self.assertEqual(r.data['statut'], 'clos')

    def test_write_requires_role(self):
        normal = make_user(self.company, role='normal')
        api = auth(normal)
        r = api.post(f'{BASE}/commandes-cadre/', {
            'intitule': 'X', 'fournisseur': self.f.id,
        })
        self.assertEqual(r.status_code, 403, r.data)

    def test_scope_isolation(self):
        other = make_company()
        f_o = make_fournisseur(other)
        CommandeCadre.objects.create(
            company=other, reference='CC-O-1', intitule='Autre',
            fournisseur=f_o)
        r = self.api.get(f'{BASE}/commandes-cadre/')
        results = r.data['results'] if 'results' in r.data else r.data
        self.assertEqual(len(results), 1)
