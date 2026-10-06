"""ADOC26 — l'alias e-mail d'un dossier se saisit, se relit, est unique, et
un e-mail adressé à cet alias est classé dans le dossier.

Constat #36 de l'audit documents (2026-10-05) : PATCH {alias_email:'compta'}
ignoré (Folder.alias_email restait ''), donc importer_message_email == [].
"""
from email.message import EmailMessage
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged import services
from apps.ged.models import Cabinet, Folder
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ged/dossiers/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _email(to_addr):
    msg = EmailMessage()
    msg['From'] = 'fournisseur@example.com'
    msg['To'] = to_addr
    msg['Subject'] = 'Facture'
    msg['Message-ID'] = '<adoc26@x.com>'
    msg.set_content('Voir pièce jointe.')
    msg.add_attachment(b'%PDF-1.4\n%test\n%%EOF', maintype='application',
                       subtype='pdf', filename='facture.pdf')
    return msg.as_bytes()


class AliasEmailTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc26', defaults={'nom': 'ADOC26'})[0]
        self.resp = User.objects.create_user(
            username='adoc26-resp', password='x', company=self.co,
            role_legacy='responsable')
        self.cab = Cabinet.objects.create(company=self.co, nom='Cab')
        self.compta = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='Compta')
        self.autre = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='Autre')

    def test_patch_alias_persiste(self):
        api = auth(self.resp)
        resp = api.patch(f'{BASE}{self.compta.pk}/', {'alias_email': 'Compta'},
                         format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.compta.refresh_from_db()
        self.assertEqual(self.compta.alias_email, 'compta')
        relu = api.get(f'{BASE}{self.compta.pk}/')
        self.assertEqual(relu.data['alias_email'], 'compta')

    def test_email_classe(self):
        auth(self.resp).patch(f'{BASE}{self.compta.pk}/',
                              {'alias_email': 'compta'}, format='json')
        with mock.patch('apps.records.storage.store_attachment',
                        return_value=({'file_key': 'attachments/f.pdf',
                                       'filename': 'facture.pdf', 'size': 20,
                                       'mime': 'application/pdf'}, None)):
            crees = services.importer_message_email(
                _email('ged+compta@taqinor.ma'), company=self.co)
        self.assertEqual(len(crees), 1)
        self.assertEqual(crees[0].folder_id, self.compta.pk)

    def test_alias_unique(self):
        api = auth(self.resp)
        api.patch(f'{BASE}{self.compta.pk}/', {'alias_email': 'compta'},
                  format='json')
        resp = api.patch(f'{BASE}{self.autre.pk}/', {'alias_email': 'compta'},
                         format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('déjà utilisé', str(resp.data['alias_email']))
        self.autre.refresh_from_db()
        self.assertEqual(self.autre.alias_email, '')
