"""
XFAC18 — Workflow de revue facture (ségrégation des tâches, style Odoo 19).

Flag OFF (défaut) : rien ne change. Flag ON : un commercial (rôle avec
permission d'écriture mais palier de menu limité) crée mais ne peut pas
émettre ; le responsable voit les anomalies et émet ; audit trail complet.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xfac18_revue_facture -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from apps.roles.models import Role
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='xfac18-co', nom='XFAC18 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='xfac18@example.com'):
    return Client.objects.create(
        company=company, nom='Revue', prenom='Client',
        email=email, telephone='+212600000064', adresse='Casablanca',
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XFAC18RevueFactureTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.admin = User.objects.create_user(
            username='xfac18_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        # Commercial : rôle fin avec permission d'écriture (ventes_creer) mais
        # SANS roles_gerer/users_voir → menu_tier reste 'normal' (palier
        # limité) tout en passant IsResponsableOrAdmin (is_responsable=True).
        commercial_role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['ventes_creer', 'ventes_voir'],
        )
        self.commercial = User.objects.create_user(
            username='xfac18_commercial', password='x',
            company=self.company, role=commercial_role,
        )
        self.assertTrue(self.commercial.is_responsable)
        self.assertEqual(self.commercial.menu_tier, 'normal')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau solaire', sku='SKU-XFAC18',
            prix_vente=Decimal('1000'), prix_achat=Decimal('800'),
            quantite_stock=100,
        )

    def _create_facture_via_api(self, user):
        api = auth(user)
        r = api.post('/api/django/ventes/factures/', {
            'client': self.client_obj.id,
            'taux_tva': '20.00',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        facture = Facture.objects.get(pk=r.data['id'])
        LigneFacture.objects.create(
            facture=facture, produit=self.produit,
            designation='Panneau solaire',
            quantite=1, prix_unitaire=Decimal('1000'), taux_tva=Decimal('20'),
        )
        return facture

    def test_flag_off_commercial_can_emit_byte_identical(self):
        """Flag OFF (défaut) : comportement historique — n'importe qui émet."""
        facture = self._create_facture_via_api(self.commercial)
        self.assertEqual(facture.revue_statut, '')
        api = auth(self.commercial)
        r = api.post(
            f'/api/django/ventes/factures/{facture.id}/emettre/', {},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.EMISE)

    def test_flag_on_commercial_creates_a_valider(self):
        profile = CompanyProfile.get(company=self.company)
        profile.revue_factures_active = True
        profile.save(update_fields=['revue_factures_active'])
        facture = self._create_facture_via_api(self.commercial)
        self.assertEqual(facture.revue_statut, Facture.RevueStatut.A_VALIDER)

    def test_flag_on_commercial_cannot_emit_own_facture(self):
        profile = CompanyProfile.get(company=self.company)
        profile.revue_factures_active = True
        profile.save(update_fields=['revue_factures_active'])
        facture = self._create_facture_via_api(self.commercial)
        api = auth(self.commercial)
        r = api.post(
            f'/api/django/ventes/factures/{facture.id}/emettre/', {},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.BROUILLON)

    def test_flag_on_admin_can_emit_and_sees_validee(self):
        profile = CompanyProfile.get(company=self.company)
        profile.revue_factures_active = True
        profile.save(update_fields=['revue_factures_active'])
        facture = self._create_facture_via_api(self.commercial)
        api = auth(self.admin)
        r = api.post(
            f'/api/django/ventes/factures/{facture.id}/emettre/', {},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.EMISE)
        self.assertEqual(facture.revue_statut, Facture.RevueStatut.VALIDEE)

    def test_flag_on_admin_creating_directly_not_flagged(self):
        """Un responsable/admin qui crée directement n'a pas besoin d'être
        re-validé (revue_statut reste vide)."""
        profile = CompanyProfile.get(company=self.company)
        profile.revue_factures_active = True
        profile.save(update_fields=['revue_factures_active'])
        facture = self._create_facture_via_api(self.admin)
        self.assertEqual(facture.revue_statut, '')

    def test_anomaly_credit_limit_surfaced_to_validator(self):
        """Client au-delà de son plafond : le valideur voit l'anomalie."""
        self.client_obj.plafond_credit = Decimal('100')
        self.client_obj.save(update_fields=['plafond_credit'])
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-9001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('5000'), created_by=self.admin,
        )
        profile = CompanyProfile.get(company=self.company)
        profile.revue_factures_active = True
        profile.save(update_fields=['revue_factures_active'])
        facture = self._create_facture_via_api(self.commercial)
        api = auth(self.admin)
        r = api.post(
            f'/api/django/ventes/factures/{facture.id}/emettre/', {},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        codes = [a['code'] for a in r.data.get('anomalies', [])]
        self.assertIn('plafond_credit_depasse', codes)
