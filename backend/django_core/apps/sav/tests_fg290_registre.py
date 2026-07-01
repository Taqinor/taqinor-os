"""FG290 — Registre des garanties matériel & échéancier de fin PAR PARC.

Le registre regroupe le parc par installation, rend les dates de fin de garantie
(matériel + production, calculées) et un statut d'alerte (expirée / expire
bientôt / sous garantie / non renseignée), trié par échéance la plus proche.
Company-scopé ; respecte les filtres et le seuil ?jours=N.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.sav.models import Equipement

User = get_user_model()
URL = '/api/django/sav/equipements/registre-garanties/'


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestFG290Registre(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='fg290-co', defaults={'nom': 'FG290 Co'})
        self.user = User.objects.create_user(
            username='fg290_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = _auth(self.user)
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='FG290',
            email='fg290@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-FG290-1', client=client)
        self.inst2 = Installation.objects.create(
            company=self.company, reference='CHT-FG290-2', client=client)
        self.prod = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='FG290-OND',
            marque='Huawei', prix_achat=Decimal('100'),
            prix_vente=Decimal('200'))
        today = timezone.localdate()
        # Parc 1 : une unité sous garantie, une expirée, une non renseignée.
        Equipement.objects.create(
            company=self.company, produit=self.prod, installation=self.inst,
            numero_serie='EQ-SOUS', date_fin_garantie=today + timedelta(days=400))
        Equipement.objects.create(
            company=self.company, produit=self.prod, installation=self.inst,
            numero_serie='EQ-EXP', date_fin_garantie=today - timedelta(days=10))
        Equipement.objects.create(
            company=self.company, produit=self.prod, installation=self.inst,
            numero_serie='EQ-VIDE', date_fin_garantie=None)
        # Parc 2 : une unité qui expire bientôt (dans 30 j).
        Equipement.objects.create(
            company=self.company, produit=self.prod, installation=self.inst2,
            numero_serie='EQ-SOON', date_fin_garantie=today + timedelta(days=30))

    def test_registry_groups_by_parc_with_alerts(self):
        r = self.api.get(URL)
        self.assertEqual(r.status_code, 200, r.data)
        data = r.data
        self.assertEqual(data['totaux']['equipements'], 4)
        self.assertEqual(data['totaux']['expirees'], 1)
        self.assertEqual(data['totaux']['expire_bientot'], 1)
        self.assertEqual(data['totaux']['sous_garantie'], 1)
        self.assertEqual(data['totaux']['non_renseignee'], 1)
        self.assertEqual(len(data['parcs']), 2)
        # Trié par échéance la plus proche : parc avec l'expirée (-10 j) d'abord.
        first = data['parcs'][0]
        self.assertEqual(first['installation'], self.inst.id)
        self.assertEqual(first['alertes']['expirees'], 1)

    def test_jours_threshold_widens_expiring_soon(self):
        # Avec un seuil de 500 jours, l'unité à +400 j passe « expire bientôt ».
        r = self.api.get(URL, {'jours': 500})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertGreaterEqual(r.data['totaux']['expire_bientot'], 2)
        self.assertEqual(r.data['totaux']['sous_garantie'], 0)

    def test_company_scoped(self):
        # Une autre société ne voit pas ce parc.
        other = Company.objects.create(slug='fg290-other', nom='Other')
        ou = User.objects.create_user(
            username='fg290_other', password='x', role_legacy='admin',
            company=other)
        r = _auth(ou).get(URL)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['totaux']['equipements'], 0)
        self.assertEqual(r.data['parcs'], [])
