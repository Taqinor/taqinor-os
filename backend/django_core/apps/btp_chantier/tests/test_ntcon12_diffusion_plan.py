"""Tests NTCON12 — Diffusion contrôlée de plans.

Couvre : diffusion trace qui a reçu quelle version, accusé de réception
marqué à l'ouverture du lien tokenisé, cross-tenant isolé.
"""
from django.test import TestCase
from rest_framework import status

from apps.btp_chantier.models import DiffusionPlan

from .helpers import auth, make_chantier, make_company, make_user

BASE = '/api/django/btp-chantier/diffusions-plan/'


class DiffusionPlanApiTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.destinataire = make_user(self.co, username='destinataire-diff')
        self.chantier = make_chantier(self.co)

    def test_creer_et_diffuser_trace_version(self):
        api = auth(self.user)
        resp = api.post(BASE, {
            'chantier': self.chantier.id,
            'document_ged_id': 42,
            'version_diffusee': 3,
            'destinataires_internes': [self.destinataire.id],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        diffusion_id = resp.data['id']
        self.assertIsNone(resp.data['date_diffusion'])

        resp2 = api.post(
            f'{BASE}{diffusion_id}/diffuser/', {}, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_200_OK, resp2.data)
        self.assertIsNotNone(resp2.data['date_diffusion'])
        self.assertEqual(resp2.data['version_diffusee'], 3)

    def test_accuse_reception_marque_a_l_ouverture(self):
        diffusion = DiffusionPlan.objects.create(
            company=self.co, chantier=self.chantier, document_ged_id=7,
            version_diffusee=1)
        self.assertEqual(diffusion.accuse_reception, {})

        resp = self.client.get(
            f'{BASE}public/{diffusion.token}/ouvrir/',
            {'destinataire': 'client@example.com'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

        diffusion.refresh_from_db()
        self.assertIn('client@example.com', diffusion.accuse_reception)
        self.assertTrue(diffusion.accuse_reception['client@example.com']['lu'])

    def test_lien_public_inconnu_404(self):
        resp = self.client.get(f'{BASE}public/jeton-inconnu/ouvrir/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_tenant_refused(self):
        other_co = make_company()
        other_chantier = make_chantier(other_co)
        other_diffusion = DiffusionPlan.objects.create(
            company=other_co, chantier=other_chantier, document_ged_id=1,
            version_diffusee=1)
        api = auth(self.user)
        resp = api.get(f'{BASE}{other_diffusion.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
