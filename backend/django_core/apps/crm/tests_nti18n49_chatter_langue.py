"""NTI18N49 — chatter automatique sur changement de langue documentaire/préférée.

Deux volets, sur les DEUX modèles qui portent une préférence de langue :
- ``Lead.langue_preferee`` (FR/Darija) rejoint simplement ``TRACKED_FIELDS``
  (mécanique de chatter déjà existante pour les leads, ``activity.log_changes``,
  appelée par ``LeadViewSet.perform_update`` sur chaque PATCH) ;
- ``Client.langue_document`` (FR/AR) est un champ d'un AUTRE modèle
  (``LeadActivity.lead`` est une FK stricte vers ``Lead``, jamais vers
  ``Client``) : ``activity.log_client_langue_document_change`` journalise donc
  une entrée sur CHAQUE lead rattaché au client (``Lead.client``), appelée
  par ``ClientViewSet.perform_update``.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import activity
from apps.crm.models import Client, Lead, LeadActivity

User = get_user_model()


def _company(slug='nti18n49-co', nom='NTI18N49 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class LeadLanguePrefereeChatterTests(TestCase):
    """``langue_preferee`` (Lead) suit désormais TRACKED_FIELDS."""

    def setUp(self):
        self.company = _company()
        self.user = User.objects.create_user(
            username='nti18n49_user', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(company=self.company, nom='Lead FR')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_langue_preferee_in_tracked_fields(self):
        self.assertIn('langue_preferee', activity.TRACKED_FIELDS)

    def test_patch_langue_preferee_logs_one_modification(self):
        resp = self.api.patch(
            f'/api/django/crm/leads/{self.lead.id}/',
            {'langue_preferee': 'darija'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        acts = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.MODIFICATION,
            field='langue_preferee')
        self.assertEqual(acts.count(), 1)
        act = acts.first()
        self.assertEqual(act.field_label, 'Langue préférée')
        self.assertEqual(act.new_value, 'Darija')  # libellé, pas la clé brute
        self.assertEqual(act.user_id, self.user.id)


class ClientLangueDocumentChatterTests(TestCase):
    """``langue_document`` (Client) journalisé sur le(s) lead(s) rattaché(s)."""

    def setUp(self):
        self.company = _company(slug='nti18n49-co2', nom='NTI18N49 Co2')
        self.user = User.objects.create_user(
            username='nti18n49_user2', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client FR', langue_document='fr')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead lié', client=self.client_obj)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _modifications(self):
        return LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.MODIFICATION,
            field='client_langue_document')

    def test_patch_via_api_creates_chatter_entry_on_linked_lead(self):
        resp = self.api.patch(
            f'/api/django/crm/clients/{self.client_obj.id}/',
            {'langue_document': 'ar'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        acts = self._modifications()
        self.assertEqual(acts.count(), 1)
        act = acts.first()
        self.assertEqual(act.field_label, 'Langue des documents (client)')
        self.assertEqual(act.old_value, 'Français')
        self.assertEqual(act.new_value, 'العربية')
        self.assertEqual(act.user_id, self.user.id)
        self.assertEqual(act.company_id, self.company.id)

    def test_no_op_when_value_unchanged(self):
        resp = self.api.patch(
            f'/api/django/crm/clients/{self.client_obj.id}/',
            {'langue_document': 'fr'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._modifications().count(), 0)

    def test_service_function_logs_one_entry_per_linked_lead(self):
        lead2 = Lead.objects.create(
            company=self.company, nom='Deuxième lead', client=self.client_obj)
        entries = activity.log_client_langue_document_change(
            self.client_obj, self.user, old_value='fr', new_value='ar')
        self.assertEqual(len(entries), 2)
        self.assertEqual(
            set(LeadActivity.objects.filter(
                field='client_langue_document').values_list('lead_id', flat=True)),
            {self.lead.id, lead2.id},
        )

    def test_client_without_lead_is_silently_skipped(self):
        orphan = Client.objects.create(
            company=self.company, nom='Sans lead', langue_document='fr')
        # Ne doit lever aucune exception, et ne rien créer.
        entries = activity.log_client_langue_document_change(
            orphan, self.user, old_value='fr', new_value='ar')
        self.assertEqual(entries, [])

    def test_no_op_helper_returns_empty_list_when_values_equal(self):
        entries = activity.log_client_langue_document_change(
            self.client_obj, self.user, old_value='fr', new_value='fr')
        self.assertEqual(entries, [])
        self.assertEqual(self._modifications().count(), 0)
