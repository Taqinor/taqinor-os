"""Tests FG139 — Retenue à la source (RAS) sur honoraires/prestations.

Couvre : le calcul du montant retenu par taux (base × taux %, arrondi), le
bornage sur la date de pièce, les totaux du bordereau de versement regroupés par
prestataire (auxiliaire tiers ou prestataire libre), l'isolation multi-société,
l'endpoint ``create`` (montant posé côté serveur, jamais imposable), l'action
``verser``, le gate de rôle (Admin/Responsable) et les exports CSV (détail +
bordereau, déclenchés par ``?export=csv`` — jamais ``?format=``). Tout est
additif et scopé société.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import RetenueSource

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


class RetenueSourceCalculServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('fg139-svc', 'FG139 Svc')
        self.user = make_user(self.co, 'fg139-svc-user')

    def test_montant_calcule_au_taux_defaut(self):
        # Base 10 000 × 10 % (défaut) = 1 000 retenu ; net 9 000.
        ras = services.enregistrer_retenue_source(
            self.co, date_piece=date(2026, 1, 10), base=Decimal('10000'),
            tiers_nom='Cabinet X', user=self.user)
        self.assertEqual(ras.taux, Decimal('10.00'))
        self.assertEqual(ras.montant, Decimal('1000.00'))
        self.assertEqual(ras.net_a_payer, Decimal('9000.00'))
        self.assertEqual(ras.statut, RetenueSource.Statut.A_VERSER)
        # Référence auto-numérotée (RAS-YYYYMM-NNNN), jamais vide.
        self.assertTrue(ras.reference.startswith('RAS-'))
        self.assertEqual(ras.created_by, self.user)

    def test_montant_calcule_taux_explicite_et_arrondi(self):
        # Base 1 234,56 × 7,5 % = 92,592 → arrondi 92,59.
        ras = services.enregistrer_retenue_source(
            self.co, date_piece=date(2026, 2, 1), base=Decimal('1234.56'),
            taux=Decimal('7.5'), tiers_nom='Consultant Y', user=self.user)
        self.assertEqual(ras.taux, Decimal('7.5'))
        self.assertEqual(ras.montant, Decimal('92.59'))

    def test_taux_20_pourcent(self):
        ras = services.enregistrer_retenue_source(
            self.co, date_piece=date(2026, 3, 1), base=Decimal('5000'),
            taux=Decimal('20'), tiers_nom='Loueur Z',
            type_prestation=RetenueSource.TypePrestation.LOYERS,
            user=self.user)
        self.assertEqual(ras.montant, Decimal('1000.00'))
        self.assertEqual(ras.type_prestation,
                         RetenueSource.TypePrestation.LOYERS)

    def test_references_uniques_consecutives(self):
        r1 = services.enregistrer_retenue_source(
            self.co, date_piece=date(2026, 1, 5), base=Decimal('1000'),
            user=self.user)
        r2 = services.enregistrer_retenue_source(
            self.co, date_piece=date(2026, 1, 6), base=Decimal('1000'),
            user=self.user)
        self.assertNotEqual(r1.reference, r2.reference)

    def test_marquer_versee(self):
        ras = services.enregistrer_retenue_source(
            self.co, date_piece=date(2026, 1, 5), base=Decimal('1000'),
            user=self.user)
        services.marquer_ras_versee(ras)
        ras.refresh_from_db()
        self.assertEqual(ras.statut, RetenueSource.Statut.VERSEE)


class RetenueSourcePeriodeBordereauTests(TestCase):
    def setUp(self):
        self.co = make_company('fg139-per', 'FG139 Per')
        self.user = make_user(self.co, 'fg139-per-user')

    def _ras(self, jour, base, taux=None, **kw):
        return services.enregistrer_retenue_source(
            self.co, date_piece=jour, base=Decimal(base),
            taux=(Decimal(taux) if taux is not None else None),
            user=self.user, **kw)

    def test_liste_periode_totaux(self):
        self._ras(date(2026, 1, 5), '10000', tiers_nom='A')
        self._ras(date(2026, 1, 20), '2000', taux='5', tiers_nom='B')
        data = selectors.retenues_source_periode(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31))
        self.assertEqual(len(data['lignes']), 2)
        # 1000 (10% de 10000) + 100 (5% de 2000) = 1100 retenu.
        self.assertEqual(data['totaux']['montant'], Decimal('1100.00'))
        self.assertEqual(data['totaux']['base'], Decimal('12000.00'))
        self.assertEqual(data['totaux']['net'], Decimal('10900.00'))

    def test_bornee_a_la_periode(self):
        # Une pièce de janvier ne compte pas dans le bordereau de février.
        self._ras(date(2026, 1, 20), '10000', tiers_nom='A')
        data = selectors.retenues_source_periode(
            self.co, date_debut=date(2026, 2, 1), date_fin=date(2026, 2, 28))
        self.assertEqual(len(data['lignes']), 0)
        self.assertEqual(data['totaux']['montant'], Decimal('0'))

    def test_bordereau_regroupe_par_prestataire(self):
        # Deux pièces pour le même tiers (auxiliaire) → une ligne cumulée.
        self._ras(date(2026, 1, 5), '10000', tiers_type='fournisseur',
                  tiers_id=42, tiers_nom='Cabinet X', identifiant_fiscal='IF42')
        self._ras(date(2026, 1, 15), '5000', tiers_type='fournisseur',
                  tiers_id=42, tiers_nom='Cabinet X')
        # Un autre prestataire (libre, sans tiers_id).
        self._ras(date(2026, 1, 18), '2000', tiers_nom='Consultant Y',
                  identifiant_fiscal='IFY')
        bord = selectors.bordereau_versement_ras(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31))
        self.assertEqual(len(bord['lignes']), 2)
        # Trié par montant décroissant : Cabinet X en tête.
        tete = bord['lignes'][0]
        self.assertEqual(tete['tiers_id'], 42)
        self.assertEqual(tete['nb_pieces'], 2)
        # 1000 + 500 = 1500 retenu pour Cabinet X.
        self.assertEqual(tete['montant'], Decimal('1500.00'))
        self.assertEqual(tete['base'], Decimal('15000.00'))
        self.assertEqual(tete['identifiant_fiscal'], 'IF42')
        # Total à verser = 1500 + 200 = 1700.
        self.assertEqual(bord['total_a_verser'], Decimal('1700.00'))
        self.assertEqual(bord['totaux']['nb_pieces'], 3)

    def test_bordereau_filtre_statut(self):
        ras1 = self._ras(date(2026, 1, 5), '10000', tiers_nom='A')
        self._ras(date(2026, 1, 6), '2000', tiers_nom='B')
        services.marquer_ras_versee(ras1)
        bord = selectors.bordereau_versement_ras(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31),
            statut=RetenueSource.Statut.A_VERSER)
        # Seule la RAS non versée (B, 200 retenu) reste.
        self.assertEqual(bord['total_a_verser'], Decimal('200.00'))


class RetenueSourceIsolationApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('fg139-a', 'FG139 A')
        self.co_b = make_company('fg139-b', 'FG139 B')
        self.user_a = make_user(self.co_a, 'fg139-user-a')
        self.user_b = make_user(self.co_b, 'fg139-user-b')
        # Une RAS chez A seulement.
        services.enregistrer_retenue_source(
            self.co_a, date_piece=date(2026, 1, 10), base=Decimal('10000'),
            tiers_nom='Cabinet A', user=self.user_a)

    def test_isolation_selector(self):
        data_a = selectors.retenues_source_periode(self.co_a)
        data_b = selectors.retenues_source_periode(self.co_b)
        self.assertEqual(len(data_a['lignes']), 1)
        self.assertEqual(len(data_b['lignes']), 0)

    def test_endpoint_create_pose_company_et_montant_serveur(self):
        api = auth(self.user_a)
        resp = api.post(
            '/api/django/compta/retenues-source/',
            {'date_piece': '2026-02-01', 'base': '8000', 'taux': '10',
             'tiers_nom': 'Cabinet Z',
             'montant': '999999',          # tentative d'imposer le montant.
             'company': self.co_b.id},     # tentative d'injection ignorée.
            format='json')
        self.assertEqual(resp.status_code, 201)
        # Montant dérivé côté serveur (8000 × 10 % = 800), jamais 999999.
        self.assertEqual(Decimal(str(resp.data['montant'])), Decimal('800.00'))
        ras = RetenueSource.objects.get(id=resp.data['id'])
        self.assertEqual(ras.company_id, self.co_a.id)
        self.assertEqual(ras.montant, Decimal('800.00'))

    def test_endpoint_liste_isolee_par_societe(self):
        resp_b = auth(self.user_b).get(
            '/api/django/compta/retenues-source/')
        self.assertEqual(resp_b.status_code, 200)
        results = resp_b.data.get('results', resp_b.data)
        self.assertEqual(len(results), 0)

    def test_endpoint_verser(self):
        ras = RetenueSource.objects.filter(company=self.co_a).first()
        resp = auth(self.user_a).post(
            f'/api/django/compta/retenues-source/{ras.id}/verser/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'], RetenueSource.Statut.VERSEE)

    def test_endpoint_refuse_role_normal(self):
        normal = make_user(self.co_a, 'fg139-normal', role='normal')
        resp = auth(normal).post(
            '/api/django/compta/retenues-source/',
            {'date_piece': '2026-01-01', 'base': '1000'},
            format='json')
        self.assertEqual(resp.status_code, 403)

    def test_bordereau_export_csv(self):
        resp = auth(self.user_a).get(
            '/api/django/compta/retenues-source/bordereau/',
            {'date_debut': '2026-01-01', 'date_fin': '2026-01-31',
             'export': 'csv'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])
        body = resp.content.decode('utf-8')
        self.assertIn('Bordereau de versement', body)
        self.assertIn('Total à verser', body)
        self.assertIn('Cabinet A', body)

    def test_export_detail_csv(self):
        resp = auth(self.user_a).get(
            '/api/django/compta/retenues-source/export/',
            {'date_debut': '2026-01-01', 'date_fin': '2026-01-31'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        body = resp.content.decode('utf-8')
        self.assertIn('Montant retenu', body)
        self.assertIn('Cabinet A', body)
