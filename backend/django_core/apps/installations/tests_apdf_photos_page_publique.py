"""APDF38 (C-APDF-012) / ACHT68 (C-ACHT-065) — la page publique du rapport
d'intervention sert ses photos par une route À JETON qui vérifie
l'appartenance de la pièce à l'intervention du jeton ; la route authentifiée
`records/attachments/<id>/download/` n'apparaît plus dans la charge utile.

Seule la lecture de l'objet stocké (MinIO) est remplacée par un faux.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_apdf_photos_page_publique"
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company

from apps.installations import field_services
from apps.installations.models import Installation, Intervention
from apps.records.models import Attachment

User = get_user_model()
PUBLIC = '/api/django/public/installations/intervention-rapport'
OCTETS = b'\xff\xd8\xff\xe0JFIF-test'


class PhotosPagePubliqueTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-apdf38', defaults={'nom': 'Co APDF38'})
        self.user = User.objects.create_user(
            username='resp-apdf38', password='x', company=self.company,
            role_legacy='responsable')
        inst = Installation.objects.create(
            company=self.company, reference='CH-APDF38')
        self.iv = self._iv(inst)
        self.autre = self._iv(inst)
        field_services.seed_shotlist_slots(self.company)
        self.slot = next(
            s for s in field_services.active_shotlist(self.company)
            if s.phase == 'avant')
        self.p1 = self._photo(self.iv, 1)
        self.p2 = self._photo(self.iv, 2)
        self.etrangere = self._photo(self.autre, 3)
        self.token = self.iv.ensure_lien_rapport_token()

    def _iv(self, inst):
        return Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', created_by=self.user,
            technicien=self.user, statut=Intervention.Statut.VALIDEE)

    def _photo(self, iv, n):
        ct = ContentType.objects.get_for_model(Intervention)
        return Attachment.objects.create(
            company=self.company, content_type=ct, object_id=iv.id,
            file_key=f'k/apdf38/{n}', mime='image/jpeg',
            filename=field_services.encode_slot_filename(
                self.slot.cle, f'p{n}.jpg'))

    def _fetch(self):
        return mock.patch('apps.records.storage.fetch_attachment',
                          lambda key: (OCTETS, None))

    def test_payload_urls_tokenisees(self):
        r = self.client.get(f'{PUBLIC}/{self.token}/')
        self.assertEqual(r.status_code, 200)
        urls = [p['url'] for p in r.data['photos']['avant']]
        self.assertEqual(len(urls), 2)
        for url in urls:
            self.assertIn(f'/intervention-rapport/{self.token}/photo', url)
            self.assertNotIn('records/attachments', url)

    def test_photo_200_anonyme(self):
        r = self.client.get(f'{PUBLIC}/{self.token}/')
        with self._fetch():
            for photo in r.data['photos']['avant']:
                rep = self.client.get(photo['url'])
                self.assertEqual(rep.status_code, 200)
                self.assertEqual(rep['Content-Type'], 'image/jpeg')
                self.assertEqual(rep.content, OCTETS)
            # Alias ACHT68 (`photos/<id>/`).
            rep = self.client.get(
                f'{PUBLIC}/{self.token}/photos/{self.p1.id}/')
            self.assertEqual(rep.status_code, 200)

    def test_piece_etrangere_404(self):
        with self._fetch():
            rep = self.client.get(
                f'{PUBLIC}/{self.token}/photo/{self.etrangere.id}/')
            self.assertEqual(rep.status_code, 404)
            rep = self.client.get(
                f'{PUBLIC}/jeton-invalide/photo/{self.p1.id}/')
            self.assertEqual(rep.status_code, 404)
