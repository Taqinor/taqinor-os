"""Tests FG137 — Préparation de la déclaration de TVA.

Couvre : agrégation depuis le grand livre (TVA collectée 4455 − déductible 3455)
sur une période, le montant à déclarer et le crédit reportable, le crédit
antérieur, le régime (mensuel/trimestriel) + la méthode (débit/encaissement)
figés sur le snapshot, le borné-à-la-période (les écritures hors période ne
comptent pas), l'isolation multi-société, l'endpoint ``preparer`` (admin-gated)
et l'export CSV. Tout se déduit du grand livre de la compta — aucune dépendance
cross-app.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import DeclarationTVA, Journal

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


def _ecriture(company, code_journal, lignes_par_numero, *, jour):
    """Passe une écriture équilibrée à partir de paires (numero, debit, credit)."""
    journal = services._journal(company, _TYPES[code_journal])
    lignes = []
    for numero, debit, credit in lignes_par_numero:
        lignes.append({
            'compte': services.get_compte(company, numero),
            'debit': Decimal(debit), 'credit': Decimal(credit),
        })
    return services.creer_ecriture(
        company, journal, jour, 'Test FG137', lignes)


def _vente_ttc(company, ht, tva, *, jour):
    """Facture client : débit 3421 TTC / crédit 7121 HT + 4455 TVA."""
    ttc = Decimal(ht) + Decimal(tva)
    _ecriture(company, 'VTE', [
        ('3421', str(ttc), '0'),
        ('7121', '0', str(ht)),
        ('4455', '0', str(tva)),
    ], jour=jour)


def _achat_ttc(company, ht, tva, *, jour):
    """Facture fournisseur : débit 6111 HT + 3455 TVA / crédit 4411 TTC."""
    ttc = Decimal(ht) + Decimal(tva)
    _ecriture(company, 'ACH', [
        ('6111', str(ht), '0'),
        ('3455', str(tva), '0'),
        ('4411', '0', str(ttc)),
    ], jour=jour)


class PreparerDeclarationSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('fg137', 'FG137 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)

    def test_tva_collectee_moins_deductible(self):
        # TVA collectée 1000, TVA déductible 400 → à déclarer 600.
        _vente_ttc(self.co, '5000', '1000', jour=date(2026, 1, 10))
        _achat_ttc(self.co, '2000', '400', jour=date(2026, 1, 15))
        calc = selectors.preparer_declaration_tva(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31))
        self.assertEqual(calc['tva_collectee'], Decimal('1000'))
        self.assertEqual(calc['tva_deductible'], Decimal('400'))
        self.assertEqual(calc['tva_a_declarer'], Decimal('600'))
        self.assertEqual(calc['credit_reportable'], Decimal('0'))

    def test_credit_reportable_quand_deductible_depasse(self):
        # TVA collectée 200 < déductible 500 → à déclarer 0, reportable 300.
        _vente_ttc(self.co, '1000', '200', jour=date(2026, 2, 5))
        _achat_ttc(self.co, '2500', '500', jour=date(2026, 2, 8))
        calc = selectors.preparer_declaration_tva(
            self.co, date_debut=date(2026, 2, 1), date_fin=date(2026, 2, 28))
        self.assertEqual(calc['tva_a_declarer'], Decimal('0'))
        self.assertEqual(calc['credit_reportable'], Decimal('300'))

    def test_credit_anterieur_deduit_du_net(self):
        # Collectée 1000 − déductible 0 − crédit antérieur 250 = 750.
        _vente_ttc(self.co, '5000', '1000', jour=date(2026, 3, 3))
        calc = selectors.preparer_declaration_tva(
            self.co, date_debut=date(2026, 3, 1), date_fin=date(2026, 3, 31),
            credit_anterieur=Decimal('250'))
        self.assertEqual(calc['tva_a_declarer'], Decimal('750'))

    def test_bornee_a_la_periode(self):
        # Une vente en janvier ne compte pas dans la déclaration de février.
        _vente_ttc(self.co, '5000', '1000', jour=date(2026, 1, 20))
        calc = selectors.preparer_declaration_tva(
            self.co, date_debut=date(2026, 2, 1), date_fin=date(2026, 2, 28))
        self.assertEqual(calc['tva_collectee'], Decimal('0'))
        self.assertEqual(calc['tva_a_declarer'], Decimal('0'))

    def test_avoir_reduit_la_collectee(self):
        # Vente TVA 1000 puis avoir TVA 200 (débit 4455) → collectée nette 800.
        _vente_ttc(self.co, '5000', '1000', jour=date(2026, 4, 4))
        _ecriture(self.co, 'OD', [
            ('4455', '200', '0'),
            ('3421', '0', '200'),
        ], jour=date(2026, 4, 10))
        calc = selectors.preparer_declaration_tva(
            self.co, date_debut=date(2026, 4, 1), date_fin=date(2026, 4, 30))
        self.assertEqual(calc['tva_collectee'], Decimal('800'))


class PreparerDeclarationServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('fg137-svc', 'FG137 Svc')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.user = make_user(self.co, 'fg137-svc-user')

    def test_service_fige_snapshot_mensuel_debit(self):
        _vente_ttc(self.co, '5000', '1000', jour=date(2026, 1, 10))
        _achat_ttc(self.co, '2000', '400', jour=date(2026, 1, 15))
        decl = services.preparer_declaration_tva(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31),
            regime='mensuel', methode='debit', user=self.user)
        self.assertEqual(decl.regime, DeclarationTVA.Regime.MENSUEL)
        self.assertEqual(decl.methode, DeclarationTVA.Methode.DEBIT)
        self.assertEqual(decl.statut, DeclarationTVA.Statut.PREPAREE)
        self.assertEqual(decl.tva_collectee, Decimal('1000'))
        self.assertEqual(decl.tva_deductible, Decimal('400'))
        self.assertEqual(decl.tva_a_declarer, Decimal('600'))
        self.assertEqual(decl.created_by, self.user)
        # Référence auto-numérotée (TVA-YYYYMM-NNNN), jamais vide.
        self.assertTrue(decl.reference.startswith('TVA-'))

    def test_service_trimestriel_encaissement(self):
        _vente_ttc(self.co, '9000', '1800', jour=date(2026, 1, 5))
        _vente_ttc(self.co, '3000', '600', jour=date(2026, 3, 20))
        decl = services.preparer_declaration_tva(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 3, 31),
            regime='trimestriel', methode='encaissement', user=self.user)
        self.assertEqual(decl.regime, DeclarationTVA.Regime.TRIMESTRIEL)
        self.assertEqual(decl.methode, DeclarationTVA.Methode.ENCAISSEMENT)
        # TVA collectée du trimestre = 1800 + 600 = 2400.
        self.assertEqual(decl.tva_collectee, Decimal('2400'))
        self.assertEqual(decl.tva_a_declarer, Decimal('2400'))

    def test_references_uniques_consecutives(self):
        d1 = services.preparer_declaration_tva(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31),
            user=self.user)
        d2 = services.preparer_declaration_tva(
            self.co, date_debut=date(2026, 2, 1), date_fin=date(2026, 2, 28),
            user=self.user)
        self.assertNotEqual(d1.reference, d2.reference)


class DeclarationTVAIsolationApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('fg137-a', 'FG137 A')
        self.co_b = make_company('fg137-b', 'FG137 B')
        for co in (self.co_a, self.co_b):
            services.seed_plan_comptable(co)
            services.seed_journaux(co)
        # TVA chez A seulement.
        _vente_ttc(self.co_a, '5000', '1000', jour=date(2026, 1, 10))
        self.user_a = make_user(self.co_a, 'fg137-user-a')
        self.user_b = make_user(self.co_b, 'fg137-user-b')

    def test_isolation_selector(self):
        calc_a = selectors.preparer_declaration_tva(
            self.co_a, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31))
        calc_b = selectors.preparer_declaration_tva(
            self.co_b, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31))
        self.assertEqual(calc_a['tva_collectee'], Decimal('1000'))
        self.assertEqual(calc_b['tva_collectee'], Decimal('0'))

    def test_endpoint_preparer_pose_company_serveur(self):
        api = auth(self.user_a)
        resp = api.post(
            '/api/django/compta/declarations-tva/preparer/',
            {'date_debut': '2026-01-01', 'date_fin': '2026-01-31',
             'regime': 'mensuel', 'methode': 'debit',
             'company': self.co_b.id},  # tentative d'injection ignorée.
            format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Decimal(str(resp.data['tva_a_declarer'])),
                         Decimal('1000'))
        decl = DeclarationTVA.objects.get(id=resp.data['id'])
        # company posée côté serveur : A, jamais B (corps ignoré).
        self.assertEqual(decl.company_id, self.co_a.id)

    def test_endpoint_liste_isolee_par_societe(self):
        services.preparer_declaration_tva(
            self.co_a, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31),
            user=self.user_a)
        resp_b = auth(self.user_b).get('/api/django/compta/declarations-tva/')
        self.assertEqual(resp_b.status_code, 200)
        results = resp_b.data.get('results', resp_b.data)
        self.assertEqual(len(results), 0)

    def test_endpoint_refuse_role_normal(self):
        normal = make_user(self.co_a, 'fg137-normal', role='normal')
        resp = auth(normal).post(
            '/api/django/compta/declarations-tva/preparer/',
            {'date_debut': '2026-01-01', 'date_fin': '2026-01-31'},
            format='json')
        self.assertEqual(resp.status_code, 403)

    def test_export_csv(self):
        decl = services.preparer_declaration_tva(
            self.co_a, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31),
            user=self.user_a)
        resp = auth(self.user_a).get(
            f'/api/django/compta/declarations-tva/{decl.id}/export/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])
        body = resp.content.decode('utf-8')
        self.assertIn('TVA à déclarer', body)
        self.assertIn('TVA collectée', body)
