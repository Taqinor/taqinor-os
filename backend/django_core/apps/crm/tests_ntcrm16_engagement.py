"""NTCRM16 — Score d'engagement multi-signaux (Client, fidélisation/upsell)."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.engagement import compute_engagement_score, engagement_label
from apps.crm.models import Client, Lead, LeadActivity, PointContact
from apps.roles.models import Role
from apps.ventes.models import Devis, Facture

User = get_user_model()


class EngagementScoreTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM16', slug='taqinor-ntcrm16')

    def test_client_sans_aucun_signal_score_zero(self):
        client = Client.objects.create(company=self.company, nom='Vide')
        self.assertEqual(compute_engagement_score(client), 0)
        self.assertEqual(engagement_label(0), 'Froid')

    def test_deux_clients_avec_historiques_differents_scores_coherents(self):
        # Client A : très engagé (contacts récents, activité récente,
        # factures payées, devis acceptés).
        client_a = Client.objects.create(company=self.company, nom='Engagé')
        lead_a = Lead.objects.create(company=self.company, client=client_a, nom='Lead A')
        now = timezone.now()
        for _ in range(4):
            PointContact.objects.create(
                company=self.company, lead=lead_a, canal='telephone',
                date_contact=now - datetime.timedelta(days=5))
        LeadActivity.objects.create(
            company=self.company, lead=lead_a, kind=LeadActivity.Kind.NOTE,
            body='contact récent')
        devis_a = Devis.objects.create(
            company=self.company, client=client_a, reference='DVA',
            statut=Devis.Statut.ACCEPTE)
        Facture.objects.create(
            company=self.company, client=client_a, devis=devis_a,
            reference='FA1', statut=Facture.Statut.PAYEE)

        # Client B : jamais actif (devis envoyé non signé, facture impayée).
        client_b = Client.objects.create(company=self.company, nom='Froid')
        devis_b = Devis.objects.create(
            company=self.company, client=client_b, reference='DVB',
            statut=Devis.Statut.ENVOYE)
        Facture.objects.create(
            company=self.company, client=client_b, devis=devis_b,
            reference='FB1', statut=Facture.Statut.EMISE)

        score_a = compute_engagement_score(client_a, now=now)
        score_b = compute_engagement_score(client_b, now=now)
        self.assertGreater(score_a, score_b)
        self.assertEqual(engagement_label(score_a), 'Chaud')

    def test_client_avec_devis_uniquement_score_partiel(self):
        client = Client.objects.create(company=self.company, nom='Devis seul')
        Devis.objects.create(
            company=self.company, client=client, reference='DVC',
            statut=Devis.Statut.ACCEPTE)
        score = compute_engagement_score(client)
        self.assertGreater(score, 0)
        self.assertLess(score, 100)

    def test_client_avec_activite_recente_seule(self):
        client = Client.objects.create(company=self.company, nom='Activité seule')
        lead = Lead.objects.create(company=self.company, client=client, nom='Lead')
        LeadActivity.objects.create(
            company=self.company, lead=lead, kind=LeadActivity.Kind.NOTE,
            body='note')
        score = compute_engagement_score(client)
        self.assertGreater(score, 0)


class EngagementEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM16b', slug='taqinor-ntcrm16b')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_creer'])
        self.user = User.objects.create_user(
            username='vendeur_ntcrm16', password='x',
            company=self.company, role=self.role)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_endpoint_detail(self):
        client = Client.objects.create(company=self.company, nom='Client détail')
        resp = self.api.get(f'/api/django/crm/clients/{client.pk}/engagement/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('score', resp.data)
        self.assertIn('label', resp.data)

    def test_endpoint_bulk(self):
        Client.objects.create(company=self.company, nom='C1')
        Client.objects.create(company=self.company, nom='C2')
        resp = self.api.get('/api/django/crm/clients/engagement-bulk/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 2)
