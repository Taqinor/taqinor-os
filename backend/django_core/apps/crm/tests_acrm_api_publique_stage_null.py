"""ACRM58 — ``stage: null`` sur l'API publique en écriture = 400 sous le
champ ``stage`` (comme ``''``), jamais un 500 (IntegrityError) — rejoue la
sonde LSVC4-10.

Test-du-test : remettre l'exception ``field != 'stage'`` sans la garde ⇒
test_null_400 échoue (500).
"""
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.crm import services, stages
from apps.crm.models import Lead
from apps.publicapi.models import ApiKey
from apps.publicapi.portees import SCOPE_WRITE_LEADS
from authentication.models import Company

URL = '/api/public/v1/leads-write/{}/'


class ApiPubliqueStageNullTests(TestCase):

    def setUp(self):
        self.co = Company.objects.create(
            nom='ACRM58 Solaire', slug='acrm58-stage-null')
        _, brute = ApiKey.issue(
            company=self.co, label='ecriture', scopes=[SCOPE_WRITE_LEADS])
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=f'Api-Key {brute}')
        self.lead = Lead.objects.create(
            company=self.co, nom='Integ', email='integ@example.com',
            stage=stages.NEW)

    def _patch(self, body):
        return self.api.patch(URL.format(self.lead.pk), body, format='json')

    def test_null_400(self):
        for valeur in (None, ''):
            with self.subTest(valeur=valeur):
                resp = self._patch({'stage': valeur})
                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertIn('stage', str(resp.data))
                self.lead.refresh_from_db()
                self.assertEqual(self.lead.stage, stages.NEW)

    def test_valide_ok(self):
        resp = self._patch({'stage': stages.CONTACTED})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.CONTACTED)

    def test_chaque_champ_null_jamais_500(self):
        for champ in services.PUBLIC_LEAD_WRITABLE_FIELDS:
            with self.subTest(champ=champ):
                resp = self._patch({champ: None})
                self.assertLess(resp.status_code, 500, (champ, resp.data))
                attendu = 400 if champ == 'stage' else 200
                self.assertEqual(resp.status_code, attendu, (champ, resp.data))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.nom, 'Integ')
        self.assertEqual(self.lead.stage, stages.NEW)

    def test_ligne_import_en_erreur_nommee(self):
        from apps.publicapi.bulk import _process_lead_row
        with self.assertRaises(ValidationError) as ctx:
            _process_lead_row(
                self.co, 'upsert', 'email',
                {'email': 'integ@example.com', 'stage': None})
        self.assertIn('stage', str(ctx.exception.detail))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.NEW)
