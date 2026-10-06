"""ADOC64 — Un destinataire dont l'authentification extra est requise
(auth_extra_effective ≠ 'aucune') ne signe JAMAIS sans code validé ; seule la
dégradation EXPLICITE « passerelle absente », posée par l'envoi du code,
laisse signer sans code.

Sources réelles : vue publique `public_signataire`, services GED, passerelle
`core.sms` réelle (aucune intégration configurée → sent=False) ; la seule
doublure est la passerelle SMS EXTERNE quand un envoi réussi est requis.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.ged import services
from apps.ged.models import (
    Cabinet, Document, Folder, RoleSignataire, SIGNATAIRE_NOTIFIE,
)

User = get_user_model()


class _SmsEnvoye:
    sent = True
    detail = ''
    provider = 'externe'
    message_id = 'm1'


class OtpObligatoireBase(TestCase):
    def setUp(self):
        self.co_a, _ = Company.objects.get_or_create(
            slug='adoc64-a', defaults={'nom': 'Adoc64 A'})
        self.admin = User.objects.create_user(
            username='adoc64-admin', password='x', company=self.co_a,
            role_legacy='admin')
        cab = Cabinet.objects.create(company=self.co_a, nom='Admin')
        folder = Folder.objects.create(
            company=self.co_a, cabinet=cab, nom='Contrats')
        self.doc = Document.objects.create(
            company=self.co_a, folder=folder, nom='contrat.pdf')
        role = RoleSignataire.objects.create(
            company=self.co_a, nom='Client', auth_extra='sms')
        demande = services.creer_demande_multi_signataires(
            self.doc, destinataires=[{
                'nom': 'A', 'email': 'a@x.ma', 'telephone': '+212600000000',
                'role_signataire': role.pk}],
            company=self.co_a, created_by=self.admin)
        self.signataire = demande.signataires.get()
        self.url = f'/api/django/ged/signataire/{self.signataire.token}/'
        self.anon = APIClient()

    def _signer(self):
        return self.anon.post(self.url, {
            'action': 'signer', 'consentement': True,
            'signature_texte': 'A'}, format='json')


class OtpObligatoireTests(OtpObligatoireBase):
    def test_get_expose_otp_requis_au_chargement(self):
        resp = self.anon.get(self.url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['otp_requis'])
        self.assertFalse(resp.data['otp_degrade'])

    def test_signer_sans_code_refuse(self):
        resp = self._signer()
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('Authentification supplémentaire requise',
                      resp.data['detail'])
        self.signataire.refresh_from_db()
        self.assertEqual(self.signataire.statut, SIGNATAIRE_NOTIFIE)
        self.assertFalse(self.signataire.otp_valide)

    def test_code_valide_puis_signer_200(self):
        captured = {}

        def _envoi(company, to, message):
            captured['code'] = message.split(':')[-1].strip()
            return _SmsEnvoye()

        with mock.patch('core.sms.send_sms', side_effect=_envoi):
            r1 = self.anon.post(self.url, {'action': 'envoyer-code'},
                                format='json')
        self.assertTrue(r1.data['envoye'], r1.data)
        r2 = self.anon.post(self.url, {
            'action': 'valider-code', 'code': captured['code']},
            format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.signataire.refresh_from_db()
        self.assertIsNotNone(self.signataire.otp_valide_le)
        self.assertEqual(self._signer().status_code, 200)

    def test_passerelle_absente_degrade_explicite(self):
        # Aucune intégration SMS configurée : la VRAIE passerelle répond
        # sent=False → dégradation explicite posée et journalisée.
        with self.assertLogs('apps.ged.services', level='WARNING'):
            resp = self.anon.post(self.url, {'action': 'envoyer-code'},
                                  format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['envoye'])
        self.assertTrue(resp.data['degrade'])
        self.signataire.refresh_from_db()
        self.assertTrue(self.signataire.otp_degrade)
        self.assertEqual(self.signataire.otp_code_hash, '')
        self.assertFalse(self.anon.get(self.url).data['otp_requis'])
        self.assertEqual(self._signer().status_code, 200)
