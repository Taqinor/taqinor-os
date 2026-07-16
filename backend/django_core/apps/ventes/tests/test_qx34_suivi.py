"""QX34 — suivi post-signature public en lecture seule (timeline jalons).

L'endpoint dérive l'état des jalons (accepté → acompte → matériel → installation
→ facturé) depuis les lignes existantes, sans toucher aucun statut/PDF.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import (
    Devis, Facture, Paiement, ShareLink,
)

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class Qx34SuiviTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='QX34 Co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QX34',
            telephone='+212600000055')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-QX3401',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        self.link = ShareLink.for_devis(self.devis)
        self.api = APIClient()

    def _url(self, token):
        return f'/api/django/ventes/suivi/{token}/'

    def test_invalid_token_404(self):
        self.assertEqual(self.api.get(self._url('bad')).status_code, 404)

    def test_timeline_reflects_accepted(self):
        self.devis.statut = Devis.Statut.ACCEPTE
        self.devis.date_acceptation = timezone.localdate()
        self.devis.save(update_fields=['statut', 'date_acceptation'])
        resp = self.api.get(self._url(self.link.token))
        self.assertEqual(resp.status_code, 200, resp.content)
        ms = {m['key']: m for m in resp.data['milestones']}
        self.assertTrue(ms['accepte']['done'])
        self.assertFalse(ms['acompte']['done'])
        self.assertFalse(ms['facture']['done'])

    def test_timeline_reflects_payment_and_invoice(self):
        self.devis.statut = Devis.Statut.ACCEPTE
        self.devis.save(update_fields=['statut'])
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-QX3401',
            client=self.client_obj, devis=self.devis,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20'))
        Paiement.objects.create(
            company=self.company, facture=facture,
            montant=Decimal('1000'), date_paiement=timezone.localdate(),
            mode=Paiement.Mode.VIREMENT)
        resp = self.api.get(self._url(self.link.token))
        ms = {m['key']: m for m in resp.data['milestones']}
        self.assertTrue(ms['acompte']['done'])
        self.assertTrue(ms['facture']['done'])

    def test_no_prix_achat_in_payload(self):
        resp = self.api.get(self._url(self.link.token))
        self.assertNotIn('prix_achat', str(resp.data))
        self.assertNotIn('marge', str(resp.data))
