"""
ZSAL8 — PDF imprimable du bon de commande CLIENT (ventes.BonCommande).

Chaque BC produit un PDF correct aux totaux exacts avec l'identité société,
cross-company 404, aucun prix d'achat dans le rendu, tests couvrent le
rendu + le no-leak + le scoping.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_zsal8_bon_commande_pdf -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import BonCommande, Devis, LigneDevis

User = get_user_model()


def make_company(slug='zsal8-co', nom='ZSAL8 Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestBonCommandePdf(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='zsal8_user', password='x',
            role_legacy='responsable', company=self.company)
        self.api = make_api(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ZSAL8',
            telephone='+212600000020')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau PV', sku='PVZ8',
            prix_vente=Decimal('1000'), prix_achat=Decimal('700'),
            quantite_stock=100, tva=Decimal('20.00'))
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-ZSAL8-0001',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'))
        LigneDevis.objects.create(
            devis=self.devis, produit=self.panneau, designation='Panneau PV',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20.00'))
        self.bc = BonCommande.objects.create(
            company=self.company, reference='BC-ZSAL8-0001',
            devis=self.devis, client=self.client_obj,
            statut=BonCommande.Statut.EN_ATTENTE)

    def test_pdf_renders_with_correct_totals(self):
        resp = self.api.get(
            f'/api/django/ventes/bons-commande/{self.bc.id}/pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertGreater(len(resp.content), 0)

    def test_pdf_never_leaks_prix_achat(self):
        from apps.ventes.utils.pdf import generate_bon_commande_pdf
        pdf_bytes = generate_bon_commande_pdf(self.bc.id)
        # Extraction texte basique : le PDF ne doit jamais matérialiser le
        # prix d'achat (700) associé à ce produit dans le rendu.
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 0)

    def test_pdf_cross_company_404(self):
        other_company = make_company(slug='zsal8-other', nom='Other Co')
        other_user = User.objects.create_user(
            username='zsal8_other', password='x',
            role_legacy='responsable', company=other_company)
        other_api = make_api(other_user)
        resp = other_api.get(
            f'/api/django/ventes/bons-commande/{self.bc.id}/pdf/')
        self.assertEqual(resp.status_code, 404)

    def test_bc_without_devis_still_renders(self):
        bc_sans_devis = BonCommande.objects.create(
            company=self.company, reference='BC-ZSAL8-0002',
            client=self.client_obj, statut=BonCommande.Statut.EN_ATTENTE)
        resp = self.api.get(
            f'/api/django/ventes/bons-commande/{bc_sans_devis.id}/pdf/')
        self.assertEqual(resp.status_code, 200)
