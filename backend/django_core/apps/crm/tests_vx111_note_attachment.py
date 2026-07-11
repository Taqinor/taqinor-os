"""VX111 — attacher une pièce jointe à une note du chatter lead.

Correction du critic Fable : le Lead a DÉJÀ un point d'entrée pièce-jointe
fonctionnel (`records.Attachment` whiteliste `('crm','lead')`,
`AttachmentsPanel`) — le vrai manque, étroit, était : (a) une pièce jointe
n'était pas RATTACHABLE à une note du chatter (le composer `noter` postait
en texte pur uniquement), (b) `AttachmentsPanel` reste réellement présent
dans le flux mobile (nav rail — déjà vrai, pas un manque).

Cette suite couvre le point (a) : `POST .../noter/` accepte désormais un
fichier multipart optionnel, crée UNE `records.Attachment` (magasin RETENU,
jamais un second magasin), la lie à la `LeadActivity` créée, et
`LeadActivitySerializer` expose son URL de téléchargement (même proxy Django
que `AttachmentsPanel`, jamais MinIO direct). Le comportement JSON existant
(note texte seule, sans fichier) reste STRICTEMENT inchangé (non-régression).
"""
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import LeadActivity
from apps.records.models import Attachment

User = get_user_model()

# PNG magic bytes minimal (suffisant pour passer la détection de type).
_FAKE_PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 40


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NoterAttachmentTests(TestCase):
    def setUp(self):
        self.company = make_company('vx111-a', 'A')
        self.user = make_user(self.company, 'vx111-user')
        self.api = auth(self.user)
        resp = self.api.post('/api/django/crm/leads/', {'nom': 'VX111 Lead'})
        self.assertEqual(resp.status_code, 201, resp.data)
        self.lead_id = resp.data['id']

    def _noter_url(self):
        return f'/api/django/crm/leads/{self.lead_id}/noter/'

    # ── Non-régression : note texte pure (JSON), comportement inchangé ──────

    def test_note_json_sans_fichier_inchangee(self):
        resp = self.api.post(
            self._noter_url(), {'body': 'Note texte simple'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['body'], 'Note texte simple')
        self.assertIsNone(resp.data['attachment_url'])
        self.assertEqual(Attachment.objects.count(), 0)

    def test_note_vide_sans_fichier_toujours_400(self):
        resp = self.api.post(self._noter_url(), {'body': ''}, format='json')
        self.assertEqual(resp.status_code, 400)

    # ── Nouveau : note + pièce jointe (multipart) ────────────────────────────

    def test_note_avec_fichier_cree_une_seule_attachment_liee(self):
        upload = SimpleUploadedFile('photo.png', _FAKE_PNG, content_type='image/png')
        resp = self.api.post(
            self._noter_url(),
            {'body': 'Photo du chantier', 'file': upload},
            format='multipart',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['body'], 'Photo du chantier')
        self.assertIsNotNone(resp.data['attachment_url'])
        self.assertEqual(resp.data['attachment_filename'], 'photo.png')

        # UNE SEULE attachment créée — pas de second magasin, pas de doublon.
        self.assertEqual(Attachment.objects.count(), 1)
        att = Attachment.objects.get()
        self.assertEqual(att.company_id, self.company.id)

        # La pièce jointe cible le LEAD (donc visible aussi dans
        # AttachmentsPanel, qui liste model='crm.lead' id=<lead_id>).
        ct = ContentType.objects.get(app_label='crm', model='lead')
        self.assertEqual(att.content_type_id, ct.id)
        self.assertEqual(att.object_id, self.lead_id)

        # La LeadActivity (note) porte bien la référence à cette attachment.
        act = LeadActivity.objects.get(lead_id=self.lead_id, kind='note')
        self.assertEqual(act.attachment_id, att.id)

    def test_note_sans_body_mais_avec_fichier_est_acceptee(self):
        # Photo seule, sans texte — la note reçoit un corps par défaut plutôt
        # que d'échouer (une pièce jointe EST du contenu).
        upload = SimpleUploadedFile('photo2.png', _FAKE_PNG, content_type='image/png')
        resp = self.api.post(
            self._noter_url(), {'file': upload}, format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNotNone(resp.data['attachment_url'])

    def test_attachment_visible_dans_attachmentspanel_du_lead(self):
        # Non-duplication : la pièce jointe créée via noter() apparaît dans
        # la MÊME liste que records.attachments?model=crm.lead&id=<id>
        # (le point d'entrée AttachmentsPanel existant — jamais un 2e magasin).
        upload = SimpleUploadedFile('photo3.png', _FAKE_PNG, content_type='image/png')
        self.api.post(
            self._noter_url(), {'body': 'note', 'file': upload}, format='multipart')
        listing = self.api.get(
            '/api/django/records/attachments/',
            {'model': 'crm.lead', 'id': self.lead_id},
        )
        self.assertEqual(listing.status_code, 200, listing.data)
        results = listing.data.get('results', listing.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['filename'], 'photo3.png')

    def test_fichier_invalide_400_aucune_note_ni_attachment_creee(self):
        upload = SimpleUploadedFile('bad.txt', b'not-a-real-image', content_type='text/plain')
        resp = self.api.post(
            self._noter_url(), {'body': 'x', 'file': upload}, format='multipart')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Attachment.objects.count(), 0)
        self.assertEqual(LeadActivity.objects.filter(kind='note').count(), 0)

    def test_company_scoping_attachment(self):
        upload = SimpleUploadedFile('photo4.png', _FAKE_PNG, content_type='image/png')
        self.api.post(
            self._noter_url(), {'body': 'x', 'file': upload}, format='multipart')
        other_company = make_company('vx111-b', 'B')
        other_user = make_user(other_company, 'vx111-other')
        other_api = auth(other_user)
        listing = other_api.get(
            '/api/django/records/attachments/',
            {'model': 'crm.lead', 'id': self.lead_id},
        )
        # Cible hors société → aucun résultat (jamais une fuite inter-société).
        self.assertIn(listing.status_code, (200, 400))
        if listing.status_code == 200:
            results = listing.data.get('results', listing.data)
            self.assertEqual(len(results), 0)
