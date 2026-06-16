"""Tests N11 — conformité Article 145 CGI sur la facture.

`Facture.mentions_manquantes` AVERTIT mais ne bloque jamais l'émission.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='conf-co', nom='Conf Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='conf@example.com', **extra):
    return Client.objects.create(
        company=company, nom='Conf', prenom='Client',
        email=email, telephone='+212600000010', adresse='Casablanca', **extra)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestFactureConformite(TestCase):
    def setUp(self):
        self.company = make_company(slug='conf-fac-co', nom='Conf Fac Co')
        self.user = User.objects.create_user(
            username='conf_fac_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)

    def _make_facture(self, client_obj, **kw):
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-7001',
            client=client_obj, statut=Facture.Statut.BROUILLON,
            taux_tva=Decimal('20.00'), **kw)
        prod = Produit.objects.create(
            company=self.company, nom='Panneau', sku='PVF-1',
            prix_vente=Decimal('1000'), quantite_stock=50, tva=Decimal('10.00'))
        LigneFacture.objects.create(
            facture=facture, produit=prod, designation='Panneau PV',
            quantite=Decimal('5'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), taux_tva=Decimal('10.00'))
        return facture

    def test_b2b_facture_missing_client_ice_warns_but_does_not_block(self):
        client_pro = make_client(
            self.company, email='pro@example.com', type_client='entreprise')
        facture = self._make_facture(client_pro)
        self.assertIn(
            'ICE du client (client professionnel)',
            facture.mentions_manquantes)
        # Une mention manquante NE bloque PAS l'émission (override autorisé).
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/emettre/')
        self.assertEqual(r.status_code, 200, r.data)

    def test_b2c_facture_does_not_require_client_ice(self):
        client_part = make_client(
            self.company, email='part@example.com', type_client='particulier')
        facture = self._make_facture(client_part)
        self.assertNotIn(
            'ICE du client (client professionnel)',
            facture.mentions_manquantes)

    def test_missing_delivery_date_and_payment_terms_warn(self):
        client_obj = make_client(self.company, email='c@example.com')
        facture = self._make_facture(client_obj)
        manquantes = facture.mentions_manquantes
        self.assertIn('Date de livraison / prestation', manquantes)
        self.assertIn('Conditions et mode de paiement', manquantes)

    def test_conformity_exposed_on_serializer(self):
        client_obj = make_client(self.company, email='c2@example.com')
        facture = self._make_facture(client_obj)
        r = self.api.get(f'/api/django/ventes/factures/{facture.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('mentions_manquantes', r.data)
        self.assertIsInstance(r.data['mentions_manquantes'], list)

    def test_complete_facture_has_no_missing_mentions(self):
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.get(company=self.company)
        profile.nom = 'Conf Fac Co'
        profile.identifiant_fiscal = 'IF123'
        profile.ice = 'ICE000111222'
        profile.rc = 'RC456'
        profile.save()
        client_obj = make_client(self.company, email='full@example.com')
        facture = self._make_facture(
            client_obj, date_livraison=date(2026, 6, 1),
            conditions_paiement='Virement à 30 jours')
        self.assertEqual(facture.mentions_manquantes, [])
