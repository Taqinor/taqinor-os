"""AGR405 (D-AGR-9) — drapeau d'incohérence segment lead ↔ devis, jamais de
changement automatique du type du lead.

Contrat partagé : ``apps/crm/contract_samples/lead_pompage.json`` (AGR1,
bloc ``exemple_incoherent.incoherence_segment`` + ``regles``).

Run :
    python manage.py test apps.crm.tests_agr405_incoherence_segment -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead, LeadActivity
from apps.crm.serializers import incoherence_segment
from apps.ventes.domain.cycle_vie import accept_devis, mark_devis_sent
from apps.ventes.models import Devis
from apps.ventes.selectors import devis_par_mode_pour_lead

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_pompage.json').read_text(encoding='utf-8'))


class _Base(TestCase):
    slug = 'agr405'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': 'AGR405 Co'})
        self.user = User.objects.create_user(
            username=f'{self.slug}_u', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client',
            email=f'{self.slug}@example.com')
        self.lead = Lead.objects.create(
            company=self.company, nom='Exploitant',
            type_installation='residentiel')
        self._n = 0

    def _devis(self, mode, company=None, client=None):
        self._n += 1
        return Devis.objects.create(
            company=company or self.company,
            reference=f'DEV-{self.slug}-{self._n}',
            client=client or self.client_obj, lead=self.lead,
            statut='brouillon', taux_tva=Decimal('20.00'),
            mode_installation=mode)

    def _detail(self):
        resp = self.api.get(f'/api/django/crm/leads/{self.lead.id}/')
        self.assertEqual(resp.status_code, 200)
        return resp.data


class IncoherenceSegment(_Base):
    def test_lead_residentiel_devis_agricole_bloc_renseigne(self):
        devis = self._devis('agricole')
        bloc = self._detail()['incoherence_segment']
        attendu = CONTRAT['exemple_incoherent']['incoherence_segment']
        self.assertEqual(set(bloc), set(attendu))
        self.assertEqual(bloc['segment_lead'], 'residentiel')
        self.assertEqual(bloc['mode_devis'], 'agricole')
        self.assertEqual(bloc['devis'],
                         [{'id': devis.id, 'reference': devis.reference}])
        self.assertEqual(bloc['message'], attendu['message'])

    def test_lead_sans_type_devis_agricole_bloc_renseigne(self):
        Lead.objects.filter(pk=self.lead.pk).update(type_installation=None)
        self._devis('agricole')
        bloc = self._detail()['incoherence_segment']
        self.assertIsNone(bloc['segment_lead'])
        self.assertEqual(bloc['mode_devis'], 'agricole')

    def test_lead_agricole_tous_devis_residentiels_inverse(self):
        Lead.objects.filter(pk=self.lead.pk).update(
            type_installation='agricole')
        self._devis('residentiel')
        bloc = self._detail()['incoherence_segment']
        self.assertEqual(bloc['segment_lead'], 'agricole')
        self.assertEqual(bloc['mode_devis'], 'residentiel')

    def test_lead_agricole_avec_un_devis_agricole_rien(self):
        Lead.objects.filter(pk=self.lead.pk).update(
            type_installation='agricole')
        self._devis('residentiel')
        self._devis('agricole')
        self.assertIsNone(self._detail()['incoherence_segment'])

    def test_sans_devis_rien(self):
        self.assertIsNone(self._detail()['incoherence_segment'])

    def test_patch_manuel_efface_le_drapeau_et_journalise(self):
        self._devis('agricole')
        self.assertIsNotNone(self._detail()['incoherence_segment'])
        resp = self.api.patch(f'/api/django/crm/leads/{self.lead.id}/',
                              {'type_installation': 'agricole'},
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(self._detail()['incoherence_segment'])
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, field='type_installation',
            new_value__icontains='agricole').exists())

    def test_creer_puis_accepter_ne_change_pas_le_type(self):
        devis = self._devis('agricole')
        mark_devis_sent(devis=devis, user=self.user)
        devis.refresh_from_db()
        accept_devis(devis=devis, user=self.user, nom='Client')
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.type_installation, 'residentiel')

    def test_devis_d_une_autre_societe_ignore(self):
        autre, _ = Company.objects.get_or_create(
            slug='agr405-autre', defaults={'nom': 'AGR405 Autre'})
        client_autre = Client.objects.create(
            company=autre, nom='Autre', email='agr405-autre@example.com')
        self._devis('agricole', company=autre, client=client_autre)
        self.assertIsNone(self._detail()['incoherence_segment'])
        self.assertEqual(devis_par_mode_pour_lead(self.lead.id, self.company),
                         [])

    def test_liste_ne_sert_pas_le_bloc_et_garde_ses_requetes(self):
        def _compte():
            with CaptureQueriesContext(connection) as ctx:
                resp = self.api.get('/api/django/crm/leads/')
            self.assertEqual(resp.status_code, 200)
            return resp, len(ctx.captured_queries)

        resp, avant = _compte()
        for ligne in resp.data.get('results', resp.data):
            self.assertNotIn('incoherence_segment', ligne)
        self._devis('agricole')
        self._devis('residentiel')
        _resp, apres = _compte()
        self.assertEqual(apres, avant)


class FonctionPure(TestCase):
    def test_message_conforme_au_contrat(self):
        bloc = incoherence_segment(
            'residentiel', [{'id': 4021, 'reference': 'DEV-2026-10-0007',
                             'mode_installation': 'agricole',
                             'statut': 'brouillon'}])
        self.assertEqual(
            bloc, CONTRAT['exemple_incoherent']['incoherence_segment'])
