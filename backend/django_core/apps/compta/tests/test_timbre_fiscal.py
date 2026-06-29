"""Tests FG144 — Droit de timbre sur encaissements en espèces.

Couvre : le calcul du droit de timbre (base × taux %, avec plancher forfaitaire),
l'EXONÉRATION des règlements non espèces (virement/chèque/carte → aucun timbre),
le taux et le minimum configurables, l'arrondi décimal, le bornage sur la date
d'encaissement et les totaux de la période, l'isolation multi-société, l'endpoint
``create`` (montant posé côté serveur, jamais imposable ; company jamais lue du
corps), l'action ``verser``, le gate de rôle (Admin/Responsable) et l'export CSV
détail (déclenché par ``?export=csv`` — jamais ``?format=``). Tout est additif et
scopé société.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import TimbreFiscal

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


class TimbreFiscalCalculServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('fg144-svc', 'FG144 Svc')
        self.user = make_user(self.co, 'fg144-svc-user')

    def test_montant_au_taux_defaut(self):
        # Base 10 000 × 0,25 % (défaut) = 25,00 (au-dessus du minimum 0,25).
        tf = services.enregistrer_timbre_fiscal(
            self.co, date_encaissement=date(2026, 1, 10),
            base=Decimal('10000'), tiers_nom='Client X', user=self.user)
        self.assertIsNotNone(tf)
        self.assertEqual(tf.taux, Decimal('0.25'))
        self.assertEqual(tf.minimum, Decimal('0.25'))
        self.assertEqual(tf.montant, Decimal('25.00'))
        self.assertEqual(tf.statut, TimbreFiscal.Statut.A_VERSER)
        # Référence auto-numérotée (TIMBRE-YYYYMM-NNNN), jamais vide.
        self.assertTrue(tf.reference.startswith('TIMBRE-'))
        self.assertEqual(tf.created_by, self.user)
        self.assertEqual(tf.mode_reglement, 'especes')

    def test_minimum_forfaitaire_applique_sur_petite_base(self):
        # Base 50 × 0,25 % = 0,125 → arrondi 0,13, mais < minimum 0,25 →
        # on retient le plancher 0,25.
        tf = services.enregistrer_timbre_fiscal(
            self.co, date_encaissement=date(2026, 1, 11),
            base=Decimal('50'), tiers_nom='Petit', user=self.user)
        self.assertEqual(tf.montant, Decimal('0.25'))

    def test_arrondi_proportionnel(self):
        # Base 1 234,56 × 0,25 % = 3,0864 → arrondi 3,09 (> minimum).
        tf = services.enregistrer_timbre_fiscal(
            self.co, date_encaissement=date(2026, 2, 1),
            base=Decimal('1234.56'), tiers_nom='Y', user=self.user)
        self.assertEqual(tf.montant, Decimal('3.09'))

    def test_taux_et_minimum_configurables(self):
        # Taux 1 % et minimum 5 MAD : base 200 × 1 % = 2 < 5 → plancher 5.
        tf = services.enregistrer_timbre_fiscal(
            self.co, date_encaissement=date(2026, 3, 1), base=Decimal('200'),
            taux=Decimal('1'), minimum=Decimal('5'), tiers_nom='Z',
            user=self.user)
        self.assertEqual(tf.taux, Decimal('1.00'))
        self.assertEqual(tf.minimum, Decimal('5.00'))
        self.assertEqual(tf.montant, Decimal('5.00'))

    def test_base_nulle_donne_montant_zero(self):
        tf = services.enregistrer_timbre_fiscal(
            self.co, date_encaissement=date(2026, 3, 2), base=Decimal('0'),
            tiers_nom='Vide', user=self.user)
        self.assertEqual(tf.montant, Decimal('0.00'))

    def test_reglement_non_especes_exonere(self):
        # Virement / chèque / carte : aucun droit de timbre (None, rien créé).
        for mode in ('virement', 'cheque', 'carte', 'prelevement', 'autre'):
            tf = services.enregistrer_timbre_fiscal(
                self.co, date_encaissement=date(2026, 1, 10),
                base=Decimal('10000'), mode_reglement=mode, user=self.user)
            self.assertIsNone(tf, f"mode {mode} doit être exonéré")
        self.assertEqual(TimbreFiscal.objects.count(), 0)

    def test_est_reglement_especes_helper(self):
        self.assertTrue(services.est_reglement_especes('especes'))
        self.assertTrue(services.est_reglement_especes('  ESPECES '))
        self.assertFalse(services.est_reglement_especes('virement'))
        self.assertFalse(services.est_reglement_especes(''))
        self.assertFalse(services.est_reglement_especes(None))

    def test_references_uniques_consecutives(self):
        t1 = services.enregistrer_timbre_fiscal(
            self.co, date_encaissement=date(2026, 1, 5), base=Decimal('1000'),
            user=self.user)
        t2 = services.enregistrer_timbre_fiscal(
            self.co, date_encaissement=date(2026, 1, 6), base=Decimal('1000'),
            user=self.user)
        self.assertNotEqual(t1.reference, t2.reference)

    def test_string_ref_au_paiement(self):
        # Le paiement d'origine est référencé par string-id, jamais d'import.
        tf = services.enregistrer_timbre_fiscal(
            self.co, date_encaissement=date(2026, 1, 7), base=Decimal('3000'),
            paiement_id=4242, facture_ref='FAC-202601-0007',
            tiers_type='client', tiers_id=11, tiers_nom='Client Lié',
            user=self.user)
        self.assertEqual(tf.paiement_id, 4242)
        self.assertEqual(tf.facture_ref, 'FAC-202601-0007')
        self.assertEqual(tf.tiers_id, 11)

    def test_marquer_verse(self):
        tf = services.enregistrer_timbre_fiscal(
            self.co, date_encaissement=date(2026, 1, 5), base=Decimal('1000'),
            user=self.user)
        services.marquer_timbre_verse(tf)
        tf.refresh_from_db()
        self.assertEqual(tf.statut, TimbreFiscal.Statut.VERSEE)


class TimbreFiscalPeriodeTests(TestCase):
    def setUp(self):
        self.co = make_company('fg144-per', 'FG144 Per')
        self.user = make_user(self.co, 'fg144-per-user')

    def _tf(self, jour, base, taux=None, **kw):
        return services.enregistrer_timbre_fiscal(
            self.co, date_encaissement=jour, base=Decimal(base),
            taux=(Decimal(taux) if taux is not None else None),
            user=self.user, **kw)

    def test_liste_periode_totaux(self):
        self._tf(date(2026, 1, 5), '10000', tiers_nom='A')   # 25,00
        self._tf(date(2026, 1, 20), '4000', taux='0.5', tiers_nom='B')  # 20,00
        data = selectors.timbres_fiscaux_periode(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31))
        self.assertEqual(len(data['lignes']), 2)
        self.assertEqual(data['totaux']['montant'], Decimal('45.00'))
        self.assertEqual(data['totaux']['base'], Decimal('14000.00'))
        self.assertEqual(data['totaux']['nb_pieces'], 2)
        self.assertEqual(data['total_a_verser'], Decimal('45.00'))

    def test_bornee_a_la_periode(self):
        # Un encaissement de janvier ne compte pas dans la période de février.
        self._tf(date(2026, 1, 20), '10000', tiers_nom='A')
        data = selectors.timbres_fiscaux_periode(
            self.co, date_debut=date(2026, 2, 1), date_fin=date(2026, 2, 28))
        self.assertEqual(len(data['lignes']), 0)
        self.assertEqual(data['total_a_verser'], Decimal('0'))

    def test_filtre_statut(self):
        t1 = self._tf(date(2026, 1, 5), '10000', tiers_nom='A')  # 25,00
        self._tf(date(2026, 1, 6), '8000', tiers_nom='B')        # 20,00
        services.marquer_timbre_verse(t1)
        data = selectors.timbres_fiscaux_periode(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31),
            statut=TimbreFiscal.Statut.A_VERSER)
        self.assertEqual(len(data['lignes']), 1)
        self.assertEqual(data['total_a_verser'], Decimal('20.00'))


class TimbreFiscalIsolationApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('fg144-a', 'FG144 A')
        self.co_b = make_company('fg144-b', 'FG144 B')
        self.user_a = make_user(self.co_a, 'fg144-user-a')
        self.user_b = make_user(self.co_b, 'fg144-user-b')
        # Un timbre chez A seulement.
        services.enregistrer_timbre_fiscal(
            self.co_a, date_encaissement=date(2026, 1, 10),
            base=Decimal('10000'), tiers_nom='Client A', user=self.user_a)

    def test_isolation_selector(self):
        data_a = selectors.timbres_fiscaux_periode(self.co_a)
        data_b = selectors.timbres_fiscaux_periode(self.co_b)
        self.assertEqual(len(data_a['lignes']), 1)
        self.assertEqual(len(data_b['lignes']), 0)

    def test_endpoint_create_pose_company_et_montant_serveur(self):
        api = auth(self.user_a)
        resp = api.post(
            '/api/django/compta/timbres-fiscaux/',
            {'date_encaissement': '2026-02-01', 'base': '8000',
             'mode_reglement': 'especes', 'tiers_nom': 'Client Z',
             'montant': '999999',          # tentative d'imposer le montant.
             'company': self.co_b.id},     # tentative d'injection ignorée.
            format='json')
        self.assertEqual(resp.status_code, 201)
        # Montant dérivé côté serveur (8000 × 0,25 % = 20,00), jamais 999999.
        self.assertEqual(Decimal(str(resp.data['montant'])), Decimal('20.00'))
        tf = TimbreFiscal.objects.get(id=resp.data['id'])
        self.assertEqual(tf.company_id, self.co_a.id)
        self.assertEqual(tf.montant, Decimal('20.00'))

    def test_endpoint_create_refuse_non_especes(self):
        # Un règlement non espèces est exonéré → 400, aucun timbre créé.
        resp = auth(self.user_a).post(
            '/api/django/compta/timbres-fiscaux/',
            {'date_encaissement': '2026-02-01', 'base': '8000',
             'mode_reglement': 'virement', 'tiers_nom': 'Client V'},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(
            TimbreFiscal.objects.filter(tiers_nom='Client V').exists())

    def test_endpoint_liste_isolee_par_societe(self):
        resp_b = auth(self.user_b).get(
            '/api/django/compta/timbres-fiscaux/')
        self.assertEqual(resp_b.status_code, 200)
        results = resp_b.data.get('results', resp_b.data)
        self.assertEqual(len(results), 0)

    def test_endpoint_verser(self):
        tf = TimbreFiscal.objects.filter(company=self.co_a).first()
        resp = auth(self.user_a).post(
            f'/api/django/compta/timbres-fiscaux/{tf.id}/verser/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'], TimbreFiscal.Statut.VERSEE)

    def test_endpoint_refuse_role_normal(self):
        normal = make_user(self.co_a, 'fg144-normal', role='normal')
        resp = auth(normal).post(
            '/api/django/compta/timbres-fiscaux/',
            {'date_encaissement': '2026-01-01', 'base': '1000'},
            format='json')
        self.assertEqual(resp.status_code, 403)

    def test_export_detail_csv(self):
        resp = auth(self.user_a).get(
            '/api/django/compta/timbres-fiscaux/export/',
            {'date_debut': '2026-01-01', 'date_fin': '2026-01-31',
             'export': 'csv'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])
        body = resp.content.decode('utf-8')
        self.assertIn('Droits de timbre', body)
        self.assertIn('Total à verser', body)
        self.assertIn('Client A', body)
