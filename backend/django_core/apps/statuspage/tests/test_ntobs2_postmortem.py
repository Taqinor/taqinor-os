"""NTOBS2 — post-mortems publiés (action Directeur), jamais un contenu
non-publié exposé publiquement."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.roles.models import Role

from ..models import IncidentPublic

User = get_user_model()


class PublierPostmortemTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-nt2')
        self.role_directeur = Role.objects.create(
            company=self.company, nom='Directeur')
        self.role_commercial = Role.objects.create(
            company=self.company, nom='Commercial')
        self.directeur = User.objects.create_user(
            'directeur', password='x', company=self.company,
            role=self.role_directeur)
        self.commercial = User.objects.create_user(
            'commercial', password='x', company=self.company,
            role=self.role_commercial)
        self.incident = IncidentPublic.objects.create(
            titre='Panne stockage', statut=IncidentPublic.Statut.RESOLVED,
            debute_le=timezone.now(), resolu_le=timezone.now(), company=None,
            postmortem_markdown='Cause : disque plein. Correctif : purge.',
        )

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def test_directeur_can_publish_postmortem(self):
        url = f'/api/django/statuspage/incidents/{self.incident.pk}/publier-postmortem/'
        resp = self._client(self.directeur).post(url)
        self.assertEqual(resp.status_code, 200)
        self.incident.refresh_from_db()
        self.assertIsNotNone(self.incident.postmortem_publie_le)

    def test_non_directeur_forbidden(self):
        url = f'/api/django/statuspage/incidents/{self.incident.pk}/publier-postmortem/'
        resp = self._client(self.commercial).post(url)
        self.assertEqual(resp.status_code, 403)

    def test_cannot_publish_before_resolved(self):
        self.incident.statut = IncidentPublic.Statut.INVESTIGATING
        self.incident.save(update_fields=['statut'])
        url = f'/api/django/statuspage/incidents/{self.incident.pk}/publier-postmortem/'
        resp = self._client(self.directeur).post(url)
        self.assertEqual(resp.status_code, 400)

    def test_postmortem_hidden_until_published(self):
        client = APIClient()
        resp = client.get(
            f'/api/django/statuspage/public/incidents/{self.incident.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['postmortem_markdown'], '')

        self._client(self.directeur).post(
            f'/api/django/statuspage/incidents/{self.incident.pk}/publier-postmortem/')
        resp2 = client.get(
            f'/api/django/statuspage/public/incidents/{self.incident.pk}/')
        self.assertIn('disque plein', resp2.data['postmortem_markdown'])
