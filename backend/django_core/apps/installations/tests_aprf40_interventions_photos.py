"""APRF40 (C-APRF-022) — la liste des interventions précharge les pièces jointes
de toute la page (une requête `Attachment`) et lit la shot-list par `company_id` :
5 puis 25 interventions, avec créneaux photo obligatoires, coûtent le même
nombre de requêtes ; `photos_obligatoires_manquantes` reste exact.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_aprf40_interventions_photos"
"""
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.field_services import seed_shotlist_slots
from apps.installations.models import (
    Installation, Intervention, ShotListSlot,
)
from apps.records.models import Attachment

User = get_user_model()
URL = '/api/django/installations/interventions/'


class InterventionsListePhotosTests(TestCase):
    def setUp(self):
        from authentication.models import Company
        self.company, _ = Company.objects.get_or_create(
            slug='co-aprf40', defaults={'nom': 'Co APRF40'})
        self.user = User.objects.create_user(
            username='resp-aprf40', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.inst = Installation.objects.create(
            company=self.company, reference='APRF40-1',
            statut=Installation.Statut.EN_COURS)
        self.n = 0

    def _interventions(self, nb):
        ct = ContentType.objects.get_for_model(Intervention)
        for _ in range(nb):
            self.n += 1
            iv = Intervention.objects.create(
                company=self.company, installation=self.inst,
                type_intervention=Intervention.Type.POSE,
                statut=Intervention.Statut.PRETE, technicien=self.user,
                date_prevue='2026-10-26')
            if self.n % 2 == 0:
                Attachment.objects.create(
                    company=self.company, content_type=ct, object_id=iv.id,
                    file_key=f'aprf40/{iv.id}',
                    filename='slot:toiture_apres|toit.jpg')

    def _liste(self):
        with CaptureQueriesContext(connection) as ctx:
            r = self.api.get(URL)
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        return len(ctx.captured_queries), rows

    def _compte(self, sans_creneaux):
        if not sans_creneaux:
            seed_shotlist_slots(self.company)
        self._interventions(5)
        n5, rows5 = self._liste()
        self._interventions(20)
        n25, rows25 = self._liste()
        self.assertEqual((len(rows5), len(rows25)), (5, 25))
        self.assertEqual(n5, n25, (n5, n25))
        return rows25

    def test_sans_creneaux_requetes_identiques(self):
        ShotListSlot.objects.filter(company=self.company).delete()
        self._compte(sans_creneaux=True)

    def test_creneaux_obligatoires_requetes_identiques_et_manquants_exacts(self):
        rows = self._compte(sans_creneaux=False)
        obligatoires = ShotListSlot.objects.filter(
            company=self.company, actif=True, obligatoire=True).count()
        self.assertGreaterEqual(obligatoires, 2)
        ct = ContentType.objects.get_for_model(Intervention)
        for row in rows:
            avec_photo = Attachment.objects.filter(
                content_type=ct, object_id=row['id']).exists()
            attendu = obligatoires - (1 if avec_photo else 0)
            self.assertEqual(row['photos_obligatoires_manquantes'], attendu,
                             row['id'])
