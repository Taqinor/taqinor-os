"""AANA41 — les ops hors-ligne CRM respectent la portée de `LeadViewSet`.

Un commercial en portée « équipe/propre » ne doit pas pouvoir noter ni
tagger, via la file hors-ligne, le lead d'un autre commercial qu'il ne voit
pas en ligne.
"""
from django.test import TestCase

from apps.crm.models import Lead, LeadActivity
from apps.roles.models import Role
from apps.roles.permissions_registre import SCOPE_TEAM

from .models import OfflineOperation
from .tests import BATCH, User, auth, make_company, op


class PorteeCrmHorsLigneTests(TestCase):
    def setUp(self):
        self.co = make_company('aana41', 'Société AANA41')
        role = Role.objects.create(
            company=self.co, nom='commercial-equipe',
            permissions=['crm_voir', 'crm_modifier', SCOPE_TEAM])
        self.chef = User.objects.create_user(
            username='aana41-chef', password='x', company=self.co,
            role_legacy='responsable')
        self.moi = User.objects.create_user(
            username='aana41-moi', password='x', company=self.co,
            role_legacy='normal', role=role)
        self.autre = User.objects.create_user(
            username='aana41-autre', password='x', company=self.co,
            role_legacy='normal', role=role, supervisor=self.chef)
        self.mon_lead = Lead.objects.create(
            company=self.co, nom='Mien', owner=self.moi)
        self.lead_autre = Lead.objects.create(
            company=self.co, nom='Autre', owner=self.autre)
        self.api = auth(self.moi)

    def _post(self, cle, op_type, lead, **extra):
        payload = {'lead': lead.id}
        payload.update(extra)
        return self.api.post(
            BATCH, {'ops': [op(cle, op_type, payload)]}, format='json')

    def test_lead_hors_portee_refuse(self):
        resp = self._post('a41-noter', 'crm.lead.noter', self.lead_autre,
                          body='intrusion')
        self.assertEqual(resp.data['results'][0]['status'], 'error')
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.lead_autre).count(), 0)
        self.assertEqual(OfflineOperation.objects.get(
            client_op_id='a41-noter').statut, OfflineOperation.Statut.REJETEE)

    def test_tag_hors_portee_refuse(self):
        resp = self._post('a41-tag', 'crm.lead.tag', self.lead_autre,
                          tag='vip')
        self.assertEqual(resp.data['results'][0]['status'], 'error')
        self.lead_autre.refresh_from_db()
        self.assertNotIn('vip', self.lead_autre.tags or [])

    def test_lead_dans_la_portee_accepte(self):
        resp = self._post('a41-ok', 'crm.lead.noter', self.mon_lead,
                          body='ma note')
        self.assertEqual(resp.data['results'][0]['status'], 'applied')
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.mon_lead).count(), 1)
