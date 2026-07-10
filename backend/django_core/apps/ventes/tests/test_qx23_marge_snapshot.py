"""QX23be — instantané de marge (interne, manager-only).

  * ``compute_marge_snapshot`` = Σ HT − Σ(qté × prix_achat) ; None sans coût ;
  * ``mark_devis_sent`` fige la marge ;
  * le serializer n'expose la marge QU'AU responsable (jamais au commercial),
    jamais dans un PDF/sortie client (prix_achat rule).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.serializers import DevisSerializer
from apps.ventes.services import compute_marge_snapshot, mark_devis_sent

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class Qx23MargeSnapshotTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qx23-co', defaults={'nom': 'QX23 Co'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QX23',
            telephone='+212600000045')

    def _devis(self, ref, *, prix_achat='600', prix_vente='1000', qty='10'):
        devis = Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut=Devis.Statut.BROUILLON, taux_tva=Decimal('20'))
        produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku=f'{ref}-PV',
            prix_vente=Decimal(prix_vente), prix_achat=Decimal(prix_achat),
            quantite_stock=100)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Panneau',
            quantite=Decimal(qty), prix_unitaire=Decimal(prix_vente),
            remise=Decimal('0'))
        return devis

    def test_compute_marge(self):
        # 10×1000 = 10000 HT ; coût 10×600 = 6000 → marge 4000.
        devis = self._devis(f'DEV-{MONTH}-QX2301')
        self.assertEqual(compute_marge_snapshot(devis), Decimal('4000.00'))

    def test_none_when_no_prix_achat(self):
        devis = self._devis(f'DEV-{MONTH}-QX2302', prix_achat='0')
        self.assertIsNone(compute_marge_snapshot(devis))

    def test_mark_sent_freezes_marge(self):
        devis = self._devis(f'DEV-{MONTH}-QX2303')
        mark_devis_sent(devis=devis, user=None)
        devis.refresh_from_db()
        self.assertEqual(devis.marge_snapshot, Decimal('4000.00'))

    def test_serializer_hides_marge_from_non_manager(self):
        devis = self._devis(f'DEV-{MONTH}-QX2304')
        devis.marge_snapshot = Decimal('4000.00')
        devis.save(update_fields=['marge_snapshot'])
        commercial = User.objects.create_user(
            username='qx23_com', password='x', role_legacy='commercial',
            company=self.company)
        req = type('R', (), {'user': commercial})()
        data = DevisSerializer(devis, context={'request': req}).data
        self.assertIsNone(data['marge_snapshot'])

    def test_serializer_shows_marge_to_manager(self):
        devis = self._devis(f'DEV-{MONTH}-QX2305')
        devis.marge_snapshot = Decimal('4000.00')
        devis.save(update_fields=['marge_snapshot'])
        manager = User.objects.create_user(
            username='qx23_resp', password='x', role_legacy='responsable',
            company=self.company)
        req = type('R', (), {'user': manager})()
        data = DevisSerializer(devis, context={'request': req}).data
        self.assertEqual(data['marge_snapshot'], '4000.00')

    def test_api_list_hides_marge_from_commercial(self):
        devis = self._devis(f'DEV-{MONTH}-QX2306')
        devis.marge_snapshot = Decimal('4000.00')
        devis.save(update_fields=['marge_snapshot'])
        commercial = User.objects.create_user(
            username='qx23_com2', password='x', role_legacy='commercial',
            company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(commercial)}')
        resp = api.get(f'/api/django/ventes/devis/{devis.id}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIsNone(resp.data.get('marge_snapshot'))
