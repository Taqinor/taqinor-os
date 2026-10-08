"""ADEV31 (C-ADEV-043) — un échec de rendu de ``/proposal`` ne sert plus le
texte brut de l'exception (hôte MinIO, bucket, chemin serveur) : message
neutre, exception journalisée avec sa pile.

L'échec est injecté en doublant la SEULE fonction de rendu (doublure déclarée,
comme la sonde VB r5) ; la vue est réelle.

Test-du-test : remettre ``f'… : {exc}'`` ⇒ le test échoue.
"""
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

SECRET = 'minio:9000 bucket=erp-pdf secret-path /app/x.py'


class ProposalErreurNeutreTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='adev31-co', nom='ADEV31')
        self.user = make_user(self.company)
        self.devis = make_devis(
            self.company, self.user, make_client(self.company),
            [('Onduleur hybride', '1', '12000')], reference='DEV-ADEV31-1')

    def test_aucun_texte_d_exception_servi(self):
        api = APIClient()
        api.force_authenticate(self.user)
        with mock.patch(
                'apps.ventes.quote_engine.generate_premium_devis_pdf',
                side_effect=RuntimeError(SECRET)), \
                self.assertLogs('apps.ventes.views.devis_pdf',
                                level='ERROR') as journal:
            resp = api.get(
                '/api/django/ventes/devis/%s/proposal/' % self.devis.pk)
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(
            resp.json(),
            {'detail': 'Génération de la proposition momentanément '
                       'indisponible.'})
        corps = resp.content.decode()
        for fragment in ('minio', 'bucket', 'erp-pdf', '/app/x.py'):
            self.assertNotIn(fragment, corps)
        # La pile est journalisée côté serveur.
        self.assertTrue(any(SECRET in ligne for ligne in journal.output))
