"""ACRM47 — la garde « devis accepté » du placement échoue FERMÉ : si
``ventes.selectors.leads_avec_devis_accepte`` est en panne, POST
``placement-cadences`` répond 503 ``{detail}`` (contrat ACRM61) et RIEN n'est
appliqué ; sans panne, le lead à devis accepté est écarté comme avant —
rejoue la sonde LSVC4-9.

Test-du-test : rétablir le ``return (set(), {})`` ⇒
test_panne_ventes_rien_applique échoue (lead au Froid, 200).
"""
import datetime
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import stages
from apps.crm.models import Client, Lead
from apps.crm.cadence_placement import PLACEMENT_DEVIS_ILLISIBLES
from apps.ventes.models import Devis

User = get_user_model()
URL = '/api/django/crm/leads/placement-cadences/'


def _panne(*args, **kwargs):
    raise RuntimeError('ventes indisponible (doublure de panne)')


class PlacementGardeFermeeTests(TestCase):

    def setUp(self):
        from apps.roles.models import Role
        from apps.roles.permissions_registre import ADMIN_PERMISSIONS
        self.company = Company.objects.create(
            nom='ACRM47 Solaire', slug='acrm47-garde')
        role, _ = Role.objects.get_or_create(
            company=self.company, nom='Administrateur',
            defaults={'permissions': ADMIN_PERMISSIONS, 'est_systeme': True})
        self.user = User.objects.create_user(
            username='acrm47-admin', password='x', company=self.company,
            role=role, role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='47')
        self.lead = Lead.objects.create(
            company=self.company, nom='Accepté', stage=stages.QUOTE_SENT,
            owner=self.user, client=client)
        Lead.objects.filter(pk=self.lead.pk).update(
            date_creation=timezone.now() - datetime.timedelta(days=60))
        Devis.objects.create(
            company=self.company, reference='DEV-ACRM47-0001', client=client,
            lead=self.lead, statut='accepte', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user)
        self.lead.refresh_from_db()
        self.tags_avant = self.lead.tags

    def test_panne_ventes_rien_applique(self):
        with mock.patch('apps.ventes.selectors.leads_avec_devis_accepte',
                        _panne):
            resp = self.api.post(URL, {'apply': True}, format='json')
        self.assertEqual(resp.status_code, 503, resp.data)
        self.assertEqual(resp.data['detail'], PLACEMENT_DEVIS_ILLISIBLES)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.QUOTE_SENT)
        self.assertEqual(self.lead.tags, self.tags_avant)

    def test_sans_panne_ecarte(self):
        resp = self.api.post(URL, {'apply': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['ignores']['devis_accepte_non_signe'], 1)
        self.assertEqual(resp.data['applique'], 0)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.QUOTE_SENT)
