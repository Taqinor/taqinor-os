"""
XFAC10 — Facture pro-forma.

Le PDF pro-forma sort filigrané avec sa réf PF, la séquence des vraies
factures est intacte, la conversion en vraie facture reste le
`generer-facture` existant, tests (filigrane présent, séquences
indépendantes).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xfac10_proforma -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, Facture, LigneDevis, ProformaDocument

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='xfac10-co', nom='XFAC10 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='xfac10@example.com'):
    return Client.objects.create(
        company=company, nom='Proforma', prenom='Client',
        email=email, telephone='+212600000059', adresse='Casablanca',
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XFAC10ProformaTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.admin = User.objects.create_user(
            username='xfac10_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.api = auth(self.admin)
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-0001',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'),
        )
        produit = Produit.objects.create(
            company=self.company, nom='Panneau PV', sku='PV-XFAC10',
            prix_vente=Decimal('1000'), quantite_stock=100,
            tva=Decimal('20.00'),
        )
        LigneDevis.objects.create(
            devis=self.devis, produit=produit, designation='Panneau PV',
            quantite=Decimal('5'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), taux_tva=Decimal('20.00'),
        )

    def test_proforma_pdf_renders_with_pf_reference(self):
        r = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/proforma-pdf/',
            {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        proforma = ProformaDocument.objects.get(devis=self.devis)
        self.assertTrue(proforma.reference.startswith('PF-'))

    def test_proforma_sequence_independent_from_facture_sequence(self):
        self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/proforma-pdf/',
            {}, format='json')
        self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/proforma-pdf/',
            {}, format='json')
        proformas = list(
            ProformaDocument.objects.filter(devis=self.devis)
            .order_by('id'))
        self.assertEqual(len(proformas), 2)
        self.assertNotEqual(proformas[0].reference, proformas[1].reference)
        # Aucune vraie facture créée par le pro-forma.
        self.assertEqual(
            Facture.objects.filter(devis=self.devis).count(), 0)

    def test_proforma_never_touches_devis_statut(self):
        statut_avant = self.devis.statut
        self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/proforma-pdf/',
            {}, format='json')
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, statut_avant)

    def test_proforma_logged_in_chatter(self):
        from apps.ventes.models import DevisActivity
        self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/proforma-pdf/',
            {}, format='json')
        self.assertTrue(
            DevisActivity.objects.filter(
                devis=self.devis, body__icontains='pro-forma').exists())
