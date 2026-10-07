"""ACAL177 — fusion et corbeille d'un lead porteur d'un calepinage.

Constat C-ACAL-001 (audit 2026-10-04) : la fusion de leads ne déplaçait aucun
calepinage, et la corbeille d'un lead (unitaire comme en masse) ignorait le
calepinage ouvert qu'il portait.

Ce qui est tenu ici, par les chemins HTTP RÉELS (``/merge/``, ``DELETE``,
``/bulk/``) et le service calepinage réel :
  * ``merge_leads`` fait suivre le calepinage au survivant ;
  * ``DELETE`` d'un lead porteur d'un calepinage OUVERT répond 409 en le
    nommant, le lead reste vivant et le calepinage garde son lead ;
  * l'opération en masse ``delete`` saute ce lead (même garde) ;
  * un calepinage ARCHIVÉ ne bloque pas ;
  * un échec du transfert ne casse jamais la fusion.

Run :
    python manage.py test apps.crm.test_acal_fusion_suppression_lead -v2
"""
from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage
from apps.calepinage.services.archivage import archiver
from apps.crm.models import Client, Lead, LeadActivity
from authentication.models import Company

User = get_user_model()

LEADS = '/api/django/crm/leads/'


class FusionSuppressionLeadTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Fusion Co',
                                              slug='fusion-co-acal177')
        self.admin = User.objects.create_user(
            username='acal177_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.client_l1 = Client.objects.create(company=self.company,
                                               nom='Client survivant')
        self.l1 = Lead.objects.create(company=self.company, nom='Survivant',
                                      client=self.client_l1)
        self.l2 = Lead.objects.create(company=self.company, nom='Absorbé')
        self.c = Calepinage.objects.create(
            company=self.company, lead_id=self.l2.pk, titre='Toiture Anfa')

    def test_merge_deplace_le_calepinage_http(self):
        reponse = self.api.post(f'{LEADS}{self.l1.pk}/merge/',
                                {'others': [self.l2.pk]}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.c.refresh_from_db()
        self.assertEqual(self.c.lead_id, self.l1.pk)
        self.assertEqual(self.c.client_id, self.client_l1.pk)

    def test_destroy_lead_avec_calepinage_ouvert_409(self):
        reponse = self.api.delete(f'{LEADS}{self.l2.pk}/')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('« Toiture Anfa »', reponse.data['detail'])
        self.assertIn(f'#{self.c.pk}', reponse.data['detail'])
        self.assertEqual(reponse.data['calepinages'], [self.c.pk])
        lead = Lead.all_objects.get(pk=self.l2.pk)
        self.assertFalse(lead.is_deleted)
        self.c.refresh_from_db()
        self.assertEqual(self.c.lead_id, self.l2.pk)

    def test_bulk_delete_saute_le_lead_avec_calepinage_ouvert(self):
        libre = Lead.objects.create(company=self.company, nom='Libre')
        reponse = self.api.post(f'{LEADS}bulk/', {
            'action': 'delete', 'ids': [libre.pk, self.l2.pk]}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['updated'], 1)
        sautes = reponse.data['skipped']
        self.assertEqual([s['id'] for s in sautes], [self.l2.pk])
        self.assertIn('Toiture Anfa', sautes[0]['reason'])
        self.assertFalse(Lead.all_objects.get(pk=self.l2.pk).is_deleted)
        self.assertTrue(Lead.all_objects.get(pk=libre.pk).is_deleted)

    def test_calepinage_archive_ne_bloque_pas(self):
        archiver(self.c)
        reponse = self.api.delete(f'{LEADS}{self.l2.pk}/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertTrue(Lead.all_objects.get(pk=self.l2.pk).is_deleted)

    def test_echec_du_transfert_ne_casse_pas_la_fusion(self):
        with mock.patch(
                'apps.calepinage.services.liens.transferer_lead',
                side_effect=RuntimeError('panne simulée')):
            reponse = self.api.post(f'{LEADS}{self.l1.pk}/merge/',
                                    {'others': [self.l2.pk]}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.l2.refresh_from_db()
        self.assertTrue(self.l2.is_archived)
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.l1, body__contains='pas pu être rattachés').exists())
        self.c.refresh_from_db()
        self.assertEqual(self.c.lead_id, self.l2.pk)
