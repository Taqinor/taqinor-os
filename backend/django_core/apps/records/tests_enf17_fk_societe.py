"""ENF17 — records : FK des sérialiseurs bornées société.

* ``TaggedItemSerializer.tag`` : la création passait déjà par
  ``get_company_object`` (vue), mais le PUT/PATCH générique du
  ``TaggedItemViewSet`` résolvait ``tag`` sans borne — on pouvait re-pointer
  une association vers le tag d'une AUTRE société. Désormais l'id d'ailleurs
  reçoit la réponse d'un id absent (400 « objet inexistant »).
* ``AttachmentSerializer.uploaded_by`` : faux positif de la garde (le
  sérialiseur est entièrement en lecture, ``read_only_fields = fields`` n'était
  pas lisible par l'AST) — la liste est maintenant littérale ; le test fige que
  le champ reste en lecture seule.

Run:
    python manage.py test apps.records.tests_enf17_fk_societe -v 2
"""
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.records.models import Tag, TaggedItem
from apps.records.serializers import AttachmentSerializer, TaggedItemSerializer
from authentication.models import Company

User = get_user_model()

ID_ABSENT = 99999999


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TaggedItemTagBorneTests(TestCase):
    def setUp(self):
        self.co_a = Company.objects.create(nom='enf17-rec-a', slug='enf17-rec-a')
        self.co_b = Company.objects.create(nom='enf17-rec-b', slug='enf17-rec-b')
        self.resp_a = User.objects.create_user(
            username='enf17-rec-resp-a', password='x',
            role_legacy='responsable', company=self.co_a)
        self.lead_a = Lead.objects.create(company=self.co_a, nom='Lead A')
        self.tag_a = Tag.objects.create(company=self.co_a, nom='Tag A')
        self.tag_a2 = Tag.objects.create(company=self.co_a, nom='Tag A2')
        self.tag_b = Tag.objects.create(company=self.co_b, nom='TAG-B-SECRET')
        self.item = TaggedItem.objects.create(
            tag=self.tag_a, content_type=ContentType.objects.get_for_model(Lead),
            object_id=self.lead_a.id)
        self.ctx = {'request': SimpleNamespace(user=self.resp_a)}

    def test_serializer_tag_etranger_comme_absent(self):
        ser = TaggedItemSerializer(data={'tag': self.tag_b.pk}, partial=True,
                                   context=self.ctx)
        self.assertFalse(ser.is_valid())
        self.assertEqual(ser.errors['tag'][0].code, 'does_not_exist')
        absent = TaggedItemSerializer(data={'tag': ID_ABSENT}, partial=True,
                                      context=self.ctx)
        self.assertFalse(absent.is_valid())
        self.assertEqual(
            str(ser.errors['tag'][0]).replace(str(self.tag_b.pk), '<ID>'),
            str(absent.errors['tag'][0]).replace(str(ID_ABSENT), '<ID>'))
        champ = TaggedItemSerializer(context=self.ctx).fields['tag']
        self.assertEqual(champ.to_internal_value(self.tag_a2.pk), self.tag_a2)

    def test_patch_tag_etranger_400(self):
        api = _api(self.resp_a)
        url = f'/api/django/records/tagged-items/{self.item.pk}/'
        r = api.patch(url, {'tag': self.tag_b.pk}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('tag', r.data)
        self.assertNotIn('TAG-B-SECRET', str(r.data))
        self.item.refresh_from_db()
        self.assertEqual(self.item.tag_id, self.tag_a.pk)
        r_ok = api.patch(url, {'tag': self.tag_a2.pk}, format='json')
        self.assertEqual(r_ok.status_code, 200, r_ok.data)
        self.item.refresh_from_db()
        self.assertEqual(self.item.tag_id, self.tag_a2.pk)


class AttachmentUploadedByLectureSeuleTests(TestCase):
    def test_uploaded_by_en_lecture_seule(self):
        champs = AttachmentSerializer().fields
        self.assertTrue(champs['uploaded_by'].read_only)
        # Rien n'est inscriptible sur ce sérialiseur (pièce posée par l'upload).
        self.assertEqual(
            [nom for nom, champ in champs.items() if not champ.read_only], [])
