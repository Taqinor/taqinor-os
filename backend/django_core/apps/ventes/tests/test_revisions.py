"""T10 — révisions / versionnage des devis."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()


class TestDevisRevision(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='rev-co', defaults={'nom': 'Rev Co'})[0]
        self.user = User.objects.create_user(
            username='rev_u', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(company=self.company, nom='C')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit', sku='REV-1',
            prix_vente=Decimal('1000'), quantite_stock=10)
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-REV-0001', client=self.client_obj,
            statut='envoye', taux_tva=Decimal('20'), remise_globale=Decimal('0'))
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit, designation='Kit',
            quantite=Decimal('2'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))

    def test_revise_creates_v2_and_supersedes_v1(self):
        resp = self.api.post(f'/api/django/ventes/devis/{self.devis.id}/reviser/')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['version'], 2)
        self.assertTrue(resp.data['is_active'])
        new_id = resp.data['id']
        # v2 a cloné les lignes.
        self.assertEqual(LigneDevis.objects.filter(devis_id=new_id).count(), 1)
        # v1 est inactive et pointe vers v2.
        self.devis.refresh_from_db()
        self.assertFalse(self.devis.is_active)
        self.assertEqual(self.devis.superseded_by_id, new_id)
        # Lien client préservé ; nouvelle référence distincte.
        self.assertEqual(resp.data['client'], self.client_obj.id)
        self.assertNotEqual(resp.data['reference'], self.devis.reference)

    def test_v1_serializer_exposes_superseded_ref(self):
        new = self.api.post(f'/api/django/ventes/devis/{self.devis.id}/reviser/').data
        resp = self.api.get(f'/api/django/ventes/devis/{self.devis.id}/')
        self.assertEqual(resp.data['superseded_by_ref'], new['reference'])
        self.assertFalse(resp.data['is_active'])

    def test_v2_serializer_exposes_version_parent_ref(self):
        # La v2 expose la référence de la v1 (chaîne de versions dans l'UI).
        new = self.api.post(f'/api/django/ventes/devis/{self.devis.id}/reviser/').data
        resp = self.api.get(f"/api/django/ventes/devis/{new['id']}/")
        self.assertEqual(resp.data['version_parent_ref'], self.devis.reference)
