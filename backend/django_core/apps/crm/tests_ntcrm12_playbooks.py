"""NTCRM12 — Playbooks de vente par étape STAGES.py."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm import stages
from apps.crm.models import (
    Lead, LeadPlaybookProgress, Playbook, PlaybookEtape, PlaybookTache,
)
from apps.crm.services import generer_playbook_progress
from apps.roles.models import Role

User = get_user_model()


class PlaybookProgressGenerationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor NTCRM12', slug='taqinor-ntcrm12')
        self.role = Role.objects.create(
            company=self.company, nom='Responsable', permissions=['crm_creer', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='resp_ntcrm12', password='x', company=self.company, role=self.role)
        self.playbook = Playbook.objects.create(
            company=self.company, nom='Playbook devis envoyé', actif=True)
        self.etape = PlaybookEtape.objects.create(
            playbook=self.playbook, stage=stages.QUOTE_SENT, ordre=1)
        self.tache_obligatoire = PlaybookTache.objects.create(
            etape=self.etape, libelle='Appeler le client', obligatoire=True, ordre=1)
        self.tache_optionnelle = PlaybookTache.objects.create(
            etape=self.etape, libelle='Envoyer une brochure', obligatoire=False, ordre=2)

    def test_lead_passant_a_quote_sent_genere_les_taches(self):
        lead = Lead.objects.create(company=self.company, nom='Lead QS', stage=stages.NEW)
        created = generer_playbook_progress(lead, stages.QUOTE_SENT)
        self.assertEqual(len(created), 2)
        self.assertEqual(
            LeadPlaybookProgress.objects.filter(lead=lead).count(), 2)

    def test_generation_idempotente_rejouee_ne_duplique_pas(self):
        lead = Lead.objects.create(company=self.company, nom='Lead QS2', stage=stages.NEW)
        generer_playbook_progress(lead, stages.QUOTE_SENT)
        generer_playbook_progress(lead, stages.QUOTE_SENT)
        self.assertEqual(
            LeadPlaybookProgress.objects.filter(lead=lead).count(), 2)

    def test_playbook_inactif_ne_genere_rien(self):
        self.playbook.actif = False
        self.playbook.save(update_fields=['actif'])
        lead = Lead.objects.create(company=self.company, nom='Lead inactif', stage=stages.NEW)
        created = generer_playbook_progress(lead, stages.QUOTE_SENT)
        self.assertEqual(created, [])


class PlaybookEndToEndApiTests(TestCase):
    """Chaîne complète : PATCH stage sur /crm/leads/{id}/ → signal
    lead_stage_changed → génération auto → cocher via leads/{id}/playbook/."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM12 E2E', slug='taqinor-ntcrm12-e2e')
        self.role = Role.objects.create(
            company=self.company, nom='Responsable', permissions=['crm_creer', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='resp_ntcrm12_e2e', password='x', company=self.company, role=self.role)
        self.playbook = Playbook.objects.create(
            company=self.company, nom='Playbook E2E', actif=True)
        self.etape = PlaybookEtape.objects.create(
            playbook=self.playbook, stage=stages.QUOTE_SENT, ordre=1)
        self.tache = PlaybookTache.objects.create(
            etape=self.etape, libelle='Confirmer réception devis', obligatoire=True, ordre=1)
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead E2E', stage=stages.NEW)
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.user)

    def test_changement_stage_via_api_genere_puis_cocher_tache(self):
        resp = self.client_api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/', {'stage': stages.QUOTE_SENT})
        self.assertEqual(resp.status_code, 200, resp.data)

        resp = self.client_api.get(
            f'/api/django/crm/leads/{self.lead.pk}/playbook/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        progress_id = resp.data[0]['id']
        self.assertFalse(resp.data[0]['fait'])

        resp = self.client_api.post(
            f'/api/django/crm/leads/{self.lead.pk}/playbook/',
            {'tache': self.tache.pk, 'fait': True})
        self.assertEqual(resp.status_code, 200, resp.data)
        progress = LeadPlaybookProgress.objects.get(pk=progress_id)
        self.assertTrue(progress.fait)
        self.assertEqual(progress.fait_par, self.user)
        self.assertIsNotNone(progress.fait_le)

    def test_changement_stage_non_bloque_meme_avec_taches_obligatoires(self):
        # Le changement de stage réussit MÊME si aucune tâche n'est cochée —
        # jamais un blocage dur (playbook.bloquant=False par défaut).
        resp = self.client_api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/', {'stage': stages.QUOTE_SENT})
        self.assertEqual(resp.status_code, 200)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.QUOTE_SENT)
