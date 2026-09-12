"""NTAPI2 — politique de dépréciation + en-têtes `Deprecation`/`Sunset`.

Critère d'acceptation, dans les deux sens :
  * appeler un endpoint DÉPRÉCIÉ renvoie `Deprecation: true`, `Sunset: <date>`
    (HTTP-date RFC 7231, comme l'exige la RFC 8594) avec la BONNE date, et
    `Link: <doc>; rel="deprecation"` ;
  * un endpoint COURANT ne renvoie AUCUN de ces en-têtes.

Couvre en plus la portée : une annonce ciblée sur une société ne fuite jamais
sur une autre, et une annonce datée dans le FUTUR n'est pas encore active.
"""
import datetime

from django.test import TestCase
from django.utils import timezone
from django.utils.http import http_date
from rest_framework.test import APIClient

from authentication.models import Company
from core.api_deprecation import DEFAULT_DEPRECATION_DOC_URL, deprecation_pour
from core.models import ApiDeprecation

from .constants import SCOPE_READ_LEADS
from .models import ApiKey


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def _key_client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


class Ntapi2DeprecationHeadersTests(TestCase):
    def setUp(self):
        self.co = _company('ntapi2', 'NTAPI2')
        self.autre = _company('ntapi2-autre', 'NTAPI2 autre')
        self.key, self.raw = ApiKey.issue(
            company=self.co, label='dep', scopes=[SCOPE_READ_LEADS])
        self.sunset = timezone.now() + datetime.timedelta(days=180)

    def _annonce(self, pattern='/api/public/v1/leads/*', **kwargs):
        champs = {
            'version': 'v1',
            'endpoint_pattern': pattern,
            'deprecated_at': timezone.now() - datetime.timedelta(days=1),
            'sunset_at': self.sunset,
            'message': 'Migrez vers /api/public/v1/leads-write/.',
        }
        champs.update(kwargs)
        return ApiDeprecation.objects.create(**champs)

    # ── Le cœur du critère ────────────────────────────────────────────────
    def test_endpoint_deprecie_renvoie_les_entetes_rfc8594(self):
        self._annonce()
        resp = _key_client(self.raw).get('/api/public/v1/leads/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Deprecation'], 'true')
        # RFC 8594 : Sunset est un HTTP-date, jamais un ISO-8601.
        self.assertEqual(resp['Sunset'], http_date(self.sunset.timestamp()))
        self.assertEqual(
            resp['Link'], f'<{DEFAULT_DEPRECATION_DOC_URL}>; rel="deprecation"')

    def test_endpoint_courant_ne_renvoie_aucun_entete(self):
        # Annonce posée sur une AUTRE ressource : /leads/ reste courant.
        self._annonce(pattern='/api/public/v1/produits/*')
        resp = _key_client(self.raw).get('/api/public/v1/leads/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Deprecation', resp)
        self.assertNotIn('Sunset', resp)
        self.assertNotIn('Link', resp)

    def test_aucune_annonce_du_tout_ne_pose_rien(self):
        resp = _key_client(self.raw).get('/api/public/v1/leads/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Deprecation', resp)

    # ── Portée & activation ───────────────────────────────────────────────
    def test_annonce_ciblee_ne_fuite_pas_sur_une_autre_societe(self):
        self._annonce(company=self.autre)
        resp = _key_client(self.raw).get('/api/public/v1/leads/')
        self.assertNotIn('Deprecation', resp)

    def test_annonce_ciblee_sur_ma_societe_sapplique(self):
        self._annonce(company=self.co)
        resp = _key_client(self.raw).get('/api/public/v1/leads/')
        self.assertEqual(resp['Deprecation'], 'true')

    def test_annonce_future_pas_encore_active(self):
        self._annonce(
            deprecated_at=timezone.now() + datetime.timedelta(days=30))
        resp = _key_client(self.raw).get('/api/public/v1/leads/')
        self.assertNotIn('Deprecation', resp)

    def test_annonce_inactive_ignoree(self):
        self._annonce(actif=False)
        resp = _key_client(self.raw).get('/api/public/v1/leads/')
        self.assertNotIn('Deprecation', resp)

    def test_lien_doc_personnalise_utilise(self):
        self._annonce(doc_url='/api/public/v1/errors/#deprecated_endpoint')
        resp = _key_client(self.raw).get('/api/public/v1/leads/')
        self.assertEqual(
            resp['Link'],
            '<%s>; rel="deprecation"' % '/api/public/v1/errors/#deprecated_endpoint')

    # ── Sélecteur de fondation ────────────────────────────────────────────
    def test_selecteur_retient_le_sunset_le_plus_proche(self):
        loin = self._annonce(pattern='/api/public/v1/*')
        proche = self._annonce(
            pattern='/api/public/v1/leads/*',
            sunset_at=timezone.now() + datetime.timedelta(days=10))
        trouve = deprecation_pour(
            '/api/public/v1/leads/', version='v1', company_id=self.co.id)
        self.assertEqual(trouve.pk, proche.pk)
        self.assertNotEqual(trouve.pk, loin.pk)

    def test_selecteur_ignore_une_autre_version(self):
        self._annonce(version='v2')
        self.assertIsNone(
            deprecation_pour('/api/public/v1/leads/', version='v1',
                             company_id=self.co.id))
