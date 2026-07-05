"""Tests YHARD3 — diff structuré (AuditLog.changes) + reconstruction as-of.

Purement additif : ne touche ni le chatter CRM (crm.LeadActivity), ni la piste
compta hash-chaînée, ni XSTK13. Couvre : reconstruction champ-par-champ à une
date passée, dégradation propre sans ``changes`` (legacy), endpoint scopé
société, et non-régression du comportement existant de ``record()`` quand
``changes`` est omis.
"""
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company, CustomUser
from apps.audit import recorder
from apps.audit.models import AuditLog
from apps.audit.selectors import reconstruct_as_of
from apps.crm.models import Client


def make_company(slug='yhard3-co', nom='YHARD3 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestReconstructAsOf(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='YHARD3',
            email='yhard3@example.com', telephone='+212600000099')
        self.ct = ContentType.objects.get_for_model(Client)

    def test_replays_structured_diffs_up_to_date(self):
        t0 = timezone.now() - timedelta(days=2)
        t1 = timezone.now() - timedelta(days=1)
        entry0 = AuditLog.objects.create(
            company=self.company, action=AuditLog.Action.UPDATE,
            content_type=self.ct, object_id=str(self.client_obj.pk),
            changes=[{'field': 'nom', 'old': 'Ancien', 'new': 'Client'}],
        )
        AuditLog.objects.filter(pk=entry0.pk).update(timestamp=t0)
        entry1 = AuditLog.objects.create(
            company=self.company, action=AuditLog.Action.UPDATE,
            content_type=self.ct, object_id=str(self.client_obj.pk),
            changes=[{'field': 'nom', 'old': 'Client', 'new': 'ClientRenomme'}],
        )
        AuditLog.objects.filter(pk=entry1.pk).update(timestamp=t1)

        # As-of avant la 2e modification : doit voir la 1re valeur.
        result = reconstruct_as_of(
            self.client_obj, dt=t0 + timedelta(hours=1), company=self.company)
        self.assertEqual(result['fields'].get('nom'), 'Client')

        # As-of après les deux : doit voir la dernière valeur.
        result2 = reconstruct_as_of(
            self.client_obj, dt=timezone.now(), company=self.company)
        self.assertEqual(result2['fields'].get('nom'), 'ClientRenomme')

    def test_degrades_cleanly_without_changes(self):
        AuditLog.objects.create(
            company=self.company, action=AuditLog.Action.UPDATE,
            content_type=self.ct, object_id=str(self.client_obj.pk),
            detail='Nom : Ancien -> Client', changes=None,
        )
        result = reconstruct_as_of(
            self.client_obj, dt=timezone.now(), company=self.company)
        self.assertEqual(result['fields'], {})
        self.assertEqual(result['covered_changes'], 0)

    def test_scoped_by_company(self):
        other_company = make_company(slug='yhard3-other', nom='Autre société')
        AuditLog.objects.create(
            company=other_company, action=AuditLog.Action.UPDATE,
            content_type=self.ct, object_id=str(self.client_obj.pk),
            changes=[{'field': 'nom', 'old': 'X', 'new': 'Y'}],
        )
        result = reconstruct_as_of(
            self.client_obj, dt=timezone.now(), company=self.company)
        self.assertEqual(result['fields'], {})


class TestRecordChangesBackwardCompatible(TestCase):
    def setUp(self):
        self.company = make_company(slug='yhard3-rec', nom='YHARD3 Rec')

    def test_record_without_changes_stores_null(self):
        recorder.record(
            AuditLog.Action.UPDATE, content_type=None, object_id='1',
            detail='ancien style', company=self.company, user=None)
        entry = AuditLog.objects.filter(company=self.company).latest('timestamp')
        self.assertIsNone(entry.changes)

    def test_record_with_changes_stores_diff(self):
        diff = [{'field': 'statut', 'old': 'brouillon', 'new': 'envoye'}]
        recorder.record(
            AuditLog.Action.UPDATE, content_type=None, object_id='2',
            detail='statut', company=self.company, user=None, changes=diff)
        entry = AuditLog.objects.filter(
            company=self.company, object_id='2').latest('timestamp')
        self.assertEqual(entry.changes, diff)


class TestObjectAsOfEndpoint(TestCase):
    def setUp(self):
        self.company = make_company(slug='yhard3-ep', nom='YHARD3 Endpoint')
        self.director = CustomUser.objects.create_user(
            username='yhard3dir', password='pass12345', company=self.company,
            is_superuser=True, is_staff=True)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='EP',
            email='yhard3ep@example.com', telephone='+212600000098')
        self.ct = ContentType.objects.get_for_model(Client)
        AuditLog.objects.create(
            company=self.company, action=AuditLog.Action.UPDATE,
            content_type=self.ct, object_id=str(self.client_obj.pk),
            changes=[{'field': 'nom', 'old': 'Ancien', 'new': 'Client'}],
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.director)

    def test_endpoint_returns_reconstructed_fields(self):
        url = reverse('audit-object-as-of', kwargs={
            'content_type': 'crm.client', 'object_id': str(self.client_obj.pk)})
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['fields'].get('nom'), 'Client')

    def test_endpoint_requires_permission(self):
        plain_user = CustomUser.objects.create_user(
            username='yhard3plain', password='pass12345', company=self.company)
        api = APIClient()
        api.force_authenticate(user=plain_user)
        url = reverse('audit-object-as-of', kwargs={
            'content_type': 'crm.client', 'object_id': str(self.client_obj.pk)})
        resp = api.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_endpoint_invalid_content_type_404(self):
        url = reverse('audit-object-as-of', kwargs={
            'content_type': 'bogus.model', 'object_id': '1'})
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 404)
