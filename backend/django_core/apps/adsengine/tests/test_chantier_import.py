"""PUB73 — Pipeline photo-chantier → créathèque.

Prouve : une photo de chantier s'importe en ``CreativeAsset(source_lane=
'chantier')`` avec provenance + métadonnées ville/kWc ; sans consentement client
actif (PUB75, portée photo) → refus EXPLIQUÉ (rien créé). La lecture de la photo
passe par ``installations.selectors`` (mockée ici — pas de fixture chantier).
"""
import datetime
from unittest import mock

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import creative_factory as cf
from apps.adsengine.models import ConsentRecord, CreativeAsset


class _FakeAttachment:
    def __init__(self, file_key):
        self.file_key = file_key


def make_consent(company, client_id=42, photo=True, **kw):
    defaults = dict(
        company=company, client_id=client_id, client_nom='Client Chantier',
        portee_photo=photo, date_consentement=datetime.date(2026, 1, 1))
    defaults.update(kw)
    return ConsentRecord.objects.create(**defaults)


class ChantierImportTests(TestCase):
    def setUp(self):
        _p = mock.patch(
            'apps.installations.selectors.chantier_client_id',
            return_value=42)
        _p.start()
        self.addCleanup(_p.stop)
        self.company = Company.objects.create(nom='Chantier Co', slug='chan-co')

    def _import(self, **kw):
        params = dict(chantier_id=7, attachment_id=99, client_id=42,
                      puissance_kwc=6.0, ville=None)
        params.update(kw)
        return cf.import_chantier_photo(self.company, **params)

    def test_import_with_consent_creates_asset(self):
        make_consent(self.company)
        with mock.patch('apps.installations.selectors.chantier_photo',
                        return_value=_FakeAttachment('chantier/7/photo.jpg')), \
                mock.patch('apps.installations.selectors.chantier_ville',
                           return_value='Fès'):
            res = self._import()
        self.assertTrue(res['imported'], res)
        asset = res['asset']
        self.assertEqual(asset.source_lane, 'chantier')
        self.assertTrue(asset.depicts_real_client)
        self.assertEqual(asset.file_key, 'chantier/7/photo.jpg')
        self.assertIsNotNone(asset.consent_id)
        self.assertFalse(asset.is_policy_passed)  # PENDING
        self.assertIn('Fès', asset.hook_text)
        self.assertIn('6 kWc', asset.hook_text)

    def test_blocked_without_consent(self):
        # Aucun ConsentRecord → refus expliqué, rien créé.
        with mock.patch('apps.installations.selectors.chantier_photo',
                        return_value=_FakeAttachment('x')):
            res = self._import()
        self.assertFalse(res['imported'])
        self.assertEqual(res['blocked_reason'], 'consentement_manquant')
        self.assertIn('CNDP', res['message'])
        self.assertEqual(CreativeAsset.objects.count(), 0)

    def test_blocked_when_consent_photo_scope_missing(self):
        make_consent(self.company, photo=False, portee_temoignage=True)
        with mock.patch('apps.installations.selectors.chantier_photo',
                        return_value=_FakeAttachment('x')):
            res = self._import()
        self.assertFalse(res['imported'])
        self.assertEqual(res['blocked_reason'], 'consentement_manquant')

    def test_photo_not_found(self):
        make_consent(self.company)
        with mock.patch('apps.installations.selectors.chantier_photo',
                        return_value=None):
            res = self._import()
        self.assertFalse(res['imported'])
        self.assertEqual(res['blocked_reason'], 'photo_introuvable')
        self.assertEqual(CreativeAsset.objects.count(), 0)

    def test_revoked_consent_blocks(self):
        c = make_consent(self.company)
        c.revoked_at = datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc)
        c.save(update_fields=['revoked_at'])
        with mock.patch('apps.installations.selectors.chantier_photo',
                        return_value=_FakeAttachment('x')):
            res = self._import()
        self.assertFalse(res['imported'])
        self.assertEqual(res['blocked_reason'], 'consentement_manquant')


class ImportChantierPhotoViewIdsTests(TestCase):
    """CAD177 — un identifiant non entier n'est plus un 500 (filtre ORM sur
    ``client_id='g'``, relevé par le marcheur aléatoire) mais un 400 FR."""

    def setUp(self):
        _p = mock.patch(
            'apps.installations.selectors.chantier_client_id',
            return_value=42)
        _p.start()
        self.addCleanup(_p.stop)
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        from apps.roles.models import Role

        self.company = Company.objects.create(nom='Ids Co', slug='ids-co')
        role = Role.objects.create(
            company=self.company, nom='ads-manage',
            permissions=['adsengine_manage'])
        user = get_user_model().objects.create_user(
            username='ads-ids', password='x', company=self.company,
            role_legacy='normal', role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')

    def _post(self, corps):
        return self.api.post(
            '/api/django/adsengine/creatifs/import-chantier/', corps,
            format='json')

    def test_client_id_non_entier_400(self):
        resp = self._post(
            {'chantier_id': 7, 'attachment_id': 99, 'client_id': 'g'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['field'], 'client_id')
        self.assertEqual(CreativeAsset.objects.count(), 0)

    def test_chantier_id_non_entier_400(self):
        resp = self._post({'chantier_id': 'abc', 'attachment_id': 99})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['field'], 'chantier_id')

    def test_sans_consentement_reste_un_refus_explique(self):
        with mock.patch('apps.installations.selectors.chantier_photo',
                        return_value=_FakeAttachment('x')):
            resp = self._post({'chantier_id': '7', 'attachment_id': '99',
                               'client_id': '42'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json()['blocked_reason'], 'consentement_manquant')
