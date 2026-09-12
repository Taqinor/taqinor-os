"""NTEXT29 — éditeur no-code de conditions (arbre ET/OU/NON) réutilisable.

``GET core/regles/operateurs/`` liste chaque opérateur de feuille sûr
(``core.rules.LEAF_OPERATORS``) avec un libellé FR ; ``POST core/regles/
valider/`` valide/rejette un arbre soumis (dry-run, socle partagé par
XPLT15/NTEXT5/NTEXT21).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.rules import LEAF_OPERATORS

User = get_user_model()

URL_OPERATEURS = '/api/django/core/regles/operateurs/'
URL_VALIDER = '/api/django/core/regles/valider/'


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RegleOperateursTests(TestCase):
    def setUp(self):
        company = Company.objects.create(nom='NTEXT29 Co')
        self.api = _auth(User.objects.create_user(
            username='ntext29_u', password='x', company=company))

    def test_liste_chaque_operateur_avec_libelle_fr(self):
        res = self.api.get(URL_OPERATEURS)
        self.assertEqual(res.status_code, 200, res.data)
        operateurs = {o['operateur'] for o in res.data['operateurs']}
        self.assertEqual(operateurs, set(LEAF_OPERATORS))
        for op in res.data['operateurs']:
            self.assertTrue(op['libelle'])
            self.assertTrue(op['exemple'])
            self.assertTrue(op['symbole'])


class RegleValiderTests(TestCase):
    def setUp(self):
        company = Company.objects.create(nom='NTEXT29 Valider Co')
        self.api = _auth(User.objects.create_user(
            username='ntext29_v', password='x', company=company))

    def test_arbre_valide_accepte(self):
        res = self.api.post(URL_VALIDER, {
            'conditions': {'field': 'montant', 'operator': 'gt',
                           'value': 1000},
        }, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(res.data['ok'])
        self.assertEqual(res.data['erreurs'], [])

    def test_groupe_et_ou_valide(self):
        res = self.api.post(URL_VALIDER, {
            'conditions': {'op': 'and', 'conditions': [
                {'field': 'a', 'operator': 'eq', 'value': 1},
                {'field': 'b', 'operator': 'exists', 'value': True},
            ]},
        }, format='json')
        self.assertTrue(res.data['ok'])

    def test_operateur_inconnu_rejete_avec_erreur(self):
        res = self.api.post(URL_VALIDER, {
            'conditions': {'field': 'a', 'operator': 'bogus', 'value': 1},
        }, format='json')
        self.assertFalse(res.data['ok'])
        self.assertTrue(res.data['erreurs'])

    def test_conditions_manquantes_refuse_400_propre(self):
        res = self.api.post(URL_VALIDER, {}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertFalse(res.data['ok'])
