"""Tests FG142 — Trousse liasse fiscale (états de synthèse, paquet DGI).

Couvre : l'assemblage des quatre sections (bilan + CPC + balance + annexe TVA)
en RÉUTILISANT les sélecteurs standalone (totaux strictement cohérents 1:1), le
bornage à l'exercice (date_debut/date_fin), l'isolation multi-société,
``validees_seulement``, l'endpoint ``liasse-fiscale`` (admin-gated, scopé
société), l'export CSV multi-sections et le garde-fou ``?format=`` → 404. Tout
se déduit du grand livre — aucune écriture n'est créée par la liasse.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import EcritureComptable, ExerciceComptable, Journal

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


def make_exercice(company, annee=2026):
    return ExerciceComptable.objects.create(
        company=company, libelle=f'Exercice {annee}',
        date_debut=date(annee, 1, 1), date_fin=date(annee, 12, 31))


def passer_vente(company, jour, libelle, montant, *, statut=None):
    """Vente : banque (5141) ⇄ ventes (7121) — produit (classe 7)."""
    journal = services._journal(company, Journal.Type.OPERATIONS_DIVERSES)
    lignes = [
        {'compte': services.get_compte(company, '5141'),
         'debit': Decimal(montant), 'credit': Decimal('0')},
        {'compte': services.get_compte(company, '7121'),
         'debit': Decimal('0'), 'credit': Decimal(montant)},
    ]
    return services.creer_ecriture(
        company, journal, jour, libelle, lignes, statut=statut)


def passer_charge(company, jour, libelle, montant, *, statut=None):
    """Charge : achats (6111) ⇄ banque (5141) — charge (classe 6)."""
    journal = services._journal(company, Journal.Type.OPERATIONS_DIVERSES)
    lignes = [
        {'compte': services.get_compte(company, '6111'),
         'debit': Decimal(montant), 'credit': Decimal('0')},
        {'compte': services.get_compte(company, '5141'),
         'debit': Decimal('0'), 'credit': Decimal(montant)},
    ]
    return services.creer_ecriture(
        company, journal, jour, libelle, lignes, statut=statut)


class LiasseFiscaleSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('fg142-co', 'FG142 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.ex = make_exercice(self.co)

    def test_assemble_les_quatre_sections(self):
        passer_vente(self.co, date(2026, 3, 1), 'Vente', '1000')
        data = selectors.liasse_fiscale(self.co, self.ex)
        self.assertEqual(data['sections'], selectors.LIASSE_SECTIONS)
        for section in ('bilan', 'cpc', 'balance', 'annexe_tva'):
            self.assertIn(section, data)
        # Structure de chaque section reconnaissable.
        self.assertIn('actif', data['bilan'])
        self.assertIn('passif', data['bilan'])
        self.assertIn('produits', data['cpc'])
        self.assertIn('charges', data['cpc'])
        self.assertIn('lignes', data['balance'])
        self.assertIn('lignes', data['annexe_tva'])

    def test_meta_exercice_et_dates(self):
        data = selectors.liasse_fiscale(self.co, self.ex)
        self.assertEqual(data['exercice'], 'Exercice 2026')
        self.assertEqual(data['date_debut'], '2026-01-01')
        self.assertEqual(data['date_fin'], '2026-12-31')

    def test_totaux_coherents_avec_selecteurs_standalone(self):
        passer_vente(self.co, date(2026, 3, 1), 'Vente', '5000')
        passer_charge(self.co, date(2026, 4, 1), 'Achat', '1200')
        data = selectors.liasse_fiscale(self.co, self.ex)
        # CPC standalone bornée à l'exercice = section CPC de la liasse.
        cpc_seul = selectors.cpc(
            self.co, date_debut=self.ex.date_debut, date_fin=self.ex.date_fin)
        self.assertEqual(
            data['cpc']['total_produits'], cpc_seul['total_produits'])
        self.assertEqual(
            data['cpc']['total_charges'], cpc_seul['total_charges'])
        self.assertEqual(data['cpc']['resultat'], cpc_seul['resultat'])
        self.assertEqual(data['resultat'], cpc_seul['resultat'])
        # Bilan standalone à la clôture = section bilan de la liasse.
        bilan_seul = selectors.bilan(self.co, date_fin=self.ex.date_fin)
        self.assertEqual(
            data['bilan']['total_actif'], bilan_seul['total_actif'])
        self.assertEqual(
            data['bilan']['total_passif'], bilan_seul['total_passif'])
        # Balance standalone bornée à l'exercice = section balance de la liasse.
        balance_seul = selectors.balance_generale(
            self.co, date_debut=self.ex.date_debut, date_fin=self.ex.date_fin)
        self.assertEqual(
            data['balance']['total_debit'], balance_seul['total_debit'])
        self.assertEqual(
            data['balance']['total_credit'], balance_seul['total_credit'])

    def test_resultat_egale_produits_moins_charges(self):
        passer_vente(self.co, date(2026, 3, 1), 'Vente', '5000')
        passer_charge(self.co, date(2026, 4, 1), 'Achat', '1200')
        data = selectors.liasse_fiscale(self.co, self.ex)
        self.assertEqual(data['resultat'], Decimal('3800'))

    def test_equilibre_vrai_quand_bilan_et_balance_bouclent(self):
        passer_vente(self.co, date(2026, 3, 1), 'Vente', '5000')
        passer_charge(self.co, date(2026, 4, 1), 'Achat', '1200')
        data = selectors.liasse_fiscale(self.co, self.ex)
        self.assertTrue(data['balance']['equilibree'])
        self.assertTrue(data['bilan']['equilibre'])
        self.assertTrue(data['equilibre'])

    def test_bornage_exercice_exclut_hors_periode(self):
        # Dans l'exercice 2026.
        passer_vente(self.co, date(2026, 6, 1), 'Dedans', '1000')
        # Hors exercice : produit de décembre 2025 et janvier 2027.
        passer_vente(self.co, date(2025, 12, 31), 'Avant', '999')
        passer_vente(self.co, date(2027, 1, 1), 'Apres', '888')
        data = selectors.liasse_fiscale(self.co, self.ex)
        # Le CPC ne retient que la vente de l'exercice.
        self.assertEqual(data['cpc']['total_produits'], Decimal('1000'))
        cpc_seul = selectors.cpc(
            self.co, date_debut=self.ex.date_debut, date_fin=self.ex.date_fin)
        self.assertEqual(
            data['cpc']['total_produits'], cpc_seul['total_produits'])

    def test_validees_seulement(self):
        passer_vente(self.co, date(2026, 3, 1), 'Brouillon', '100')
        passer_vente(
            self.co, date(2026, 4, 1), 'Validee', '200',
            statut=EcritureComptable.Statut.VALIDEE)
        data = selectors.liasse_fiscale(self.co, self.ex, validees_seulement=True)
        # Seul le produit validé entre dans la liasse.
        self.assertEqual(data['cpc']['total_produits'], Decimal('200'))

    def test_isolation_par_societe(self):
        autre = make_company('fg142-autre', 'FG142 Autre')
        services.seed_plan_comptable(autre)
        services.seed_journaux(autre)
        ex_autre = make_exercice(autre)
        passer_vente(self.co, date(2026, 3, 1), 'Vente co', '1000')
        passer_vente(autre, date(2026, 3, 1), 'Vente autre', '5000')
        data_co = selectors.liasse_fiscale(self.co, self.ex)
        data_autre = selectors.liasse_fiscale(autre, ex_autre)
        self.assertEqual(data_co['cpc']['total_produits'], Decimal('1000'))
        self.assertEqual(data_autre['cpc']['total_produits'], Decimal('5000'))


class LiasseFiscaleEndpointTests(TestCase):
    def setUp(self):
        self.co_a = make_company('fg142-a', 'FG142 A')
        self.co_b = make_company('fg142-b', 'FG142 B')
        for co in (self.co_a, self.co_b):
            services.seed_plan_comptable(co)
            services.seed_journaux(co)
        self.ex_a = make_exercice(self.co_a)
        self.ex_b = make_exercice(self.co_b)
        passer_vente(self.co_a, date(2026, 3, 1), 'Vente A', '1000')
        passer_charge(self.co_a, date(2026, 4, 1), 'Achat A', '400')
        self.user_a = make_user(self.co_a, 'fg142-user-a')
        self.user_b = make_user(self.co_b, 'fg142-user-b')

    def test_endpoint_json(self):
        resp = auth(self.user_a).get(
            f'/api/django/compta/etats/liasse-fiscale/?exercice={self.ex_a.pk}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['sections'], selectors.LIASSE_SECTIONS)
        self.assertIn('bilan', resp.data)
        self.assertIn('cpc', resp.data)
        self.assertIn('balance', resp.data)
        self.assertIn('annexe_tva', resp.data)
        self.assertEqual(resp.data['resultat'], Decimal('600'))

    def test_endpoint_exercice_requis(self):
        resp = auth(self.user_a).get('/api/django/compta/etats/liasse-fiscale/')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_exercice_introuvable(self):
        resp = auth(self.user_a).get(
            '/api/django/compta/etats/liasse-fiscale/?exercice=999999')
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_isole_b_ne_voit_pas_exercice_a(self):
        resp = auth(self.user_b).get(
            f'/api/django/compta/etats/liasse-fiscale/?exercice={self.ex_a.pk}')
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_export_csv_multi_sections(self):
        resp = auth(self.user_a).get(
            f'/api/django/compta/etats/liasse-fiscale/?exercice={self.ex_a.pk}'
            '&export=csv')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])
        self.assertIn('.csv', resp['Content-Disposition'])
        body = resp.content.decode('utf-8')
        # Les quatre sections figurent dans l'export, dans l'ordre.
        self.assertIn('BILAN', body)
        self.assertIn('CPC', body)
        self.assertIn('BALANCE', body)
        self.assertIn('ANNEXE', body)

    def test_endpoint_format_query_renvoie_404(self):
        # Garde-fou pitfall : ?format= n'est pas notre sélecteur d'export.
        resp = auth(self.user_a).get(
            f'/api/django/compta/etats/liasse-fiscale/?exercice={self.ex_a.pk}'
            '&format=csv')
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_refuse_role_normal(self):
        normal = make_user(self.co_a, 'fg142-normal', role='normal')
        resp = auth(normal).get(
            f'/api/django/compta/etats/liasse-fiscale/?exercice={self.ex_a.pk}')
        self.assertEqual(resp.status_code, 403)
