"""NTDST24 — relevé de consignation imprimable (PDF simple, PAS quote_engine).

Critère d'acceptation testé : le relevé contient EXACTEMENT les lignes de
mouvement du dépôt, TRIÉES PAR DATE, avec le SOLDE RESTANT en pied de page.

Le HTML est testé sans WeasyPrint (fonction pure) ; le rendu PDF réel est
isolé dans une classe étiquetée ``@tag('pdf')``.

Run :
    python manage.py test apps.stock.test_ntdst24_releve_consignation -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, tag
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import DeclarationConsommation, Produit
from apps.stock.services_consignation import (
    creer_depot_consignation, declarer_consommation,
)
from apps.stock.utils.pdf_consignation import render_releve_consignation_html

User = get_user_model()

DEPOT_LE = datetime.date(2026, 3, 1)
CONSO_1 = datetime.date(2026, 3, 10)
CONSO_2 = datetime.date(2026, 4, 5)


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntdst24Base(TestCase):
    def setUp(self):
        from apps.crm.models import Client

        self.company = make_company('ntdst24-co', 'NTDST24 Co')
        self.admin = User.objects.create_user(
            username='ntdst24_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_crm = Client.objects.create(
            company=self.company, nom='Client NTDST24')
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie 5 kWh', sku='BAT-NTDST24',
            prix_achat=Decimal('4000'), prix_vente=Decimal('5500'),
            quantite_stock=100)
        self.depot = creer_depot_consignation(
            company=self.company, user=self.admin,
            client_id=self.client_crm.id, produit_id=self.produit.id,
            quantite=30, date_depot=DEPOT_LE, adresse_site='Site Marrakech')
        # Déclarations volontairement créées dans le DÉSORDRE chronologique.
        declarer_consommation(depot=self.depot, user=self.admin, quantite=4,
                              date_declaration=CONSO_2)
        premiere = declarer_consommation(
            depot=self.depot, user=self.admin, quantite=7,
            date_declaration=CONSO_1)
        premiere.statut = DeclarationConsommation.Statut.FACTUREE
        premiere.document_reference = 'FAC-NTDST24-0001'
        premiere.save(update_fields=['statut', 'document_reference'])
        self.depot.refresh_from_db()


class Ntdst24HtmlTests(Ntdst24Base):
    def test_les_lignes_sont_triees_par_date(self):
        html = render_releve_consignation_html(self.depot)
        position_1 = html.index(CONSO_1.isoformat())
        position_2 = html.index(CONSO_2.isoformat())
        self.assertLess(html.index(DEPOT_LE.isoformat()), position_1)
        self.assertLess(position_1, position_2)

    def test_le_solde_restant_est_en_pied_de_tableau(self):
        html = render_releve_consignation_html(self.depot)
        pied = html[html.index('<tfoot>'):]
        self.assertIn('Solde restant', pied)
        self.assertIn('>19<', pied)  # 30 déposés − 11 consommés

    def test_le_releve_porte_les_quatre_quantites(self):
        html = render_releve_consignation_html(self.depot)
        self.assertIn('déposé 30', html)
        self.assertIn('consommé 11', html)
        self.assertIn('facturé 7', html)

    def test_len_tete_est_la_societe_jamais_une_marque_en_dur(self):
        html = render_releve_consignation_html(self.depot)
        self.assertNotIn('TAQINOR', html.upper())

    def test_le_document_de_facturation_apparait(self):
        html = render_releve_consignation_html(self.depot)
        self.assertIn('FAC-NTDST24-0001', html)


class Ntdst24EndpointTests(Ntdst24Base):
    def test_endpoint_refuse_lanonyme(self):
        res = APIClient().get(
            f'/api/django/stock/consignations/{self.depot.id}/releve-pdf/')
        self.assertEqual(res.status_code, 401)


@tag('pdf')
class Ntdst24PdfTests(Ntdst24Base):
    """Rendu WeasyPrint RÉEL — hors palier rapide (étiquette `pdf`)."""

    def test_le_pdf_est_genere_et_servi_inline(self):
        res = auth(self.admin).get(
            f'/api/django/stock/consignations/{self.depot.id}/releve-pdf/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertTrue(res.content.startswith(b'%PDF'))
