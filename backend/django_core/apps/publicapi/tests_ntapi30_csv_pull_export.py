"""NTAPI30 — Export live vers Google Sheets `GET /api/public/exports/<entite>.csv?token=<clé>`.

Couvre : un pull CSV synchrone renvoie les données à jour de la société de la
clé, scopé READ-ONLY par entité (mêmes scopes que NTAPI14), jamais de
prix d'achat, un token invalide/désactivé/expiré → 401, aucun moyen d'écrire
avec ce jeton (query string uniquement, jamais l'en-tête Authorization).
"""
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Lead

from .constants import SCOPE_READ_LEADS, SCOPE_READ_STOCK, SCOPE_WRITE_LEADS
from .models import ApiKey


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def _key(company, scopes):
    return ApiKey.issue(company=company, label='k', scopes=scopes)


class Ntapi30CsvPullExportTests(TestCase):
    def setUp(self):
        self.co = _company('ntapi30', 'NTAPI30')
        self.other_co = _company('ntapi30-other', 'Autre société')
        self.api_key, self.raw = _key(self.co, [SCOPE_READ_LEADS])

    def test_pull_returns_csv_of_own_company(self):
        Lead.objects.create(company=self.co, nom='Lead A')
        Lead.objects.create(company=self.co, nom='Lead B')
        Lead.objects.create(company=self.other_co, nom='Lead fuite')

        resp = APIClient().get(f'/api/public/exports/leads.csv?token={self.raw}')

        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        text = resp.content.decode('utf-8')
        self.assertIn('Lead A', text)
        self.assertIn('Lead B', text)
        self.assertNotIn('Lead fuite', text)

    def test_empty_result_still_returns_valid_csv_header(self):
        resp = APIClient().get(f'/api/public/exports/leads.csv?token={self.raw}')
        self.assertEqual(resp.status_code, 200)
        text = resp.content.decode('utf-8')
        self.assertIn('nom', text)  # en-têtes présents même sans ligne

    def test_missing_token_is_401(self):
        resp = APIClient().get('/api/public/exports/leads.csv')
        self.assertEqual(resp.status_code, 401)

    def test_invalid_token_is_401(self):
        resp = APIClient().get('/api/public/exports/leads.csv?token=bogus')
        self.assertEqual(resp.status_code, 401)

    def test_disabled_key_is_401(self):
        self.api_key.enabled = False
        self.api_key.save(update_fields=['enabled'])
        resp = APIClient().get(f'/api/public/exports/leads.csv?token={self.raw}')
        self.assertEqual(resp.status_code, 401)

    def test_wrong_scope_is_403(self):
        # Une clé `read:leads` ne peut PAS lire les produits (scope
        # read:stock requis).
        resp = APIClient().get(f'/api/public/exports/produits.csv?token={self.raw}')
        self.assertEqual(resp.status_code, 403)

    def test_write_only_key_cannot_pull(self):
        # Une clé purement écriture n'a aucun scope read:* -> 403 partout.
        _write_key, write_raw = _key(self.co, [SCOPE_WRITE_LEADS])
        resp = APIClient().get(f'/api/public/exports/leads.csv?token={write_raw}')
        self.assertEqual(resp.status_code, 403)

    def test_unknown_entity_is_400(self):
        resp = APIClient().get(f'/api/public/exports/inconnue.csv?token={self.raw}')
        self.assertEqual(resp.status_code, 400)

    def test_produits_key_can_pull_produits_never_purchase_price(self):
        from apps.stock.models import Produit
        from decimal import Decimal
        Produit.objects.create(
            company=self.co, nom='Panneau', sku='NTAPI30-1',
            prix_vente=Decimal('1000'), prix_achat=Decimal('700'),
            quantite_stock=5)
        _key2, raw2 = _key(self.co, [SCOPE_READ_STOCK])

        resp = APIClient().get(f'/api/public/exports/produits.csv?token={raw2}')

        self.assertEqual(resp.status_code, 200)
        text = resp.content.decode('utf-8')
        self.assertIn('Panneau', text)
        self.assertNotIn('700', text)  # jamais le prix d'achat

    def test_authorization_header_alone_is_not_accepted(self):
        # NTAPI30 est un jeton EN QUERY STRING — l'en-tête Api-Key habituel
        # ne doit PAS suffire ici (surface volontairement distincte).
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Api-Key {self.raw}')
        resp = api.get('/api/public/exports/leads.csv')
        self.assertEqual(resp.status_code, 401)
