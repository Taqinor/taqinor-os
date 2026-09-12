"""NTUX32 — webhooks sortants sur les objets UX (`saved_view_shared` /
`record_restored`), déclenchés depuis `core.events` par
`apps/publicapi/uxviews_event_receivers.py` (jamais un import direct
`apps.uxviews`/`apps.trash` -> `apps.publicapi`).
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead
from apps.roles.models import Role
from apps.uxviews.models import SavedView
from core.events import record_soft_deleted

from . import delivery
from .constants import EVENT_RECORD_RESTORED, EVENT_SAVED_VIEW_SHARED

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class SavedViewSharedWebhookTests(TestCase):
    BASE = '/api/django/uxviews/saved-views/'

    def setUp(self):
        self.co = make_company('pa-ux32-a', 'PA UX32 A')
        self.role = Role.objects.create(
            company=self.co, nom='Outillé', est_systeme=False,
            permissions=['ux_vue_partager_equipe'])
        self.user = User.objects.create_user(
            username='pa-ux32-user', password='x', company=self.co,
            role=self.role)

    def test_creating_a_team_view_dispatches_saved_view_shared(self):
        with mock.patch.object(delivery, 'dispatch_event') as m:
            resp = auth(self.user).post(
                self.BASE,
                {'ecran': 'crm.leads', 'nom': 'Équipe',
                 'visibilite': SavedView.Visibilite.EQUIPE},
                format='json',
            )
        self.assertEqual(resp.status_code, 201, resp.data)
        m.assert_called_once()
        args, _kwargs = m.call_args
        self.assertEqual(args[0], self.co.id)
        self.assertEqual(args[1], EVENT_SAVED_VIEW_SHARED)
        self.assertEqual(args[2]['action'], 'partagee')
        self.assertEqual(args[2]['ecran'], 'crm.leads')

    def test_creating_a_personal_view_does_not_dispatch(self):
        with mock.patch.object(delivery, 'dispatch_event') as m:
            resp = auth(self.user).post(
                self.BASE, {'ecran': 'crm.leads', 'nom': 'Perso'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        m.assert_not_called()

    def test_deleting_a_team_view_dispatches_suppression(self):
        view = SavedView.objects.create(
            company=self.co, owner=self.user, ecran='crm.leads', nom='Équipe',
            visibilite=SavedView.Visibilite.EQUIPE,
        )
        with mock.patch.object(delivery, 'dispatch_event') as m:
            resp = auth(self.user).delete(f'{self.BASE}{view.id}/')
        self.assertEqual(resp.status_code, 204)
        m.assert_called_once()
        args, _kwargs = m.call_args
        self.assertEqual(args[1], EVENT_SAVED_VIEW_SHARED)
        self.assertEqual(args[2]['action'], 'suppression')


class RecordRestoredWebhookTests(TestCase):
    def setUp(self):
        self.co = make_company('pa-ux32-b', 'PA UX32 B')
        self.lead = Lead.objects.create(company=self.co, nom='Alaoui')

    def test_restoring_a_lead_dispatches_record_restored_with_type_and_id(self):
        from apps.trash.models import ElementSupprime
        from apps.trash.services import restaurer

        self.lead.is_archived = True
        self.lead.save(update_fields=['is_archived'])
        record_soft_deleted.send(
            sender=type(self.lead), instance=self.lead, company=self.co,
            user=None, type_libelle='Lead', libelle='Alaoui')
        element = ElementSupprime.objects.get()

        with mock.patch.object(delivery, 'dispatch_event') as m:
            restaurer(element)
        m.assert_called_once()
        args, _kwargs = m.call_args
        self.assertEqual(args[0], self.co.id)
        self.assertEqual(args[1], EVENT_RECORD_RESTORED)
        self.assertEqual(args[2]['type'], 'crm.lead')
        self.assertEqual(args[2]['object_id'], self.lead.pk)
        self.assertTrue(args[2]['restaure'])

    def test_restoring_an_already_restored_entry_does_not_redispatch(self):
        from apps.trash.models import ElementSupprime
        from apps.trash.services import restaurer

        self.lead.is_archived = True
        self.lead.save(update_fields=['is_archived'])
        record_soft_deleted.send(
            sender=type(self.lead), instance=self.lead, company=self.co,
            user=None, type_libelle='Lead', libelle='Alaoui')
        element = ElementSupprime.objects.get()
        restaurer(element)

        with mock.patch.object(delivery, 'dispatch_event') as m:
            restaurer(element)
        m.assert_not_called()
