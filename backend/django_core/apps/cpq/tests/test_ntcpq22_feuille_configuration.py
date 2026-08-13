"""NTCPQ22 — Feuille de configuration technique INTERNE (marge visible),
strictement distincte du PDF client ``/proposal`` (règle #4)."""
from decimal import Decimal

from django.test import TestCase, tag
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.cpq.services import (
    donnees_feuille_configuration, rendre_feuille_configuration_html,
)
from apps.ventes.models import LigneDevis
from authentication.models import CustomUser
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestFeuilleConfiguration(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.staff = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.commercial = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_NORMAL)
        self.produit = ProduitFactory(
            company=self.company, nom='Onduleur X',
            prix_achat=Decimal('600.00'), prix_vente=Decimal('1000.00'))
        self.devis = DevisFactory(company=self.company)
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal('2'),
            prix_unitaire=Decimal('1000.00'))

    def test_donnees_portent_la_marge_par_ligne(self):
        data = donnees_feuille_configuration(self.devis)
        ligne = data['lignes'][0]
        self.assertEqual(ligne['prix_achat'], Decimal('600.00'))
        self.assertEqual(ligne['cout_total'], Decimal('1200.00'))
        self.assertEqual(ligne['marge'], Decimal('800.00'))
        self.assertEqual(ligne['marge_pct'], Decimal('40.00'))
        self.assertEqual(data['totaux']['marge'], Decimal('800.00'))

    def test_html_interne_affiche_la_marge_et_se_declare_interne(self):
        html = rendre_feuille_configuration_html(self.devis)
        self.assertIn("Prix d'achat", html)
        self.assertIn('Marge', html)
        self.assertIn('DOCUMENT INTERNE', html)
        self.assertIn('Feuille de configuration technique', html)

    def test_le_document_nest_jamais_nomme_devis_ni_proposition(self):
        html = rendre_feuille_configuration_html(self.devis).lower()
        self.assertNotIn('proposition', html)
        # « devis » n'apparaît pas comme nom de document (seule la référence
        # peut le contenir) — on vérifie l'absence des libellés interdits.
        self.assertNotIn('votre devis', html)

    def test_proposal_client_ne_montre_jamais_la_marge(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(self.devis)
        blob = str(data)
        self.assertNotIn('prix_achat', blob)
        self.assertNotIn('marge', blob)

    def test_endpoint_json_reserve_au_staff(self):
        url = (f'/api/django/cpq/devis/{self.devis.id}/'
               'feuille-configuration/?format=json')
        resp = auth(self.commercial).get(url)
        self.assertEqual(resp.status_code, 403)
        resp = auth(self.staff).get(url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['lignes'][0]['marge'], Decimal('800.00'))

    def test_endpoint_isole_les_societes(self):
        autre = DevisFactory(company=CompanyFactory())
        resp = auth(self.staff).get(
            f'/api/django/cpq/devis/{autre.id}/feuille-configuration/'
            '?format=json')
        self.assertEqual(resp.status_code, 404)

    @tag('pdf')
    def test_rendu_pdf_interne(self):
        resp = auth(self.staff).get(
            f'/api/django/cpq/devis/{self.devis.id}/feuille-configuration/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))
