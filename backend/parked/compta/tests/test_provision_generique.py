"""Tests XACC26 — Provisions pour risques & charges + dépréciation stock/immo.

Couvre : dotation équilibrée (débit charge / crédit passif selon nature),
reprise partielle puis totale (idempotence sur provision soldée), l'état
récapitulatif ``etats/provisions/`` groupé par nature, la pose ``company`` /
``reference`` côté serveur et l'isolation multi-société.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import LigneEcriture, Provision

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


class ProvisionServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc26-svc', 'XACC26 Svc')
        self.user = make_user(self.co, 'xacc26-svc-user')

    def test_dotation_risques_charges_ecriture_equilibree(self):
        prov = services.enregistrer_provision(
            self.co, nature=Provision.Nature.RISQUES_CHARGES,
            date_dotation=date(2026, 6, 30), montant=Decimal('30000'),
            motif='Litige prud’homal', user=self.user)
        self.assertTrue(prov.reference.startswith('PROV-'))
        self.assertIsNotNone(prov.ecriture_dotation_id)
        lignes = LigneEcriture.objects.filter(
            ecriture_id=prov.ecriture_dotation_id)
        debit = sum((x.debit for x in lignes), Decimal('0'))
        credit = sum((x.credit for x in lignes), Decimal('0'))
        self.assertEqual(debit, credit)
        self.assertEqual(debit, Decimal('30000.00'))
        numeros = {x.compte.numero for x in lignes}
        self.assertIn('6195', numeros)
        self.assertIn('1516', numeros)

    def test_dotation_depreciation_stock_comptes(self):
        prov = services.enregistrer_provision(
            self.co, nature=Provision.Nature.DEPRECIATION_STOCK,
            date_dotation=date(2026, 6, 30), montant=Decimal('5000'),
            motif='Stock obsolète', user=self.user)
        lignes = LigneEcriture.objects.filter(
            ecriture_id=prov.ecriture_dotation_id)
        numeros = {x.compte.numero for x in lignes}
        self.assertIn('6196', numeros)
        self.assertIn('3910', numeros)

    def test_reprise_partielle_puis_totale(self):
        prov = services.enregistrer_provision(
            self.co, nature=Provision.Nature.DEPRECIATION_IMMO,
            date_dotation=date(2026, 1, 15), montant=Decimal('10000'),
            user=self.user)
        services.reprendre_provision(
            prov, montant=Decimal('4000'), date_reprise=date(2026, 6, 30),
            user=self.user)
        prov.refresh_from_db()
        self.assertEqual(prov.montant_repris, Decimal('4000'))
        self.assertEqual(prov.solde, Decimal('6000'))
        self.assertFalse(prov.est_soldee)

        services.reprendre_provision(prov, user=self.user)  # reste = solde
        prov.refresh_from_db()
        self.assertEqual(prov.montant_repris, Decimal('10000'))
        self.assertTrue(prov.est_soldee)

        with self.assertRaises(Exception):
            services.reprendre_provision(prov, user=self.user)

    def test_reprise_superieure_au_solde_refusee(self):
        prov = services.enregistrer_provision(
            self.co, nature=Provision.Nature.RISQUES_CHARGES,
            date_dotation=date(2026, 1, 1), montant=Decimal('1000'),
            user=self.user)
        with self.assertRaises(Exception):
            services.reprendre_provision(
                prov, montant=Decimal('5000'), user=self.user)

    def test_etat_provisions_groupe_par_nature(self):
        services.enregistrer_provision(
            self.co, nature=Provision.Nature.RISQUES_CHARGES,
            date_dotation=date(2026, 3, 1), montant=Decimal('2000'),
            user=self.user)
        services.enregistrer_provision(
            self.co, nature=Provision.Nature.DEPRECIATION_STOCK,
            date_dotation=date(2026, 3, 15), montant=Decimal('3000'),
            user=self.user)
        from apps.compta.selectors import etat_provisions
        data = etat_provisions(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31))
        self.assertIn(Provision.Nature.RISQUES_CHARGES, data)
        self.assertIn(Provision.Nature.DEPRECIATION_STOCK, data)
        self.assertEqual(
            data[Provision.Nature.RISQUES_CHARGES]['total_dotation'],
            Decimal('2000'))


class ProvisionApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('xacc26-a', 'XACC26 A')
        self.co_b = make_company('xacc26-b', 'XACC26 B')
        self.user_a = make_user(self.co_a, 'xacc26-user-a')
        self.user_b = make_user(self.co_b, 'xacc26-user-b')

    def test_create_pose_company_et_reference_serveur(self):
        resp = auth(self.user_a).post(
            '/api/django/compta/provisions/',
            {'nature': Provision.Nature.RISQUES_CHARGES,
             'date_dotation': '2026-06-30', 'montant_dotation': '15000',
             'montant_repris': '999999',  # tentative d'imposer.
             'company': self.co_b.id},
            format='json')
        self.assertEqual(resp.status_code, 201)
        prov = Provision.objects.get(id=resp.data['id'])
        self.assertEqual(prov.company_id, self.co_a.id)
        self.assertEqual(prov.montant_repris, Decimal('0'))

    def test_action_reprendre(self):
        prov = services.enregistrer_provision(
            self.co_a, nature=Provision.Nature.RISQUES_CHARGES,
            date_dotation=date(2026, 6, 30), montant=Decimal('1000'),
            user=self.user_a)
        resp = auth(self.user_a).post(
            f'/api/django/compta/provisions/{prov.id}/reprendre/',
            {'date_reprise': '2026-12-31'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['solde'], '0.00')

    def test_isolation_liste(self):
        services.enregistrer_provision(
            self.co_a, nature=Provision.Nature.RISQUES_CHARGES,
            date_dotation=date(2026, 6, 30), montant=Decimal('1000'),
            user=self.user_a)
        resp_b = auth(self.user_b).get('/api/django/compta/provisions/')
        results = resp_b.data.get('results', resp_b.data)
        self.assertEqual(len(results), 0)

    def test_refuse_role_normal(self):
        normal = make_user(self.co_a, 'xacc26-normal', role='normal')
        resp = auth(normal).post(
            '/api/django/compta/provisions/',
            {'nature': Provision.Nature.RISQUES_CHARGES,
             'date_dotation': '2026-06-30', 'montant_dotation': '1000'},
            format='json')
        self.assertEqual(resp.status_code, 403)

    def test_etat_provisions_endpoint(self):
        services.enregistrer_provision(
            self.co_a, nature=Provision.Nature.RISQUES_CHARGES,
            date_dotation=date(2026, 6, 30), montant=Decimal('1000'),
            user=self.user_a)
        resp = auth(self.user_a).get(
            '/api/django/compta/etats/provisions/',
            {'date_debut': '2026-01-01', 'date_fin': '2026-12-31'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn(Provision.Nature.RISQUES_CHARGES, resp.data)
