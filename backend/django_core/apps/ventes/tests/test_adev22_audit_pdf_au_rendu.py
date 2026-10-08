"""ADEV22 (C-ADEV-028) — l'entrée d'audit « PDF devis généré » est écrite au
RENDU réussi (``/proposal`` 200, fin de la tâche Celery), plus jamais à la
DEMANDE ``generer-pdf`` (202) dont la tâche peut échouer.

Le moteur est exécuté réellement ; seul le stockage MinIO (upload, bucket,
relecture) est doublé — le test le dit. Signal ``document_pdf_generated`` et
receveur ``audit/receivers.py`` réels.

Test-du-test : remettre l'émission dans ``generer_pdf`` ⇒
``test_tache_en_echec_zero_ligne`` échoue.
"""
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.ventes.tasks import task_generate_devis_pdf
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

DETAIL = 'PDF devis généré'


class AuditPdfAuRenduTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='adev22-co', nom='ADEV22')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '12', '1500'),
            ('Onduleur hybride', '1', '12000'),
            ('Structures acier', '12', '450'),
        ], reference='DEV-ADEV22-1')
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def _lignes_audit(self):
        return AuditLog.objects.filter(
            action=AuditLog.Action.PDF, object_id=str(self.devis.pk),
            detail=DETAIL).count()

    def _minio_double(self):
        """Doublure du SEUL stockage : l'upload capture les octets rendus."""
        captures = {}

        def _upload(pdf_bytes, key, *a, **k):
            captures[key] = pdf_bytes
            return key
        return captures, [
            mock.patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket'),
            mock.patch('apps.ventes.utils.pdf._upload_pdf',
                       side_effect=_upload),
            mock.patch('apps.ventes.utils.pdf.download_pdf',
                       side_effect=lambda key: captures.get(key, b'')),
        ]

    def test_proposal_200_une_ligne(self):
        _, doublures = self._minio_double()
        for d in doublures:
            d.start()
            self.addCleanup(d.stop)
        resp = self.api.get(
            '/api/django/ventes/devis/%s/proposal/' % self.devis.pk)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._lignes_audit(), 1)

    def test_tache_en_echec_zero_ligne(self):
        # La demande ne journalise plus rien ; la tâche (exécutée ici, en
        # échec) non plus.
        with mock.patch('apps.ventes.tasks.task_generate_devis_pdf.delay') \
                as delay:
            delay.return_value = mock.Mock(id='t-adev22')
            resp = self.api.post(
                '/api/django/ventes/devis/%s/generer-pdf/' % self.devis.pk,
                {}, format='json')
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(self._lignes_audit(), 0)
        with mock.patch(
                'apps.ventes.quote_engine.generate_premium_devis_pdf',
                side_effect=RuntimeError('rendu en échec')), \
                mock.patch('apps.ventes.tasks._idempotent_cached_key',
                           return_value=None):
            resultat = task_generate_devis_pdf.apply(
                args=[self.devis.pk, None], retries=3)
        self.assertTrue(resultat.failed())
        self.assertEqual(self._lignes_audit(), 0)

    def test_tache_reussie_une_ligne(self):
        _, doublures = self._minio_double()
        for d in doublures:
            d.start()
            self.addCleanup(d.stop)
        with mock.patch('apps.ventes.tasks._idempotent_cached_key',
                        return_value=None), \
                mock.patch('apps.ventes.tasks._remember_render'):
            resultat = task_generate_devis_pdf.apply(
                args=[self.devis.pk, {'pdf_mode': 'onepage'}])
        self.assertTrue(resultat.successful(), resultat.traceback)
        self.assertEqual(self._lignes_audit(), 1)
