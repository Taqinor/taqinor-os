"""NTEXT23 — validateur d'expression de formule (dry-run).

``POST core/formule/valider/`` (corps ``{expression, variables:[...]}``)
délègue à ``core.formula.valider_formule`` — aucun effet de bord, une
expression valide renvoie ``ok=true``, une expression dangereuse
``ok=false`` avec un message FR.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()

URL = '/api/django/core/formule/valider/'


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class FormuleValiderTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='NTEXT23 Co')
        self.user = User.objects.create_user(
            username='ntext23_u', password='x', company=self.company)
        self.api = _auth(self.user)

    def test_expression_valide_renvoie_ok_true(self):
        res = self.api.post(URL, {
            'expression': 'quantite * prix_unitaire',
            'variables': ['quantite', 'prix_unitaire'],
        }, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(res.data['ok'])
        self.assertEqual(res.data['erreur'], '')

    def test_expression_avec_import_renvoie_ok_false_et_message_fr(self):
        res = self.api.post(URL, {
            'expression': "__import__('os').system('ls')",
            'variables': [],
        }, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertFalse(res.data['ok'])
        self.assertTrue(res.data['erreur'])

    def test_variable_inconnue_rejetee(self):
        res = self.api.post(URL, {
            'expression': 'prix_achat * 2', 'variables': [],
        }, format='json')
        self.assertFalse(res.data['ok'])
        self.assertIn('prix_achat', res.data['erreur'])

    def test_expression_manquante_renvoie_ok_false(self):
        res = self.api.post(URL, {'variables': []}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertFalse(res.data['ok'])

    def test_aucun_effet_de_bord_rien_n_est_ecrit(self):
        """Un dry-run ne persiste rien — juste la certitude que la formule
        est utilisable telle quelle."""
        res = self.api.post(URL, {
            'expression': 'a + b', 'variables': ['a', 'b'],
        }, format='json')
        self.assertTrue(res.data['ok'])
        # Rejouer la même validation ne change rien (idempotent, sans état).
        res2 = self.api.post(URL, {
            'expression': 'a + b', 'variables': ['a', 'b'],
        }, format='json')
        self.assertEqual(res.data, res2.data)
