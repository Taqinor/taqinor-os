"""Tests NTCON13 — Alerte plan périmé consulté.

Couvre : le badge apparaît quand un intervenant a ouvert une version
antérieure à la dernière diffusion, et JAMAIS quand seule la dernière
version a été consultée.
"""
from django.test import TestCase
from rest_framework import status

from apps.btp_chantier.models import DiffusionPlan
from apps.btp_chantier.selectors import plans_perimes_sur_chantier

from .helpers import auth, make_chantier, make_company, make_user

BASE = '/api/django/btp-chantier/diffusions-plan/'


class PlansPerimesTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)

    def test_badge_quand_version_anterieure_consultee(self):
        DiffusionPlan.objects.create(
            company=self.co, chantier=self.chantier, document_ged_id=10,
            version_diffusee=1,
            accuse_reception={'a@x.com': {'lu': True, 'horodatage': 'x'}})
        DiffusionPlan.objects.create(
            company=self.co, chantier=self.chantier, document_ged_id=10,
            version_diffusee=2)

        alertes = plans_perimes_sur_chantier(self.chantier)
        self.assertEqual(len(alertes), 1)
        self.assertEqual(alertes[0]['document_ged_id'], 10)
        self.assertEqual(alertes[0]['version_consultee'], 1)
        self.assertEqual(alertes[0]['derniere_version'], 2)
        self.assertEqual(alertes[0]['destinataire'], 'a@x.com')

    def test_pas_de_badge_quand_derniere_version_consultee(self):
        DiffusionPlan.objects.create(
            company=self.co, chantier=self.chantier, document_ged_id=11,
            version_diffusee=1)
        DiffusionPlan.objects.create(
            company=self.co, chantier=self.chantier, document_ged_id=11,
            version_diffusee=2,
            accuse_reception={'b@x.com': {'lu': True, 'horodatage': 'x'}})

        alertes = plans_perimes_sur_chantier(self.chantier)
        self.assertEqual(len(alertes), 0)

    def test_endpoint_plans_perimes(self):
        DiffusionPlan.objects.create(
            company=self.co, chantier=self.chantier, document_ged_id=12,
            version_diffusee=1,
            accuse_reception={'c@x.com': {'lu': True, 'horodatage': 'x'}})
        DiffusionPlan.objects.create(
            company=self.co, chantier=self.chantier, document_ged_id=12,
            version_diffusee=2)
        api = auth(self.user)
        resp = api.get(f'{BASE}plans-perimes/', {'chantier': self.chantier.id})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(len(resp.data), 1)
