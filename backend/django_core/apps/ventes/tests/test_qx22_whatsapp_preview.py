"""QX22be — préversion WhatsApp vs envoi réel.

  * whatsapp-preview construit le lien SANS marquer « envoyé » (ouvrir/fermer
    la modale laisse le brouillon intact) ;
  * whatsapp (click-through) marque « envoyé » exactement une fois.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class Qx22WhatsappPreviewTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qx22-co', defaults={'nom': 'QX22 Co'})
        self.user = User.objects.create_user(
            username='qx22_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QX22',
            telephone='+212600000057')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-QX2201',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20'), created_by=self.user)

    def test_preview_does_not_mark_sent(self):
        resp = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/whatsapp-preview/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data['preview'])
        self.assertIn('wa_url', resp.data)
        self.devis.refresh_from_db()
        # Toujours brouillon : ouvrir la modale n'a rien envoyé.
        self.assertEqual(self.devis.statut, Devis.Statut.BROUILLON)

    def test_send_marks_sent_once(self):
        resp = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/whatsapp/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ENVOYE)
        envoi = self.devis.date_envoi
        # Deuxième click : idempotent, pas de re-stamp.
        self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/whatsapp/',
            {}, format='json')
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.date_envoi, envoi)

    def test_preview_no_phone_400(self):
        self.client_obj.telephone = ''
        self.client_obj.save(update_fields=['telephone'])
        resp = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/whatsapp-preview/',
            {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.BROUILLON)
