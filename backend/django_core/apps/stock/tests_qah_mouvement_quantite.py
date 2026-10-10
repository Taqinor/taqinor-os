"""Régression ERR-QAH-STOCK-MOUVEMENT-QUANTITE-DECIMALE-TRONQUEE.

`MouvementStock.quantite` est un `IntegerField` — le stock se compte en
unités, jamais en fractions (aucune migration dans le périmètre de cette
lane). Le bug observé par le QA-explorer était CÔTÉ FRONTEND
(`MouvementsPage.jsx` tronquait 7.5 en silence à 7 via `parseInt` — corrigé
dans le même lot). Ce fichier VÉRIFIE que le backend, lui, refuse déjà une
quantité fractionnaire au lieu de la tronquer/coercer en silence :
`rest_framework.fields.IntegerField.to_internal_value` ne strip QUE les
`.0*` finaux (``7.0`` → ``7``, une équivalence honnête) — une vraie fraction
(``7.5``) échoue avec un 400 nommant le champ ``quantite``, jamais un
``int()`` tronquant. Filet anti-régression si un futur changement du
sérialiseur venait à introduire une coercion silencieuse.

Run:
    python manage.py test apps.stock.tests_qah_mouvement_quantite -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Produit

User = get_user_model()


def make_company(slug='qah-mv-co', nom='QAH Mv Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom})
    return company


def make_produit(company, nom='Panneau QAH', stock=10):
    return Produit.objects.create(
        company=company, nom=nom,
        prix_achat=Decimal('100'), prix_vente=Decimal('150'),
        quantite_stock=stock)


def auth_client(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


class TestMouvementQuantiteFractionnaireRefusee(TestCase):
    def setUp(self):
        self.company = make_company()
        self.resp = User.objects.create_user(
            username='qah_mv_resp', password='x',
            role_legacy='responsable', company=self.company)
        self.produit = make_produit(self.company)
        self.client = auth_client(self.resp)

    def _post(self, **body):
        return self.client.post(
            '/api/django/stock/mouvements/', body, content_type='application/json')

    def test_quantite_decimale_7_5_est_refusee_400_champ_nomme(self):
        """Reproduction du corps QA-explorer (quantite fractionnaire) :
        jamais tronqué en silence à 7, jamais un 201."""
        r = self._post(
            produit=self.produit.id, type_mouvement='entree', quantite=7.5)
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('quantite', r.data)
        self.produit.refresh_from_db()
        # Le stock n'a PAS bougé (ni vers 17, ni vers 17.5).
        self.assertEqual(self.produit.quantite_stock, 10)

    def test_quantite_decimale_en_chaine_7_5_est_refusee(self):
        r = self._post(
            produit=self.produit.id, type_mouvement='entree',
            quantite='7.5')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('quantite', r.data)

    def test_quantite_entiere_7_est_acceptee(self):
        r = self._post(
            produit=self.produit.id, type_mouvement='entree', quantite=7)
        self.assertEqual(r.status_code, 201, r.data)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 17)
