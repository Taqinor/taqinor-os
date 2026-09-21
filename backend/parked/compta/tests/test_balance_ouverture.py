"""XACC2 — Import de la balance d'ouverture (reprise des existants).

Couvre :

* le fichier modèle téléchargeable (colonnes attendues, endpoint ``gabarit``) ;
* un import valide poste UNE écriture AN équilibrée + items ouverts rattachés
  aux comptes tiers (3421/4411) via ``tiers_type``/``tiers_id`` ;
* un fichier invalide (compte inconnu, ligne déséquilibrée, débit+crédit tous
  deux posés) est rejeté SANS rien écrire, avec le détail par ligne ;
* idempotence : rejouer le même exercice ne duplique pas l'écriture.
"""
import io
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import EcritureComptable, ExerciceComptable, LigneEcriture

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


class GabaritTests(TestCase):
    def test_gabarit_contient_les_colonnes_attendues(self):
        data = services.gabarit_import_balance_ouverture()
        text = data.decode('utf-8-sig')
        header = text.splitlines()[0]
        for col in ('compte', 'libelle', 'debit', 'credit', 'tiers_type',
                    'tiers_id'):
            self.assertIn(col, header)


class ImporterBalanceOuvertureServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('bal-ouv', 'Balance Ouverture')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.exercice = ExerciceComptable.objects.create(
            company=self.co, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 12, 31), libelle='Exercice 2026')

    def _rows_valides(self):
        return [
            {'compte': '3421', 'libelle': 'Client A', 'debit': '12000',
             'credit': '', 'tiers_type': 'client', 'tiers_id': '1'},
            {'compte': '1111', 'libelle': 'Capital', 'debit': '',
             'credit': '12000', 'tiers_type': '', 'tiers_id': ''},
        ]

    def test_import_valide_poste_ecriture_equilibree(self):
        res = services.importer_balance_ouverture(
            self.co, self._rows_valides(), exercice=self.exercice)
        self.assertTrue(res['ok'])
        ecr = res['ecriture']
        self.assertIsNotNone(ecr)
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(ecr.total_debit, Decimal('12000'))
        self.assertEqual(ecr.journal.code, 'AN')

    def test_item_ouvert_rattache_au_tiers(self):
        services.importer_balance_ouverture(
            self.co, self._rows_valides(), exercice=self.exercice)
        ligne = LigneEcriture.objects.get(
            company=self.co, compte__numero='3421')
        self.assertEqual(ligne.tiers_type, 'client')
        self.assertEqual(ligne.tiers_id, 1)
        self.assertEqual(ligne.lettrage, '')  # item ouvert, non lettré.

    def test_fichier_invalide_compte_inconnu_rejette_sans_rien_ecrire(self):
        rows = [
            {'compte': '9999', 'libelle': 'Inconnu', 'debit': '100',
             'credit': '', 'tiers_type': '', 'tiers_id': ''},
        ]
        res = services.importer_balance_ouverture(
            self.co, rows, exercice=self.exercice)
        self.assertFalse(res['ok'])
        self.assertIsNone(res['ecriture'])
        self.assertEqual(len(res['erreurs']), 1)
        self.assertEqual(res['erreurs'][0]['ligne'], 1)
        self.assertIn('compte inconnu', res['erreurs'][0]['raison'])
        self.assertEqual(
            EcritureComptable.objects.filter(company=self.co).count(), 0)

    def test_ligne_debit_et_credit_rejetee(self):
        rows = [
            {'compte': '3421', 'debit': '100', 'credit': '100',
             'libelle': '', 'tiers_type': '', 'tiers_id': ''},
        ]
        res = services.importer_balance_ouverture(
            self.co, rows, exercice=self.exercice)
        self.assertFalse(res['ok'])
        self.assertEqual(len(res['erreurs']), 1)

    def test_import_deseiquilibre_rejete_avant_ecriture(self):
        rows = [
            {'compte': '3421', 'debit': '100', 'credit': '', 'libelle': '',
             'tiers_type': '', 'tiers_id': ''},
            {'compte': '1111', 'debit': '', 'credit': '50', 'libelle': '',
             'tiers_type': '', 'tiers_id': ''},
        ]
        with self.assertRaises(Exception):
            services.importer_balance_ouverture(
                self.co, rows, exercice=self.exercice)
        self.assertEqual(
            EcritureComptable.objects.filter(company=self.co).count(), 0)

    def test_idempotent_meme_exercice(self):
        a = services.importer_balance_ouverture(
            self.co, self._rows_valides(), exercice=self.exercice)
        b = services.importer_balance_ouverture(
            self.co, self._rows_valides(), exercice=self.exercice)
        self.assertEqual(a['ecriture'].id, b['ecriture'].id)
        self.assertTrue(b['deja_importee'])
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co, source_type='balance_ouverture').count(), 1)


class BalanceOuvertureAPITests(TestCase):
    def setUp(self):
        self.co = make_company('bal-ouv-api', 'Balance Ouverture API')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.exercice = ExerciceComptable.objects.create(
            company=self.co, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 12, 31), libelle='Exercice 2026')
        self.user = make_user(self.co, 'admin-bal-ouv')
        self.api = auth(self.user)

    def test_telecharger_gabarit(self):
        resp = self.api.get('/api/django/compta/balance-ouverture/gabarit/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])

    def _upload(self, csv_text, exercice_id):
        f = io.BytesIO(csv_text.encode('utf-8'))
        f.name = 'balance.csv'
        return self.api.post(
            '/api/django/compta/balance-ouverture/importer/',
            {'file': f, 'exercice': str(exercice_id)}, format='multipart')

    def test_import_valide_via_api(self):
        csv_text = (
            'compte;libelle;debit;credit;tiers_type;tiers_id\n'
            '3421;Client A;12000;;client;1\n'
            '1111;Capital;;12000;;\n'
        )
        resp = self._upload(csv_text, self.exercice.id)
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(resp.data['ok'])

    def test_import_invalide_via_api_detaille_les_erreurs(self):
        csv_text = (
            'compte;libelle;debit;credit;tiers_type;tiers_id\n'
            '9999;Inconnu;100;;;\n'
        )
        resp = self._upload(csv_text, self.exercice.id)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(len(resp.data['erreurs']), 1)
