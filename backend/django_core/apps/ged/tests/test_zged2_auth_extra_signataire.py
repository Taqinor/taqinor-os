"""ZGED2 — Authentification extra du signataire par SMS/OTP email
(key-gated, no-op sans passerelle).

Couvre :
  * avec la passerelle SMS posée, un signataire en mode `sms` doit saisir le
    code reçu avant de signer ;
  * mauvais code / expiré -> refus tracé ;
  * épuisement des essais ;
  * sans passerelle, la demande se signe sans OTP et le résultat le note
    (no-op, aucun appel, aucune dépendance nouvelle) ;
  * isolation société.
"""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import Cabinet, Document, Folder, RoleSignataire

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _FakeSmsResult:
    def __init__(self, sent, detail=''):
        self.sent = sent
        self.detail = detail
        self.provider = 'fake'
        self.message_id = ''


class ZGed2Base(TestCase):
    def setUp(self):
        self.co_a = make_company('zged2-a', 'Zged2 A')
        self.admin_a = make_user(self.co_a, 'zged2-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Contrats')
        self.doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='contrat.pdf')

    def _demande_avec_sms(self, telephone='+212600000000'):
        role = RoleSignataire.objects.create(
            company=self.co_a, nom='Client SMS', auth_extra='sms')
        demande = services.creer_demande_multi_signataires(
            self.doc, destinataires=[
                {'nom': 'Client A', 'email': 'a@example.com',
                 'telephone': telephone, 'role_signataire': role.pk},
            ], company=self.co_a, created_by=self.admin_a)
        return demande.signataires.first()


class OtpServiceTests(ZGed2Base):
    def test_signature_bloquee_sans_otp_valide(self):
        signataire = self._demande_avec_sms()
        with mock.patch(
                'core.sms.send_sms', return_value=_FakeSmsResult(True)):
            services.envoyer_code_otp_signataire(signataire)
        signataire.refresh_from_db()
        with self.assertRaises(ValueError):
            services.signer_signataire(
                signataire, consentement=True, signature_texte='Client A')

    def test_bon_code_debloque_la_signature(self):
        signataire = self._demande_avec_sms()
        captured = {}

        def _fake_send(company, to, message):
            captured['message'] = message
            return _FakeSmsResult(True)

        with mock.patch('core.sms.send_sms', side_effect=_fake_send):
            services.envoyer_code_otp_signataire(signataire)
        signataire.refresh_from_db()
        code = captured['message'].split(':')[-1].strip()
        services.valider_code_otp_signataire(signataire, code)
        signataire.refresh_from_db()
        self.assertTrue(signataire.otp_valide)
        signataire = services.signer_signataire(
            signataire, consentement=True, signature_texte='Client A')
        self.assertEqual(signataire.statut, 'signe')

    def test_mauvais_code_refuse_et_trace_essai(self):
        signataire = self._demande_avec_sms()
        with mock.patch(
                'core.sms.send_sms', return_value=_FakeSmsResult(True)):
            services.envoyer_code_otp_signataire(signataire)
        signataire.refresh_from_db()
        with self.assertRaises(ValueError):
            services.valider_code_otp_signataire(signataire, '000000')
        signataire.refresh_from_db()
        self.assertEqual(signataire.otp_essais, 1)
        self.assertFalse(signataire.otp_valide)

    def test_code_expire_refuse(self):
        signataire = self._demande_avec_sms()
        with mock.patch(
                'core.sms.send_sms', return_value=_FakeSmsResult(True)):
            services.envoyer_code_otp_signataire(signataire)
        signataire.refresh_from_db()
        signataire.otp_expires_at = timezone.now() - datetime.timedelta(
            minutes=1)
        signataire.save(update_fields=['otp_expires_at'])
        with self.assertRaises(ValueError):
            services.valider_code_otp_signataire(signataire, '123456')

    def test_essais_epuises_refuse(self):
        signataire = self._demande_avec_sms()
        with mock.patch(
                'core.sms.send_sms', return_value=_FakeSmsResult(True)):
            services.envoyer_code_otp_signataire(signataire)
        signataire.refresh_from_db()
        for _ in range(3):
            with self.assertRaises(ValueError):
                services.valider_code_otp_signataire(signataire, '000000')
            signataire.refresh_from_db()
        with self.assertRaises(ValueError):
            services.valider_code_otp_signataire(signataire, '000000')

    def test_sans_passerelle_degrade_signature_sans_otp(self):
        signataire = self._demande_avec_sms()
        with mock.patch(
                'core.sms.send_sms',
                return_value=_FakeSmsResult(False, 'non configuré')):
            resultat = services.envoyer_code_otp_signataire(signataire)
        self.assertFalse(resultat['envoye'])
        self.assertEqual(resultat['mode'], 'aucune')
        signataire.refresh_from_db()
        # Pas d'OTP requis -> la signature passe directement (comportement
        # XGED1 inchangé).
        signataire = services.signer_signataire(
            signataire, consentement=True, signature_texte='Client A')
        self.assertEqual(signataire.statut, 'signe')

    def test_aucune_auth_extra_no_op(self):
        demande = services.creer_demande_multi_signataires(
            self.doc, destinataires=[
                {'nom': 'Client B', 'email': 'b@example.com'},
            ], company=self.co_a, created_by=self.admin_a)
        signataire = demande.signataires.first()
        resultat = services.envoyer_code_otp_signataire(signataire)
        self.assertEqual(resultat, {
            'envoye': False, 'mode': 'aucune',
            'detail': 'Aucune authentification extra requise.'})


class OtpViewTests(ZGed2Base):
    def test_endpoint_cycle_envoyer_valider_signer(self):
        signataire = self._demande_avec_sms()
        captured = {}

        def _fake_send(company, to, message):
            captured['message'] = message
            return _FakeSmsResult(True)

        with mock.patch('core.sms.send_sms', side_effect=_fake_send):
            resp = self.client.post(
                f'/api/django/ged/signataire/{signataire.token}/',
                {'action': 'envoyer-code'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['envoye'])
        code = captured['message'].split(':')[-1].strip()

        resp2 = self.client.post(
            f'/api/django/ged/signataire/{signataire.token}/',
            {'action': 'valider-code', 'code': code}, format='json')
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertFalse(resp2.data['otp_requis'])

        resp3 = self.client.post(
            f'/api/django/ged/signataire/{signataire.token}/',
            {'action': 'signer', 'consentement': True,
             'signature_texte': 'Client A'}, format='json')
        self.assertEqual(resp3.status_code, 200, resp3.data)
        self.assertEqual(resp3.data['statut'], 'signe')

    def test_signer_sans_otp_valide_400(self):
        signataire = self._demande_avec_sms()
        with mock.patch(
                'core.sms.send_sms', return_value=_FakeSmsResult(True)):
            self.client.post(
                f'/api/django/ged/signataire/{signataire.token}/',
                {'action': 'envoyer-code'}, format='json')
        resp = self.client.post(
            f'/api/django/ged/signataire/{signataire.token}/',
            {'action': 'signer', 'consentement': True,
             'signature_texte': 'Client A'}, format='json')
        self.assertEqual(resp.status_code, 400)
