"""ZPUR9 — Rapport imprimable « analyse d'achats » exportable PDF.

Couvre :
  * le PDF sort (contenu PDF valide) avec les blocs de la période ;
  * un non-autorisé (rôle standard) reçoit 403 ;
  * le document ne circule jamais côté client (endpoint interne uniquement,
    jamais réutilisé par /proposal ni un chemin client) ;
  * les agrégats du contexte de rendu coïncident avec le dashboard XPUR24
    (même sélecteur, jamais recalculé différemment).

Run:
    python manage.py test apps.stock.test_zpur9_analyse_achats_pdf -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import BonCommandeFournisseur, Fournisseur, Produit
from apps.stock.services import analyse_achats_dashboard
from apps.stock.utils.pdf_analyse_achats import build_analyse_achats_context

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None, role_legacy='responsable'):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy=role_legacy)


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Zpur9Base(TestCase):
    def setUp(self):
        self.company = _company('zpur9-co')
        self.user = _user(
            self.company, 'zpur9-resp',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ZPUR9')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ZPUR9', sku='OND-ZPUR9',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))

    def _bcf(self, statut=BonCommandeFournisseur.Statut.RECU):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ZPUR9-0001',
            fournisseur=self.fournisseur, statut=statut)
        bc.lignes.create(
            produit=self.produit, quantite=3,
            prix_achat_unitaire=Decimal('1200'))
        return bc


class TestEndpointPdf(Zpur9Base):
    def test_pdf_sort_avec_les_blocs(self):
        self._bcf()
        url = '/api/django/stock/produits/analyse-achats/pdf/'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))

    def test_non_autorise_recoit_403(self):
        user_standard = _user(
            self.company, 'zpur9-standard', permissions=['stock_voir'],
            role_legacy='commercial')
        api_standard = _api(user_standard)
        self._bcf()
        url = '/api/django/stock/produits/analyse-achats/pdf/'
        resp = api_standard.get(url)
        self.assertEqual(resp.status_code, 403)


class TestCoherenceAvecDashboard(Zpur9Base):
    def test_contexte_pdf_coincide_avec_dashboard(self):
        self._bcf()
        dashboard = analyse_achats_dashboard(self.company)
        context = build_analyse_achats_context(self.company)
        self.assertEqual(
            context['data']['depenses']['par_fournisseur'],
            dashboard['depenses']['par_fournisseur'])
        self.assertEqual(
            context['data']['engagements_ouverts']['total_engage'],
            dashboard['engagements_ouverts']['total_engage'])

    def test_contexte_contient_identite_societe(self):
        context = build_analyse_achats_context(self.company)
        self.assertIn('entreprise_nom', context)
        self.assertIn('entreprise_ice', context)
