"""ZSTK5 — Étiquette de colis (contenu + code-barres colis).

Couvre :
  * l'action `colis/{id}/etiquette/` (apps.installations) rend une étiquette
    imprimable HTML encodant le jeton `COLIS:<id>` (planche du moteur N20),
    avec le n° de colis, le chantier et le contenu condensé (désignation +
    qté SEULEMENT) — jamais de prix ;
  * scanner ce jeton (`produits/resolve/`) résout le colis (lu via
    `installations.selectors`, jamais son modèle) ;
  * cross-company : colis d'une autre société → 404 (étiquette ET scan).

Run:
    python manage.py test apps.stock.test_zstk5_etiquette_colis -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Colis, ColisLigne, Installation
from apps.roles.models import Role
from apps.stock import labels
from apps.stock.models import Produit

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Zstk5Base(TestCase):
    def setUp(self):
        self.company = _company('zstk5-co')
        self.user = _user(
            self.company, 'zstk5-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client ZSTK5',
            email='zstk5@example.invalid')
        self.installation = Installation.objects.create(
            company=self.company, reference='CHT-ZSTK5-0001',
            client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ZSTK5', sku='OND-ZSTK5',
            prix_vente=54321, prix_achat=98765)
        self.colis = Colis.objects.create(
            company=self.company, reference='COL-ZSTK5-0001',
            installation=self.installation)
        ColisLigne.objects.create(
            colis=self.colis, produit=self.produit,
            designation='Onduleur ZSTK5', quantite=2)
        ColisLigne.objects.create(
            colis=self.colis, designation='Câble PV 10m', quantite=3)


class TestEtiquetteColis(Zstk5Base):
    def test_etiquette_rend_html_avec_jeton_et_contenu_sans_prix(self):
        url = f'/api/django/installations/colis/{self.colis.id}/etiquette/'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        self.assertIn(labels.colis_token(self.colis.id), html)
        self.assertIn(self.colis.reference, html)
        self.assertIn(self.installation.reference, html)
        self.assertIn('Onduleur ZSTK5', html)
        self.assertIn('Câble PV 10m', html)
        # Jamais de prix affiché sur une étiquette (prix_achat/prix_vente).
        self.assertNotIn('54321', html)
        self.assertNotIn('98765', html)

    def test_etiquette_colis_vide_ne_casse_pas(self):
        colis_vide = Colis.objects.create(
            company=self.company, reference='COL-ZSTK5-VIDE',
            installation=self.installation)
        url = f'/api/django/installations/colis/{colis_vide.id}/etiquette/'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Colis vide', resp.content.decode('utf-8'))

    def test_etiquette_colis_autre_societe_404(self):
        other_co = _company('zstk5-autre')
        other_client = Client.objects.create(
            company=other_co, nom='Autre Client',
            email='zstk5-autre@example.invalid')
        other_installation = Installation.objects.create(
            company=other_co, reference='CHT-ZSTK5-AUTRE',
            client=other_client)
        other_colis = Colis.objects.create(
            company=other_co, reference='COL-ZSTK5-AUTRE',
            installation=other_installation)
        url = f'/api/django/installations/colis/{other_colis.id}/etiquette/'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 404)


class TestResolutionColis(Zstk5Base):
    def test_scan_colis_ouvre_le_colis(self):
        code = labels.colis_token(self.colis.id)
        url = f'/api/django/stock/produits/resolve/?code={code}'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['type'], 'colis')
        self.assertEqual(resp.data['id'], self.colis.id)
        self.assertEqual(resp.data['label'], self.colis.reference)
        self.assertEqual(resp.data['chantier'], self.installation.reference)

    def test_scan_colis_inconnu_404(self):
        code = labels.colis_token(999999)
        url = f'/api/django/stock/produits/resolve/?code={code}'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_scan_colis_cross_company_404(self):
        other_co = _company('zstk5-autre-scan')
        other_client = Client.objects.create(
            company=other_co, nom='Autre Client 2',
            email='zstk5-autre2@example.invalid')
        other_installation = Installation.objects.create(
            company=other_co, reference='CHT-ZSTK5-AUTRE2',
            client=other_client)
        other_colis = Colis.objects.create(
            company=other_co, reference='COL-ZSTK5-AUTRE2',
            installation=other_installation)
        code = labels.colis_token(other_colis.id)
        url = f'/api/django/stock/produits/resolve/?code={code}'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 404)
