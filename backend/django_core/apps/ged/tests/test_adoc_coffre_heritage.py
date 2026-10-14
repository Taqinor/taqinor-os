"""ADOC4 — les documents dérivés héritent du coffre ; un coffre non vide ne
se supprime pas.

Rejoue les sondes #4/#5 de l'audit documents (2026-10-05) : la source était
invisible d'U2 (404) mais ses segments scindés naissaient hors coffre
(visibles, 200) ; DELETE d'un coffre non vide → 204 et ses documents
devenaient visibles de tous.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged import services
from apps.ged.models import Cabinet, Coffre, Document, Folder
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ged/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _pdf(pages):
    import fitz
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page()
    out = doc.tobytes()
    doc.close()
    return out


class CoffreHeritageTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc4', defaults={'nom': 'ADOC4'})[0]
        self.admin = User.objects.create_user(
            username='adoc4-admin', password='x', company=self.co,
            role_legacy='admin')
        self.u1 = User.objects.create_user(
            username='adoc4-u1', password='x', company=self.co,
            role_legacy='responsable')
        self.u2 = User.objects.create_user(
            username='adoc4-u2', password='x', company=self.co,
            role_legacy='normal')
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=cab, nom='R')
        self.coffre = Coffre.objects.create(
            company=self.co, nom='Coffre U1', proprietaire=self.u1)
        self.coffre_autre = Coffre.objects.create(
            company=self.co, nom='Coffre admin', proprietaire=self.admin)
        self.d = self._doc('D', self.coffre)
        self.d2 = self._doc('D2', self.coffre)
        self.e = self._doc('E', self.coffre_autre)

    def _doc(self, nom, coffre):
        doc = Document.objects.create(
            company=self.co, folder=self.folder, nom=nom, coffre=coffre)
        services.add_version(doc, file_key=f'attachments/{nom}.pdf',
                             company=self.co, uploaded_by=self.u1)
        return doc

    def _patches(self, octets):
        compteur = iter(range(1000))
        return (
            mock.patch('apps.ged.services._fetch_version_bytes',
                       return_value=(octets, None)),
            mock.patch('apps.ged.services._store_bytes',
                       side_effect=lambda data, mime='application/pdf': (
                           f'attachments/seg-{next(compteur)}.pdf',
                           {'filename': 'seg.pdf', 'size': len(data),
                            'mime': 'application/pdf'})),
        )

    def test_scinder_herite_coffre(self):
        p1, p2 = self._patches(_pdf(3))
        with p1, p2:
            resp = auth(self.u1).post(
                f'{BASE}documents/{self.d.pk}/scinder/',
                {'points_de_coupe': [1, 2]}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        ids = [s['id'] for s in resp.data]
        self.assertEqual(len(ids), 2)
        for seg in Document.objects.filter(pk__in=ids):
            self.assertEqual(seg.coffre_id, self.coffre.pk)
            self.assertEqual(seg.created_by_id, self.u1.pk)
        for pk in ids:
            self.assertEqual(
                auth(self.u2).get(f'{BASE}documents/{pk}/').status_code, 404)

    def test_fusion_meme_coffre(self):
        p1, p2 = self._patches(_pdf(1))
        with p1, p2:
            resp = auth(self.u1).post(f'{BASE}documents/fusionner/', {
                'documents': [self.d.pk, self.d2.pk]}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        fusion = Document.objects.get(pk=resp.data['id'])
        self.assertEqual(fusion.coffre_id, self.coffre.pk)
        self.assertEqual(fusion.created_by_id, self.u1.pk)
        self.assertEqual(
            auth(self.u2).get(f'{BASE}documents/{fusion.pk}/').status_code,
            404)

    def test_fusion_coffres_differents_400(self):
        avant = Document.objects.count()
        p1, p2 = self._patches(_pdf(1))
        with p1, p2:
            resp = auth(self.admin).post(f'{BASE}documents/fusionner/', {
                'documents': [self.d.pk, self.e.pk]}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('coffres différents', resp.data['detail'])
        self.assertEqual(Document.objects.count(), avant)

    def test_fusion_hors_coffre_inchangee(self):
        a = self._doc('A', None)
        b = self._doc('B', None)
        p1, p2 = self._patches(_pdf(1))
        with p1, p2:
            fusion = services.fusionner_pdf([a, b], company=self.co,
                                            created_by=self.u1)
        self.assertIsNone(fusion.coffre_id)

    def test_supprimer_coffre_non_vide_409(self):
        resp = auth(self.admin).delete(f'{BASE}coffres/{self.coffre.pk}/')
        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertIn('2 document(s)', resp.data['detail'])
        self.d.refresh_from_db()
        self.assertEqual(self.d.coffre_id, self.coffre.pk)
        self.assertEqual(
            auth(self.u2).get(f'{BASE}documents/{self.d.pk}/').status_code,
            404)
        self.assertTrue(Coffre.objects.filter(pk=self.coffre.pk).exists())
        vide = Coffre.objects.create(
            company=self.co, nom='Vide', proprietaire=self.u1)
        resp = auth(self.admin).delete(f'{BASE}coffres/{vide.pk}/')
        self.assertEqual(resp.status_code, 204, resp.content)


class CoffreProprietaireContratTests(TestCase):
    """CI #998 api-fuzz — PUT /coffres/{id}/ : le propriétaire se REMPLACE,
    il ne se vide pas (``null`` ⇒ 400 « non nullable », le schéma l'annonce) ;
    un corps sans owner garde l'owner en place ; les deux owners ⇒ 400."""

    def setUp(self):
        from apps.crm.models import Client
        self.co = Company.objects.get_or_create(
            slug='adoc4b', defaults={'nom': 'ADOC4b'})[0]
        self.admin = User.objects.create_user(
            username='adoc4b-admin', password='x', company=self.co,
            role_legacy='admin')
        self.u1 = User.objects.create_user(
            username='adoc4b-u1', password='x', company=self.co,
            role_legacy='normal')
        self.client_crm = Client.objects.create(
            company=self.co, nom='Client coffre', email='coffre@example.com')
        self.coffre = Coffre.objects.create(
            company=self.co, nom='Coffre U1', proprietaire=self.u1)
        self.api = auth(self.admin)
        self.url = f'{BASE}coffres/{self.coffre.pk}/'

    def test_put_sans_owner_garde_le_proprietaire(self):
        resp = self.api.put(self.url, {'nom': 'Renommé'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.coffre.refresh_from_db()
        self.assertEqual(self.coffre.nom, 'Renommé')
        self.assertEqual(self.coffre.proprietaire_id, self.u1.pk)
        self.assertIsNone(self.coffre.client_id)

    def test_put_client_transfere_la_propriete(self):
        resp = self.api.put(
            self.url, {'nom': 'Coffre client', 'client': self.client_crm.pk},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.coffre.refresh_from_db()
        self.assertEqual(self.coffre.client_id, self.client_crm.pk)
        self.assertIsNone(self.coffre.proprietaire_id)
        # Retour vers un employé : le client est effacé.
        resp = self.api.put(
            self.url, {'nom': 'Coffre U1', 'proprietaire': self.u1.pk},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.coffre.refresh_from_db()
        self.assertEqual(self.coffre.proprietaire_id, self.u1.pk)
        self.assertIsNone(self.coffre.client_id)

    def test_put_owner_nul_ou_double_400(self):
        for corps in ({'nom': 'x', 'proprietaire': None},
                      {'nom': 'x', 'client': None},
                      {'nom': 'x', 'proprietaire': self.u1.pk,
                       'client': self.client_crm.pk}):
            resp = self.api.put(self.url, corps, format='json')
            self.assertEqual(resp.status_code, 400, (corps, resp.content))
        self.coffre.refresh_from_db()
        self.assertEqual(self.coffre.proprietaire_id, self.u1.pk)

    def test_post_sans_owner_reste_400(self):
        resp = self.api.post(f'{BASE}coffres/', {'nom': 'Orphelin'},
                             format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
