"""Tests FG141 — Export FEC (Fichier des Écritures Comptables, format DGI).

Couvre : la sélection bornée à l'exercice (date_debut/date_fin), l'ordre
auditable (par date d'écriture puis numéro de pièce puis ordre de saisie), la
forme des colonnes normalisées, l'équilibre Σ débit = Σ crédit, l'isolation
multi-société, le rendu délimité (tabulé FEC + CSV point-virgule),
``validees_seulement``, et l'endpoint ``export-fec`` (admin-gated, scopé
société). Tout se déduit du grand livre — aucune écriture n'est créée par
l'export.
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


def passer_ecriture(company, jour, libelle, montant, *, statut=None,
                    reference=''):
    """Passe une écriture équilibrée banque/ventes (5141 ⇄ 7121)."""
    journal = services._journal(company, Journal.Type.OPERATIONS_DIVERSES)
    lignes = [
        {'compte': services.get_compte(company, '5141'),
         'debit': Decimal(montant), 'credit': Decimal('0')},
        {'compte': services.get_compte(company, '7121'),
         'debit': Decimal('0'), 'credit': Decimal(montant)},
    ]
    return services.creer_ecriture(
        company, journal, jour, libelle, lignes, statut=statut,
        reference=reference)


class ExportFecSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('fg141-co', 'FG141 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.ex = make_exercice(self.co)

    def test_une_ligne_par_ligne_ecriture(self):
        passer_ecriture(self.co, date(2026, 3, 1), 'Vente A', '1000')
        passer_ecriture(self.co, date(2026, 4, 1), 'Vente B', '2000')
        data = selectors.export_fec(self.co, self.ex)
        # 2 écritures × 2 lignes = 4 lignes FEC.
        self.assertEqual(data['nb_lignes'], 4)
        self.assertEqual(len(data['lignes']), 4)

    def test_colonnes_normalisees_dans_l_ordre(self):
        passer_ecriture(self.co, date(2026, 3, 1), 'Vente A', '1000')
        data = selectors.export_fec(self.co, self.ex)
        self.assertEqual(data['columns'], selectors.FEC_COLUMNS)
        self.assertEqual(data['columns'][0], 'JournalCode')
        self.assertEqual(data['columns'][2], 'EcritureNum')
        self.assertEqual(data['columns'][3], 'EcritureDate')
        self.assertEqual(data['columns'][4], 'CompteNum')
        self.assertIn('Debit', data['columns'])
        self.assertIn('Credit', data['columns'])
        # Chaque ligne porte exactement les colonnes du standard.
        for ligne in data['lignes']:
            self.assertEqual(set(ligne.keys()), set(selectors.FEC_COLUMNS))

    def test_ordre_par_date_puis_piece(self):
        # Insérées dans le désordre : avril puis février.
        passer_ecriture(self.co, date(2026, 4, 10), 'Tardive', '500')
        passer_ecriture(self.co, date(2026, 2, 5), 'Précoce', '300')
        data = selectors.export_fec(self.co, self.ex)
        dates = [lig['EcritureDate'] for lig in data['lignes']]
        # Les lignes de février doivent précéder celles d'avril.
        self.assertEqual(dates, sorted(dates))
        self.assertEqual(dates[0], '20260205')
        self.assertEqual(dates[-1], '20260410')

    def test_totaux_equilibres(self):
        passer_ecriture(self.co, date(2026, 3, 1), 'Vente A', '1000')
        passer_ecriture(self.co, date(2026, 6, 1), 'Vente B', '2500')
        data = selectors.export_fec(self.co, self.ex)
        self.assertEqual(data['total_debit'], Decimal('3500'))
        self.assertEqual(data['total_credit'], Decimal('3500'))
        self.assertTrue(data['equilibre'])

    def test_bornage_exercice_exclut_hors_periode(self):
        # Dans l'exercice 2026.
        passer_ecriture(self.co, date(2026, 6, 1), 'Dedans', '1000')
        # Hors exercice : décembre 2025 et janvier 2027.
        passer_ecriture(self.co, date(2025, 12, 31), 'Avant', '999')
        passer_ecriture(self.co, date(2027, 1, 1), 'Après', '888')
        data = selectors.export_fec(self.co, self.ex)
        self.assertEqual(data['nb_lignes'], 2)
        libelles = {lig['EcritureLib'] for lig in data['lignes']}
        self.assertEqual(libelles, {'Dedans'})

    def test_montants_formates_virgule_deux_decimales(self):
        passer_ecriture(self.co, date(2026, 3, 1), 'Vente', '1234.50')
        data = selectors.export_fec(self.co, self.ex)
        debits = [lig['Debit'] for lig in data['lignes'] if lig['Debit'] != '0,00']
        self.assertIn('1234,50', debits)
        # Le côté non mouvementé est '0,00', jamais vide.
        for lig in data['lignes']:
            self.assertIn(',', lig['Debit'])
            self.assertIn(',', lig['Credit'])

    def test_validees_seulement(self):
        passer_ecriture(self.co, date(2026, 3, 1), 'Brouillon', '100')
        passer_ecriture(
            self.co, date(2026, 4, 1), 'Validee', '200',
            statut=EcritureComptable.Statut.VALIDEE)
        data = selectors.export_fec(self.co, self.ex, validees_seulement=True)
        self.assertEqual(data['nb_lignes'], 2)
        libelles = {lig['EcritureLib'] for lig in data['lignes']}
        self.assertEqual(libelles, {'Validee'})

    def test_piece_ref_remplie(self):
        passer_ecriture(
            self.co, date(2026, 3, 1), 'Vente', '100', reference='FAC-001')
        data = selectors.export_fec(self.co, self.ex)
        self.assertTrue(all(lig['PieceRef'] for lig in data['lignes']))
        self.assertIn('FAC-001', {lig['PieceRef'] for lig in data['lignes']})

    def test_isolation_par_societe(self):
        autre = make_company('fg141-autre', 'FG141 Autre')
        services.seed_plan_comptable(autre)
        services.seed_journaux(autre)
        ex_autre = make_exercice(autre)
        passer_ecriture(self.co, date(2026, 3, 1), 'Vente co', '1000')
        passer_ecriture(autre, date(2026, 3, 1), 'Vente autre', '5000')
        data_co = selectors.export_fec(self.co, self.ex)
        data_autre = selectors.export_fec(autre, ex_autre)
        self.assertEqual(data_co['total_debit'], Decimal('1000'))
        self.assertEqual(data_autre['total_debit'], Decimal('5000'))


class ExportFecEndpointTests(TestCase):
    def setUp(self):
        self.co_a = make_company('fg141-a', 'FG141 A')
        self.co_b = make_company('fg141-b', 'FG141 B')
        for co in (self.co_a, self.co_b):
            services.seed_plan_comptable(co)
            services.seed_journaux(co)
        self.ex_a = make_exercice(self.co_a)
        self.ex_b = make_exercice(self.co_b)
        passer_ecriture(self.co_a, date(2026, 3, 1), 'Vente A', '1000')
        self.user_a = make_user(self.co_a, 'fg141-user-a')
        self.user_b = make_user(self.co_b, 'fg141-user-b')

    def test_endpoint_json(self):
        resp = auth(self.user_a).get(
            f'/api/django/compta/etats/export-fec/?exercice={self.ex_a.pk}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['nb_lignes'], 2)
        self.assertEqual(resp.data['columns'], selectors.FEC_COLUMNS)
        self.assertTrue(resp.data['equilibre'])

    def test_endpoint_exercice_requis(self):
        resp = auth(self.user_a).get('/api/django/compta/etats/export-fec/')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_exercice_introuvable(self):
        resp = auth(self.user_a).get(
            '/api/django/compta/etats/export-fec/?exercice=999999')
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_isole_b_ne_voit_pas_exercice_a(self):
        resp = auth(self.user_b).get(
            f'/api/django/compta/etats/export-fec/?exercice={self.ex_a.pk}')
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_export_fec_tabule(self):
        resp = auth(self.user_a).get(
            f'/api/django/compta/etats/export-fec/?exercice={self.ex_a.pk}'
            '&export=fec')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/plain', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])
        self.assertIn('.txt', resp['Content-Disposition'])
        body = resp.content.decode('utf-8')
        # En-tête tabulé + au moins une ligne de données.
        first_line = body.splitlines()[0]
        self.assertEqual(first_line.split('\t'), selectors.FEC_COLUMNS)
        self.assertIn('JournalCode\t', body)

    def test_endpoint_export_csv(self):
        resp = auth(self.user_a).get(
            f'/api/django/compta/etats/export-fec/?exercice={self.ex_a.pk}'
            '&export=csv')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertIn('.csv', resp['Content-Disposition'])
        body = resp.content.decode('utf-8')
        self.assertIn('JournalCode;', body)

    def test_endpoint_format_query_renvoie_404(self):
        # Garde-fou pitfall : ?format= n'est pas notre sélecteur d'export.
        resp = auth(self.user_a).get(
            f'/api/django/compta/etats/export-fec/?exercice={self.ex_a.pk}'
            '&format=fec')
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_refuse_role_normal(self):
        normal = make_user(self.co_a, 'fg141-normal', role='normal')
        resp = auth(normal).get(
            f'/api/django/compta/etats/export-fec/?exercice={self.ex_a.pk}')
        self.assertEqual(resp.status_code, 403)
