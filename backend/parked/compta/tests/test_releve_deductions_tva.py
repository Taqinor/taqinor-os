"""Tests FG138 — Relevé de déductions détaillé (annexe TVA, DGI).

Couvre : l'agrégation ligne par ligne depuis le grand livre (une ligne d'annexe
par pièce portant de la TVA récupérable 3455…), la base HT / TVA / taux déduits
de chaque écriture, le tiers fournisseur résolu depuis la ligne 4411, le
borné-à-la-période (les écritures hors période ne comptent pas), la
réconciliation du total TVA avec la déclaration FG137, l'isolation
multi-société, l'endpoint ``releve-deductions-tva`` (admin-gated) et l'export
CSV. Tout se déduit du grand livre — aucune dépendance cross-app obligatoire.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import Journal

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


_TYPES = {
    'VTE': Journal.Type.VENTE, 'ACH': Journal.Type.ACHAT,
    'OD': Journal.Type.OPERATIONS_DIVERSES,
}


def _achat_ttc(company, ht, tva, *, jour, reference='', tiers_id=None):
    """Facture fournisseur : débit 6111 HT + 3455 TVA / crédit 4411 TTC.

    Le tiers fournisseur (auxiliaire) est porté par la ligne 4411 pour que
    l'annexe puisse le résoudre.
    """
    journal = services._journal(company, _TYPES['ACH'])
    ttc = Decimal(ht) + Decimal(tva)
    lignes = [
        {'compte': services.get_compte(company, '6111'),
         'debit': Decimal(ht), 'credit': Decimal('0')},
        {'compte': services.get_compte(company, '3455'),
         'debit': Decimal(tva), 'credit': Decimal('0')},
        {'compte': services.get_compte(company, '4411'),
         'debit': Decimal('0'), 'credit': ttc,
         'tiers_type': 'fournisseur', 'tiers_id': tiers_id},
    ]
    return services.creer_ecriture(
        company, journal, jour, 'Achat FG138', lignes, reference=reference)


def _vente_ttc(company, ht, tva, *, jour):
    """Facture client : débit 3421 TTC / crédit 7121 HT + 4455 TVA (collectée)."""
    journal = services._journal(company, _TYPES['VTE'])
    ttc = Decimal(ht) + Decimal(tva)
    lignes = [
        {'compte': services.get_compte(company, '3421'),
         'debit': ttc, 'credit': Decimal('0')},
        {'compte': services.get_compte(company, '7121'),
         'debit': Decimal('0'), 'credit': Decimal(ht)},
        {'compte': services.get_compte(company, '4455'),
         'debit': Decimal('0'), 'credit': Decimal(tva)},
    ]
    return services.creer_ecriture(
        company, journal, jour, 'Vente FG138', lignes)


class ReleveDeductionsSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('fg138', 'FG138 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)

    def test_une_ligne_par_piece_deductible(self):
        _achat_ttc(self.co, '2000', '400', jour=date(2026, 1, 10),
                   reference='FA-001')
        _achat_ttc(self.co, '1000', '200', jour=date(2026, 1, 20),
                   reference='FA-002')
        # Une vente ne DOIT PAS apparaître dans le relevé de déductions.
        _vente_ttc(self.co, '5000', '1000', jour=date(2026, 1, 15))
        releve = selectors.releve_deductions_tva(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31))
        self.assertEqual(len(releve['lignes']), 2)
        refs = {lig['reference'] for lig in releve['lignes']}
        self.assertEqual(refs, {'FA-001', 'FA-002'})

    def test_base_tva_taux_par_ligne(self):
        _achat_ttc(self.co, '2000', '400', jour=date(2026, 1, 10),
                   reference='FA-001')
        releve = selectors.releve_deductions_tva(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31))
        ligne = releve['lignes'][0]
        self.assertEqual(ligne['base_ht'], Decimal('2000'))
        self.assertEqual(ligne['tva'], Decimal('400'))
        self.assertEqual(ligne['taux'], Decimal('20.00'))
        self.assertEqual(ligne['journal'], 'ACH')

    def test_taux_none_sans_base(self):
        # Régularisation OD : TVA déductible seule, sans base HT.
        journal = services._journal(self.co, _TYPES['OD'])
        services.creer_ecriture(
            self.co, journal, date(2026, 1, 5), 'Régul TVA',
            [{'compte': services.get_compte(self.co, '3455'),
              'debit': Decimal('120'), 'credit': Decimal('0')},
             {'compte': services.get_compte(self.co, '4411'),
              'debit': Decimal('0'), 'credit': Decimal('120')}])
        releve = selectors.releve_deductions_tva(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31))
        self.assertEqual(len(releve['lignes']), 1)
        self.assertEqual(releve['lignes'][0]['tva'], Decimal('120'))
        self.assertIsNone(releve['lignes'][0]['taux'])

    def test_totaux_reconcilient_avec_declaration(self):
        _achat_ttc(self.co, '2000', '400', jour=date(2026, 1, 10))
        _achat_ttc(self.co, '1000', '200', jour=date(2026, 1, 20))
        releve = selectors.releve_deductions_tva(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31))
        decl = selectors.preparer_declaration_tva(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31))
        self.assertEqual(releve['totaux']['tva'], Decimal('600'))
        self.assertEqual(releve['totaux']['base_ht'], Decimal('3000'))
        # Le total de l'annexe = la TVA déductible de la déclaration (FG137).
        self.assertEqual(releve['totaux']['tva'], decl['tva_deductible'])

    def test_bornee_a_la_periode(self):
        _achat_ttc(self.co, '2000', '400', jour=date(2026, 1, 10))
        releve = selectors.releve_deductions_tva(
            self.co, date_debut=date(2026, 2, 1), date_fin=date(2026, 2, 28))
        self.assertEqual(releve['lignes'], [])
        self.assertEqual(releve['totaux']['tva'], Decimal('0'))
        self.assertEqual(releve['totaux']['base_ht'], Decimal('0'))

    def test_reference_fallback_sur_journal_id(self):
        # Sans référence saisie, la pièce est désignée par journal-id.
        _achat_ttc(self.co, '2000', '400', jour=date(2026, 1, 10))
        releve = selectors.releve_deductions_tva(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31))
        ref = releve['lignes'][0]['reference']
        self.assertTrue(ref.startswith('ACH-'))


class ReleveDeductionsApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('fg138-a', 'FG138 A')
        self.co_b = make_company('fg138-b', 'FG138 B')
        for co in (self.co_a, self.co_b):
            services.seed_plan_comptable(co)
            services.seed_journaux(co)
        _achat_ttc(self.co_a, '2000', '400', jour=date(2026, 1, 10),
                   reference='FA-A1')
        self.user_a = make_user(self.co_a, 'fg138-user-a')
        self.user_b = make_user(self.co_b, 'fg138-user-b')

    def test_isolation_par_societe(self):
        releve_a = selectors.releve_deductions_tva(
            self.co_a, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31))
        releve_b = selectors.releve_deductions_tva(
            self.co_b, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31))
        self.assertEqual(len(releve_a['lignes']), 1)
        self.assertEqual(releve_b['lignes'], [])

    def test_endpoint_json(self):
        api = auth(self.user_a)
        resp = api.get(
            '/api/django/compta/etats/releve-deductions-tva/'
            '?date_debut=2026-01-01&date_fin=2026-01-31')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['lignes']), 1)
        self.assertEqual(Decimal(str(resp.data['totaux']['tva'])),
                         Decimal('400'))

    def test_endpoint_isole_b_ne_voit_pas_a(self):
        resp = auth(self.user_b).get(
            '/api/django/compta/etats/releve-deductions-tva/'
            '?date_debut=2026-01-01&date_fin=2026-01-31')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['lignes'], [])

    def test_export_csv(self):
        resp = auth(self.user_a).get(
            '/api/django/compta/etats/releve-deductions-tva/'
            '?date_debut=2026-01-01&date_fin=2026-01-31&export=csv')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])
        body = resp.content.decode('utf-8')
        self.assertIn('Relevé de déductions de TVA', body)
        self.assertIn('FA-A1', body)
        self.assertIn('Totaux', body)

    def test_endpoint_refuse_role_normal(self):
        normal = make_user(self.co_a, 'fg138-normal', role='normal')
        resp = auth(normal).get(
            '/api/django/compta/etats/releve-deductions-tva/'
            '?date_debut=2026-01-01&date_fin=2026-01-31')
        self.assertEqual(resp.status_code, 403)
