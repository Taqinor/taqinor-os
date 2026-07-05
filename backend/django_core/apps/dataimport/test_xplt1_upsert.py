"""XPLT1 — mode maj/upsert + identifiant externe (ExternalRef) sur l'import
générique. Réutilise le cadre de test de ``tests.py`` (ImportBase)."""
from django.contrib.contenttypes.models import ContentType

from apps.crm.models import Client, Lead
from authentication.models import Company

from .models import ExternalRef
from .tests import ImportBase


class TestModeCreerInchange(ImportBase):
    """Comportement par défaut (mode absent = ``creer``) strictement identique
    à avant XPLT1 : création seule, doublon ignoré, aucune ligne de
    ``ExternalRef`` créée."""

    def test_default_mode_still_create_only(self):
        Lead.objects.create(company=self.company, nom='Old', email='dup@x.ma')
        f = self._csv('Nom,Email\nAlaoui,new@x.ma\nDoublon,dup@x.ma\n')
        resp = self.api.post(
            '/api/django/imports/commit/',
            {'file': f, 'target': 'leads'}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['mode'], 'creer')
        self.assertEqual(resp.data['created'], 1)
        self.assertEqual(resp.data['updated'], 0)
        self.assertEqual(len(resp.data['skipped']), 1)
        self.assertFalse(ExternalRef.objects.exists())


class TestModeUpsertLeads(ImportBase):
    def test_upsert_reimport_same_file_updates_no_duplicate(self):
        f1 = self._csv('Nom,Email,Telephone,External_id\n'
                       'Alaoui,a@x.ma,0600000000,ODOO-1\n')
        resp1 = self.api.post(
            '/api/django/imports/commit/',
            {'file': f1, 'target': 'leads', 'mode': 'upsert'}, format='multipart')
        self.assertEqual(resp1.status_code, 200, resp1.data)
        self.assertEqual(resp1.data['created'], 1)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 1)
        self.assertEqual(ExternalRef.objects.count(), 1)

        # Ré-import du MÊME fichier + un champ modifié (ville) : pas de doublon,
        # le champ modifié est mis à jour.
        f2 = self._csv('Nom,Email,Telephone,External_id,Ville\n'
                       'Alaoui,a@x.ma,0600000000,ODOO-1,Casablanca\n')
        resp2 = self.api.post(
            '/api/django/imports/commit/',
            {'file': f2, 'target': 'leads', 'mode': 'upsert'}, format='multipart')
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertEqual(resp2.data['created'], 0)
        self.assertEqual(resp2.data['updated'], 1)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 1)
        lead = Lead.objects.get(company=self.company)
        self.assertEqual(lead.ville, 'Casablanca')
        self.assertEqual(lead.email, 'a@x.ma')  # champ fourni de nouveau, inchangé

    def test_upsert_unknown_external_id_creates(self):
        f = self._csv('Nom,Email,External_id\nInconnu,inconnu@x.ma,NEW-999\n')
        resp = self.api.post(
            '/api/django/imports/commit/',
            {'file': f, 'target': 'leads', 'mode': 'upsert'}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 1)
        self.assertTrue(Lead.objects.filter(
            company=self.company, email='inconnu@x.ma').exists())
        self.assertTrue(ExternalRef.objects.filter(
            company=self.company, external_id='NEW-999').exists())

    def test_upsert_matches_by_contact_without_external_id(self):
        Lead.objects.create(
            company=self.company, nom='Bennani', email='ben@x.ma', telephone=None)
        f = self._csv('Nom,Email,Telephone\nBennani,ben@x.ma,0622222222\n')
        resp = self.api.post(
            '/api/django/imports/commit/',
            {'file': f, 'target': 'leads', 'mode': 'upsert'}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 0)
        self.assertEqual(resp.data['updated'], 1)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 1)
        lead = Lead.objects.get(company=self.company)
        self.assertEqual(lead.telephone, '0622222222')

    def test_mode_maj_never_creates(self):
        f = self._csv('Nom,Email\nInconnu,jamais@x.ma\n')
        resp = self.api.post(
            '/api/django/imports/commit/',
            {'file': f, 'target': 'leads', 'mode': 'maj'}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 0)
        self.assertEqual(len(resp.data['skipped']), 1)
        self.assertFalse(Lead.objects.filter(email='jamais@x.ma').exists())


class TestModeUpsertClients(ImportBase):
    def test_upsert_updates_existing_client_by_email(self):
        Client.objects.create(company=self.company, nom='Ancien', email='c@x.ma')
        f = self._csv('Nom,Email,Ice\nNouveauNom,c@x.ma,001122334455667\n')
        resp = self.api.post(
            '/api/django/imports/commit/',
            {'file': f, 'target': 'clients', 'mode': 'upsert'}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 0)
        self.assertEqual(resp.data['updated'], 1)
        self.assertEqual(Client.objects.filter(company=self.company).count(), 1)
        client = Client.objects.get(company=self.company)
        self.assertEqual(client.nom, 'NouveauNom')
        self.assertEqual(client.ice, '001122334455667')


class TestTenantIsolation(ImportBase):
    def test_external_ref_isolated_per_company(self):
        other = Company.objects.create(slug='imp-co-2', nom='Imp Co 2')
        other_user_lead = Lead.objects.create(
            company=other, nom='AutreSociete', email='cross@x.ma')
        ExternalRef.objects.create(
            company=other, external_system='import', external_id='SHARED-1',
            content_type=ContentType.objects.get_for_model(Lead),
            object_id=other_user_lead.pk)

        # Même external_id, société DIFFÉRENTE : ne doit RIEN rapprocher, doit
        # créer une fiche neuve isolée à self.company.
        f = self._csv('Nom,Email,External_id\nMoi,moi@x.ma,SHARED-1\n')
        resp = self.api.post(
            '/api/django/imports/commit/',
            {'file': f, 'target': 'leads', 'mode': 'upsert'}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 1)
        self.assertEqual(
            Lead.objects.filter(company=self.company, email='moi@x.ma').count(), 1)
        self.assertEqual(Lead.objects.filter(company=other).count(), 1)
        self.assertEqual(ExternalRef.objects.filter(company=self.company).count(), 1)
        self.assertEqual(ExternalRef.objects.filter(company=other).count(), 1)

    def test_unsupported_mode_for_products_rejected(self):
        f = self._csv('Nom,SKU\nPanneau,SKU-X\n')
        resp = self.api_dir.post(
            '/api/django/imports/commit/',
            {'file': f, 'target': 'products', 'mode': 'upsert'}, format='multipart')
        self.assertEqual(resp.status_code, 400, resp.data)
