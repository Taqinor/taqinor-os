"""T17 — garde d'approbation de remise avant envoi du devis."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()


class TestDiscountGuard(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='dg-co', defaults={'nom': 'DG Co'})[0]
        self.resp = User.objects.create_user(
            username='dg_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.admin = User.objects.create_user(
            username='dg_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(company=self.company, nom='C')

    def _api(self, user):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def _devis(self, remise):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-DG-{remise}', client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20'), remise_globale=Decimal(remise))

    def test_threshold_off_by_default_allows_send(self):
        # Seuil non configuré → comportement inchangé : envoi autorisé.
        d = self._devis('30')
        r = self._api(self.resp).patch(f'/api/django/ventes/devis/{d.id}/',
                                       {'statut': 'envoye'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_over_threshold_blocks_responsable(self):
        CompanyProfile.objects.update_or_create(
            company=self.company, defaults={'discount_approval_threshold': Decimal('10')})
        d = self._devis('25')
        r = self._api(self.resp).patch(f'/api/django/ventes/devis/{d.id}/',
                                       {'statut': 'envoye'}, format='json')
        self.assertEqual(r.status_code, 400)
        d.refresh_from_db()
        self.assertEqual(d.statut, 'brouillon')  # non envoyé

    def test_admin_send_auto_approves(self):
        CompanyProfile.objects.update_or_create(
            company=self.company, defaults={'discount_approval_threshold': Decimal('10')})
        d = self._devis('25')
        r = self._api(self.admin).patch(f'/api/django/ventes/devis/{d.id}/',
                                        {'statut': 'envoye'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        d.refresh_from_db()
        self.assertTrue(d.remise_approuvee)

    def test_approval_then_responsable_can_send(self):
        CompanyProfile.objects.update_or_create(
            company=self.company, defaults={'discount_approval_threshold': Decimal('10')})
        d = self._devis('25')
        self._api(self.admin).post(
            f'/api/django/ventes/devis/{d.id}/approuver-remise/')
        r = self._api(self.resp).patch(f'/api/django/ventes/devis/{d.id}/',
                                       {'statut': 'envoye'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
