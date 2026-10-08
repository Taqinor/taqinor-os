"""ASTK202 (C-ASTK-050) — archiver un emplacement est gardé comme le
supprimer : principal non archivable (400), emplacement détenant du stock
non archivable (409), quel que soit le geste (PATCH ou PUT).

Sonde MVT-12 d'origine : archiver la camionnette (10) faisait remonter le
principal de 90 à 100 ; archiver un DE_TIERS (40) faisait entrer 40 unités
d'un tiers dans notre valorisation.

Aucun mock : vue, serializer et services de ventilation réels.

Run :
    python manage.py test apps.stock.test_astk_archivage_emplacement -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    EmplacementStock, Produit, StockEmplacement,
)
from apps.stock.services import (
    ensure_emplacements, stock_breakdown, stock_valuation_by_location,
)

User = get_user_model()

URL = '/api/django/stock/emplacements/'


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ArchivageTests(TestCase):
    def setUp(self):
        self.co = make_company('astk202-co', 'ASTK202 Co')
        self.admin = User.objects.create_user(
            username='astk202_admin', password='x', role_legacy='admin',
            company=self.co)
        self.api = auth(self.admin)
        ensure_emplacements(self.co)
        self.principal = EmplacementStock.objects.get(
            company=self.co, is_principal=True)
        self.camionnette = EmplacementStock.objects.create(
            company=self.co, nom='Camionnette ASTK202', ordre=50)
        self.de_tiers = EmplacementStock.objects.create(
            company=self.co, nom='Dépôt-vente ASTK202',
            type_proprietaire=EmplacementStock.TypeProprietaire.DE_TIERS,
            tiers_nom='Partenaire SARL', ordre=800)
        self.vide = EmplacementStock.objects.create(
            company=self.co, nom='Vide ASTK202', ordre=60)
        self.produit = Produit.objects.create(
            company=self.co, nom='Onduleur ASTK202', sku='ASTK202-1',
            prix_achat=Decimal('10'), prix_vente=Decimal('20'),
            quantite_stock=140)
        StockEmplacement.objects.create(
            company=self.co, produit=self.produit,
            emplacement=self.camionnette, quantite=10)
        StockEmplacement.objects.create(
            company=self.co, produit=self.produit,
            emplacement=self.de_tiers, quantite=40)

    def _etat(self):
        return (stock_breakdown(self.produit),
                stock_valuation_by_location(self.co)['total'])

    def _archived(self, emp):
        emp.refresh_from_db()
        return emp.archived

    def test_camionnette_non_vide_409(self):
        avant = self._etat()
        rep = self.api.patch(f'{URL}{self.camionnette.id}/',
                             {'archived': True}, format='json')
        self.assertEqual(rep.status_code, 409, rep.content)
        self.assertEqual(
            rep.json()['detail'],
            "Cet emplacement détient du stock — transférez-le avant de "
            "l'archiver.")
        self.assertFalse(self._archived(self.camionnette))
        self.assertEqual(self._etat(), avant)
        # Même garde par PUT.
        rep = self.api.put(f'{URL}{self.camionnette.id}/', {
            'nom': self.camionnette.nom, 'ordre': 50, 'archived': True,
        }, format='json')
        self.assertEqual(rep.status_code, 409, rep.content)
        self.assertFalse(self._archived(self.camionnette))

    def test_principal_400(self):
        rep = self.api.patch(f'{URL}{self.principal.id}/',
                             {'archived': True}, format='json')
        self.assertEqual(rep.status_code, 400, rep.content)
        self.assertEqual(rep.json()['detail'],
                         'Le dépôt principal ne peut pas être archivé.')
        self.assertFalse(self._archived(self.principal))

    def test_de_tiers_non_vide_409(self):
        avant = self._etat()
        rep = self.api.patch(f'{URL}{self.de_tiers.id}/',
                             {'archived': 'true'}, format='json')
        self.assertEqual(rep.status_code, 409, rep.content)
        self.assertFalse(self._archived(self.de_tiers))
        self.assertEqual(self._etat(), avant)

    def test_vide_archive_200(self):
        rep = self.api.patch(f'{URL}{self.vide.id}/',
                             {'archived': True}, format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertTrue(self._archived(self.vide))
        # Un geste sans archivage sur un emplacement non vide passe toujours.
        rep = self.api.patch(f'{URL}{self.camionnette.id}/',
                             {'nom': 'Camionnette renommée'}, format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
