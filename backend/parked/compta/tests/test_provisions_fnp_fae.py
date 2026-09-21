"""XACC7 — Provisions FNP / FAE de fin de période.

Couvre :

* une réception non facturée génère une provision FNP (6111 débit / 4486
  crédit) équilibrée, avec extourne datée J+1 (1er jour de la période
  suivante) ;
* le miroir FAE (3427 débit / 7121 crédit) pour un avancement non facturé ;
* idempotence par item (rejouer ne duplique ni la provision ni l'extourne) ;
* le rapport de contrôle liste les pièces sources et s'exporte en CSV ;
* endpoints API.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import EcritureComptable

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


class ProvisionsFnpTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc7', 'XACC7 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)

    def test_reception_non_facturee_genere_fnp_avec_extourne(self):
        items = [{'source_id': 501, 'reference': 'REC-501',
                  'montant_ht': Decimal('8000'), 'tiers_id': 7}]
        resultats = services.generer_provisions_fnp(
            self.co, date_periode=date(2026, 1, 31), items=items,
            date_extourne=date(2026, 2, 1))
        self.assertEqual(len(resultats), 1)
        ecr = EcritureComptable.objects.get(id=resultats[0]['ecriture_id'])
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(ecr.lignes.get(compte__numero='6111').debit,
                         Decimal('8000'))
        self.assertEqual(ecr.lignes.get(compte__numero='4486').credit,
                         Decimal('8000'))
        extourne = EcritureComptable.objects.get(id=resultats[0]['extourne_id'])
        self.assertEqual(extourne.date_ecriture, date(2026, 2, 1))
        self.assertTrue(extourne.est_equilibree)
        # L'extourne inverse : crédite 6111, débite 4486.
        self.assertEqual(extourne.lignes.get(compte__numero='4486').debit,
                         Decimal('8000'))

    def test_idempotent_meme_reception(self):
        items = [{'source_id': 502, 'reference': 'REC-502',
                  'montant_ht': Decimal('1000')}]
        a = services.generer_provisions_fnp(
            self.co, date_periode=date(2026, 1, 31), items=items,
            date_extourne=date(2026, 2, 1))
        b = services.generer_provisions_fnp(
            self.co, date_periode=date(2026, 1, 31), items=items,
            date_extourne=date(2026, 2, 1))
        self.assertEqual(a[0]['ecriture_id'], b[0]['ecriture_id'])
        self.assertEqual(a[0]['extourne_id'], b[0]['extourne_id'])
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co, source_type='fnp').count(), 1)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co, source_type='extourne').count(), 1)

    def test_date_extourne_obligatoire(self):
        with self.assertRaises(ValidationError):
            services.generer_provisions_fnp(
                self.co, date_periode=date(2026, 1, 31),
                items=[{'source_id': 1, 'montant_ht': Decimal('100')}],
                date_extourne=None)

    def test_montant_nul_ignore(self):
        resultats = services.generer_provisions_fnp(
            self.co, date_periode=date(2026, 1, 31),
            items=[{'source_id': 999, 'montant_ht': Decimal('0')}],
            date_extourne=date(2026, 2, 1))
        self.assertEqual(resultats, [])


class ProvisionsFaeTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc7-fae', 'XACC7 FAE Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)

    def test_avancement_non_facture_genere_fae(self):
        items = [{'source_id': 601, 'reference': 'CHANTIER-601',
                  'montant_ht': Decimal('15000'), 'tiers_id': 3}]
        resultats = services.generer_provisions_fae(
            self.co, date_periode=date(2026, 1, 31), items=items,
            date_extourne=date(2026, 2, 1))
        ecr = EcritureComptable.objects.get(id=resultats[0]['ecriture_id'])
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(ecr.lignes.get(compte__numero='3427').debit,
                         Decimal('15000'))
        self.assertEqual(ecr.lignes.get(compte__numero='7121').credit,
                         Decimal('15000'))


class RapportProvisionsTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc7-rapport', 'XACC7 Rapport Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        services.generer_provisions_fnp(
            self.co, date_periode=date(2026, 1, 31),
            items=[{'source_id': 701, 'reference': 'REC-701',
                    'montant_ht': Decimal('500')}],
            date_extourne=date(2026, 2, 1))
        services.generer_provisions_fae(
            self.co, date_periode=date(2026, 1, 31),
            items=[{'source_id': 702, 'reference': 'CH-702',
                    'montant_ht': Decimal('700')}],
            date_extourne=date(2026, 2, 1))

    def test_rapport_liste_les_pieces_sources(self):
        rapport = services.rapport_provisions_periode(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31))
        types = {lig['type'] for lig in rapport}
        self.assertEqual(types, {'fnp', 'fae'})
        self.assertEqual(len(rapport), 2)

    def test_export_csv(self):
        data = services.export_provisions_periode_csv(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31))
        text = data.decode('utf-8-sig')
        self.assertIn('REC-701', text)
        self.assertIn('CH-702', text)


class ProvisionsAPITests(TestCase):
    def setUp(self):
        self.co = make_company('xacc7-api', 'XACC7 API Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.user = make_user(self.co, 'admin-xacc7')
        self.api = auth(self.user)

    def test_generer_fnp_via_api(self):
        resp = self.api.post(
            '/api/django/compta/provisions-periode/generer-fnp/', {
                'date_periode': '2026-01-31',
                'date_extourne': '2026-02-01',
                'items': [{'source_id': 801, 'reference': 'REC-801',
                          'montant_ht': '2000'}],
            }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(len(resp.data['postees']), 1)

    def test_rapport_et_export_via_api(self):
        self.api.post(
            '/api/django/compta/provisions-periode/generer-fae/', {
                'date_periode': '2026-01-31',
                'date_extourne': '2026-02-01',
                'items': [{'source_id': 802, 'reference': 'CH-802',
                          'montant_ht': '3000'}],
            }, format='json')
        resp = self.api.get(
            '/api/django/compta/provisions-periode/rapport/'
            '?date_debut=2026-01-01&date_fin=2026-01-31')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        resp2 = self.api.get(
            '/api/django/compta/provisions-periode/export-csv/'
            '?date_debut=2026-01-01&date_fin=2026-01-31')
        self.assertEqual(resp2.status_code, 200)
        self.assertIn('text/csv', resp2['Content-Type'])
