"""ADEV20 (C-ADEV-021) — « Code envoyé. » seulement si un code est
réellement parti.

* client sans e-mail (WhatsApp = stub, QX10) : demande du code de lecture et
  du code de signature → 409 ``{detail, code: "aucun_canal"}`` (contrat
  ``proposal_accept.json``, bloc ``otp``), aucun code mis en cache ;
* ``POST /share-link/ {otp_lecture: true}`` sur ce devis → 400
  ``{otp_lecture: [...]}``, lien inchangé ;
* client avec e-mail (backend locmem) : le code part, « Code envoyé. ».

Test-du-test : rétablir la réponse 200 inconditionnelle ⇒
``test_otp_lecture_409_sans_canal`` échoue.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_adev20_otp_sans_canal -v 2
"""
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.ventes.domain.cycle_vie import (
    _otp_cache_key, _otp_lecture_cache_key,
)
from apps.ventes.models import Devis, ShareLink
from authentication.models import Company

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'proposal_accept.json').read_text(encoding='utf-8'))
REFUS_409 = CONTRAT['otp']['reponse_409']
REPONSE_200 = CONTRAT['otp']['reponse_200']


@override_settings(
    CACHES={'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class OtpSansCanalTests(TestCase):

    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='ADEV20 Co', slug='adev20-co')
        self.user = User.objects.create_user(
            username='adev20_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.sans_email = Client.objects.create(
            company=self.company, nom='Sans', email='',
            telephone='+212600000020')
        self.avec_email = Client.objects.create(
            company=self.company, nom='Avec', email='adev20@example.com',
            telephone='+212600000021')
        self.n = 0

    def _lien(self, client, otp_lecture=True):
        self.n += 1
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ADEV20-{self.n:03d}',
            client=client, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), created_by=self.user)
        lien = ShareLink.for_devis(devis)
        lien.otp_lecture = otp_lecture
        lien.save(update_fields=['otp_lecture'])
        return lien

    def _post(self, lien, suffixe):
        return APIClient().post(
            f'/api/django/public/proposal/{lien.token}/{suffixe}/', {},
            format='json')

    def test_otp_lecture_409_sans_canal(self):
        lien = self._lien(self.sans_email)
        reponse = self._post(lien, 'otp-lecture/demander')
        self.assertEqual(reponse.status_code, 409, reponse.content)
        self.assertEqual(reponse.json(), REFUS_409)
        self.assertIsNone(cache.get(_otp_lecture_cache_key(lien.token)))
        self.assertEqual(len(mail.outbox), 0)

    def test_otp_signature_409_sans_canal(self):
        lien = self._lien(self.sans_email, otp_lecture=False)
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '1'}):
            reponse = self._post(lien, 'otp')
        self.assertEqual(reponse.status_code, 409, reponse.content)
        self.assertEqual(reponse.json(), REFUS_409)
        self.assertIsNone(cache.get(_otp_cache_key(lien.token)))
        self.assertEqual(len(mail.outbox), 0)

    def test_share_link_otp_lecture_400(self):
        lien = self._lien(self.sans_email, otp_lecture=False)
        api = APIClient()
        api.force_authenticate(user=self.user)
        reponse = api.post(
            f'/api/django/ventes/devis/{lien.devis_id}/share-link/',
            {'otp_lecture': True}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.content)
        self.assertIn('otp_lecture', reponse.json())
        lien.refresh_from_db()
        self.assertFalse(lien.otp_lecture)

    def test_email_present_code_envoye(self):
        lien = self._lien(self.avec_email)
        reponse = self._post(lien, 'otp-lecture/demander')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(reponse.json(), REPONSE_200)
        self.assertIsNotNone(cache.get(_otp_lecture_cache_key(lien.token)))
        self.assertEqual(len(mail.outbox), 1)
        with patch.dict('os.environ', {'ESIGN_OTP_ENABLED': '1'}):
            reponse = self._post(lien, 'otp')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(reponse.json(), REPONSE_200)
