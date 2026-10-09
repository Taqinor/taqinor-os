"""ACHT16 (C-ACHT-015) — estimations d'achat d'une demande d'achat masquées
sans `prix_achat_voir` (option a d'ACHT90) ; la saisie de `prix_estime`
reste acceptée.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_da_prix_masques"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import DemandeAchat, DemandeAchatLigne
from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES

User = get_user_model()
BASE = '/api/django/installations'


def _api(user):
    api = APIClient()
    api.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DaPrixMasquesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACHT16', slug='acht16-co')
        perms = list(dict(CANONICAL_SYSTEM_ROLES)['Administrateur'])
        role_admin = Role.objects.create(
            company=self.company, nom='Administrateur', permissions=perms)
        role_resp = Role.objects.create(
            company=self.company, nom='Responsable achats',
            permissions=[p for p in perms if p != 'prix_achat_voir'])
        self.admin = User.objects.create_user(
            username='admin-acht16', password='x', company=self.company,
            role=role_admin)
        self.resp = User.objects.create_user(
            username='resp-acht16', password='x', company=self.company,
            role=role_resp)
        self.assertTrue(self.admin.can_view_buy_prices)
        self.assertFalse(self.resp.can_view_buy_prices)
        self.da = DemandeAchat.objects.create(
            company=self.company, reference='DA-ACHT16-1', objet='Test',
            created_by=self.admin)
        DemandeAchatLigne.objects.create(
            demande=self.da, designation='Onduleur', quantite=Decimal('2'),
            prix_estime=Decimal('820'))

    def test_responsable_sans_droit(self):
        api = _api(self.resp)
        r = api.get(f'{BASE}/demandes-achat/{self.da.id}/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertNotIn('montant_estime', r.data)
        for ligne in r.data['lignes']:
            self.assertNotIn('prix_estime', ligne)
            self.assertNotIn('total_estime', ligne)
        r = api.get(f'{BASE}/demandes-achat-lignes/?demande={self.da.id}')
        self.assertEqual(r.status_code, 200, r.data)
        lignes = r.data['results'] if isinstance(r.data, dict) else r.data
        self.assertTrue(lignes)
        for ligne in lignes:
            self.assertNotIn('prix_estime', ligne)
            self.assertNotIn('total_estime', ligne)

    def test_admin_voit(self):
        r = _api(self.admin).get(f'{BASE}/demandes-achat/{self.da.id}/')
        self.assertEqual(Decimal(str(r.data['montant_estime'])),
                         Decimal('1640'))
        self.assertEqual(Decimal(str(r.data['lignes'][0]['prix_estime'])),
                         Decimal('820'))

    def test_saisie_ecriture_seule(self):
        r = _api(self.resp).post(f'{BASE}/demandes-achat-lignes/', {
            'demande': self.da.id, 'designation': 'Câble',
            'quantite': '3', 'prix_estime': '50'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertNotIn('prix_estime', r.data)
        ligne = DemandeAchatLigne.objects.get(pk=r.data['id'])
        self.assertEqual(ligne.prix_estime, Decimal('50'))
