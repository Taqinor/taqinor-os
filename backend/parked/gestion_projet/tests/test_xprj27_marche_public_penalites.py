"""Tests du volet marchés publics & pénalités de retard (XPRJ27).

Couvre : les champs marché-public sont FACULTATIFS et sans impact sur les
projets privés ; l'exposition aux pénalités est nulle avant le délai
contractuel ; le calcul (jours de dépassement × taux × montant, plafonné) ;
le plafond en % du montant du marché ; isolation société ; l'endpoint
``projets/<id>/penalites-retard/``.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import Projet

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


class PenalitesRetardSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-x27-sel', 'S')

    def test_projet_prive_non_applicable(self):
        projet = Projet.objects.create(
            company=self.co, code='P-PRIVE', nom='P privé')
        data = selectors.penalites_retard(projet)
        self.assertFalse(data['applicable'])
        self.assertEqual(data['exposition'], Decimal('0'))

    def test_avant_delai_exposition_nulle(self):
        projet = Projet.objects.create(
            company=self.co, code='P-MP1', nom='P',
            numero_marche='MP-2026-001', maitre_ouvrage='Commune X',
            date_debut=date(2026, 1, 1), delai_execution_jours=90,
            taux_penalite_retard=Decimal('1.0'),
            montant_marche=Decimal('1000000'))
        data = selectors.penalites_retard(
            projet, date_reference=date(2026, 2, 1))
        self.assertTrue(data['applicable'])
        self.assertEqual(data['jours_depassement'], 0)
        self.assertEqual(data['exposition'], Decimal('0'))
        self.assertFalse(data['decompte_definitif_a_etablir'])

    def test_apres_delai_calcule_exposition(self):
        projet = Projet.objects.create(
            company=self.co, code='P-MP2', nom='P',
            numero_marche='MP-2026-002', maitre_ouvrage='Commune Y',
            date_debut=date(2026, 1, 1), delai_execution_jours=90,
            taux_penalite_retard=Decimal('1.0'),  # 1‰/jour
            montant_marche=Decimal('1000000'))
        date_limite = date(2026, 1, 1) + timedelta(days=90)
        reference = date_limite + timedelta(days=10)
        data = selectors.penalites_retard(projet, date_reference=reference)
        self.assertEqual(data['jours_depassement'], 10)
        # 10 jours x (1/1000) x 1 000 000 = 10 000
        self.assertEqual(data['exposition_brute'], Decimal('10000.00'))
        self.assertEqual(data['exposition'], Decimal('10000.00'))
        self.assertFalse(data['plafonnee'])
        self.assertTrue(data['decompte_definitif_a_etablir'])

    def test_plafond_respecte(self):
        projet = Projet.objects.create(
            company=self.co, code='P-MP3', nom='P',
            numero_marche='MP-2026-003', maitre_ouvrage='Commune Z',
            date_debut=date(2026, 1, 1), delai_execution_jours=10,
            taux_penalite_retard=Decimal('5.0'),  # 5‰/jour — élevé exprès
            montant_marche=Decimal('1000000'),
            plafond_penalite_pct=Decimal('10'))  # plafond 10% = 100 000
        date_limite = date(2026, 1, 1) + timedelta(days=10)
        # 100 jours de retard x 5‰ x 1M = 500 000, largement > plafond 100 000
        reference = date_limite + timedelta(days=100)
        data = selectors.penalites_retard(projet, date_reference=reference)
        self.assertEqual(data['plafond_montant'], Decimal('100000.00'))
        self.assertTrue(data['plafonnee'])
        self.assertEqual(data['exposition'], Decimal('100000.00'))
        self.assertGreater(data['exposition_brute'], data['exposition'])


class PenalitesRetardApiTests(TestCase):
    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co_a = make_company('gp-x27-a', 'A')
        self.co_b = make_company('gp-x27-b', 'B')
        self.user_a = make_user(self.co_a, 'gp-x27-a-u')
        self.user_b = make_user(self.co_b, 'gp-x27-b-u')
        self.projet_a = Projet.objects.create(
            company=self.co_a, code='P-X27A', nom='A',
            numero_marche='MP-A', maitre_ouvrage='M.O A',
            date_debut=date(2026, 1, 1), delai_execution_jours=30,
            taux_penalite_retard=Decimal('1'),
            montant_marche=Decimal('500000'))

    def test_endpoint_expose_exposition(self):
        api = auth(self.user_a)
        resp = api.get(f'{self.BASE}{self.projet_a.id}/penalites-retard/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('exposition', resp.data)
        self.assertTrue(resp.data['applicable'])

    def test_champs_marche_facultatifs_creation_sans_impact(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'code': 'P-PRIV-X27', 'nom': 'Projet privé',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['numero_marche'], '')

    def test_isolation_societe_404(self):
        api = auth(self.user_b)
        resp = api.get(f'{self.BASE}{self.projet_a.id}/penalites-retard/')
        self.assertEqual(resp.status_code, 404)
