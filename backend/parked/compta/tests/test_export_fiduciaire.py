"""Tests COMPTA37 — Export fiduciaire (Sage / CEGID).

Couvre : la reprojection des écritures de l'exercice dans le jeu de colonnes
d'échange fiduciaire (RÉUTILISANT ``export_fec``), le sens D/C + montant unique,
le bornage à l'exercice, ``validees_seulement``, l'isolation multi-société, la
synthèse de liasse, l'endpoint ``export-fiduciaire`` (admin-gated, scopé
société), l'export CSV Sage/CEGID et le garde-fou ``?format=`` → 404. Aucun
appel externe : un fichier téléchargeable produit des seuls modèles comptables.
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
    """Vente : banque (5141) ⇄ ventes (7121)."""
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
    """Charge : achats (6111) ⇄ banque (5141)."""
    journal = services._journal(company, Journal.Type.OPERATIONS_DIVERSES)
    lignes = [
        {'compte': services.get_compte(company, '6111'),
         'debit': Decimal(montant), 'credit': Decimal('0')},
        {'compte': services.get_compte(company, '5141'),
         'debit': Decimal('0'), 'credit': Decimal(montant)},
    ]
    return services.creer_ecriture(
        company, journal, jour, libelle, lignes, statut=statut)


class ExportFiduciaireSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('compta37-co', 'COMPTA37 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.ex = make_exercice(self.co)

    def test_colonnes_et_format(self):
        passer_vente(self.co, date(2026, 3, 1), 'Vente', '1000')
        data = selectors.export_fiduciaire(self.co, self.ex)
        self.assertEqual(data['format'], 'sage-cegid')
        self.assertEqual(data['columns'], selectors.FIDUCIAIRE_COLUMNS)
        self.assertEqual(data['exercice'], 'Exercice 2026')
        self.assertEqual(data['date_debut'], '2026-01-01')
        self.assertEqual(data['date_fin'], '2026-12-31')

    def test_une_ligne_par_mouvement_avec_sens_et_montant(self):
        passer_vente(self.co, date(2026, 3, 1), 'Vente', '1000')
        data = selectors.export_fiduciaire(self.co, self.ex)
        # Deux lignes d'écriture → deux enregistrements fiduciaires.
        self.assertEqual(len(data['lignes']), 2)
        self.assertEqual(data['nb_lignes'], 2)
        # Chaque ligne porte toutes les colonnes.
        for ligne in data['lignes']:
            for col in selectors.FIDUCIAIRE_COLUMNS:
                self.assertIn(col, ligne)
        sens = {ligne['Sens'] for ligne in data['lignes']}
        self.assertEqual(sens, {'D', 'C'})
        # Le débit (banque 5141) est côté D, le crédit (ventes 7121) côté C.
        par_compte = {ligne['CompteGeneral']: ligne for ligne in data['lignes']}
        self.assertEqual(par_compte['5141']['Sens'], 'D')
        self.assertEqual(par_compte['5141']['Montant'], '1000,00')
        self.assertEqual(par_compte['7121']['Sens'], 'C')
        self.assertEqual(par_compte['7121']['Montant'], '1000,00')

    def test_totaux_et_equilibre(self):
        passer_vente(self.co, date(2026, 3, 1), 'Vente', '5000')
        passer_charge(self.co, date(2026, 4, 1), 'Achat', '1200')
        data = selectors.export_fiduciaire(self.co, self.ex)
        self.assertEqual(data['total_debit'], Decimal('6200'))
        self.assertEqual(data['total_credit'], Decimal('6200'))
        self.assertTrue(data['equilibre'])

    def test_synthese_liasse(self):
        passer_vente(self.co, date(2026, 3, 1), 'Vente', '5000')
        passer_charge(self.co, date(2026, 4, 1), 'Achat', '1200')
        data = selectors.export_fiduciaire(self.co, self.ex)
        self.assertEqual(data['synthese']['total_produits'], Decimal('5000'))
        self.assertEqual(data['synthese']['total_charges'], Decimal('1200'))
        self.assertEqual(data['synthese']['resultat'], Decimal('3800'))

    def test_bornage_exercice(self):
        passer_vente(self.co, date(2026, 6, 1), 'Dedans', '1000')
        passer_vente(self.co, date(2025, 12, 31), 'Avant', '999')
        passer_vente(self.co, date(2027, 1, 1), 'Apres', '888')
        data = selectors.export_fiduciaire(self.co, self.ex)
        # Seule l'écriture de l'exercice (2 lignes) est exportée.
        self.assertEqual(data['nb_lignes'], 2)
        libelles = {ligne['Libelle'] for ligne in data['lignes']}
        self.assertEqual(libelles, {'Dedans'})

    def test_validees_seulement(self):
        passer_vente(self.co, date(2026, 3, 1), 'Brouillon', '100')
        passer_vente(
            self.co, date(2026, 4, 1), 'Validee', '200',
            statut=EcritureComptable.Statut.VALIDEE)
        data = selectors.export_fiduciaire(self.co, self.ex,
                                           validees_seulement=True)
        self.assertEqual(data['nb_lignes'], 2)
        libelles = {ligne['Libelle'] for ligne in data['lignes']}
        self.assertEqual(libelles, {'Validee'})

    def test_isolation_par_societe(self):
        autre = make_company('compta37-autre', 'COMPTA37 Autre')
        services.seed_plan_comptable(autre)
        services.seed_journaux(autre)
        ex_autre = make_exercice(autre)
        passer_vente(self.co, date(2026, 3, 1), 'Vente co', '1000')
        passer_vente(autre, date(2026, 3, 1), 'Vente autre', '5000')
        data_co = selectors.export_fiduciaire(self.co, self.ex)
        data_autre = selectors.export_fiduciaire(autre, ex_autre)
        self.assertEqual(data_co['nb_lignes'], 2)
        self.assertEqual(
            {lg['Montant'] for lg in data_co['lignes']}, {'1000,00'})
        self.assertEqual(
            {lg['Montant'] for lg in data_autre['lignes']}, {'5000,00'})


class ExportFiduciaireEndpointTests(TestCase):
    def setUp(self):
        self.co_a = make_company('compta37-a', 'COMPTA37 A')
        self.co_b = make_company('compta37-b', 'COMPTA37 B')
        for co in (self.co_a, self.co_b):
            services.seed_plan_comptable(co)
            services.seed_journaux(co)
        self.ex_a = make_exercice(self.co_a)
        self.ex_b = make_exercice(self.co_b)
        passer_vente(self.co_a, date(2026, 3, 1), 'Vente A', '1000')
        passer_charge(self.co_a, date(2026, 4, 1), 'Achat A', '400')
        self.user_a = make_user(self.co_a, 'compta37-user-a')
        self.user_b = make_user(self.co_b, 'compta37-user-b')

    def test_endpoint_json(self):
        resp = auth(self.user_a).get(
            '/api/django/compta/etats/export-fiduciaire/'
            f'?exercice={self.ex_a.pk}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['format'], 'sage-cegid')
        self.assertEqual(resp.data['columns'], selectors.FIDUCIAIRE_COLUMNS)
        self.assertEqual(resp.data['nb_lignes'], 4)
        self.assertEqual(resp.data['synthese']['resultat'], Decimal('600'))

    def test_endpoint_exercice_requis(self):
        resp = auth(self.user_a).get(
            '/api/django/compta/etats/export-fiduciaire/')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_exercice_introuvable(self):
        resp = auth(self.user_a).get(
            '/api/django/compta/etats/export-fiduciaire/?exercice=999999')
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_isole_b_ne_voit_pas_exercice_a(self):
        resp = auth(self.user_b).get(
            '/api/django/compta/etats/export-fiduciaire/'
            f'?exercice={self.ex_a.pk}')
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_export_csv(self):
        resp = auth(self.user_a).get(
            '/api/django/compta/etats/export-fiduciaire/'
            f'?exercice={self.ex_a.pk}&export=csv')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])
        self.assertIn('fiduciaire_sage_cegid', resp['Content-Disposition'])
        body = resp.content.decode('utf-8')
        # Entête de colonnes + synthèse présents.
        self.assertIn('CodeJournal', body)
        self.assertIn('Sens', body)
        self.assertIn('SYNTHESE LIASSE', body)
        self.assertIn('Resultat', body)

    def test_endpoint_format_query_renvoie_404(self):
        resp = auth(self.user_a).get(
            '/api/django/compta/etats/export-fiduciaire/'
            f'?exercice={self.ex_a.pk}&format=csv')
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_refuse_role_normal(self):
        normal = make_user(self.co_a, 'compta37-normal', role='normal')
        resp = auth(normal).get(
            '/api/django/compta/etats/export-fiduciaire/'
            f'?exercice={self.ex_a.pk}')
        self.assertEqual(resp.status_code, 403)
