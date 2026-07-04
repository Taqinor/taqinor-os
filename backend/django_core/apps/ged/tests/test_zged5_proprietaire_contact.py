"""ZGED5 — Champ propriétaire/responsable + contact assigné sur le document
(panneau d'informations).

Couvre :
  * un gestionnaire réassigne le propriétaire d'un document et lui attache un
    client ;
  * les listes filtrent par propriétaire/contact ;
  * la résolution du libellé client passe par `crm.selectors` (dégrade
    proprement) ;
  * scoping société testé.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.ged.models import Cabinet, Document, Folder

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


class ZGed5Base(TestCase):
    def setUp(self):
        self.co_a = make_company('zged5-a', 'Zged5 A')
        self.admin_a = make_user(self.co_a, 'zged5-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Contrats')
        self.doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='contrat.pdf')
        self.client_a = Client.objects.create(
            company=self.co_a, nom='Alaoui', prenom='Karim')


class ViewTests(ZGed5Base):
    def test_gestionnaire_reassigne_proprietaire_et_contact(self):
        api = auth(self.admin_a)
        autre = make_user(self.co_a, 'zged5-autre-a', 'normal')
        resp = api.post(
            f'/api/django/ged/documents/{self.doc.pk}/assigner/',
            {'proprietaire': autre.pk, 'contact': self.client_a.pk},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['proprietaire'], autre.pk)
        self.assertEqual(resp.data['contact_id'], self.client_a.pk)
        self.assertEqual(resp.data['contact_label'], 'Karim Alaoui')
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.proprietaire_id, autre.pk)
        self.assertEqual(self.doc.contact_id, self.client_a.pk)

    def test_assigner_null_efface(self):
        self.doc.proprietaire = self.admin_a
        self.doc.contact_id = self.client_a.pk
        self.doc.save()
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/documents/{self.doc.pk}/assigner/',
            {'proprietaire': None, 'contact': None}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.doc.refresh_from_db()
        self.assertIsNone(self.doc.proprietaire_id)
        self.assertIsNone(self.doc.contact_id)

    def test_contact_autre_societe_rejete(self):
        co_b = make_company('zged5-b', 'Zged5 B')
        client_b = Client.objects.create(company=co_b, nom='Bennani')
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/documents/{self.doc.pk}/assigner/',
            {'contact': client_b.pk}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_liste_filtre_par_proprietaire_et_contact(self):
        autre = make_user(self.co_a, 'zged5-autre-a2', 'normal')
        doc2 = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='autre.pdf',
            proprietaire=autre)
        self.doc.contact_id = self.client_a.pk
        self.doc.save()
        api = auth(self.admin_a)
        resp = api.get(
            f'/api/django/ged/documents/?proprietaire={autre.pk}')
        ids = {d['id'] for d in resp.data['results']} \
            if isinstance(resp.data, dict) and 'results' in resp.data \
            else {d['id'] for d in resp.data}
        self.assertIn(doc2.pk, ids)
        self.assertNotIn(self.doc.pk, ids)
        resp2 = api.get(
            f'/api/django/ged/documents/?contact={self.client_a.pk}')
        ids2 = {d['id'] for d in resp2.data['results']} \
            if isinstance(resp2.data, dict) and 'results' in resp2.data \
            else {d['id'] for d in resp2.data}
        self.assertIn(self.doc.pk, ids2)
        self.assertNotIn(doc2.pk, ids2)

    def test_contact_label_absent_sans_contact(self):
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/ged/documents/{self.doc.pk}/')
        self.assertIsNone(resp.data['contact_label'])

    def test_isolation_societe_proprietaire(self):
        co_b = make_company('zged5-b2', 'Zged5 B2')
        admin_b = make_user(co_b, 'zged5-admin-b2', 'admin')
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/documents/{self.doc.pk}/assigner/',
            {'proprietaire': admin_b.pk}, format='json')
        self.assertEqual(resp.status_code, 404)
