"""NTEXT37 — ``POST core/formule/tester/`` : banc d'essai d'une expression.

Tester une formule sur les premières lignes RÉELLES d'un dataset enregistré
renvoie les valeurs calculées (ou une erreur française claire), sans jamais
écrire quoi que ce soit.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core import data_explorer

User = get_user_model()

URL = '/api/django/core/formule/tester/'


def _dataset_utilisateurs(company, user):
    return User.objects.filter(company=company)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class FormuleTesterTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='NTEXT37 Co')
        self.autre = Company.objects.create(nom='NTEXT37 Autre')
        self.user = User.objects.create_user(
            username='ntext37_u', password='x', role_legacy='admin',
            company=self.company)
        for i in range(6):
            User.objects.create_user(
                username=f'ntext37_m{i}', password='x', company=self.company)
        User.objects.create_user(
            username='ntext37_hors', password='x', company=self.autre)
        data_explorer.register_dataset(
            'ntext37_utilisateurs', 'Utilisateurs NTEXT37',
            ['id', 'username', 'is_active'], _dataset_utilisateurs)
        self.api = _auth(self.user)

    def test_expression_calculee_sur_cinq_lignes_reelles(self):
        res = self.api.post(URL, {
            'expression': 'id * 2',
            'dataset': 'ntext37_utilisateurs',
            'limite': 5,
        }, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        lignes = res.data['lignes']
        self.assertEqual(len(lignes), 5)
        for ligne in lignes:
            self.assertEqual(ligne['valeur'], ligne['contexte']['id'] * 2)

    def test_limite_par_defaut_et_bornee(self):
        res = self.api.post(URL, {
            'expression': 'id', 'dataset': 'ntext37_utilisateurs',
        }, format='json')
        self.assertEqual(len(res.data['lignes']), 5)

        res = self.api.post(URL, {
            'expression': 'id', 'dataset': 'ntext37_utilisateurs',
            'limite': 500,
        }, format='json')
        self.assertLessEqual(len(res.data['lignes']), 20)

    def test_expression_sur_alias_dagregats(self):
        res = self.api.post(URL, {
            'expression': 'ca / nb_devis',
            'dataset': 'ntext37_utilisateurs',
            'group_by': ['is_active'],
            'agregats': [
                {'alias': 'ca', 'fn': 'count', 'field': 'id'},
                {'alias': 'nb_devis', 'fn': 'count', 'field': 'id'},
            ],
        }, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(res.data['lignes'])
        self.assertEqual(res.data['lignes'][0]['valeur'], 1.0)

    def test_expression_illegale_renvoie_400_francais(self):
        res = self.api.post(URL, {
            'expression': '__import__("os").system("ls")',
            'dataset': 'ntext37_utilisateurs',
        }, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('Expression invalide', res.data['detail'])

    def test_variable_inconnue_renvoie_400_avec_colonnes_disponibles(self):
        res = self.api.post(URL, {
            'expression': 'ca / nb_devis',
            'dataset': 'ntext37_utilisateurs',
        }, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('Colonnes disponibles', res.data['detail'])

    def test_dataset_inconnu_renvoie_404_francais(self):
        res = self.api.post(URL, {
            'expression': 'id', 'dataset': 'nexiste_pas',
        }, format='json')
        self.assertEqual(res.status_code, 404)
        self.assertIn('inconnu', res.data['detail'])

    def test_filtre_hors_liste_blanche_refuse(self):
        res = self.api.post(URL, {
            'expression': 'id', 'dataset': 'ntext37_utilisateurs',
            'filtres': {'password': 'x'},
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_expression_requise(self):
        res = self.api.post(URL, {'dataset': 'ntext37_utilisateurs'},
                            format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('requise', res.data['detail'])

    def test_aucun_effet_de_bord(self):
        avant = User.objects.count()
        self.api.post(URL, {
            'expression': 'id * 2', 'dataset': 'ntext37_utilisateurs',
        }, format='json')
        self.assertEqual(User.objects.count(), avant)

    def test_scope_societe(self):
        res = self.api.post(URL, {
            'expression': 'id', 'dataset': 'ntext37_utilisateurs',
            'limite': 20,
        }, format='json')
        noms = {ligne['contexte']['username'] for ligne in res.data['lignes']}
        self.assertNotIn('ntext37_hors', noms)
