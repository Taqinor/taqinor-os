"""NTI18N4 — langue de sortie résolue, câblée sur `/proposal`.

Deux volets :
- `clean_pdf_options` whiteliste `langue_sortie` (fr/en/ar), rejette tout le
  reste sur le défaut historique `None` (unité pure, pas de DB) ;
- `DevisViewSet.proposal` résout systématiquement une langue (via
  `apps.parametres.i18n_resolver.resolve_langue_sortie`) et la transmet au
  moteur — `?langue=` explicite écrase, sinon `Client.langue_document` décide.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from testkit.factories import ClientFactory, DevisFactory, UserFactory
from apps.ventes.quote_engine.builder import clean_pdf_options

User = get_user_model()


class CleanPdfOptionsLangueSortieTests(TestCase):
    def test_default_is_none(self):
        self.assertIsNone(clean_pdf_options({})['langue_sortie'])

    def test_accepts_fr_en_ar(self):
        for langue in ('fr', 'en', 'ar'):
            self.assertEqual(
                clean_pdf_options({'langue_sortie': langue})['langue_sortie'],
                langue)

    def test_rejects_unknown_value(self):
        self.assertIsNone(
            clean_pdf_options({'langue_sortie': 'darija'})['langue_sortie'])
        self.assertIsNone(
            clean_pdf_options({'langue_sortie': ''})['langue_sortie'])


def _auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ProposalLangueQueryParamTests(TestCase):
    def setUp(self):
        self.user = UserFactory(role_legacy='responsable')
        self.company = self.user.company
        self.client_ar = ClientFactory(company=self.company, langue_document='ar')
        self.devis = DevisFactory(company=self.company, client=self.client_ar)
        self.api = _auth_client(self.user)

    def _get_proposal(self, query=''):
        with mock.patch(
            'apps.ventes.quote_engine.generate_premium_devis_pdf',
            return_value='fake-key',
        ) as gen_mock, mock.patch(
            'apps.ventes.utils.pdf.download_pdf',
            return_value=b'%PDF-1.4 fake',
        ):
            resp = self.api.get(
                f'/api/django/ventes/devis/{self.devis.id}/proposal/{query}')
        return resp, gen_mock

    def test_auto_resolves_from_client_langue_document(self):
        resp, gen_mock = self._get_proposal()
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        opts = gen_mock.call_args[0][1]
        self.assertEqual(opts['langue_sortie'], 'ar')

    def test_explicit_query_param_overrides_client(self):
        resp, gen_mock = self._get_proposal('?langue=en')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        opts = gen_mock.call_args[0][1]
        self.assertEqual(opts['langue_sortie'], 'en')

    def test_invalid_explicit_query_param_falls_back_to_client(self):
        resp, gen_mock = self._get_proposal('?langue=klingon')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        opts = gen_mock.call_args[0][1]
        self.assertEqual(opts['langue_sortie'], 'ar')

    def test_client_without_langue_document_preference_defaults_fr(self):
        client_fr = ClientFactory(company=self.company, langue_document='fr')
        devis_fr = DevisFactory(company=self.company, client=client_fr)
        with mock.patch(
            'apps.ventes.quote_engine.generate_premium_devis_pdf',
            return_value='fake-key',
        ) as gen_mock, mock.patch(
            'apps.ventes.utils.pdf.download_pdf',
            return_value=b'%PDF-1.4 fake',
        ):
            resp = self.api.get(
                f'/api/django/ventes/devis/{devis_fr.id}/proposal/')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        opts = gen_mock.call_args[0][1]
        self.assertEqual(opts['langue_sortie'], 'fr')
