"""ADEV37 — la capture d'e-mail entrant reconnaît le VRAI numéro de document.

Avant : ``_REF_RE`` n'exigeait aucun chiffre, si bien que « Re: Votre facture
FAC-202610-0002 » capturait le mot « FACTURE » (FAC+TURE) et que la facture
n'était jamais rattachée ; « Device DEV-… » capturait « DEVICE ».
Test-du-test : remettre ``[A-Z0-9][A-Z0-9-]{2,}`` sans chiffre exigé ⇒ les cas
facture échouent.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.inbound_email import capture_inbound_email, extract_reference
from apps.ventes.models import Devis, EmailLog, Facture

User = get_user_model()


class CaptureReferenceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ADEV37 Co')
        self.user = User.objects.create_user(
            username='adev37_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ADEV37',
            email='adev37@example.com', telephone='+212600003737')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-202610-0003',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), created_by=self.user)
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-202610-0002',
            devis=self.devis, client=self.client_obj,
            statut=Facture.Statut.EMISE, montant_ht=Decimal('100'),
            montant_tva=Decimal('20'), montant_ttc=Decimal('120'),
            created_by=self.user)

    def test_sujets_facture_emis_rattachent_la_facture(self):
        # Les trois sujets émis par email_service.py (envoi, rappel, relance).
        sujets = [
            'Re: Votre facture FAC-202610-0002',
            'Re: Rappel de paiement — facture FAC-202610-0002',
            'Re: Relance 1 — facture FAC-202610-0002',
        ]
        for sujet in sujets:
            with self.subTest(sujet=sujet):
                log = capture_inbound_email(
                    from_email='inconnu@example.com', subject=sujet,
                    company=self.company)
                self.assertIsNotNone(log)
                self.assertEqual(log.reference, 'FAC-202610-0002')
                self.assertEqual(log.facture_id, self.facture.id)
                # CLAUSE PERSISTANCE : relu en base.
                relu = EmailLog.objects.get(pk=log.pk)
                self.assertEqual(relu.facture_id, self.facture.id)
                self.assertEqual(relu.reference, 'FAC-202610-0002')

    def test_sujet_devis_rattache_le_devis(self):
        log = capture_inbound_email(
            from_email='inconnu@example.com',
            subject='Re: Votre devis DEV-202610-0003', company=self.company)
        self.assertIsNotNone(log)
        self.assertEqual(log.reference, 'DEV-202610-0003')
        self.assertEqual(EmailLog.objects.get(pk=log.pk).devis_id,
                         self.devis.id)

    def test_device_ne_capture_plus_le_mot(self):
        self.assertEqual(extract_reference('Device DEV-2026-0001'),
                         'DEV-2026-0001')
        self.assertEqual(extract_reference('Votre facture'), '')
        self.assertEqual(extract_reference('Device sans numéro'), '')
