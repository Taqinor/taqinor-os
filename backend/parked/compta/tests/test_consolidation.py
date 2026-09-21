"""Tests FG153 — Inter-sociétés / consolidation multi-entités.

Couvre : le rattachement d'une entité au périmètre (idempotent), le CPC
consolidé qui agrège la tête de groupe + les membres (intégration globale =
100 %, mise en équivalence = pondérée par % d'intérêt), la pose ``company``
(tête de groupe) côté serveur et le gate de rôle.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import EntiteConsolidation, Journal

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _resultat(company, produit, charge):
    services.seed_plan_comptable(company)
    services.seed_journaux(company)
    journal = services._journal(company, Journal.Type.OPERATIONS_DIVERSES)
    services.creer_ecriture(
        company, journal, date(2026, 1, 10), 'CA',
        [
            {'compte': services.get_compte(company, '3421'),
             'debit': Decimal(produit), 'credit': Decimal('0')},
            {'compte': services.get_compte(company, '7121'),
             'debit': Decimal('0'), 'credit': Decimal(produit)},
        ], statut='validee')
    services.creer_ecriture(
        company, journal, date(2026, 1, 11), 'Achat',
        [
            {'compte': services.get_compte(company, '6111'),
             'debit': Decimal(charge), 'credit': Decimal('0')},
            {'compte': services.get_compte(company, '5141'),
             'debit': Decimal('0'), 'credit': Decimal(charge)},
        ], statut='validee')


class ConsolidationTests(TestCase):
    def setUp(self):
        self.tete = make_company('fg153-tete', 'EI Tête')
        self.membre = make_company('fg153-membre', 'SARL Membre')
        self.user = make_user(self.tete, 'fg153-user')
        _resultat(self.tete, '100000', '60000')
        _resultat(self.membre, '50000', '20000')

    def test_ajout_entite_idempotent(self):
        e1 = services.ajouter_entite_consolidation(
            self.tete, entite=self.membre)
        e2 = services.ajouter_entite_consolidation(
            self.tete, entite=self.membre)
        self.assertEqual(e1.id, e2.id)
        self.assertEqual(EntiteConsolidation.objects.count(), 1)

    def test_cpc_consolide_integration_globale(self):
        services.ajouter_entite_consolidation(self.tete, entite=self.membre)
        data = selectors.cpc_consolide(self.tete)
        # Tête (100k-60k) + membre (50k-20k) = 150k produits, 80k charges.
        self.assertEqual(data['total_produits'], Decimal('150000'))
        self.assertEqual(data['total_charges'], Decimal('80000'))
        self.assertEqual(data['resultat'], Decimal('70000'))
        self.assertEqual(len(data['entites']), 2)

    def test_cpc_consolide_mise_en_equivalence_ponderee(self):
        services.ajouter_entite_consolidation(
            self.tete, entite=self.membre,
            pourcentage_interet=Decimal('40'),
            methode=EntiteConsolidation.Methode.MISE_EN_EQUIVALENCE)
        data = selectors.cpc_consolide(self.tete)
        # Tête 100k + membre 50k×40 % = 20k → 120k produits.
        self.assertEqual(data['total_produits'], Decimal('120000'))
        self.assertEqual(data['total_charges'], Decimal('68000'))

    def test_api_pose_company_et_consolide(self):
        resp = auth(self.user).post(
            '/api/django/compta/entites-consolidation/',
            {'entite': self.membre.id, 'pourcentage_interet': '100'},
            format='json')
        self.assertEqual(resp.status_code, 201)
        ec = EntiteConsolidation.objects.get(id=resp.data['id'])
        self.assertEqual(ec.company_id, self.tete.id)
        resp2 = auth(self.user).get(
            '/api/django/compta/entites-consolidation/cpc_consolide/')
        self.assertEqual(resp2.status_code, 200)
        self.assertIn('resultat', resp2.data)

    def test_refuse_role_normal(self):
        normal = make_user(self.tete, 'fg153-normal', role='normal')
        resp = auth(normal).post(
            '/api/django/compta/entites-consolidation/',
            {'entite': self.membre.id}, format='json')
        self.assertEqual(resp.status_code, 403)
