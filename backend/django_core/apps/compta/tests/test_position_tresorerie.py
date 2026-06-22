"""Tests FG122 — Position de trésorerie consolidée + projection nette.

Couvre : solde consolidé par compte/caisse + total (solde initial + grand livre),
projection nette tirée des soldes AR (3421) / AP (4411) / paie (44xx) / TVA, et
l'isolation multi-société (A ne voit jamais la trésorerie de B). Tout se déduit
du grand livre de la compta — aucune dépendance cross-app.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import CompteTresorerie

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


def _ecriture(company, code_journal, lignes_par_numero, *, jour=None):
    """Passe une écriture équilibrée à partir de paires (numero, debit, credit)."""
    journal = services._journal(company, _type_for(code_journal))
    lignes = []
    for numero, debit, credit in lignes_par_numero:
        lignes.append({
            'compte': services.get_compte(company, numero),
            'debit': Decimal(debit), 'credit': Decimal(credit),
        })
    return services.creer_ecriture(
        company, journal, jour or date(2026, 1, 10), 'Test FG122', lignes)


def _type_for(code):
    from apps.compta.models import Journal
    return {
        'VTE': Journal.Type.VENTE, 'ACH': Journal.Type.ACHAT,
        'BNK': Journal.Type.BANQUE, 'CSH': Journal.Type.CAISSE,
        'OD': Journal.Type.OPERATIONS_DIVERSES,
    }[code]


class PositionTresorerieSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('fg122', 'FG122 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        # Une banque (solde initial 1000) et une caisse (solde initial 200).
        self.banque = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE', solde_initial=Decimal('1000'),
            compte_comptable=services.get_compte(self.co, '5141'))
        self.caisse = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.CAISSE,
            libelle='Caisse principale', solde_initial=Decimal('200'),
            compte_comptable=services.get_compte(self.co, '5161'))

    def test_position_consolidee_solde_initial_seul(self):
        pos = selectors.position_tresorerie(self.co)
        self.assertEqual(len(pos['comptes']), 2)
        self.assertEqual(pos['total'], Decimal('1200'))
        soldes = {c['libelle']: c['solde'] for c in pos['comptes']}
        self.assertEqual(soldes['BMCE'], Decimal('1000'))
        self.assertEqual(soldes['Caisse principale'], Decimal('200'))

    def test_position_integre_mouvements_grand_livre(self):
        # Encaissement de 300 en banque (débit 5141 / crédit 3421).
        _ecriture(self.co, 'BNK', [
            ('5141', '300', '0'),
            ('3421', '0', '300'),
        ])
        pos = selectors.position_tresorerie(self.co)
        soldes = {c['libelle']: c['solde'] for c in pos['comptes']}
        self.assertEqual(soldes['BMCE'], Decimal('1300'))  # 1000 + 300
        self.assertEqual(pos['total'], Decimal('1500'))  # 1300 + 200

    def test_compte_inactif_exclu(self):
        self.caisse.actif = False
        self.caisse.save(update_fields=['actif'])
        pos = selectors.position_tresorerie(self.co)
        self.assertEqual(len(pos['comptes']), 1)
        self.assertEqual(pos['total'], Decimal('1000'))

    def test_projection_nette_ar_ap_tva(self):
        # AR : facture client 1200 TTC (débit 3421 / crédit 7121 1000 + 4455 200).
        _ecriture(self.co, 'VTE', [
            ('3421', '1200', '0'),
            ('7121', '0', '1000'),
            ('4455', '0', '200'),
        ])
        # AP : facture fournisseur 600 TTC (débit 6111 500 + 3455 100 / crédit
        # 4411 600).
        _ecriture(self.co, 'ACH', [
            ('6111', '500', '0'),
            ('3455', '100', '0'),
            ('4411', '0', '600'),
        ])
        proj = selectors.projection_tresorerie(self.co)
        self.assertEqual(proj['tresorerie_actuelle'], Decimal('1200'))
        self.assertEqual(proj['creances_clients'], Decimal('1200'))
        self.assertEqual(proj['dettes_fournisseurs'], Decimal('600'))
        # TVA nette = TVA collectée 200 − TVA récupérable 100 = 100.
        self.assertEqual(proj['tva_nette'], Decimal('100'))
        self.assertEqual(proj['dettes_paie'], Decimal('0'))
        # Projection = 1200 + 1200 − 600 − 0 − 100 = 1700.
        self.assertEqual(proj['projection_nette'], Decimal('1700'))

    def test_projection_tva_nette_jamais_negative(self):
        # TVA récupérable seule (achat) sans TVA collectée → TVA nette = 0.
        _ecriture(self.co, 'ACH', [
            ('6111', '500', '0'),
            ('3455', '100', '0'),
            ('4411', '0', '600'),
        ])
        proj = selectors.projection_tresorerie(self.co)
        self.assertEqual(proj['tva_nette'], Decimal('0'))


class PositionTresorerieIsolationTests(TestCase):
    def setUp(self):
        self.co_a = make_company('fg122-a', 'FG122 A')
        self.co_b = make_company('fg122-b', 'FG122 B')
        for co in (self.co_a, self.co_b):
            services.seed_plan_comptable(co)
            services.seed_journaux(co)
        # Banque seulement chez A.
        CompteTresorerie.objects.create(
            company=self.co_a, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='Banque A', solde_initial=Decimal('5000'),
            compte_comptable=services.get_compte(self.co_a, '5141'))
        self.user_a = make_user(self.co_a, 'fg122-user-a')
        self.user_b = make_user(self.co_b, 'fg122-user-b')

    def test_position_isolee_par_societe(self):
        pos_a = selectors.position_tresorerie(self.co_a)
        pos_b = selectors.position_tresorerie(self.co_b)
        self.assertEqual(pos_a['total'], Decimal('5000'))
        self.assertEqual(pos_b['total'], Decimal('0'))
        self.assertEqual(len(pos_b['comptes']), 0)

    def test_endpoint_position_tresorerie(self):
        api = auth(self.user_a)
        resp = api.get('/api/django/compta/etats/position-tresorerie/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('comptes', resp.data)
        self.assertIn('total', resp.data)
        self.assertIn('projection', resp.data)
        self.assertEqual(Decimal(str(resp.data['total'])), Decimal('5000'))
        self.assertIn('projection_nette', resp.data['projection'])
        # B ne voit que SA trésorerie (vide), jamais celle de A.
        resp_b = auth(self.user_b).get(
            '/api/django/compta/etats/position-tresorerie/')
        self.assertEqual(resp_b.status_code, 200)
        self.assertEqual(len(resp_b.data['comptes']), 0)

    def test_endpoint_refuse_role_normal(self):
        normal = make_user(self.co_a, 'fg122-normal', role='normal')
        resp = auth(normal).get(
            '/api/django/compta/etats/position-tresorerie/')
        self.assertEqual(resp.status_code, 403)
