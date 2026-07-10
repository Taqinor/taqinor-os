"""QX33be — acompte au moment de la signature (mode dégradé sans PSP).

  * le payload de succès post-signature porte l'acompte (tranche 1 sur le TTC
    remisé QX1) + RIB si configuré + slot lien carte seulement si PSP ;
  * l'endpoint « j'ai effectué le virement » notifie le vendeur + stampe le
    chatter, sans changer le statut ni créer de Paiement.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, LigneDevis, Paiement, ShareLink

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class Qx33DepositSuccessTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='QX33 Co')
        self.seller = User.objects.create_user(
            username='qx33_seller', password='x', role_legacy='commercial',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QX33',
            telephone='+212600000054')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-QX3301',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), remise_globale=Decimal('10'),
            created_by=self.seller)
        produit = self._produit()
        LigneDevis.objects.create(
            devis=self.devis, produit=produit, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))
        self.link = ShareLink.for_devis(self.devis)
        self.api = APIClient()

    def _produit(self):
        from apps.stock.models import Produit
        return Produit.objects.create(
            company=self.company, nom='Panneau', sku='QX33-PV',
            prix_vente=Decimal('1000'), quantite_stock=100)

    @override_settings(COMPANY_RIB='001 TAQINOR BANK 1234567')
    def test_accept_success_payload_has_deposit(self):
        resp = self.api.post(
            f'/api/django/public/proposal/{self.link.token}/accept/',
            {'nom': 'Client', 'consent_esign': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        pay = resp.data['paiement']
        # 10000 HT − 10 % = 9000 ; TTC 10800 ; acompte 30 % = 3240.
        self.assertEqual(pay['acompte_ttc'], '3240.00')
        self.assertIn('TAQINOR BANK', pay['rib'])
        # Pas de PSP configuré → pas de lien carte.
        self.assertIsNone(pay['card_payment_url'])
        self.assertIn('virement', pay['declare_url'])

    @override_settings(PAYMENT_PROVIDER='hosted')
    def test_card_slot_activates_with_psp(self):
        resp = self.api.post(
            f'/api/django/public/proposal/{self.link.token}/accept/',
            {'nom': 'Client', 'consent_esign': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNotNone(resp.data['paiement']['card_payment_url'])

    def test_virement_declaration_notifies_seller(self):
        self.devis.statut = Devis.Statut.ACCEPTE
        self.devis.save(update_fields=['statut'])
        from apps.notifications.models import Notification
        resp = self.api.post(
            f'/api/django/public/proposal/{self.link.token}/virement/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(Notification.objects.filter(
            recipient=self.seller).exists())
        # Statut inchangé, aucun Paiement créé (règle #4).
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(
            Paiement.objects.filter(facture__devis=self.devis).count(), 0)

    def test_virement_declaration_idempotent(self):
        self.devis.statut = Devis.Statut.ACCEPTE
        self.devis.save(update_fields=['statut'])
        url = f'/api/django/public/proposal/{self.link.token}/virement/'
        self.api.post(url, {}, format='json')
        second = self.api.post(url, {}, format='json')
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data.get('already'))
