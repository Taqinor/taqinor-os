"""WIR164 — Chemin d'écriture pour les tampons société (`TamponSocieteViewSet`).

Avant ce ViewSet, `tampons_disponibles()` ne retombait QUE sur les 3 tampons
système (`TAMPONS_SYSTEME`) : aucun chemin d'écriture n'existait pour qu'une
société ajoute les siens (le modèle `TamponSociete` existait déjà, mais
seulement peuplable en base directement).

Couvre :
  * lecture ouverte à tout rôle, écriture (créer/supprimer) responsable/admin ;
  * `company` posée côté serveur ; isolation société ;
  * DONE (critère du plan) — « un tampon société propre se crée et s'appose » :
    un tampon créé via l'API apparaît IMMÉDIATEMENT dans
    `GET annotations/tampons/` (`services.tampons_disponibles`) ET peut être
    apposé sur un document via le chemin existant `POST annotations/`
    (`type_annotation='tampon'`), bout en bout via l'API.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged.models import (
    AnnotationDocument, Cabinet, Document, DocumentVersion, Folder,
    TAMPONS_SYSTEME, TamponSociete,
)

User = get_user_model()

BASE = '/api/django/ged/tampons-societe/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Wir164Base(TestCase):
    def setUp(self):
        self.co_a = make_company('wir164-a', 'WIR164 A')
        self.co_b = make_company('wir164-b', 'WIR164 B')
        self.admin_a = make_user(self.co_a, 'wir164-admin-a', 'admin')
        self.responsable_a = make_user(self.co_a, 'wir164-resp-a', 'responsable')
        self.normal_a = make_user(self.co_a, 'wir164-normal-a', 'normal')


class PermissionsTests(Wir164Base):
    def test_lecture_ouverte_a_tout_role(self):
        resp = auth(self.normal_a).get(BASE)
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_creation_refusee_a_un_role_normal(self):
        resp = auth(self.normal_a).post(
            BASE, {'libelle': 'Reçu'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_creation_autorisee_responsable_et_admin(self):
        for i, user in enumerate((self.responsable_a, self.admin_a)):
            resp = auth(user).post(
                BASE, {'libelle': f'Tampon {i}'}, format='json')
            self.assertEqual(resp.status_code, 201, resp.data)

    def test_company_posee_cote_serveur(self):
        resp = auth(self.admin_a).post(
            BASE, {'libelle': 'Archivé RH', 'company': 999999}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        tampon = TamponSociete.objects.get(id=resp.data['id'])
        self.assertEqual(tampon.company_id, self.co_a.id)

    def test_suppression_reservee_responsable_admin(self):
        tampon = TamponSociete.objects.create(
            company=self.co_a, libelle='Confidentiel')
        resp = auth(self.normal_a).delete(f'{BASE}{tampon.id}/')
        self.assertEqual(resp.status_code, 403, resp.data)
        resp = auth(self.admin_a).delete(f'{BASE}{tampon.id}/')
        self.assertEqual(resp.status_code, 204, resp.data)
        self.assertFalse(TamponSociete.objects.filter(id=tampon.id).exists())


class IsolationTests(Wir164Base):
    def test_isolation_societe(self):
        TamponSociete.objects.create(company=self.co_b, libelle='Autre société')
        resp = auth(self.admin_a).get(BASE)
        self.assertEqual(resp.data['count'], 0, resp.data)


class TamponBoutEnBoutTests(Wir164Base):
    """DONE — un tampon société propre se crée (API) ET s'appose (API)."""

    def setUp(self):
        super().setUp()
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Contrats')
        self.doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Bail commercial')
        self.version = DocumentVersion.objects.create(
            company=self.co_a, document=self.doc, version=1,
            file_key='attachments/bail.pdf', filename='bail.pdf',
            size=10, mime='application/pdf')

    def test_creation_puis_apposition_via_api(self):
        api = auth(self.admin_a)

        # 1) SE CRÉE — un tampon propre à la société, via l'API de gestion.
        resp = api.post(BASE, {'libelle': 'Archivé RH'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        tampon_id = resp.data['id']

        # Effet immédiat : le nouveau tampon apparaît dans le catalogue
        # combiné (système + société), déjà exposé par XGED16.
        resp = api.get('/api/django/ged/annotations/tampons/')
        self.assertEqual(resp.status_code, 200, resp.data)
        for systeme in TAMPONS_SYSTEME:
            self.assertIn(systeme, resp.data)
        self.assertIn('Archivé RH', resp.data)

        # 2) S'APPOSE — l'utilisateur pose ce tampon sur le document via le
        # chemin d'écriture EXISTANT (POST annotations/, type_annotation=
        # 'tampon') : aucune nouvelle route requise pour l'apposition.
        resp = api.post('/api/django/ged/annotations/', {
            'version': self.version.id, 'type_annotation': 'tampon',
            'page': 0, 'x': 10.0, 'y': 10.0, 'contenu': 'Archivé RH',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        annotation = AnnotationDocument.objects.get(id=resp.data['id'])
        self.assertEqual(annotation.type_annotation, 'tampon')
        self.assertEqual(annotation.contenu, 'Archivé RH')
        self.assertEqual(annotation.version_id, self.version.id)
        self.assertEqual(annotation.auteur_id, self.admin_a.id)

        # Suppression du tampon société : disparaît du catalogue, mais
        # l'apposition déjà posée reste (couche annotation séparée, jamais
        # rétroactivement modifiée).
        api.delete(f'{BASE}{tampon_id}/')
        resp = api.get('/api/django/ged/annotations/tampons/')
        self.assertNotIn('Archivé RH', resp.data)
        annotation.refresh_from_db()
        self.assertEqual(annotation.contenu, 'Archivé RH')
