"""NTMOB11 — capture multi-photos horodatées géotaguées par étape de
checklist. Couvre le nouveau modèle ``PhotoChecklistMeta`` et l'endpoint
``POST installations/chantiers/<id>/checklist-photo/`` (métadonnées d'une
pièce jointe DÉJÀ uploadée via le flux générique ``records.Attachment``).
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.installations.models import Installation, PhotoChecklistMeta
from apps.installations.services import (
    create_installation_from_devis, ensure_checklist_items,
)
from apps.records.models import Attachment
from apps.ventes.models import Devis

User = get_user_model()
_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    slug = slug or f'ntmob11-co-{n}'
    nom = nom or f'NTMOB11 Co {n}'
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_chantier(company, user):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'ntmob11-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-NTMOB11-{company.id}-{n}',
        client=client, lead=lead, statut=Devis.Statut.ACCEPTE,
        taux_tva=Decimal('20'))
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst


def make_attachment(company, inst, filename='photo.jpg'):
    ct = ContentType.objects.get_for_model(Installation)
    return Attachment.objects.create(
        company=company, content_type=ct, object_id=inst.id,
        file_key=f'attachments/{company.id}/{filename}', filename=filename,
        size=1024, mime='image/jpeg', phase='pendant')


class ChecklistPhotoMetaEndpointTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other_company = make_company()
        self.user = User.objects.create_user(
            username='ntmob11-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.normal_user = User.objects.create_user(
            username='ntmob11-normal', password='x', role_legacy='normal',
            company=self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)
        self.items = ensure_checklist_items(self.inst)
        self.cle = self.items[0].cle

    def _url(self):
        return f'/api/django/installations/chantiers/{self.inst.id}/checklist-photo/'

    def test_creates_meta_linked_to_attachment_and_item(self):
        att = make_attachment(self.company, self.inst)
        resp = self.api.post(self._url(), {
            'attachment': att.id, 'cle': self.cle,
            'latitude': 33.589, 'longitude': -7.603, 'precision_m': 8.5,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        meta = PhotoChecklistMeta.objects.get(attachment=att)
        self.assertEqual(meta.checklist_item_id, self.items[0].id)
        self.assertEqual(meta.company_id, self.company.id)
        self.assertEqual(meta.latitude, Decimal('33.589000'))
        self.assertEqual(meta.longitude, Decimal('-7.603000'))
        self.assertEqual(meta.precision_m, 8.5)
        self.assertIsNotNone(meta.horodatage_capture)

    def test_geoloc_is_optional(self):
        att = make_attachment(self.company, self.inst)
        resp = self.api.post(
            self._url(), {'attachment': att.id, 'cle': self.cle}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        meta = PhotoChecklistMeta.objects.get(attachment=att)
        self.assertIsNone(meta.latitude)
        self.assertIsNone(meta.longitude)
        self.assertIsNone(meta.precision_m)

    def test_missing_attachment_400(self):
        resp = self.api.post(self._url(), {'cle': self.cle}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_attachment_from_other_installation_404(self):
        other_inst = make_chantier(self.company, self.user)
        att = make_attachment(self.company, other_inst)
        resp = self.api.post(
            self._url(), {'attachment': att.id, 'cle': self.cle}, format='json')
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(PhotoChecklistMeta.objects.filter(attachment=att).exists())

    def test_attachment_from_other_company_404(self):
        other_user = User.objects.create_user(
            username='ntmob11-other', password='x', role_legacy='responsable',
            company=self.other_company)
        other_inst = make_chantier(self.other_company, other_user)
        att = make_attachment(self.other_company, other_inst)
        resp = self.api.post(
            self._url(), {'attachment': att.id, 'cle': self.cle}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_unknown_cle_leaves_checklist_item_null(self):
        # NTMOB11 — checklist_item est nullable : une photo prise hors
        # contexte checklist (cle absente/inconnue) n'a simplement pas de lien.
        att = make_attachment(self.company, self.inst)
        resp = self.api.post(self._url(), {'attachment': att.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        meta = PhotoChecklistMeta.objects.get(attachment=att)
        self.assertIsNone(meta.checklist_item_id)

    def test_idempotent_by_attachment(self):
        att = make_attachment(self.company, self.inst)
        body1 = {'attachment': att.id, 'cle': self.cle, 'latitude': 1, 'longitude': 1}
        r1 = self.api.post(self._url(), body1, format='json')
        self.assertEqual(r1.status_code, 201)
        body2 = {'attachment': att.id, 'cle': self.cle, 'latitude': 2, 'longitude': 2}
        r2 = self.api.post(self._url(), body2, format='json')
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(PhotoChecklistMeta.objects.filter(attachment=att).count(), 1)
        meta = PhotoChecklistMeta.objects.get(attachment=att)
        self.assertEqual(meta.latitude, Decimal('2.000000'))

    def test_normal_role_forbidden(self):
        att = make_attachment(self.company, self.inst)
        api = auth(self.normal_user)
        resp = api.post(
            self._url(), {'attachment': att.id, 'cle': self.cle}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_three_photos_on_one_step_produce_three_metas_and_count(self):
        # Critère d'acceptation NTMOB11 : 3 photos prises pour UNE étape.
        for _ in range(3):
            att = make_attachment(self.company, self.inst)
            body = {'attachment': att.id, 'cle': self.cle,
                    'latitude': 33.5, 'longitude': -7.6}
            resp = self.api.post(self._url(), body, format='json')
            self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            PhotoChecklistMeta.objects.filter(
                checklist_item=self.items[0]).count(), 3)
        # Consultable via la checklist (photos_count, sans requête séparée).
        r = self.api.get(
            f'/api/django/installations/chantiers/{self.inst.id}/checklist/')
        self.assertEqual(r.status_code, 200)
        item_data = next(it for it in r.data['items'] if it['cle'] == self.cle)
        self.assertEqual(item_data['photos_count'], 3)

    def test_deleting_checklist_item_keeps_photo_and_metadata(self):
        # SET_NULL : supprimer l'étape ne supprime JAMAIS la photo déjà prise.
        att = make_attachment(self.company, self.inst)
        self.api.post(
            self._url(), {'attachment': att.id, 'cle': self.cle}, format='json')
        self.items[0].delete()
        meta = PhotoChecklistMeta.objects.get(attachment=att)
        self.assertIsNone(meta.checklist_item_id)
        self.assertTrue(Attachment.objects.filter(id=att.id).exists())
