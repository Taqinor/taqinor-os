"""NTCPQ26 — Feuille de comparaison de variantes INTERNE (marge visible),
strictement distincte du PDF client ``/proposal`` (règle #4)."""
from decimal import Decimal

from django.test import TestCase, tag
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.cpq import services
from apps.cpq.models import ProduitEquivalent
from apps.ventes.models import LigneDevis
from authentication.models import CustomUser
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestComparaisonVariantes(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.staff = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.commercial = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_NORMAL)
        self.produit_standard = ProduitFactory(
            company=self.company, nom='Onduleur standard',
            prix_achat=Decimal('600.00'), prix_vente=Decimal('1000.00'))
        self.produit_premium = ProduitFactory(
            company=self.company, nom='Onduleur premium',
            prix_achat=Decimal('900.00'), prix_vente=Decimal('1500.00'))
        ProduitEquivalent.objects.create(
            company=self.company, produit_source=self.produit_standard,
            produit_substitut=self.produit_premium,
            tier=ProduitEquivalent.Tier.PREMIUM)
        self.devis = DevisFactory(company=self.company)
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit_standard,
            designation='Onduleur standard', quantite=1,
            prix_unitaire=Decimal('1000.00'))
        services.generer_variantes_devis(self.devis)

    def test_donnees_portent_une_colonne_par_tier(self):
        data = services.donnees_comparaison_variantes(self.devis)
        tiers = {c['tier'] for c in data['colonnes']}
        self.assertEqual(tiers, set(ProduitEquivalent.Tier.values))

    def test_colonne_premium_disponible_avec_marge(self):
        data = services.donnees_comparaison_variantes(self.devis)
        premium = next(
            c for c in data['colonnes'] if c['tier'] == 'premium')
        self.assertTrue(premium['disponible'])
        self.assertEqual(premium['total_ht'], '1500.00')
        self.assertEqual(premium['marge'], '600.00')

    def test_colonne_sans_variante_marquee_indisponible(self):
        # Aucun ProduitEquivalent pour le tier 'economique' → pas de
        # substitution, mais une variante EST générée (config de base
        # reproduite à l'identique) : la colonne reste disponible.
        data = services.donnees_comparaison_variantes(self.devis)
        eco = next(c for c in data['colonnes'] if c['tier'] == 'economique')
        self.assertTrue(eco['disponible'])
        self.assertEqual(eco['total_ht'], '1000.00')

    def test_html_interne_se_declare_interne_jamais_client(self):
        html = services.rendre_comparaison_variantes_html(self.devis)
        self.assertIn('DOCUMENT INTERNE', html)
        self.assertIn('600.00', html)  # marge visible côté interne

    def test_endpoint_json_reserve_au_staff(self):
        resp = auth(self.commercial).get(
            f'/api/django/cpq/devis/{self.devis.id}/comparaison-variantes/'
            '?format=json')
        self.assertEqual(resp.status_code, 403)
        resp2 = auth(self.staff).get(
            f'/api/django/cpq/devis/{self.devis.id}/comparaison-variantes/'
            '?format=json')
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertIn('colonnes', resp2.data)

    def test_endpoint_isole_les_societes(self):
        autre_company = CompanyFactory()
        autre_staff = UserFactory(
            company=autre_company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        resp = auth(autre_staff).get(
            f'/api/django/cpq/devis/{self.devis.id}/comparaison-variantes/'
            '?format=json')
        self.assertEqual(resp.status_code, 404)

    @tag('pdf')
    def test_rendu_pdf_interne(self):
        pdf = services.generer_comparaison_variantes_pdf(self.devis)
        self.assertTrue(pdf.startswith(b'%PDF'))
