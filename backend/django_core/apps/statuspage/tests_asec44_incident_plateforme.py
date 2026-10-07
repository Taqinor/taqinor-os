"""ASEC44 — la publication d'un incident PLATEFORME (``company=None``) est
réservée à la plateforme.

Constat C-ASEC-013 : un Directeur de n'importe quel tenant publiait le
post-mortem d'un incident système affiché sur la page de statut publique.
Attendu : Directeur de tenant → 403 sans écriture ; superuser plateforme →
200 ; les incidents de SA société restent publiables par le Directeur.
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.roles.models import Role
from apps.statuspage.models import IncidentPublic
from authentication.models import Company

User = get_user_model()


def _url(incident):
    return (f'/api/django/statuspage/incidents/{incident.pk}/'
            'publier-postmortem/')


class IncidentPlateformeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='ASEC44', slug='asec44')
        role = Role.objects.create(company=self.company, nom='Directeur')
        self.directeur = User.objects.create_user(
            'asec44_directeur', password='x', company=self.company, role=role)
        self.plateforme = User.objects.create_superuser(
            'asec44_plateforme', password='x', email='p@example.invalid')
        kwargs = dict(
            statut=IncidentPublic.Statut.RESOLVED, debute_le=timezone.now(),
            resolu_le=timezone.now(),
            postmortem_markdown='Cause : disque plein.')
        self.systeme = IncidentPublic.objects.create(
            titre='Panne plateforme', company=None, **kwargs)
        self.du_tenant = IncidentPublic.objects.create(
            titre='Panne tenant', company=self.company, **kwargs)

    def _client(self, user):
        api = APIClient()
        api.force_authenticate(user)
        return api

    def test_directeur_tenant_403(self):
        r = self._client(self.directeur).post(_url(self.systeme))
        self.assertEqual(r.status_code, 403, r.content)
        self.systeme.refresh_from_db()
        self.assertIsNone(self.systeme.postmortem_publie_le)

    def test_superuser_200(self):
        r = self._client(self.plateforme).post(_url(self.systeme))
        self.assertEqual(r.status_code, 200, r.content)
        self.systeme.refresh_from_db()
        self.assertIsNotNone(self.systeme.postmortem_publie_le)

    def test_incident_tenant_editable(self):
        r = self._client(self.directeur).post(_url(self.du_tenant))
        self.assertEqual(r.status_code, 200, r.content)
        self.du_tenant.refresh_from_db()
        self.assertIsNotNone(self.du_tenant.postmortem_publie_le)
        # Jamais l'incident d'une AUTRE société.
        autre = Company.objects.create(nom='ASEC44 B', slug='asec44-b')
        etranger = IncidentPublic.objects.create(
            titre='Panne B', company=autre,
            statut=IncidentPublic.Statut.RESOLVED, debute_le=timezone.now(),
            resolu_le=timezone.now(), postmortem_markdown='x')
        r2 = self._client(self.directeur).post(_url(etranger))
        self.assertEqual(r2.status_code, 404, r2.content)
