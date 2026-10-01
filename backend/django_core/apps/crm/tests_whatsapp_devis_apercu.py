"""
QJR538 (Groupe QJR5) — l'aperçu WhatsApp multi-devis de la fiche lead n'écrit
plus RIEN : seul le commit (`whatsapp-devis`, appelé par « Ouvrir WhatsApp »)
marque les devis envoyés.

Contrat partagé : ``apps/crm/contract_samples/whatsapp_devis_apercu.json``
(QJR502) — la réponse de l'aperçu porte exactement les clés de son exemple.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.crm.tests_whatsapp_devis_apercu"
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.audit.models import AuditLog
from apps.crm.models import Client, Lead, LeadActivity
from apps.ventes.models import Devis, ShareLink
from authentication.models import Company

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'whatsapp_devis_apercu.json').read_text(encoding='utf-8'))


class TestWhatsAppDevisApercu(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='QJR538 Co', slug='qjr538-co')
        self.user = User.objects.create_user(
            username='qjr538_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.lead = Lead.objects.create(
            company=self.company, nom='Bennani', prenom='Amina',
            telephone='0612345678', stage='NEW')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Bennani', telephone='0612345678')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR538-1',
            client=self.client_obj, lead=self.lead, statut='brouillon')

    def _apercu(self, **corps):
        return self.api.post(
            f'/api/django/crm/leads/{self.lead.id}/whatsapp-devis-apercu/',
            {'devis_ids': [self.devis.id], 'langue': 'fr', **corps},
            format='json')

    def test_apercu_sur_brouillon_n_ecrit_rien(self):
        notes_avant = LeadActivity.objects.filter(lead=self.lead).count()
        audits_avant = AuditLog.objects.filter(
            action=AuditLog.Action.WHATSAPP).count()
        r = self._apercu()
        self.assertEqual(r.status_code, 200, r.content)
        self.devis.refresh_from_db()
        self.lead.refresh_from_db()
        self.assertEqual(self.devis.statut, 'brouillon')
        self.assertIsNone(self.devis.date_envoi)
        self.assertEqual(self.lead.stage, 'NEW')
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.lead).count(), notes_avant)
        self.assertEqual(
            AuditLog.objects.filter(action=AuditLog.Action.WHATSAPP).count(),
            audits_avant)

    def test_apercu_porte_les_cles_du_contrat(self):
        r = self._apercu()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(set(r.json()), set(CONTRAT['exemple']))
        lien = r.json()['links'][0]
        self.assertEqual(set(lien), set(CONTRAT['exemple']['links'][0]))
        self.assertTrue(r.json()['wa_url'].startswith('https://wa.me/'))

    def test_apercu_puis_commit_portent_le_meme_lien(self):
        apercu = self._apercu().json()
        commit = self.api.post(
            f'/api/django/crm/leads/{self.lead.id}/whatsapp-devis/',
            {'devis_ids': [self.devis.id], 'langue': 'fr'}, format='json')
        self.assertEqual(commit.status_code, 200, commit.content)
        self.assertEqual(apercu['links'][0]['token'],
                         commit.json()['links'][0]['token'])
        self.assertEqual(ShareLink.objects.filter(devis=self.devis).count(), 1)
        # Le commit, lui, marque le devis envoyé.
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'envoye')
        self.assertIsNotNone(self.devis.date_envoi)

    def test_apercu_selection_vide_400(self):
        r = self.api.post(
            f'/api/django/crm/leads/{self.lead.id}/whatsapp-devis-apercu/',
            {'devis_ids': []}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('detail', r.json())
