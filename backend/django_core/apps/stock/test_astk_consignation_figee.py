"""ASTK30 (C-ASTK-004) — un dépôt de consignation reste accordé à son
mouvement de stock : quantité, produit, client, emplacement et date FIGÉS
après création ; pas de suppression tant que des unités sont en dépôt.

Sonde WMS-4 d'origine : PATCH ``quantite_deposee`` 10 → 50 répondait 200
(50 en base pour UN mouvement de 10) ; DELETE → 204 sans aucun mouvement de
restitution — le dépôt disparaissait, la marchandise aussi.

Aucun mock : service de consignation et vues réels.

Run :
    python manage.py test apps.stock.test_astk_consignation_figee -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import DepotConsignation, MouvementStock, Produit
from apps.stock.services_consignation import (
    creer_depot_consignation, declarer_consommation,
)

User = get_user_model()

URL = '/api/django/stock/consignations/'
JOUR = '2026-10-01'


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth_client(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


class ConsignationFigeeTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client

        self.co = make_company('astk30-co', 'ASTK30 Co')
        self.resp = User.objects.create_user(
            username='astk30_resp', password='x', role_legacy='responsable',
            company=self.co)
        self.admin = User.objects.create_user(
            username='astk30_admin', password='x', role_legacy='admin',
            company=self.co)
        self.client_crm = Client.objects.create(
            company=self.co, nom='Client ASTK30')
        self.autre_client = Client.objects.create(
            company=self.co, nom='Autre client ASTK30')
        self.produit = Produit.objects.create(
            company=self.co, nom='Panneau ASTK30', sku='ASTK30-P',
            prix_achat=Decimal('10'), prix_vente=Decimal('20'),
            quantite_stock=100)
        self.depot = creer_depot_consignation(
            company=self.co, user=self.resp, client_id=self.client_crm.id,
            produit_id=self.produit.id, quantite=10, date_depot=JOUR)

    def _mouvements(self):
        return MouvementStock.objects.filter(
            company=self.co, reference=f'CONSIGNATION-{self.depot.id}')

    def test_patch_quantite_refuse(self):
        r = auth_client(self.resp).patch(
            f'{URL}{self.depot.id}/', {'quantite_deposee': 50},
            format='json')
        self.assertEqual(r.status_code, 400, r.content)
        for corps in ({'client': self.autre_client.id},
                      {'date_depot': '2026-01-01'},
                      {'emplacement_source': None}):
            r = auth_client(self.resp).patch(
                f'{URL}{self.depot.id}/', corps, format='json')
            self.assertEqual(r.status_code, 400, (corps, r.content))
        # Persistance relue : le dépôt reste accordé à son mouvement.
        self.depot.refresh_from_db()
        self.assertEqual(self.depot.quantite_deposee, 10)
        self.assertEqual(self.depot.client_id, self.client_crm.id)
        self.assertEqual(str(self.depot.date_depot), JOUR)
        self.assertEqual(sum(m.quantite for m in self._mouvements()), 10)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 90)

    def test_patch_champ_libre_reste_permis(self):
        r = auth_client(self.resp).patch(
            f'{URL}{self.depot.id}/', {'note': 'Site re-visité'},
            format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.depot.refresh_from_db()
        self.assertEqual(self.depot.note, 'Site re-visité')

    def test_delete_refuse_tant_que_du_stock_est_en_depot(self):
        r = auth_client(self.admin).delete(f'{URL}{self.depot.id}/')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertTrue(
            DepotConsignation.objects.filter(pk=self.depot.pk).exists())
        self.assertEqual(self._mouvements().count(), 1)

    def test_delete_permis_une_fois_tout_consomme(self):
        declarer_consommation(depot=self.depot, user=self.resp, quantite=10,
                              date_declaration=JOUR)
        r = auth_client(self.admin).delete(f'{URL}{self.depot.id}/')
        self.assertEqual(r.status_code, 204, r.content)
