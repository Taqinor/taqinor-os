"""AANA10 (C-AANA-029) — la référence externe d'import est TYPÉE.

Rouge figé par l'audit (05/10) : un lead L et un client C de même pk ; on
importe le lead avec ``external_id=A1`` puis des clients ``mode=maj`` avec
``external_id=A1`` → ``_find_by_external_id`` lisait la référence du LEAD et
renvoyait ``Client(pk=L.pk)`` : le client C était modifié
(``client.adresse='PWNED-…'``, ``updated=1``)."""
from django.contrib.contenttypes.models import ContentType

from apps.crm.models import Client, Lead

from .models import ExternalRef
from .tests import ImportBase

PK_COMMUN = 987654


class TestRefExterneTypee(ImportBase):
    def setUp(self):
        super().setUp()
        self.lead = Lead.objects.create(
            pk=PK_COMMUN, company=self.company, nom='Lead L',
            email='l@x.ma')
        self.client_c = Client.objects.create(
            pk=PK_COMMUN, company=self.company, nom='Client C',
            email='c@x.ma', adresse='Rue origine')
        # Le lead reçoit la référence A1 par un import upsert (rapproché par
        # e-mail : la référence est posée sur L).
        f = self._csv('Nom,Email,External_id\nLead L,l@x.ma,A1\n')
        resp = self.api.post('/api/django/imports/commit/', {
            'file': f, 'target': 'leads', 'mode': 'upsert',
        }, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['updated'], 1, resp.data)
        self.assertTrue(ExternalRef.objects.filter(
            company=self.company, external_id='A1',
            content_type=ContentType.objects.get_for_model(Lead),
            object_id=PK_COMMUN).exists())

    def test_ref_lead_ne_touche_pas_client(self):
        f = self._csv('Nom,Adresse,External_id\nZ,PWNED-adresse,A1\n')
        resp = self.api.post('/api/django/imports/commit/', {
            'file': f, 'target': 'clients', 'mode': 'maj', 'ecraser': 'true',
        }, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['updated'], 0, resp.data)
        self.client_c.refresh_from_db()
        self.assertEqual(self.client_c.adresse, 'Rue origine')
        self.assertEqual(self.client_c.nom, 'Client C')

    def test_upsert_client_a1_cree_sa_propre_reference(self):
        f = self._csv('Nom,Email,External_id\nNouveau,n@x.ma,A1\n')
        resp = self.api.post('/api/django/imports/commit/', {
            'file': f, 'target': 'clients', 'mode': 'upsert',
        }, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 1, resp.data)
        self.client_c.refresh_from_db()
        self.assertEqual(self.client_c.nom, 'Client C')
        nouveau = Client.objects.get(company=self.company, email='n@x.ma')
        ct_client = ContentType.objects.get_for_model(Client)
        # Deux références A1 coexistent : une par type (contrainte élargie).
        self.assertEqual(ExternalRef.objects.filter(
            company=self.company, external_id='A1').count(), 2)
        self.assertTrue(ExternalRef.objects.filter(
            company=self.company, external_id='A1', content_type=ct_client,
            object_id=nouveau.pk).exists())

        # Ré-import : le client A1 est retrouvé par SA référence.
        f = self._csv('Nom,Adresse,External_id\nNouveau,Rue neuve,A1\n')
        resp = self.api.post('/api/django/imports/commit/', {
            'file': f, 'target': 'clients', 'mode': 'maj',
        }, format='multipart')
        self.assertEqual(resp.data['updated'], 1, resp.data)
        nouveau.refresh_from_db()
        self.assertEqual(nouveau.adresse, 'Rue neuve')
        self.client_c.refresh_from_db()
        self.assertEqual(self.client_c.adresse, 'Rue origine')
