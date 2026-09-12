"""NTEXT22 — bibliothèque de fonctions de formule (catalogue documenté).

``GET core/formule/fonctions/`` liste chaque fonction/opérateur SÛR de
``core.formula`` avec un libellé FR + un exemple, sans exposer une seule
fonction non whitelistée par ``_SAFE_FUNCS``.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.formula import _SAFE_FUNCS

User = get_user_model()

URL = '/api/django/core/formule/fonctions/'


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class FormuleFonctionsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='NTEXT22 Co')
        self.user = User.objects.create_user(
            username='ntext22_u', password='x', company=self.company)
        self.api = _auth(self.user)

    def test_liste_chaque_fonction_sure_avec_libelle_et_exemple(self):
        res = self.api.get(URL)
        self.assertEqual(res.status_code, 200, res.data)
        noms = {f['nom'] for f in res.data['fonctions']}
        self.assertEqual(noms, set(_SAFE_FUNCS))
        for fonction in res.data['fonctions']:
            self.assertTrue(fonction['libelle'])
            self.assertTrue(fonction['exemple'])
            self.assertTrue(fonction['signature'])

    def test_liste_des_operateurs_avec_libelle_et_exemple(self):
        res = self.api.get(URL)
        symboles = {o['symbole'] for o in res.data['operateurs']}
        for attendu in ('+', '-', '*', '/', '==', '>', 'and', 'or', 'not'):
            self.assertIn(attendu, symboles)
        for operateur in res.data['operateurs']:
            self.assertTrue(operateur['libelle'])
            self.assertTrue(operateur['exemple'])

    def test_n_expose_aucune_fonction_non_whitelistee(self):
        res = self.api.get(URL)
        noms = {f['nom'] for f in res.data['fonctions']}
        for interdit in ('eval', 'exec', '__import__', 'open', 'compile'):
            self.assertNotIn(interdit, noms)
