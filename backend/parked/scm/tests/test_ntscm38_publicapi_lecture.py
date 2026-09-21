"""NTSCM38 — Exposition API publique des politiques de stock et prévisions
(lecture), scope `read:scm` (apps.publicapi).

Critère d'acceptation : une clé API sans le scope `scm:read` reçoit 403 sur
`GET /api/public/v1/scm/politiques-stock/`, une clé avec le scope reçoit 200.

ADAPTATION DE NOMMAGE : le catalogue de scopes de `apps.publicapi` suit
partout la convention ``read:<objet>`` (jamais ``<objet>:read``, voir
``SCOPE_READ_LEADS='read:leads'`` etc.) — le scope s'appelle donc
``read:scm`` (``SCOPE_READ_SCM``), même contrat, nom aligné sur l'existant."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.publicapi.constants import SCOPE_READ_LEADS, SCOPE_READ_SCM
from apps.publicapi.models import ApiKey
from apps.scm.models import ParametresSCM, PolitiqueStock, PrevisionDemande
from apps.stock.models import Produit

from .helpers import make_company


def _key_client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


class PublicApiScmLectureTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-publicapi', 'Supply API Publique')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550Wc', prix_vente=1800,
            prix_achat=1100, quantite_stock=40)
        PolitiqueStock.objects.create(
            company=self.company, produit=self.produit, classe_abc='A',
            service_level_pct=Decimal('95'), point_commande=Decimal('20'),
            stock_securite_calcule=Decimal('10'))
        PrevisionDemande.objects.create(
            company=self.company, produit=self.produit, segment='',
            periode='2026-03', quantite_prevue=Decimal('25'))

    def test_cle_sans_scope_scm_recoit_403(self):
        _key, raw = ApiKey.issue(
            company=self.company, label='sans scm',
            scopes=[SCOPE_READ_LEADS])
        resp = _key_client(raw).get('/api/public/v1/scm/politiques-stock/')
        self.assertEqual(resp.status_code, 403)

    def test_cle_avec_scope_scm_recoit_200(self):
        _key, raw = ApiKey.issue(
            company=self.company, label='avec scm', scopes=[SCOPE_READ_SCM])
        resp = _key_client(raw).get('/api/public/v1/scm/politiques-stock/')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_politiques_stock_ne_fuite_jamais_prix_achat(self):
        _key, raw = ApiKey.issue(
            company=self.company, label='avec scm', scopes=[SCOPE_READ_SCM])
        resp = _key_client(raw).get('/api/public/v1/scm/politiques-stock/')
        blob = str(resp.content)
        self.assertNotIn('prix_achat', blob)

    def test_previsions_demande_accessible_avec_le_scope(self):
        _key, raw = ApiKey.issue(
            company=self.company, label='avec scm', scopes=[SCOPE_READ_SCM])
        resp = _key_client(raw).get('/api/public/v1/scm/previsions-demande/')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_tableau_bord_reappro_public_sans_prix_achat(self):
        ParametresSCM.objects.get_or_create(company=self.company)
        _key, raw = ApiKey.issue(
            company=self.company, label='avec scm', scopes=[SCOPE_READ_SCM])
        resp = _key_client(raw).get('/api/public/v1/scm/tableau-bord-reappro/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('lignes', resp.data)
        blob = str(resp.content)
        self.assertNotIn('prix_achat', blob)

    def test_isolation_tenant(self):
        autre = make_company('scm-publicapi-autre', 'Autre société')
        _key, raw = ApiKey.issue(
            company=autre, label='autre societe', scopes=[SCOPE_READ_SCM])
        resp = _key_client(raw).get('/api/public/v1/scm/politiques-stock/')
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data.get('results', resp.data) if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(data), 0)
