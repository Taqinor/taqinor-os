"""Tests FG196 — Bulletin de paie (lecture seule).

Couvre :
* Upload multipart (store_attachment mocké) : ``company`` + pièce jointe posées
  CÔTÉ SERVEUR ; FK employe d'une autre société refusé ; validation mois.
* Unicité (employe, annee, mois).
* ``mes-bulletins`` : le collaborateur connecté ne voit QUE ses bulletins.
* Suppression efface la pièce jointe.
* Isolation + permission (rôle normal refusé sur l'admin, autorisé sur
  mes-bulletins).
"""
from io import BytesIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.records.models import Attachment
from apps.rh.models import BulletinPaie, DossierEmploye

User = get_user_model()

URL = '/api/django/rh/bulletins-paie/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule, user=None):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='N', prenom='P', user=user)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


def _fake_store(file):
    return ({'file_key': 'attachments/bp.pdf', 'filename': 'bulletin.pdf',
             'size': 2048, 'mime': 'application/pdf'}, None)


def _upload(api, employe_id, annee=2026, mois=6, **extra):
    data = {'employe': employe_id, 'annee': annee, 'mois': mois}
    data.update(extra)
    pdf = BytesIO(b'%PDF-1.4 fake')
    pdf.name = 'bulletin.pdf'
    data['file'] = pdf
    with mock.patch('apps.rh.views.store_attachment', side_effect=_fake_store):
        return api.post(URL, data, format='multipart')


def make_attachment(company, employe):
    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(DossierEmploye)
    return Attachment.objects.create(
        company=company, content_type=ct, object_id=employe.id,
        file_key=f'attachments/{Attachment.objects.count()}.pdf',
        filename='b.pdf', size=10, mime='application/pdf')


class BulletinPaieTests(TestCase):
    def setUp(self):
        self.co_a = make_company('bp-a', 'A')
        self.co_b = make_company('bp-b', 'B')
        self.user_a = make_user(self.co_a, 'bp-user-a')
        self.user_b = make_user(self.co_b, 'bp-user-b')
        self.emp_a = make_employe(self.co_a, 'BP1', user=self.user_a)
        self.emp_b = make_employe(self.co_b, 'BP2')

    def test_upload_company_cote_serveur(self):
        resp = _upload(auth(self.user_a), self.emp_a.id)
        self.assertEqual(resp.status_code, 201, resp.data)
        bp = BulletinPaie.objects.get(id=resp.data['id'])
        self.assertEqual(bp.company, self.co_a)
        self.assertIsNotNone(bp.attachment_id)
        self.assertIn('download', resp.data['url'])

    def test_employe_autre_societe_refuse(self):
        resp = _upload(auth(self.user_a), self.emp_b.id)
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_mois_invalide_refuse(self):
        resp = _upload(auth(self.user_a), self.emp_a.id, mois=13)
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_unicite_employe_annee_mois(self):
        att1 = make_attachment(self.co_a, self.emp_a)
        BulletinPaie.objects.create(
            company=self.co_a, employe=self.emp_a, attachment=att1,
            annee=2026, mois=6)
        att2 = make_attachment(self.co_a, self.emp_a)
        with self.assertRaises(IntegrityError):
            BulletinPaie.objects.create(
                company=self.co_a, employe=self.emp_a, attachment=att2,
                annee=2026, mois=6)

    def test_mes_bulletins_ne_voit_que_les_siens(self):
        att1 = make_attachment(self.co_a, self.emp_a)
        BulletinPaie.objects.create(
            company=self.co_a, employe=self.emp_a, attachment=att1,
            annee=2026, mois=6)
        autre = make_employe(self.co_a, 'BP9')
        att2 = make_attachment(self.co_a, autre)
        BulletinPaie.objects.create(
            company=self.co_a, employe=autre, attachment=att2,
            annee=2026, mois=6)
        # user_a est lié à emp_a → ne voit que son bulletin.
        resp = auth(self.user_a).get(f'{URL}mes-bulletins/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)

    def test_mes_bulletins_sans_dossier_vide(self):
        orphan = make_user(self.co_a, 'bp-orphan', role='normal')
        resp = auth(orphan).get(f'{URL}mes-bulletins/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_suppression_efface_piece_jointe(self):
        att = make_attachment(self.co_a, self.emp_a)
        bp = BulletinPaie.objects.create(
            company=self.co_a, employe=self.emp_a, attachment=att,
            annee=2026, mois=6)
        with mock.patch('apps.rh.views.delete_attachment') as del_mock:
            resp = auth(self.user_a).delete(f'{URL}{bp.id}/')
        self.assertEqual(resp.status_code, 204)
        del_mock.assert_called_once()
        self.assertFalse(BulletinPaie.objects.filter(id=bp.id).exists())

    def test_isolation(self):
        att = make_attachment(self.co_a, self.emp_a)
        BulletinPaie.objects.create(
            company=self.co_a, employe=self.emp_a, attachment=att,
            annee=2026, mois=6)
        resp = auth(self.user_b).get(URL)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refuse_admin_liste(self):
        normal = make_user(self.co_a, 'bp-normal', role='normal')
        resp = auth(normal).get(URL)
        self.assertEqual(resp.status_code, 403)
